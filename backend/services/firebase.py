import os
import logging
import firebase_admin
from firebase_admin import firestore, credentials, initialize_app, get_app

logger = logging.getLogger("TitleTrust-Firebase")

def initialize_firebase():
    try:
        try:
            get_app()
        except ValueError:
            # Check if we have credentials file or use default (GCP/Env)
            cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            
            if cred_path:
                 cred = credentials.Certificate(cred_path)
                 initialize_app(cred)
            else:
                 logger.warning("No FIREBASE_CREDENTIALS_PATH found. Using default/ADC.")
                 initialize_app()
        return firestore.client()
    except Exception as e:
        logger.error(f"Failed to init Firebase: {e}")
        raise e

db = initialize_firebase()
