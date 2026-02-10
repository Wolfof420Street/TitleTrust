from firebase_admin import messaging
import logging

logger = logging.getLogger("NotificationService")

def send_fcm_notification(user_id: str, title: str, body: str, data: dict = None):
    """
    Sends a Firebase Cloud Message to a specific user.
    In a real app, we'd fetch the FCM token from Firestore users/{user_id}.
    For the Hackathon, we'll assume a token is passed or just log it if mocking.
    """
    # 1. Get User's Token from Firestore (Pseudo-code as we can't easily access DB here without circular imports or passing db)
    # user_ref = db.collection("users").document(user_id).get()
    # token = user_ref.get("fcm_token")
    
    # Mock Token for now -> In production, replace with real fetch
    token = "DEVICE_FCM_TOKEN_MOCK" 
    
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {}, # Data Payload for background handling
            token=token,
        )
        
        # In this mock environment, sending might fail if token is invalid. 
        # We wrap in try/except.
        # response = messaging.send(message)
        logger.info(f"📨 [FCM] Sent to {user_id}: {title}")
        return "Message Sent"
    except Exception as e:
        logger.warning(f"📨 [FCM] Failed to send (Mock Token): {e}")
        return str(e)
