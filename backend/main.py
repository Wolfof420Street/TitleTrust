import sys
import os
import logging

# Force the current directory into the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import Routers
from routers import audit, health

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TitleTrust-Backend")

app = FastAPI(title="TitleTrust API", version="2.0.0")

# --- CORS Configuration ---
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080")
origins = [origin.strip() for origin in allowed_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# --- Include Routers ---
app.include_router(audit.router)
app.include_router(health.router)

logger.info("🚀 TitleTrust Backend v2.0 Started (Modular Architecture)")