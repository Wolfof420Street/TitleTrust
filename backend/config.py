from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    GCP_PROJECT_ID: str = Field(..., env="GCP_PROJECT_ID")
    MAPS_API_KEY: str = Field(..., env="MAPS_API_KEY")
    VERTEX_AI_LOCATION: str = Field("us-central1", env="VERTEX_AI_LOCATION")
    
    # Model Names
    FORENSIC_MODEL_NAME: str = "gemini-2.5-pro"
    VISION_MODEL_NAME: str = "gemini-2.5-flash"

    class Config:
        env_file = ".env"

settings = Settings()
