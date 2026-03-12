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
                return {"status": -1, "data": {}, "error": str(e)}

    def register(self, app_name="RogueWaves"):
        res = self.send_command(PTSL_pb2.CId_RegisterConnection, {"company_name": "LocalUser", "application_name": app_name})
        if res["status"] == 3:
            self.session_id = res["data"].get("session_id", "")
            return True
        return False

    def get_session_name(self):
        res = self.send_command(PTSL_pb2.CId_GetSessionName)
        return res.get("data", {}).get("session_name")

    def get_bounced_files_path(self):
        res = self.send_command(PTSL_pb2.CId_GetSessionPath)
        path_obj = res.get("data", {}).get("session_path", {})
        full_ptx_path = path_obj.get("path")
        if full_ptx_path:
            return os.path.join(os.path.dirname(full_ptx_path), "Bounced Files")
        return ""

    def get_available_sources(self):
        sources = []
        for p_type in ["Output", "Bus"]:
            res = self.send_command(PTSL_pb2.CId_GetExportMixSourceList, {"type": p_type})
            names = res.get("data", {}).get("source_list", [])
            for n in names:
                sources.append({"name": n, "type": "EMSType_Output" if p_type == "Output" else "EMSType_Bus"})
        return sources

    def _is_fade(self, name):
        """Identifies if a clip is a Pro Tools generated fade label."""
        lower_name = name.lower()
        return any(f in lower_name for f in ["(fade in)", "(fade out)", "(crossfade)"])

    def _clean_clip_name(self, name):
        """Cleans Event IDs and stereo suffixes."""
        name = name.replace('\t', ' ').strip()
        # Remove Event ID column
        name = re.sub(r'^\d+\s+', '', name)
        # Remove stereo legs only if NOT a fade
        if not self._is_fade(name):
            name = re.sub(r"(\.[LRCLSsrfe\d]+|_L|_R)$", "", name, flags=re.IGNORECASE)
        return name.strip()

    def get_selected_clips_details(self):
        # 1. Selection in Samples
        ts_res = self.send_command(PTSL_pb2.CId_GetEditSelection, {"location_type": "TLType_Samples"})
        sel_in = int(ts_res["data"].get("in_time", "0"))
        sel_out = int(ts_res["data"].get("out_time", "0"))

        # 2. Export in Samples
        esi_res = self.send_command(PTSL_pb2.CId_ExportSessionInfoAsText, {
            "include_clip_list": True, "track_list_type": "SelectedTracksOnly",
            "output_type": "ESI_String", "text_as_file_format": "UTF8",
            "track_offset_options": "Samples" 
        })
        
        text = esi_res.get("data", {}).get("session_info", "")
        if not text or "T R A C K  L I S T" not in text: return []

        track_section = text.split("T R A C K  L I S T")[-1]
        track_blocks = re.split(r'TRACK NAME:\s+', track_section)
        
        found_clips = []
        seen = set()
        clip_pattern = re.compile(r"^\d+\s+(.*?)\s+(\d+)\s+(\d+)", re.MULTILINE)

        for block in track_blocks[1:]:
            lines = block.splitlines()
            if not lines: continue
            track_name = re.sub(r'\s*\(.*?\)\s*$', '', lines[0].strip()).strip()
            for name, start_s, end_s in clip_pattern.findall(block):
                c_s, c_e = int(start_s), int(end_s)
                if c_s >= (sel_in - 1) and c_e <= (sel_out + 1):
                    c_name = self._clean_clip_name(name)
                    identity = (c_name, c_s, c_e, track_name)
                    if identity not in seen:
                        seen.add(identity)
                        found_clips.append({
                            "name": c_name, 
                            "start": str(c_s), "end": str(c_e), 
                            "start_val": c_s, "end_val": c_e, 
                            "track": track_name,
                            "is_fade": self._is_fade(c_name)
                        })
        return found_clips

    def perform_batch_bounce(self, clips, settings):
        if not clips: return False
        track_groups = {}
        for c in clips: track_groups.setdefault(c["track"], []).append(c)

        # Merge Logic with Fade Absorption
        final_list = []
        user_wants_merge = settings.get("merge_contiguous", False)

        for track, t_clips in track_groups.items():
            t_clips.sort(key=lambda x: x["start_val"])
            if not t_clips: continue
            
            curr = t_clips[0].copy()
            for i in range(1, len(t_clips)):
                nxt = t_clips[i]
                
                # We merge if they touch AND (User wants merge OR it's a fade)
                should_merge = False
                if abs(curr["end_val"] - nxt["start_val"]) <= 1:
                    if user_wants_merge or curr["is_fade"] or nxt["is_fade"]:
                        should_merge = True
                
                if should_merge:
                    curr["end_val"], curr["end"] = nxt["end_val"], nxt["end"]
                    # Adopt non-fade name if the current one is just a fade label
                    if curr["is_fade"] and not nxt["is_fade"]:
                        curr["name"] = nxt["name"]
                        curr["is_fade"] = False
                else:
                    if not curr["is_fade"]: final_list.append(curr)
                    curr = nxt.copy()
            if not curr["is_fade"]: final_list.append(curr)

        # Bouncing
        file_counter = 1
        bounce_groups = {}
        for c in final_list: bounce_groups.setdefault(c["track"], []).append(c)

        for track, b_clips in bounce_groups.items():
            self.send_command(PTSL_pb2.CId_SetTrackSoloState, {"track_names": [track], "enabled": True})
            try:
                for clip in b_clips:
                    fname = f"{settings['prefix']}{settings['base_name']}_{str(file_counter).zfill(settings['digit_padding'])}{settings['suffix']}" if settings["naming_mode"] == 1 else f"{settings['prefix']}{clip['name']}{settings['suffix']}"
                    self.send_command(PTSL_pb2.CId_SetTimelineSelection, {"in_time": clip["start"], "out_time": clip["end"], "location_type": "TLType_Samples"})
                    bit = f"BDepth_{settings['bit_depth']}" if settings['bit_depth'] != "32" else "BDepth_32Float"
                    bounce_req = {
                        "file_name": fname, "file_type": settings['file_type'], "offline_bounce": "TBool_True",
                        "audio_info": { "bit_depth": bit, "sample_rate": f"SRate_{settings['sample_rate']}", "export_format": "EFormat_Interleaved", "delivery_format": "EMDFormat_SingleFile" },
                        "location_info": { "file_destination": "EMFDestination_Directory" if settings['custom_path'] else "EMFDestination_SessionFolder", "directory": settings['custom_path'] },
                        "mix_source_list": [{ "source_type": settings['source_type'], "name": settings['source_name'] }]
                    }
                    self.send_command(PTSL_pb2.CId_ExportMix, bounce_req); file_counter += 1
            finally:
                self.send_command(PTSL_pb2.CId_SetTrackSoloState, {"track_names": [track], "enabled": False})
        return True