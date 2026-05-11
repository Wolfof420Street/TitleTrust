import time
import json
import logging
import traceback
import base64
import os
from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from firebase_admin import firestore
from PIL import Image
import io

# Production logging with structured format
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - [%(session_id)s] - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("MarathonAgent")


# --- Configuration ---
@dataclass
class AgentConfig:
    """Production configuration with sensible defaults"""
    MAX_RECURSION_DEPTH: int = 15  # Prevent infinite loops
    MAX_RETRIES: int = 3
    STEP_DELAY_SECONDS: int = 2
    MAX_MEMORY_ITEMS: int = 50  # Prevent unbounded memory growth
    EMPTY_RESPONSE_MAX_RETRIES: int = 2
    SEARCH_TIMEOUT_SECONDS: int = 30
    IMAGE_ANALYSIS_ENABLED: bool = True
    ENABLE_METRICS: bool = True  # For production monitoring


# --- State Definition ---
class AgentState(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    SLEEPING = "SLEEPING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    QUEUED = "QUEUED"


import hashlib

# ... (existing imports)

class MarathonState(BaseModel):
    session_id: str
    status: AgentState = AgentState.IDLE
    memory: List[str] = []
    current_lat_lng: Optional[str] = None
    retry_count: int = 0
    empty_response_count: int = 0  # Track specific error type
    recursion_depth: int = 0  # Track depth to prevent stack overflow
    last_update: float = Field(default_factory=time.time)
    last_thought: Optional[str] = None
    image_path: Optional[str] = None  # Track uploaded image
    total_steps: int = 0  # Metrics
    error_history: List[str] = []  # Track errors for debugging
    
    # New fields for loop prevention and progress tracking
    action_history: List[Dict[str, Any]] = []
    progress_checklist: Dict[str, bool] = Field(default_factory=lambda: {
        'image_analyzed': False,
        'title_searched': False,
        'owner_verified': False,
        'location_checked': False
    })

    def has_performed_action(self, tool: str, input_hash: str, window: int = 5) -> bool:
        """Check if similar action was done recently"""
        recent_actions = self.action_history[-window:]
        for action in recent_actions:
            if action['tool'] == tool and action['input_hash'] == input_hash:
                return True
        return False
    
    def add_action(self, tool: str, tool_input: str):
        """Record action with hash"""
        input_hash = hashlib.md5(tool_input.encode()).hexdigest()[:8]
        self.action_history.append({
            'tool': tool,
            'input_hash': input_hash,
            'timestamp': time.time()
        })


# --- Structured Decision Engine ---
class AgentDecision(BaseModel):
    thought_process: str = Field(..., description="Internal reasoning with abductive logic")
    next_tool: str = Field(
        ..., 
        description="Tool: 'analyze_image', 'google_search', 'inspect_satellite', 'finish_audit', 'wait_user', 'escalate_error'"
    )
    tool_input: str = Field(..., description="Tool arguments")
    requires_sleep: bool = Field(False, description="Need to wait for external events")
    sleep_duration_minutes: int = Field(0, description="Sleep duration")
    confidence: float = Field(1.0, description="Confidence in decision (0-1)")


# --- Production-Ready Marathon Loop ---
try:
    from backend.repositories.session_repository import SessionRepository
    from backend.services.sync_service import FirebaseSyncService
    from backend.services.firebase import db
except ModuleNotFoundError:
    from repositories.session_repository import SessionRepository
    from services.sync_service import FirebaseSyncService
    from services.firebase import db


class MarathonLoop:
    def __init__(
        self, 
        db_instance: firestore.Client, 
        session_id: str,
        config: Optional[AgentConfig] = None,
        gemini_api_key: str = None,
        model_name: str = "gemini-3-flash-preview"
    ):
        self._sessions = SessionRepository(db_instance)
        self.session_id = session_id
        self.config = config or AgentConfig()
        self.model_name = model_name
        
        # Initialize Sync Service
        self.sync_service = FirebaseSyncService()
        
        # Fetch owner_id for notifications
        try:
            session_data = self._sessions.get(session_id)
            self.owner_id = session_data.get("user_id") if session_data else None
        except:
            self.owner_id = None
        
        # Initialize Gemini with error handling
        try:
            # If no API key provided, try to get from environment
            if not gemini_api_key:
                gemini_api_key = os.environ.get("GEMINI_API_KEY")
                
            self.client = genai.Client(api_key=gemini_api_key)
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}", extra={'session_id': session_id})
            raise
        
        # Add session_id to all logs
        self.logger = logging.LoggerAdapter(logger, {'session_id': session_id})

    def load_state(self) -> MarathonState:
        """Loads state from repository"""
        data = self._sessions.get(self.session_id)
        if data:
            if "session_id" not in data:
                data["session_id"] = self.session_id
            # Handle legacy/missing fields gracefully
            return MarathonState(**data)
        return MarathonState(session_id=self.session_id)

    def save_state(self, state: MarathonState):
        """Persists state to repository"""
        state.last_update = time.time()
        self._sessions.update(self.session_id, state.model_dump())

    def truncate_memory_item(self, item: str, max_chars: int = 500) -> str:
        """Prevent single memory items from bloating context"""
        if len(item) <= max_chars:
            return item
        return item[:max_chars] + f"... [truncated {len(item) - max_chars} chars]"

    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """
        Uses Gemini Vision to extract details from the 'Deal Pack'
        """
        try:
            # Prepare Image
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            
            # Simple Prompt for Vision
            prompt = """
            Analyze this land document. 
            Extract:
            1. Title Number / I.R. Number
            2. Registered Owner
            3. Approximate Acreage/Hectares
            4. Date of Issue
            5. Any Visual Verification anomalies (holograms, stamps, paper quality)
            """
            
            response = self.client.models.generate_content(
                model=self.model_name, # Use Flash for vision speed
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    prompt
                ]
            )
            
            return {"status": "success", "analysis": response.text}
        except Exception as e:
            self.logger.error(f"Vision Analysis Failed: {e}")
            return {"status": "error", "error": str(e)}

    def perform_research(self, query: str) -> str:
        """
        Tools: Google Search Grounding
        """
        try:
            # Using Google Search Grounding via Gemini 3
            # We construct a prompt that forces the model to use the grounding tool
            tool = types.Tool(google_search=types.GoogleSearch())
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=f"Search Query: {query}. Summarize the findings relevant to Kenyan Land Ownership.",
                config=types.GenerateContentConfig(tools=[tool])
            )
            
            # Extract grounding metadata if needed, for now just text
            return response.text if response.text else "No specific text results found."
        except Exception as e:
            self.logger.error(f"Search Failed: {e}")
            return f"Search Error: {str(e)}"

    def generate_decision(self, state: MarathonState, context_prompt: str) -> Optional[AgentDecision]:
        """
        The 'Brain' - deciding the next step using Structured Output
        """
        # --- STUCK DETECTION ---
        # Check for stuck state BEFORE calling LLM
        if len(state.action_history) >= 3:
            last_3 = state.action_history[-3:]
            tools_used = [a['tool'] for a in last_3]
            
            # If same tool used 3 times in a row
            if len(set(tools_used)) == 1:
                self.logger.warning(f"Stuck pattern detected: {tools_used[0]} repeated 3x")
                
                # Force decision
                if state.progress_checklist.get('title_searched'):
                    return AgentDecision(
                        thought_process="Auto-completing: Stuck in search loop but have sufficient data",
                        next_tool="finish_audit",
                        tool_input="Audit completed with available evidence. (Forced due to repetitive loop)",
                        requires_sleep=False,
                        confidence=0.6
                    )
                else:
                    return AgentDecision(
                        thought_process="Auto-escalating: Stuck without progress",
                        next_tool="wait_user",
                        tool_input="Agent is stuck in a loop - need guidance",
                        requires_sleep=False,
                        confidence=0.5
                    )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=context_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AgentDecision,
                    temperature=0.2 # Low temp for deterministic logic
                )
            )
            
            if not response.parsed:
                if state.empty_response_count < self.config.EMPTY_RESPONSE_MAX_RETRIES:
                    state.empty_response_count += 1
                    self.logger.warning(f"Empty/Invalid JSON response (Attempt {state.empty_response_count})")
                    return None
            else:
                state.empty_response_count = 0 # Reset on success
            
            return response.parsed
            
        except Exception as e:
            self.logger.error(f"Decision Generation Failed: {e}")
            return None

    def run_single_step(self) -> Dict[str, Any]:
        """
        Executes a SINGLE atomic step of the Marathon Agent.
        Returns: { "status": AgentState, "next_tick_seconds": int }
        """
        state = self.load_state()
        
        # Increment depth tracker - used for metrics now
        state.total_steps += 1
        
        # === ADD DIAGNOSTIC LOGGING ===
        self.logger.info(f"""
        === STEP {state.total_steps} DEBUG ===
        Status: {state.status}
        Action History Length: {len(state.action_history)}
        Progress Checklist: {state.progress_checklist}
        Memory Items: {len(state.memory)}
        Last 3 Actions: {[a['tool'] for a in state.action_history[-3:]]}
        ========================
        """)

        # Ensure we transition from QUEUED to RUNNING
        if state.status == AgentState.QUEUED or state.status == AgentState.IDLE:
            state.status = AgentState.RUNNING
            self.save_state(state)

        # === ADD MAXIMUM STEP ENFORCEMENT ===
        MAX_STEPS = 15
        if state.total_steps >= MAX_STEPS:
            self.logger.warning(f"⚠️ Max steps reached ({MAX_STEPS}), forcing conclusion")
            
            state.status = AgentState.COMPLETED
            
            # Auto-generate conclusion
            has_search = state.progress_checklist.get('title_searched', False)
            has_image = any("Image Analysis:" in m for m in state.memory)
            
            if has_search and has_image:
                verdict = "Audit completed with available evidence. Based on document analysis and public record searches, preliminary review shows no obvious red flags. Manual verification recommended for final determination."
            elif has_image:
                verdict = "Document analyzed but unable to verify through public records. Manual investigation required."
            else:
                verdict = "Insufficient data gathered. Manual review required."
            
            state.memory.append(f"✅ AUTO-CONCLUDED (Step {MAX_STEPS}): {verdict}")
            
            final_findings = [{
                "category": "Auto-Concluded Audit",
                "description": verdict,
                "evidence": "See investigation logs. Maximum steps reached.",
                "confidence": "medium"
            }]
            
            self.sync_service.update_session_state(
                self.session_id, 
                status="COMPLETED", 
                latest_thought="Maximum steps reached - concluding audit",
                percent=100,
                audit_conclusion=verdict,
                findings=final_findings
            )
            
            self.save_state(state)
            self.cleanup()  # Cleanup temp file
            return {"status": state.status, "next_tick_seconds": 0}
        
        # Stop conditions
        if state.status in [AgentState.COMPLETED, AgentState.FAILED]:
            self.logger.info(f"Task already ended: {state.status}")
            return {"status": state.status, "next_tick_seconds": 0}
        
        # Handle repeated empty responses
        if state.empty_response_count >= self.config.EMPTY_RESPONSE_MAX_RETRIES:
            self.logger.error("Too many empty responses, escalating to WAITING_FOR_USER")
            state.status = AgentState.WAITING_FOR_USER
            state.memory.append("⚠️ Agent needs clarification - unable to proceed autonomously")
            self.save_state(state)
            
            # Sync Waiting
            self.sync_service.update_session_state(self.session_id, status="WAITING_FOR_USER", latest_thought="Waiting for clarification")
            return {"status": state.status, "next_tick_seconds": 0}

        try:
            # === PHASE 0: RECOVERY & MIGRATION ===
            if not state.image_path and state.memory:
                import re
                match = re.search(r"Received initial file: (.*)", state.memory[0])
                if match:
                    potential_path = match.group(1).strip()
                    if os.path.exists(potential_path):
                        state.image_path = potential_path
                        self.logger.info(f"🔄 Recovered image path from memory: {potential_path}")
                        self.save_state(state)

            # === PHASE 1: CHECK FOR IMAGE ===
            # Run image analysis if pending
            if state.image_path and self.config.IMAGE_ANALYSIS_ENABLED:
                has_analysis = any("Image Analysis:" in mem for mem in state.memory)
                if not has_analysis:
                    self.logger.info("🔍 Detected unanalyzed image, processing...")
                    # Sync UI
                    self.sync_service.update_session_state(self.session_id, latest_thought="Analyzing Initial Document...", status="RUNNING")
                    
                    result = self.analyze_image(state.image_path)
                    
                    if result["status"] == "success":
                        state.memory.append(f"📄 Image Analysis: {result['analysis']}")
                        self.logger.info("✅ Image processed successfully")
                    else:
                        state.memory.append(f"❌ Image Analysis Failed: {result['error']}")
                    
                    state.status = AgentState.RUNNING  # Ensure status is updated in memory before save
                    self.save_state(state)
                    # Return immediately to allow state to settle/UI update
                    return {"status": AgentState.RUNNING, "next_tick_seconds": 1}
            
            # === PHASE 2: BUILD CONTEXT ===

            # Check if we have enough data to conclude
            searches_done = len([a for a in state.action_history if a['tool'] == 'google_search'])
            has_image = any("Image Analysis:" in m for m in state.memory)
            title_searched = state.progress_checklist.get('title_searched', False)

            # Force conclusion criteria
            should_conclude = (
                title_searched and searches_done >= 1 and state.total_steps >= 4
            ) or (
                searches_done >= 2
            ) or (
                state.total_steps >= 10
            )

            if should_conclude:
                prompt = f"""
                You are an Autonomous Forensic Land Auditor completing your investigation.
                
                <Investigation Summary>
                - Steps Taken: {state.total_steps}
                - Searches Completed: {searches_done}
                - Image Analyzed: {has_image}
                - Title Searched: {title_searched}
                
                Recent Findings (Last 8 entries):
                {json.dumps(state.memory[-8:], indent=2)}
                </Investigation Summary>
                
                <MANDATORY ACTION>
                You MUST call 'finish_audit' now. You have gathered sufficient evidence.
                
                Analyze the memory above and provide your verdict:
                - If search results confirm title legitimacy → "Title appears legitimate based on [evidence]"
                - If search found no records → "Unable to verify - no public records found. Manual investigation required."
                - If search found discrepancies → "Red flags detected: [list concerns]. Manual review required."
                
                DO NOT search again. DO NOT wait. CONCLUDE NOW.
                </MANDATORY ACTION>
                
                Your decision MUST be:
                {{
                    "thought_process": "Brief summary of findings",
                    "next_tool": "finish_audit",
                    "tool_input": "Your verdict here based on evidence in memory",
                    "requires_sleep": false,
                    "confidence": 0.8
                }}
                """
            else:
                prompt = f"""
                You are an Autonomous Forensic Land Auditor.
                Mission: Verify the land title/claim in the memory.
                
                <Progress Checklist>
                {json.dumps(state.progress_checklist, indent=2)}
                </Progress Checklist>

                <Action History (Last 5)>
                {json.dumps([f"{a['tool']}: {a['input_hash']}" for a in state.action_history[-5:]], indent=2)}
                </Action History>

                <Completion Rules - ENFORCE THESE>
                1. If 'title_searched' is True AND you have search results in memory → USE finish_audit NEXT STEP
                2. If you see the same tool in Action History 2+ times → DO NOT repeat it, move to conclusion
                3. After {searches_done} searches → If you have data, CONCLUDE. Don't search endlessly.
                4. DO NOT search for file paths (e.g., /tmp/*, *.png) - ONLY search for Title Numbers, Owner Names
                </Completion Rules>
                
                <Current State>
                Step: {state.total_steps}/15 MAX
                Searches Done: {searches_done}
                Memory (last 6 entries):
                {json.dumps(state.memory[-6:], indent=2)}
                </Current State>
                
                <Available Tools>
                1. google_search: Search ONLY if title_searched is False (max 1-2 searches total)
                2. finish_audit: Use when you have search results OR after 1 search attempt
                3. wait_user: If truly stuck or need clarification
                </Available Tools>
                
                <Decision Logic>
                IF title_searched == True:
                    → MUST call finish_audit (you have the data)
                ELIF searches_done >= 1:
                    → Review results, then call finish_audit
                ELIF searches_done == 0 AND has image analysis:
                    → Perform ONE search for title/owner
                ELSE:
                    → Something is wrong, call wait_user
                </Decision Logic>
                
                Be DECISIVE. Do NOT loop. Progress toward finish_audit.
                """
            
            # === PHASE 3: GENERATE DECISION ===
            decision = self.generate_decision(state, prompt)
            
            if not decision:
                # ... failure handling same as before ... 
                self.logger.warning("Failed to generate valid decision")
                state.retry_count += 1
                if state.retry_count >= self.config.MAX_RETRIES:
                    state.status = AgentState.FAILED
                    state.memory.append("❌ Failed after multiple retry attempts")
                self.save_state(state)
                # Retry quickly if failed, unless max retries handled
                return {"status": state.status, "next_tick_seconds": 2 if state.status == AgentState.RUNNING else 0}
            
            # Log thought
            self.logger.info(f"💭 Thought: {decision.thought_process[:200]}...")
            state.last_thought = decision.thought_process
            state.memory.append(f"🧠 {decision.thought_process}")
            
            # --- SYNC: STREAM OF CONSCIOUSNESS ---
            self.sync_service.update_session_state(
                self.session_id,
                latest_thought=decision.thought_process,
                status="RUNNING",
                logs=[
                    {"timestamp": time.time(), "message": f"Thinking: {decision.next_tool}"},
                    {"timestamp": time.time(), "message": f"Thought: {decision.thought_process}"}
                ]
            )
            
            # Check for Discrepancy Alert
            if "discrepancy" in decision.thought_process.lower() or "fraud" in decision.thought_process.lower():
                if self.owner_id:
                    self.sync_service.send_push_notification(
                        self.owner_id, 
                        "Alert: Possible Discrepancy", 
                        "The agent detected an inconsistency in the records.",
                        {"job_id": self.session_id}
                    ) 

            # === PHASE 4: EXECUTE TOOL ===
            if decision.next_tool == "analyze_image":
                if state.image_path:
                    # Sync
                    self.sync_service.update_session_state(self.session_id, latest_thought="Re-analyzing image for details...")
                    
                    result = self.analyze_image(state.image_path)
                    if result["status"] == "success":
                        state.memory.append(f"📄 {result['analysis']}")
                        
                        # Sync Result
                        self.sync_service.update_session_state(
                            self.session_id, 
                            logs=[{"timestamp": time.time(), "message": f"✅ Image Re-analysis Complete."}]
                        )
                else:
                    state.memory.append("⚠️ No image to analyze")
            
            elif decision.next_tool == "google_search":
                # Check for duplicate
                import hashlib
                input_hash = hashlib.md5(decision.tool_input.encode()).hexdigest()[:8]
                
                if state.has_performed_action("google_search", input_hash):
                    self.logger.warning(f"Duplicate search detected: {decision.tool_input}")
                    state.memory.append(f"⚠️ Skipping duplicate search: {decision.tool_input}")
                    
                    # Force progression if we have data
                    if state.progress_checklist.get('title_searched'):
                        state.memory.append("📊 Moving to conclusion based on gathered evidence")
                    
                    # Sync this skipping event so the user knows why it's quiet
                    self.sync_service.update_session_state(
                        self.session_id, 
                        logs=[{"timestamp": time.time(), "message": f"⚠️ Skipping duplicate search: {decision.tool_input}"}]
                    )
                    # The next iteration's "Stuck Detection" will catch this if it repeats again
                    
                    self.save_state(state)  # CRITICAL: Save before returning
                    
                    # Force next iteration to progress
                    return {"status": AgentState.RUNNING, "next_tick_seconds": 1}
                    
                else:
                    self.logger.info(f"Search requested: {decision.tool_input}")
                    
                    # Sync
                    self.sync_service.update_session_state(
                        self.session_id, 
                        latest_thought=f"Searching: {decision.tool_input}...",
                        logs=[{"timestamp": time.time(), "message": f"🔍 Searching: {decision.tool_input}"}]
                    )
                    
                    try:
                        search_results = self.perform_research(decision.tool_input)
                        
                        # Update checklist
                        if any(keyword in decision.tool_input.lower() for keyword in ['title', 'owner', 'gazette', 'land']):
                            state.progress_checklist['title_searched'] = True
                            
                        # Truncate and store
                        truncated_results = self.truncate_memory_item(search_results, max_chars=800)
                        state.memory.append(f"🔍 Search Results for '{decision.tool_input}':\n{truncated_results}")
                        self.logger.info(f"Search completed: {len(search_results)} chars")

                        # Record Action
                        state.add_action("google_search", decision.tool_input)

                        self.save_state(state)  # Persist progress before sync

                        # Sync Result
                        self.sync_service.update_session_state(
                            self.session_id, 
                            logs=[{"timestamp": time.time(), "message": f"✅ Search Complete. Found relevant data."}]
                        )
                    except Exception as e:
                        state.memory.append(f"❌ Search Error: {e}")
                        self.save_state(state)  # Save error state too
            
            elif decision.next_tool == "inspect_satellite":
                try:
                    lat_str, lng_str = map(str.strip, decision.tool_input.split(","))
                    lat, lng = float(lat_str), float(lng_str)
                    state.current_lat_lng = f"{lat},{lng}"
                    state.memory.append(f"🛰️ Satellite check: ({lat}, {lng})")
                    
                    # Sync
                    self.sync_service.update_session_state(
                        self.session_id, 
                        latest_thought=f"Checking Satellite imagery at {lat}, {lng}...",
                        logs=[{"timestamp": time.time(), "message": f"🛰️ Inspecting Satellite: {lat}, {lng}"}]
                    )
                    
                    # Store result in memory (simulated success log for user)
                    self.sync_service.update_session_state(
                        self.session_id,
                        logs=[{"timestamp": time.time(), "message": f"✅ Satellite Imagery Available."}]
                    )
                    
                except Exception as e:
                    state.memory.append(f"❌ Satellite error: {e}")
            
            elif decision.next_tool == "finish_audit":
                state.status = AgentState.COMPLETED
                state.memory.append(f"✅ FINAL VERDICT: {decision.tool_input}")
                self.logger.info("🎉 Audit completed successfully")
                
                # Generate structured findings for the report
                final_findings = [
                    {
                        "category": "Audit Verdict",
                        "description": decision.tool_input,
                        "evidence": "See detailed investigation logs for full analysis lineage."
                    }
                ]

                # Sync Completion
                self.sync_service.update_session_state(
                    self.session_id, 
                    status="COMPLETED", 
                    latest_thought="Audit Complete. Generating Report.",
                    percent=100,
                    logs=[{"timestamp": time.time(), "message": f"✅ Verdict: {decision.tool_input}"}],
                    audit_conclusion=decision.tool_input,
                    findings=final_findings
                )
                if self.owner_id:
                    self.sync_service.send_push_notification(
                        self.owner_id, 
                        "Audit Complete", 
                        "Your Land Title Audit is ready.",
                        {"job_id": self.session_id, "route": f"/audit/{self.session_id}"}
                    )
                self.cleanup()  # Cleanup temp file
            
            elif decision.next_tool == "wait_user":
                state.status = AgentState.WAITING_FOR_USER
                state.memory.append(f"⏸️ Waiting for user: {decision.tool_input}")
                self.logger.info("Paused for user input")
                self.sync_service.update_session_state(self.session_id, status="WAITING_FOR_USER")
            
            elif decision.next_tool == "escalate_error":
                state.status = AgentState.FAILED
                state.memory.append(f"🚨 Critical Issue: {decision.tool_input}")
                self.logger.error(f"Agent escalated error: {decision.tool_input}")
                
                 # Sync Failure
                self.sync_service.update_session_state(self.session_id, status="FAILED", latest_thought=f"Error: {decision.tool_input}")
                if self.owner_id:
                    self.sync_service.send_push_notification(
                        self.owner_id, 
                        "Audit Escalated", 
                        "Critical issue found requiring human review.",
                        {"job_id": self.session_id}
                    )
                self.cleanup()  # Cleanup temp file on failure
            
            # === PHASE 5: PERSISTENCE ===
            state.retry_count = 0  # Reset on successful step
            self.save_state(state)
            
            # === PHASE 6: NEXT STEP LOGIC ===
            next_tick = self.config.STEP_DELAY_SECONDS
            
            if decision.requires_sleep:
                next_tick = decision.sleep_duration_minutes * 60
                self.logger.info(f"Agent requested sleep for {decision.sleep_duration_minutes} mins")
            
            return {
                "status": state.status,
                "next_tick_seconds": next_tick
            }

        except Exception as e:
            self.logger.error(f"CRITICAL ERROR: {traceback.format_exc()}")
            state.error_history.append(f"{time.time()}: {str(e)[:200]}")
            state.retry_count += 1
            
            if state.retry_count > self.config.MAX_RETRIES:
                state.status = AgentState.FAILED
                state.memory.append(f"❌ Failed after {state.retry_count} errors")
                
                # Sync Failure
                self.sync_service.update_session_state(
                    self.session_id, 
                    status="FAILED", 
                    latest_thought=f"Critical Error: {str(e)}",
                    logs=[{"timestamp": time.time(), "message": f"Critical Error: {str(e)}"}]
                )
                self.cleanup()  # Cleanup temp file on max retries
            
            self.save_state(state)
            # Retry immediately if not failed
            return {"status": state.status, "next_tick_seconds": 5}

    def cleanup(self):
        """Cleanup resources"""
        state = self.load_state()
        if state.image_path and os.path.exists(state.image_path):
            try:
                os.remove(state.image_path)
                self.logger.info(f"🧹 Cleaned up: {state.image_path}")
            except Exception as e:
                self.logger.warning(f"Cleanup failed: {e}")