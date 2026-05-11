import os
import logging
import firebase_admin
from firebase_admin import firestore, credentials, initialize_app, get_app
from config import get_settings

logger = logging.getLogger("TitleTrust-Firebase")
settings = get_settings()

def initialize_firebase():
    try:
        try:
            get_app()
        except ValueError:
            # Check if we have credentials file or use default (GCP/Env)
            cred_path = settings.resolved_firebase_credentials
            
            if cred_path:
                 cred = credentials.Certificate(cred_path)
                 initialize_app(cred)
            else:
                 logger.warning("No explicit Firebase credentials path found. Using ADC.")
                 initialize_app()
        return firestore.client()
    except Exception as e:
        logger.exception("Failed to initialize Firebase")
        raise

db = initialize_firebase()
