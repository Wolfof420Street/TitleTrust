import json
import logging
import time
from typing import Optional
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
try:
    from backend.config import settings
except ModuleNotFoundError:
    from config import settings

logger = logging.getLogger("CloudTasksService")

class CloudTasksService:
    def __init__(self):
        self.project = settings.CLOUD_TASKS_PROJECT_ID or settings.GCP_PROJECT_ID
        self.queue = settings.CLOUD_TASKS_QUEUE
        self.location = settings.CLOUD_TASKS_LOCATION
        self.url = settings.CLOUD_RUN_URL
        
        if self.project and self.url:
            try:
                self.client = tasks_v2.CloudTasksClient()
                self.parent = self.client.queue_path(self.project, self.location, self.queue)
                logger.info(f"✅ Cloud Tasks Initialized: {self.parent}")
            except Exception as e:
                logger.warning(f"⚠️ Cloud Tasks Client Failed (Local Dev?): {e}")
                self.client = None
        else:
            logger.warning("⚠️ Missing Cloud Tasks Config (Project/URL). Running in Local Mode.")
            self.client = None

    def schedule_next_tick(self, session_id: str, countdown_seconds: int = 5):
        """
        Schedules the next 'tick' for the Marathon Agent.
        """
        if not self.client:
            logger.info(f"🔄 [LOCAL] Simulate scheduling tick for {session_id} in {countdown_seconds}s")
            return

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{self.url}/audit/tick",
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"session_id": session_id}).encode(),
                "oidc_token": {
                    "service_account_email": settings.SERVICE_ACCOUNT_EMAIL or f"{self.project}@appspot.gserviceaccount.com"
                }
            }
        }

        # Add schedule time
        if countdown_seconds > 0:
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromSeconds(int(time.time() + countdown_seconds))
            task["schedule_time"] = timestamp

        try:
            response = self.client.create_task(request={"parent": self.parent, "task": task})
            logger.info(f"🚀 Tasks Scheduled: {response.name}")
        except Exception as e:
            logger.error(f"❌ Failed to schedule task: {e}")
