import grpc
import json
import threading
import logging

# Import the generated gRPC stubs
# Assuming you ran the protoc command in the previous step
try:
    from proto import PTSL_pb2
    from proto import PTSL_pb2_grpc
except ImportError:
    print("Error: gRPC stubs not found. Please ensure you ran the compilation command in the 'proto' folder.")

# Set up logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PTSLClient")

class PTSLClient:
    def __init__(self, address="localhost:31416"):
        """
        Initializes the connection to the Pro Tools Scripting SDK.
        Default address is localhost:31416.
        """
        self.address = address
        self.channel = grpc.insecure_channel(self.address)
        self.stub = PTSL_pb2_grpc.PTSLStub(self.channel)
        
        self.session_id = ""
        self.lock = threading.Lock()
        
        logger.info(f"Initialized PTSL Client on {self.address}")

    def register_connection(self, company_name: str, app_name: str) -> bool:
        """
        Performs the mandatory handshake with Pro Tools.
        Sets the session_id required for all future commands.
        """
        # 1. Prepare the JSON body for registration
        registration_dict = {
            "company_name": company_name,
            "application_name": app_name
        }
        
        # 2. Construct the Request object
        # Note: CommandId 1 is typically RegisterConnection
        # We use the enum from the generated proto file
        request = PTSL_pb2.Request(
            header=PTSL_pb2.RequestHeader(session_id=""), # Empty for registration
            command=PTSL_pb2.CId_RegisterConnection,
            body=json.dumps(registration_dict)
        )

        try:
            with self.lock:
                response = self.stub.SendRequest(request)
            
            if response.status == PTSL_pb2.Completed:
                # The session_id is returned inside the JSON response body
                response_body = json.loads(response.response_body)
                self.session_id = response_body.get("session_id", "")
                
                if self.session_id:
                    logger.info(f"Successfully registered with Pro Tools. Session ID: {self.session_id}")
                    return True
                else:
                    logger.error("Registration succeeded but no session_id was returned.")
            else:
                logger.error(f"Registration failed with status: {response.status}")
                logger.error(f"Error Detail: {response.response_error}")
                
        except grpc.RpcError as e:
            logger.error(f"gRPC Connection Error during registration: {e.details()}")
        
        return False

    def send_command(self, command_id, body_dict=None) -> dict:
        """
        Generic method to send any command to Pro Tools.
        Automatically handles the RequestHeader and JSON serialization.
        """
        if not self.session_id and command_id != PTSL_pb2.CId_RegisterConnection:
            raise Exception("Client is not registered. Call register_connection() first.")

        # Prepare body
        body_json = json.dumps(body_dict) if body_dict else ""

        # Construct request with the active session_id
        request = PTSL_pb2.Request(
            header=PTSL_pb2.RequestHeader(session_id=self.session_id),
            command=command_id,
            body=body_json
        )

        try:
            with self.lock:
                response = self.stub.SendRequest(request)
            
            # Parse the response body JSON
            result_data = {}
            if response.response_body:
                result_data = json.loads(response.response_body)

            # Return a clean dictionary with status and data
            return {
                "status": response.status, # Use PTSL_pb2.Completed/Failed to check
                "data": result_data,
                "error": response.response_error
            }

        except grpc.RpcError as e:
            logger.error(f"gRPC Error during command {command_id}: {e.details()}")
            return {"status": PTSL_pb2.Failed, "data": {}, "error": str(e.details())}

    def close(self):
        """Closes the gRPC channel."""
        self.channel.close()
        logger.info("PTSL Connection Closed.")

# --- TEST BLOCK ---
# This allows you to run this file alone to test the connection
if __name__ == "__main__":
    client = PTSLClient()
    # Replace with your details
    success = client.register_connection("Rogue Waves", "Bouncey")
    
    if success:
        print("HANDSHAKE SUCCESSFUL!")
        # Test a simple command: Get the track list
        # Note: In your actual app, you'll use the enum names from PTSL_pb2
        response = client.send_command(PTSL_pb2.CId_GetTrackList)
        print(f"Current Tracks: {response['data']}")
    else:
        print("HANDSHAKE FAILED. Is Pro Tools open and is the Scripting SDK enabled?")
    
    client.close()