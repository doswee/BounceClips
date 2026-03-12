import grpc
import json
import os
import re
import sys
import threading

# Ensure the proto folder is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, 'proto'))

import PTSL_pb2
import PTSL_pb2_grpc

class PTSLClient:
    def __init__(self, address="localhost:31416"):
        self.address = address
        self.channel = grpc.insecure_channel(self.address)
        self.stub = PTSL_pb2_grpc.PTSLStub(self.channel)
        self.session_id = ""
        self.lock = threading.RLock()

    def send_command(self, command_id, request_body=None):
        with self.lock:
            if not self.session_id and command_id != PTSL_pb2.CId_RegisterConnection:
                self.register()

            request = PTSL_pb2.Request()
            request.header.command = command_id
            request.header.version = 1
            request.header.session_id = self.session_id
            if request_body:
                request.request_body_json = json.dumps(request_body)

            try:
                response = self.stub.SendGrpcRequest(request)
                return {
                    "status": response.header.status,
                    "data": json.loads(response.response_body_json or "{}"),
                    "error": response.response_error_json
                }
            except Exception as e:
                print(f"PTSL ERROR: {e}")
                return {"status": -1, "data": {}, "error": str(e)}

    def register(self, app_name="RogueWaves"):
        res = self.send_command(PTSL_pb2.CId_RegisterConnection, {
            "company_name": "LocalUser",
            "application_name": app_name
        })
        if res["status"] == 3:
            self.session_id = res["data"].get("session_id", "")
            return True
        return False

    def get_session_name(self):
        res = self.send_command(PTSL_pb2.CId_GetSessionName)
        return res.get("data", {}).get("session_name")

    def get_available_sources(self):
        sources = []
        for p_type in ["Output", "Bus"]:
            res = self.send_command(PTSL_pb2.CId_GetExportMixSourceList, {"type": p_type})
            names = res.get("data", {}).get("source_list", [])
            for n in names:
                # Store the UI type for the bounce request later
                sources.append({"name": n, "type": p_type})
        return sources

    # --- YOUR WORKING LOGIC HELPERS ---
    def _tc_to_val(self, tc):
        if not tc: return 0.0
        clean = tc.replace(':', '').replace(';', '')
        return float(clean)

    def _clean_clip_name(self, name):
        """
        Cleans the clip name by:
        1. Stripping leading Event IDs (e.g., '22      Clip' -> 'Clip')
        2. Stripping Tab characters and extra whitespace
        3. Removing .L/.R/stereo suffixes
        """
        # Replace tabs with spaces and trim
        name = name.replace('\t', ' ').strip()
        
        # Aggressively remove leading digits followed by whitespace
        # This fixes the "9 characters before it" issue (the Event ID column)
        name = re.sub(r'^\d+\s+', '', name)
        
        # Remove .L, .R, _L, _R, .1, .2 etc from stereo legs
        name = re.sub(r"(\.[LRCLSsrfe\d]+|_L|_R)$", "", name, flags=re.IGNORECASE)
        
        return name.strip()

    def get_selected_clips_details(self):
        if not self.session_id: self.register()

        # 1. Get current selection from Pro Tools
        ts_res = self.send_command(PTSL_pb2.CId_GetEditSelection, {"location_type": "TLType_TimeCode"})
        sel_in = ts_res["data"].get("in_time", "00:00:00:00")
        sel_out = ts_res["data"].get("out_time", "00:00:00:00")
        
        sel_in_val = self._tc_to_val(sel_in)
        sel_out_val = self._tc_to_val(sel_out)

        # 2. Export Session Info
        esi_res = self.send_command(PTSL_pb2.CId_ExportSessionInfoAsText, {
            "include_clip_list": True,
            "track_list_type": "SelectedTracksOnly",
            "output_type": "ESI_String",
            "text_as_file_format": "UTF8",
            "track_offset_options": "TimeCode",
            "show_sub_frames": True 
        })
        
        text = esi_res.get("data", {}).get("session_info", "")
        if not text: return []

        if "T R A C K  L I S T" not in text: return []
        track_section_master = text.split("T R A C K  L I S T")[-1]
        track_blocks = re.split(r'TRACK NAME:\s+', track_section_master)
        
        found_clips = []
        seen_identities = set()

        # This regex captures the line: digit(s) -> whitespace -> Name+Index -> Timecodes
        # We clean the "Name+Index" part in the _clean_clip_name function
        clip_pattern = re.compile(r"^\d+\s+(.*?)\s+([\d:;.]+)\s+([\d:;.]+)", re.MULTILINE)

        for block in track_blocks[1:]:
            lines = block.splitlines()
            if not lines: continue
            
            raw_track_name = lines[0].strip()
            track_name_for_solo = re.sub(r'\s*\(.*?\)\s*$', '', raw_track_name).strip()

            clips_in_block = clip_pattern.findall(block)
            
            for name, start_tc, end_tc in clips_in_block:
                try:
                    clip_start_val = self._tc_to_val(start_tc)
                    clip_end_val = self._tc_to_val(end_tc)
                    
                    if clip_start_val >= (sel_in_val - 0.01) and clip_end_val <= (sel_out_val + 0.01):
                        # CLEANING HAPPENS HERE
                        clean_name = self._clean_clip_name(name)
                        
                        identity = (clean_name, start_tc, end_tc, track_name_for_solo)
                        if identity not in seen_identities:
                            seen_identities.add(identity)
                            found_clips.append({
                                "name": clean_name,
                                "start": start_tc,
                                "end": end_tc,
                                "track": track_name_for_solo
                            })
                except ValueError:
                    continue

        return found_clips

    def perform_batch_bounce(self, clips, settings):
        # Group clips by track
        track_groups = {}
        for c in clips:
            track_groups.setdefault(c["track"], []).append(c)

        for track, t_clips in track_groups.items():
            print(f"BOUNCING TRACK: {track}")
            # Solo the track
            self.send_command(PTSL_pb2.CId_SetTrackSoloState, {"track_names": [track], "enabled": True})
            
            try:
                for clip in t_clips:
                    # Select the clip
                    self.send_command(PTSL_pb2.CId_SetTimelineSelection, {
                        "in_time": clip["start"], 
                        "out_time": clip["end"],
                        "location_type": "TLType_TimeCode"
                    })

                    # Bounce
                    bounce_req = {
                        "file_name": f"{settings['prefix']}{clip['name']}{settings['suffix']}",
                        "file_type": settings['file_type'],
                        "offline_bounce": "TBool_True",
                        "audio_info": {
                            "bit_depth": f"BDepth_{settings['bit_depth']}" if settings['bit_depth'] != "32" else "BDepth_32Float",
                            "sample_rate": f"SRate_{settings['sample_rate']}",
                            "export_format": "EFormat_Interleaved",
                            "delivery_format": "EMDFormat_SingleFile"
                        },
                        "location_info": {
                            "file_destination": "EMFDestination_Directory" if settings['custom_path'] else "EMFDestination_SessionFolder",
                            "directory": settings.get('custom_path', "")
                        },
                        "mix_source_list": [{
                            "source_type": "EMSType_Output" if settings['source_type'] == "Output" else "EMSType_Bus",
                            "name": settings['source_name']
                        }]
                    }
                    self.send_command(PTSL_pb2.CId_ExportMix, bounce_req)
            finally:
                # Unsolo
                self.send_command(PTSL_pb2.CId_SetTrackSoloState, {"track_names": [track], "enabled": False})
        
        return True