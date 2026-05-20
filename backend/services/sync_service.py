import logging
from firebase_admin import messaging

try:
    from backend.repositories.session_repository import SessionRepository
    from backend.repositories.user_repository import UserRepository
    from backend.services.firebase import db
except ModuleNotFoundError:
    from repositories.session_repository import SessionRepository
    from repositories.user_repository import UserRepository
    from services.firebase import db

logger = logging.getLogger("FirebaseSyncService")


class FirebaseSyncService:
    """Service for syncing session state and sending notifications.
    
    Uses repositories for all persistence operations - no direct Firestore access.
    """
    
    def __init__(self):
        self._sessions = SessionRepository(db)
        self._users = UserRepository(db)

    def update_session_state(
        self,
        session_id: str,
        status: str = None,
        latest_thought: str = None,
        percent: int = None,
        logs: list = None,
        findings: list = None,
        audit_conclusion: str = None,
    ) -> None:
        """Updates session state via repository."""
        try:
            update_data = {}

            if status:
                update_data["status"] = status

            if latest_thought:
                update_data["latest_thought"] = latest_thought

            if percent is not None:
                update_data["percent_complete"] = percent

            if logs:
                update_data["logs"] = logs

            if findings:
                update_data["findings"] = findings

            if audit_conclusion:
                update_data["audit_conclusion"] = audit_conclusion

            if update_data:
                self._sessions.update(session_id, update_data)
                logger.debug(f"🔄 Synced session {session_id}")

        except Exception as e:
            logger.error(f"❌ Failed to sync session state: {e}")

    def send_push_notification(
        self, user_id: str, title: str, body: str, data: dict = None
    ) -> None:
        """Sends FCM push notification to user."""
        try:
            # 1. Get Token via repository
            token = self._users.get_fcm_token(user_id)
            if not token:
                logger.warning(f"📭 No FCM token found for user {user_id}. Skipping push.")
                return

            # 2. Construct Message
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
            self._users.remove_fcm_token(user_id)
        except Exception as e:
            logger.error(f"❌ Push failed: {e}")
