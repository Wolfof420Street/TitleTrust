import firebase_admin
from firebase_admin import auth
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Initialize Firebase Admin
# Uses Application Default Credentials (ADC) in Cloud Run
if not firebase_admin._apps:
    firebase_admin.initialize_app()

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    Validates the Firebase ID Token in the Authorization header.
    Returns the decoded token (user dict) if valid.
    """
    token = credentials.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        # In production, might want to log the error but return generic 401
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials"
        )
