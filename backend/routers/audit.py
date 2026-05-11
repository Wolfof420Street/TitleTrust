import os
import uuid
import logging
import tempfile
import shutil
from typing import Dict, Any, List

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.concurrency import run_in_threadpool

from auth import get_current_user
from models import AuditRequest, Document, DocumentType, GeoCheck, LiveTokenRequest
from forensic_engine import perform_forensic_audit
from geospatial_engine import vision_map_sync, LiveGeospatialVerifier
from agent.marathon_loop import MarathonLoop, AgentState, MarathonState
from repositories.session_repository import SessionRepository
from services.cloud_tasks import CloudTasksService
from services.firebase import db
from services.sync_service import FirebaseSyncService

router = APIRouter(prefix="/audit", tags=["Audit"])
logger = logging.getLogger("TitleTrust-AuditRouter")
cloud_tasks = CloudTasksService()
sessions_repo = SessionRepository(db)
sync_service = FirebaseSyncService()
ALLOWED_UPLOAD_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".mp4", ".mov"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


def _validate_upload(filename: str, file_size: int, allowed_suffixes: set[str]) -> str:
    suffix = os.path.splitext(filename or "")[1].lower()
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")
    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail=f"File {filename} exceeds 50MB limit")
    return suffix


@router.post("/tick")
async def marathon_tick(payload: Dict[str, str]):
    """
    Heartbeat for the Recursive Task Chain.
    This endpoint is called by Google Cloud Tasks.
    """
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")
        
    logger.info(f"⏰ Tick received for session: {session_id}")
    
    try:
        # Rehydrate Agent
        agent = MarathonLoop(db, session_id)
        
        # REMOVED: Force status update to RUNNING (Matches user fix to prevent race condition)
        # The agent manages its own state now.
        
        # Execute ONE Step
        result = agent.run_single_step()
        
        status = result["status"]
        next_tick = result["next_tick_seconds"]
        
        if status == AgentState.RUNNING:
            logger.info(f"🔄 Rescheduling next tick in {next_tick}s")
            cloud_tasks.schedule_next_tick(session_id, next_tick)
        elif status == AgentState.WAITING_FOR_USER:
             logger.info("⏸️ Agent waiting for user. Task chain paused.")
        elif status in [AgentState.COMPLETED, AgentState.FAILED]:
             logger.info(f"🏁 Agent finished ({status}). Task chain stopped.")
             
        return {"status": "success", "agent_status": status}
        
    except Exception as e:
        logger.exception("Tick failed")
        # Retrying handled by Cloud Tasks configuration (Queue settings)
        raise HTTPException(status_code=500, detail="Tick processing failed")


@router.post("/forensic", response_model=dict)
async def create_forensic_audit(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Uploads 'Deal Pack' (PDFs/Images).
    Uses temporary files to handle large documents efficiently.
    """
    request_id = str(uuid.uuid4())
    documents = []
    temp_file_paths = []
    
    try:
        # Validate files
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        if len(files) > 10:  # Add reasonable limit
            raise HTTPException(status_code=400, detail="Maximum 10 files allowed")
        
        for file in files:
            # Validate file size (e.g., 50MB limit)
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(0)  # Reset
            
            suffix = _validate_upload(file.filename, file_size, {".pdf", ".png", ".jpg", ".jpeg"})
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                shutil.copyfileobj(file.file, tmp)
                tmp_path = tmp.name
                temp_file_paths.append(tmp_path)
            
            logger.info(f"💾 Saved forensic upload: {file.filename} → {tmp_path} ({file_size} bytes)")

            # Determine document type
            filename = file.filename.lower()
            doc_type = DocumentType.OTHER
            if "green" in filename or "card" in filename:
                doc_type = DocumentType.GREEN_CARD
            elif "title" in filename or "deed" in filename:
                doc_type = DocumentType.TITLE_DEED
            elif "mutation" in filename:
                doc_type = DocumentType.MUTATION_FORM
            elif "sale" in filename or "agreement" in filename:
                doc_type = DocumentType.SALE_AGREEMENT
            
            documents.append(Document(
                document_id=str(uuid.uuid4()),
                type=doc_type,
                gcs_path=f"temp://{tmp_path}"  # Store actual path for forensic engine
            ))

        audit_request = AuditRequest(
            request_id=request_id,
            user_id=user["uid"],
            documents=documents,
            status="PROCESSING"
        )
        
        logger.info(f"🔍 Starting forensic audit {request_id} with {len(documents)} documents")
        
        # Run Forensic Audit in Threadpool
        findings = await run_in_threadpool(
            perform_forensic_audit, 
            audit_request, 
            file_paths=temp_file_paths
        )
        
        audit_request.findings = findings
        audit_request.status = "FLAGGED" if any("CRITICAL" in str(f) for f in findings) else "COMPLETED"
        
        logger.info(f"✅ Forensic audit {request_id} completed: {audit_request.status}")
        
        return audit_request.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Forensic audit failed")
        raise HTTPException(status_code=500, detail="Audit failed")

    finally:
        # Schedule cleanup of all temp files
        for path in temp_file_paths:
            if os.path.exists(path):
                background_tasks.add_task(os.remove, path)
                logger.debug(f"🧹 Scheduled cleanup for: {path}")


@router.post("/geospatial", response_model=GeoCheck)
async def create_geospatial_audit(
    background_tasks: BackgroundTasks,
    lat: float = Form(..., ge=-90, le=90),
    lng: float = Form(..., ge=-180, le=180),
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user),
):
    # Save UploadFile to a temporary file correctly
    # This prevents loading large videos entirely into RAM
    
    # Create temp file
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    suffix = _validate_upload(file.filename, file_size, ALLOWED_UPLOAD_SUFFIXES)
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
        
    logger.info(f"💾 Saved upload to temp file: {tmp_path} ({os.path.getsize(tmp_path)} bytes)")
    
    # Run Sync in threadpool if it involves Computer Vision
    try:
        result = await run_in_threadpool(vision_map_sync, lat, lng, tmp_path)
    finally:
        # Schedule cleanup after response is sent
        background_tasks.add_task(os.remove, tmp_path)
        logger.info(f"🧹 Scheduled cleanup for: {tmp_path}")
    
    return result


@router.post("/geospatial/live-token")
async def generate_live_token(
    req: LiveTokenRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Generates an Ephemeral Token for the Generic Live API.
    The token is locked to the specific context provided in the request body.
    """
    logger.info(f"🎟️ Requesting Live Token for Session: {req.session_id}")
    
    try:
        verifier = LiveGeospatialVerifier()
        
        context = {
            "user": req.user_name,
            "title_number": req.title_number,
            "size": req.expected_size,
            "lat": req.lat,
            "lng": req.lng
        }
        
        # Using threadpool for safety
        result = await run_in_threadpool(
            verifier.generate_session_token,
            req.session_id,
            context
        )
        
        return result
        
    except Exception as e:
        logger.exception("Failed to generate live token")
        raise HTTPException(status_code=500, detail="Live token generation failed")


@router.post("/start")
async def start_marathon_audit(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    [The Marathon Entry Point]
    Starts the Recursive Task Chain.
    """
    session_id = str(uuid.uuid4())
    logger.info(f"🚀 Starting Marathon Session: {session_id}")

    # 1. Save File to Temp Location
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    suffix = _validate_upload(file.filename, file_size, ALLOWED_UPLOAD_SUFFIXES)
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    
    logger.info(f"💾 Saved upload to: {tmp_path}")
    
    # 2. Initialize Session with COMPLETE initial state
    initial_state = MarathonState(
        session_id=session_id,
        status=AgentState.QUEUED,
        image_path=tmp_path,  # Properly inject image path
        memory=[f"📁 Received initial file: {tmp_path}"]  # Add to memory for recovery
    )
    
    # Save initial state via repository
    sessions_repo.create(
        session_id=session_id,
        user_id=user.get("uid"),
        payload=initial_state.model_dump(),
        organization_id="default"  # TODO: Get from user context
    )
    
    logger.info(f"✅ Session initialized with image_path: {tmp_path}")
    
    # 3. Bootstrap Task (First Step)
    def bootstrap_task(sid: str, path: str):
        """
        Runs the first step (image analysis) synchronously.
        Then hands off to Cloud Tasks for remaining steps.
        """
        try:
            logger.info(f"BOOTSTRAP: Starting session {sid}")
            
            # Create agent
            agent = MarathonLoop(db, sid)
            
            # Verify image path exists
            if not os.path.exists(path):
                raise FileNotFoundError(f"Image file not found: {path}")
            
            # Run first step (should analyze image)
            logger.info("BOOTSTRAP: Running image analysis...")
            result = agent.run_single_step()
            
            logger.info(f"BOOTSTRAP: First step complete. Status={result['status']}, Next={result['next_tick_seconds']}s")
            
            # If still running, schedule next tick
            if result["status"] == AgentState.RUNNING:
                logger.info("BOOTSTRAP: Handing off to Cloud Tasks")
                cloud_tasks.schedule_next_tick(sid, result["next_tick_seconds"])
            else:
                logger.warning(f"BOOTSTRAP: Unexpected status after first step: {result['status']}")
                
        except Exception as e:
            logger.error(f"❌ BOOTSTRAP FAILED for {sid}: {e}", exc_info=True)
            
            # Update session to failed via repository
            sessions_repo.update(sid, {
                "status": "FAILED",
                "error": f"Bootstrap failed: {str(e)}",
            })
            
            # Notify user via sync service
            try:
                session_data = sessions_repo.get(sid)
                if session_data:
                    owner_id = session_data.get("user_id")
                    if owner_id:
                        sync_service.send_push_notification(
                            owner_id,
                            "Audit Failed to Start",
                            "There was an error initializing your audit.",
                            {"job_id": sid}
                        )
            except:
                pass  # Don't fail if notification fails
            
        finally:
            # DON'T cleanup file here - agent needs it!
            # Agent will cleanup when done (see marathon_loop.cleanup())
            pass
    
    # 4. Run Bootstrap in Background
    background_tasks.add_task(bootstrap_task, session_id, tmp_path)
    
    return {
        "session_id": session_id,
        "status": "QUEUED",
        "message": "Investigation starting. Analyzing document..."
    }


@router.get("/status/{session_id}")
async def get_audit_status(
    session_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get current status of an audit session.
    Includes health check to detect stuck sessions.
    """
    try:
        data = sessions_repo.get(session_id)
        
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Verify user owns this session
        if data.get("user_id") != user.get("uid"):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Health check: detect stuck sessions
        import time
        last_update = data.get("last_update")
        if last_update:
            # Convert Firestore timestamp to seconds
            last_update_seconds = last_update.timestamp() if hasattr(last_update, 'timestamp') else last_update
            time_since_update = time.time() - last_update_seconds
            
            # If status is RUNNING or QUEUED but no update in 5 minutes, it's stuck
            if data.get("status") in ["RUNNING", "QUEUED"] and time_since_update > 300:
                logger.warning(f"⚠️ Session {session_id} appears stuck. Last update: {time_since_update}s ago")
                
                # Auto-fail stuck sessions via repository
                sessions_repo.update(session_id, {
                    "status": "FAILED",
                    "error": f"Session stuck - no update in {int(time_since_update)}s",
                })
                
                data["status"] = "FAILED"
                data["error"] = f"Session stuck - no update in {int(time_since_update)}s"
        
        return {
            "session_id": session_id,
            "status": data.get("status"),
            "progress": data.get("progress_checklist", {}),
            "total_steps": data.get("total_steps", 0),
            "last_thought": data.get("last_thought"),
            "error": data.get("error"),
            "findings": data.get("findings", []),
            "audit_conclusion": data.get("audit_conclusion")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Status check failed")
        raise HTTPException(status_code=500, detail="Status lookup failed")


@router.post("/retry/{session_id}")
async def retry_stuck_audit(
    session_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Manually retry a stuck or failed audit session.
    Useful when Cloud Tasks fail or agent gets stuck.
    """
    try:
        data = sessions_repo.get(session_id)
        
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Verify ownership
        if data.get("user_id") != user.get("uid"):
            raise HTTPException(status_code=403, detail="Access denied")
        
        status = data.get("status")
        
        # Only allow retry for failed or stuck sessions
        if status not in ["FAILED", "WAITING_FOR_USER", "QUEUED"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot retry session with status: {status}"
            )
        
        logger.info(f"🔄 Manual retry requested for session {session_id}")
        
        # Update status to RUNNING via repository
        sessions_repo.update(session_id, {
            "status": "RUNNING",
            "retry_count": (data.get("retry_count", 0) + 1),
        })
        
        # Schedule immediate tick
        cloud_tasks.schedule_next_tick(session_id, delay_seconds=1)
        
        return {
            "session_id": session_id,
            "status": "RETRYING",
            "message": "Session retry scheduled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Retry failed")
        raise HTTPException(status_code=500, detail="Retry failed")


@router.get("/titbits")
async def get_land_titbits(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Generates 5 interesting 'Did You Know?' facts about Kenyan Land Law 
    using Gemini 3 Flash for the loading screen.
    """
    from google import genai
    from google.genai import types
    from config import settings
    from agent.context_loader import cache_legal_context

    try:
        # Initialize Gemini 3 Flash Client (API Key)
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        # Use existing cache or create one
        cache_name = cache_legal_context()
        
        response = client.models.generate_content(
            model=settings.FORENSIC_MODEL_NAME, 
            contents="Generate 5 short, fascinating 'Did You Know?' facts about Kenyan Land Law, Title Deeds, or Fraud Prevention. Focus on surprising legal precedents or common scams. Keep each under 20 words.",
            config=types.GenerateContentConfig(
                temperature=0.7, # Reduced from 1.2 for stability
                response_mime_type="application/json",
                response_schema={
                    "type": "ARRAY",
                    "items": {"type": "STRING"}
                }
            )
        )
        
        import json
        if response.text:
             return {"titbits": json.loads(response.text)}
        else:
             return {"titbits": [
                 "Did you know? A Green Card is the only true proof of ownership, not the Title Deed.",
                 "The 'Ndungu Report' listed thousands of illegally acquired public lands.",
                 "Section 26 of the Land Act protects innocent purchasers, but not if the root title is void.",
                 "Fraudsters often create 'Air Subdivisions' that exist on maps but not on the ground.",
                 "Always verify the 'Mutation Form' before buying subdivided land."
             ]}

    except Exception as e:
        logger.exception("Titbits generation failed")
        # Fallback static titbits
        return {"titbits": [
             "Did you know? A Green Card is the only true proof of ownership, not the Title Deed.",
             "The 'Ndungu Report' listed thousands of illegally acquired public lands.",
             "Section 26 of the Land Act protects innocent purchasers, but not if the root title is void.",
             "Fraudsters often create 'Air Subdivisions' that exist on maps but not on the ground.",
             "Always verify the 'Mutation Form' before buying subdivided land."
        ]}
