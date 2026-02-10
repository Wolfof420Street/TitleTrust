import logging
import json
import googlemaps
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone

# Unified Google GenAI SDK
from google import genai
from google.genai import types

# Configuration
try:
    from config import settings
except ImportError:
    # Fallback/Mock for standalone testing
    class Settings:
        GCP_PROJECT_ID = "titletrust-f5bf6"
        VERTEX_AI_LOCATION = "us-central1"
        MAPS_API_KEY = "dummy"
        FORENSIC_MODEL_NAME = "gemini-3-pro-preview"
    settings = Settings()

# Import models for the adapter
try:
    from models import GeoCheck
except ImportError:
    pass

# Import Centralized Tools
try:
    from agent.tools import get_satellite_ground_truth
except ImportError:
    pass

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [GEO-AGENT] - %(message)s")
logger = logging.getLogger(__name__)

# --- EXTERNAL TOOLS (The "Senses") ---

# Initialize Google Maps
try:
    gmaps = googlemaps.Client(key=settings.MAPS_API_KEY)
except Exception as e:
    logger.warning(f"Google Maps API not initialized: {e}")
    gmaps = None


# --- THE GEOSPATIAL AGENT ---

class GeoVerificationAgent:
    def __init__(self):
        # Initialize Unified Client
        self.client = genai.Client(
            api_key=settings.GEMINI_API_KEY
        )

        # 1. Tool Definitions (Pass python function directly)
        self.tools = [get_satellite_ground_truth]

        # 2. System Persona (The Surveyor)
        self.system_instruction = """
        <role>
        You are an AI Field Surveyor and Auditor.
        Your goal is to perform a 'Reality Check' by comparing a User's Live Video Feed against Satellite Ground Truth.
        </role>

        <mission>
        1. **Perceive**: Analyze the uploaded image. Describe the terrain, vegetation, and structures key details.
        2. **Verify**: CALL `get_satellite_ground_truth` with the provided GPS to see what the map says *should* be there.
        3. **Reason**: Detect Land Fraud (Encroachment, Grabbing, Spoofing) by comparing Vision vs. Map Data.
        </mission>
        """

    def verify_location_integrity(self, file_path: str, lat: float, lng: float) -> Dict[str, Any]:
        """
        Main Agent Loop.
        Uses Gemini Files API to handle large media (Images/Video/PDF).
        MIME type is auto-detected by the Files API.
        """
        logger.info(f"🚁 Starting Aerial/Ground Verification Loop at {lat}, {lng}")
        
        # 1. Upload File to Gemini (Files API)
        # This handles large files (>20MB) and videos correctly
        try:
            logger.info(f"📤 Uploading file to Gemini: {file_path}")
            uploaded_file = self.client.files.upload(file=file_path)
            logger.info(f"✅ Upload Complete. URI: {uploaded_file.uri}")
        except Exception as e:
            logger.error(f"Failed to upload file to Gemini: {e}")
            return {"error": f"Media upload failed: {str(e)}"}
        
        # Start Chat with 3.0 Pro
        chat = self.client.chats.create(
            model=settings.FORENSIC_MODEL_NAME,
            config=types.GenerateContentConfig(
                 system_instruction=self.system_instruction,
                 tools=self.tools,
                 temperature=0.3, 
                 media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH, # Ensure high-fidelity video/image analysis
                 max_output_tokens=2048,
                 automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)
            )
        )

        # Prompt with File URI
        # Critical: Use the MIME type detected by the Files API
        prompt_parts = [
            types.Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type),
            f"Here is the live feed from the surveyor's device at GPS: {lat}, {lng}. Verify this location."
        ]

        # Send Message
        try:
            response = chat.send_message(prompt_parts)
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return {"error": f"AI verify failed: {str(e)}"}

        # In Auto Mode, the SDK handles the loop. We just inspect the result.
        # We need to find the final JSON in the text response
        final_json = None
        
        # Log Thoughts and Text
        if response.text:
             logger.info(f"🤖 AGENT: {response.text}")
             # Check for JSON in the text response (Unified SDK returns final text after tool calls)
             if "{" in response.text:
                 import re
                 match = re.search(r"\{.*\}", response.text, re.DOTALL)
                 if match:
                     final_json = match.group(0)

        # Parse Final Result
        if final_json:
            try:
                return json.loads(final_json)
            except json.JSONDecodeError:
                return {"error": "Failed to parse Agent JSON", "raw": final_json}
        
        # Fallback if no JSON found (it might be in parts we missed or purely text)
        return {"error": "Agent did not output structured JSON.", "raw_response": response.text}

class LiveGeospatialVerifier:
    """
    Manages Ephemeral Tokens for the Client-to-Server Live API connection.
    This allows the mobile app to stream video directly to Gemini without hitting our backend servers for media processing.
    """
    def __init__(self):
        self.client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options={'api_version': 'v1alpha'} # Live API requires v1alpha
        )

    def generate_session_token(self, session_id: str, context: Dict[str, Any]) -> Dict[str, str]:
        """
        Generates an ephemeral token locked to a specific audit context.
        """
        user_name = context.get("user", "Surveyor")
        title_number = context.get("title_number", "Unknown")
        expected_size = context.get("size", "Unknown")
        target_lat = context.get("lat")
        target_lng = context.get("lng")

        # 1. Bake Context into System Instruction
        # This ensures the model knows EXACTLY what it's looking at without the user needing to prompt it.
        system_instruction = f"""
        <role>
        You are a Field Auditor for the Kenyan Ministry of Lands.
        You are talking to {user_name}, who is on-site at a property.
        </role>

        <mission>
        Your goal is to verify if the land they are showing you matches the Title Deed: {title_number}.
        
        **Title Details**:
        - Number: {title_number}
        - Registered Size: {expected_size}
        - Expected Location: {target_lat}, {target_lng}
        </mission>

        <protocol>
        1. **Greet** the surveyor and ask them to pan the camera around.
        2. **Observe** the boundaries. Ask: "Can you show me the beacons?"
        3. **Verify** land features. If the deed says "0.05 Ha" but you see a huge ranch, FLAG IT.
        4. **Search**: Use your `google_search` tool to check for news/court cases about this specific title number if things look suspicious.
        5. **Verdict**: At the end, tell them if it looks "CLEAN" or "FLAGGED".
        </protocol>
        """

        # 2. Configure Token Constraints
        # We lock the token so it can ONLY be used for this specific task.
        expiration = datetime.now(timezone.utc) + timedelta(minutes=15) # 15 min session limit
        
        try:
            token = self.client.auth_tokens.create(
                config={
                    'uses': 1, # Token dies after one session
                    'expire_time': expiration,
                    'live_connect_constraints': {
                        'model': settings.FORENSIC_MODEL_NAME, # Enforce 3.0 Pro
                        'config': {
                            'system_instruction': {"parts": [{"text": system_instruction}]},
                            'tools': [{'google_search': {}}], # Enable Grounding
                            'response_modalities': ['AUDIO'], # Voice Mode
                        }
                    }
                }
            )
            
            logger.info(f"🎟️ Generated Ephemeral Token for Session {session_id}")
            return {
                "token": token.name, # This is what the client uses as the API Key
                "session_id": session_id,
                "expiration": expiration.isoformat(),
                "model": settings.FORENSIC_MODEL_NAME
            }
            
        except Exception as e:
            logger.error(f"Failed to generate ephemeral token: {e}")
            raise e


# --- LEGACY ADAPTER FOR MAIN.PY ---

def vision_map_sync(lat: float, lng: float, file_path: str) -> Dict[str, Any]:
    """
    Adapter to bridge main.py's vision_map_sync call to the new GeoVerificationAgent.
    """
    agent = GeoVerificationAgent()
    
    # Run the agent
    result = agent.verify_location_integrity(file_path, lat, lng)
    
    # Map to GeoCheck model fields if possible, or return dict for Pydantic to parse
    # GeoCheck expects: check_id, plot_coordinates, user_video_description, satellite_analysis_result, risk_level
    
    description = result.get("reasoning", "No description generated.")
    match_status = result.get("match_status", "UNKNOWN")
    risk_score = result.get("risk_score", 0)
    
    risk_level = "LOW"
    if risk_score > 70: risk_level = "CRITICAL"
    elif risk_score > 30: risk_level = "MEDIUM"
        
    return {
        "check_id": str(uuid.uuid4()),
        "plot_coordinates": {"lat": lat, "lng": lng},
        "user_video_description": description[:100] + "..." if len(description) > 100 else description,
        "satellite_analysis_result": f"Match Status: {match_status}. Score: {risk_score}",
        "risk_level": risk_level
    }

# --- TEST HARNESS ---
if __name__ == "__main__":
    pass
