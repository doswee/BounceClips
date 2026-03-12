import sys
import os
import grpc
import json
import re

# 1. Setup paths so the script can find your proto files
proto_path = os.path.join(os.path.dirname(__file__), 'proto')
sys.path.append(proto_path)

try:
    import PTSL_pb2
    import PTSL_pb2_grpc
except ImportError as e:
    print(f"Error: Could not find proto files in {proto_path}")
    sys.exit(1)

# Configuration
PORT = 'localhost:31416'
COMPANY_NAME = "DonalSweeney"
APP_NAME = "ClipRangeFilter"

def tc_to_val(tc):
    """Converts Timecode (HH:MM:SS:FF.ss) to a float for mathematical comparison."""
    clean = tc.replace(':', '').replace(';', '')
    return float(clean)

def clean_clip_name(name):
    """
    Removes common Pro Tools multichannel suffixes like .L, .R, .1, .2, _L, _R
    so that stereo legs are identified as the same clip.
    """
    # Regex to strip .L, .R, .C, .Ls, .Rs, .Lfe, .1, .2, _L, _R etc from the end
    cleaned = re.sub(r"(\.[LRCLSsrfe\d]+|_L|_R)$", "", name.strip(), flags=re.IGNORECASE)
    return cleaned.strip()

def get_filtered_clips():
    channel = grpc.insecure_channel(PORT)
    stub = PTSL_pb2_grpc.PTSLStub(channel)

    try:
        # --- STEP 1: REGISTER CONNECTION ---
        reg_request = PTSL_pb2.Request(
            header=PTSL_pb2.RequestHeader(command=PTSL_pb2.CId_RegisterConnection, version=1),
            request_body_json=json.dumps({"company_name": COMPANY_NAME, "application_name": APP_NAME})
        )
        
        reg_response = stub.SendGrpcRequest(reg_request)
        reg_data = json.loads(reg_response.response_body_json)
        session_id = reg_data.get('session_id')

        if not session_id:
            print("Handshake failed.")
            return

        # --- STEP 2: GET CURRENT TIMELINE SELECTION ---
        selection_request = PTSL_pb2.Request(
            header=PTSL_pb2.RequestHeader(
                command=PTSL_pb2.CId_GetEditSelection, 
                version=1, 
                session_id=session_id
            ),
            request_body_json=json.dumps({"location_type": "TLType_TimeCode"})
        )
        
        print("Fetching timeline selection...")
        sel_response = stub.SendGrpcRequest(selection_request)
        sel_data = json.loads(sel_response.response_body_json)
        
        sel_in = sel_data.get('in_time', '00:00:00:00')
        sel_out = sel_data.get('out_time', '00:00:00:00')
        
        print(f"Selected Range: {sel_in} to {sel_out}")

        # --- STEP 3: EXPORT DATA ---
        export_request = PTSL_pb2.Request(
            header=PTSL_pb2.RequestHeader(
                command=PTSL_pb2.CId_ExportSessionInfoAsText,
                version=1,
                session_id=session_id
            ),
            request_body_json=json.dumps({
                "include_clip_list": True,
                "track_list_type": "SelectedTracksOnly",
                "output_type": "ESI_String", 
                "text_as_file_format": "UTF8",
                "track_offset_options": "TimeCode",
                "show_sub_frames": True 
            })
        )

        response = stub.SendGrpcRequest(export_request)
        raw_text = json.loads(response.response_body_json).get('session_info', '')

        if not raw_text:
            print("No clip data found.")
            return

        parse_and_filter(raw_text, sel_in, sel_out)

    except Exception as e:
        print(f"Error communicating with Pro Tools: {e}")

def parse_and_filter(text, sel_in, sel_out):
    """Filters clips and consolidates multi-channel legs into single entries."""
    
    sel_in_val = tc_to_val(sel_in)
    sel_out_val = tc_to_val(sel_out)

    print("\n" + "="*60)
    print(f"CLIPS WITHIN SELECTION BOUNDARIES")
    print("="*60)

    if "T R A C K  L I S T" not in text:
        print("No Track List found.")
        return
    
    track_section = text.split("T R A C K  L I S T")[-1]
    
    # Matches: Index, Name, StartTime, EndTime
    clip_pattern = re.compile(r"^\d+\s+(.*?)\s+([\d:;.]+)\s+([\d:;.]+)", re.MULTILINE)
    clips = clip_pattern.findall(track_section)
    
    seen_clips = set() # To store unique (clean_name, start_tc, end_tc)
    match_count = 0
    
    for name, start_tc, end_tc in clips:
        try:
            clip_start_val = tc_to_val(start_tc)
            clip_end_val = tc_to_val(end_tc)
            
            # 1. Range Check
            if clip_start_val >= sel_in_val and clip_end_val <= sel_out_val:
                
                # 2. Consolidate Multi-channel (Stereo)
                base_name = clean_clip_name(name)
                # We create a unique key based on name and time
                clip_key = (base_name, start_tc, end_tc)
                
                if clip_key not in seen_clips:
                    seen_clips.add(clip_key)
                    match_count += 1
                    print(f"{match_count}. CLIP: {base_name}")
                    print(f"   In: {start_tc} | Out: {end_tc}")
                    print("-" * 40)
                    
        except ValueError:
            continue

    if match_count == 0:
        print("No clips found entirely within the selection.")

if __name__ == "__main__":
    get_filtered_clips()