from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    ENV: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    GCP_PROJECT_ID: Optional[str] = Field(default=None)
    MAPS_API_KEY: Optional[str] = Field(default=None)
    VERTEX_AI_LOCATION: str = Field(default="us-central1")
    GEMINI_API_KEY: Optional[str] = Field(default=None)
    GEMINI_MAX_CONCURRENT_REQUESTS: int = Field(default=2)
    GEMINI_RATE_LIMIT_CALLS: int = Field(default=10)
    GEMINI_RATE_LIMIT_PERIOD_SECONDS: int = Field(default=60)
    GEMINI_CACHE_TTL_SECONDS: int = Field(default=3600)
    GEMINI_CACHE_ENABLED: bool = Field(default=True)

    FIREBASE_CREDENTIALS_PATH: Optional[str] = Field(default=None, alias="FIREBASE_CREDENTIALS_PATH")
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = Field(default=None)
    UPLOAD_BUCKET_NAME: Optional[str] = Field(default=None)
    STORAGE_UPLOAD_PREFIX: str = Field(default="uploads")
    SIGNED_UPLOAD_URL_TTL_SECONDS: int = Field(default=900)

    MODEL_NAME: str = Field(default="gemini-3-flash-preview")
    FORENSIC_MODEL_NAME: str = Field(default="gemini-3-pro-preview")
    VISION_MODEL_NAME: str = Field(default="gemini-3-flash-preview")
    KNOWLEDGEBASE_DIR: str = Field(default="knowledgebase")

    CLOUD_TASKS_PROJECT_ID: Optional[str] = Field(default=None)
    CLOUD_TASKS_QUEUE: str = Field(default="marathon-queue")
    CLOUD_TASKS_LOCATION: str = Field(default="us-central1")
    CLOUD_RUN_URL: Optional[str] = Field(default=None)
    SERVICE_ACCOUNT_EMAIL: Optional[str] = Field(default=None)

    ALLOWED_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:8080")
    API_RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    REDIS_URL: Optional[str] = Field(default=None)
    SESSION_COLLECTION: str = Field(default="sessions")
    USERS_COLLECTION: str = Field(default="users")
    AUDIT_EVENT_COLLECTION: str = Field(default="audit_events")
    IDEMPOTENCY_COLLECTION: str = Field(default="idempotency_keys")
    HEALTHCHECK_COLLECTION: str = Field(default="healthchecks")
    JOB_COLLECTION: str = Field(default="jobs")
    DEAD_LETTER_COLLECTION: str = Field(default="dead_letter_jobs")
    POLICY_COLLECTION: str = Field(default="policies")
    MEMBERSHIP_COLLECTION: str = Field(default="memberships")
    DEVICE_SESSION_COLLECTION: str = Field(default="device_sessions")
    WORKER_QUEUE_NAME: str = Field(default="titletrust.jobs")
    WORKER_HEARTBEAT_TTL_SECONDS: int = Field(default=60)
    WORKER_TASK_TIMEOUT_SECONDS: int = Field(default=300)
    WORKER_MAX_RETRIES: int = Field(default=3)
    QUEUE_MODE: str = Field(default="inline")
    # Realtime broadcaster
    REDIS_PUBSUB_ENABLED: bool = Field(default=False)
    BROADCASTER_CHANNEL: str = Field(default="titletrust:realtime")
    BROADCASTER_REPLAY_BUFFER: int = Field(default=256)
    BROADCASTER_MAX_QUEUE_SIZE: int = Field(default=64)
    BROADCASTER_HEARTBEAT_INTERVAL_SECONDS: int = Field(default=15)
    # Redis streams / durable replay
    REDIS_STREAMS_ENABLED: bool = Field(default=False)
    BROADCASTER_STREAM_KEY: str = Field(default="titletrust:realtime:stream")
    BROADCASTER_STREAM_MAXLEN: int = Field(default=10000)
    # Safety controls
    BROADCASTER_MAX_REPLAY_WINDOW: int = Field(default=10000)
    MAX_EVENT_PAYLOAD_BYTES: int = Field(default=64 * 1024)  # 64KB

    @field_validator("ENV")
    @classmethod
    def validate_env(cls, value: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        lowered = value.lower()
        if lowered not in allowed:
            raise ValueError(f"ENV must be one of: {', '.join(sorted(allowed))}")
        return lowered

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def resolved_firebase_credentials(self) -> Optional[str]:
        return self.FIREBASE_CREDENTIALS_PATH or self.GOOGLE_APPLICATION_CREDENTIALS

    @property
    def allowed_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
