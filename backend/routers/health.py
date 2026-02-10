from fastapi import APIRouter
import os

router = APIRouter(tags=["Health"])

@router.get("/")
def health_check():
    return {"status": "TitleTrust Backend Operational", "env": os.getenv("ENV", "DEV")}
