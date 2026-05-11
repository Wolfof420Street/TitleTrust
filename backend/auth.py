import firebase_admin
from firebase_admin import auth
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from services.firebase import initialize_firebase

# Ensure Firebase is initialized
initialize_firebase()

security = HTTPBearer()

import logging

logger = logging.getLogger(__name__)

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    Validates the Firebase ID Token in the Authorization header.
    Returns the decoded token (user dict) if valid.
    """
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    try:
        # Verify the ID token
        return auth.verify_id_token(token)
    except (auth.InvalidIdTokenError, auth.ExpiredIdTokenError) as e:
        logger.warning(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials"
        ) from e
    except auth.AuthError as e:
        logger.exception("Firebase auth infrastructure error")
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable"
        ) from e
    except Exception as e:
        logger.exception("Unexpected authentication error")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        ) from e
