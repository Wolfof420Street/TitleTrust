import logging
from firebase_admin import firestore, messaging
from services.firebase import db
from datetime import datetime

logger = logging.getLogger("FirebaseSyncService")

class FirebaseSyncService:
    def __init__(self):
        self.db = db

    def update_session_state(self, session_id: str, status: str = None, latest_thought: str = None, percent: int = None, logs: list = None, findings: list = None, audit_conclusion: str = None):
        """
        Updates the Firestore session document with real-time state.
        """
        try:
            doc_ref = self.db.collection("sessions").document(session_id)
            
            update_data = {
                "last_updated": firestore.SERVER_TIMESTAMP
            }
            
            if status:
                update_data["status"] = status
            
            if latest_thought:
                update_data["latest_thought"] = latest_thought
                # Append thought to a history array for replay?
                # update_data["thoughts"] = firestore.ArrayUnion([{"timestamp": datetime.utcnow(), "text": latest_thought}])
            
            if percent is not None:
                update_data["percent_complete"] = percent
                
            if logs:
                # logs should be specific structured dicts
                update_data["logs"] = firestore.ArrayUnion(logs)
            
            if findings:
                update_data["findings"] = findings
            
            if audit_conclusion:
                update_data["audit_conclusion"] = audit_conclusion
            
            doc_ref.set(update_data, merge=True)
            logger.debug(f"🔄 Synced session {session_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to sync session state: {e}")

    def send_push_notification(self, user_id: str, title: str, body: str, data: dict = None):
        """
        Sends a real FCM push notification to the user.
        """
        try:
            # 1. Get Token
            token = self._get_fcm_token(user_id)
            if not token:
                logger.warning(f"📭 No FCM token found for user {user_id}. Skipping push.")
                return

            # 2. Construct Message
            # Ensure data implies click_action for Flutter
            payload = data or {}
            payload["click_action"] = "FLUTTER_NOTIFICATION_CLICK" 
            
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=payload,
                token=token,
            )

            # 3. Send
            response = messaging.send(message)
            logger.info(f"📨 Push sent to {user_id}: {response}")
            
        except messaging.UnregisteredError:
            logger.warning(f"🚫 Token unregistered for user {user_id}. Removing stale token.")
            self._remove_stale_token(user_id)
        except Exception as e:
            logger.error(f"❌ Push failed: {e}")

    def _get_fcm_token(self, user_id: str) -> str:
        """
        Fetches the FCM token from the user's Firestore document.
        """
        try:
            # For hackathon/demo, if user_id is generic or missing, we might default to a known doc
            # But here we assume robust auth.
            if user_id == "unknown": 
                 # Fallback: Try to find *a* user or just fail. 
                 # Better: The session should have an 'owner_id' field.
                 return None 

            doc = self.db.collection("users").document(user_id).get()
            if doc.exists:
                return doc.get("fcm_token")
            return None
        except Exception as e:
            logger.error(f"Error fetching token: {e}")
            return None

    def _remove_stale_token(self, user_id: str):
        try:
            self.db.collection("users").document(user_id).update({"fcm_token": firestore.DELETE_FIELD})
        except Exception:
            pass
