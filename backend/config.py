from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    GCP_PROJECT_ID: str = Field(..., env="GCP_PROJECT_ID")
    MAPS_API_KEY: str = Field(..., env="MAPS_API_KEY")
    VERTEX_AI_LOCATION: str = Field("us-central1", env="VERTEX_AI_LOCATION")
    GEMINI_API_KEY: str = Field(..., env="GEMINI_API_KEY")
    FIREBASE_CREDENTIALS: Optional[str] = Field(None, env="GOOGLE_APPLICATION_CREDENTIALS")
    
    # Model Names
    # Use Gemini 2.0 Flash for speed/vision, Pro for complex reasoning
    # Model Names
    # STRICTLY Gemini 3 (User Requirement)
    MODEL_NAME: str = "gemini-3-flash-preview"
    FORENSIC_MODEL_NAME: str = "gemini-3-pro-preview" 
    VISION_MODEL_NAME: str = "gemini-3-flash-preview"
    KNOWLEDGEBASE_DIR: str = "knowledgebase"
    
    # Cloud Tasks
    CLOUD_TASKS_PROJECT_ID: Optional[str] = Field(None, env="GCP_PROJECT_ID")
    CLOUD_TASKS_QUEUE: str = Field("marathon-queue", env="CLOUD_TASKS_QUEUE")
    CLOUD_TASKS_LOCATION: str = Field("us-central1", env="CLOUD_TASKS_LOCATION")
    CLOUD_RUN_URL: Optional[str] = Field(None, env="CLOUD_RUN_URL")
    SERVICE_ACCOUNT_EMAIL: Optional[str] = Field(None, env="SERVICE_ACCOUNT_EMAIL")
    FIREBASE_CREDENTIALS_PATH: Optional[str] = Field(None, env="FIREBASE_CREDENTIALS_PATH")

    class Config:
        env_file = ".env"

import os
settings = Settings()
os.makedirs(settings.KNOWLEDGEBASE_DIR, exist_ok=True)
