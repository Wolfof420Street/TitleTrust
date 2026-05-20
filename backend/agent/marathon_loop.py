import time
import json
import logging
import traceback
import os
import re
import uuid
from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from firebase_admin import firestore
from google.api_core.exceptions import DeadlineExceeded, NotFound, PermissionDenied, ServiceUnavailable

# Production logging with structured format
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - [%(session_id)s] - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("MarathonAgent")
MAX_SEARCH_TEXT_LEN = 10_000


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
    FLAGGED = "FLAGGED"
    FAILED = "FAILED"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    QUEUED = "QUEUED"


import hashlib

# ... (existing imports)

class MarathonState(BaseModel):
    session_id: str
    status: AgentState = AgentState.IDLE
    memory: List[str] = Field(default_factory=list)
    current_lat_lng: Optional[str] = None
    retry_count: int = 0
    empty_response_count: int = 0  # Track specific error type
    recursion_depth: int = 0  # Track depth to prevent stack overflow
    last_update: float = Field(default_factory=time.time)
    last_thought: Optional[str] = None
    image_uri: Optional[str] = None
    image_mime_type: Optional[str] = None
    source_filename: Optional[str] = None
    total_steps: int = 0  # Metrics
    error_history: List[str] = Field(default_factory=list)  # Track errors for debugging
    verification_evidence: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    evidence_backed_flags: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    
    # New fields for loop prevention and progress tracking
    action_history: List[Dict[str, Any]] = Field(default_factory=list)
    progress_checklist: Dict[str, bool] = Field(default_factory=lambda: {
        'image_analyzed': False,
        'title_searched': False,
        'physical_boundary_verified': False,
        'additional_records_checked': False,
        'zoning_checked': False,
        'historical_chain_checked': False,
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

    @staticmethod
    def _is_valid_sha256(value: str) -> bool:
        return bool(re.fullmatch(r"[a-fA-F0-9]{64}", value or ""))

    @staticmethod
    def _is_valid_trace_id(value: str) -> bool:
        return bool(value and len(value.strip()) >= 8)

    def register_evidence(
        self,
        check_name: str,
        *,
        provider: str,
        trace_id: str,
        sha256: str,
        summary: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self._is_valid_trace_id(trace_id) or not self._is_valid_sha256(sha256):
            raise ValueError(f"Evidence for {check_name} is missing a valid trace_id or sha256")
        self.verification_evidence[check_name] = {
            "provider": provider,
            "trace_id": trace_id,
            "sha256": sha256,
            "summary": summary,
            "metadata": metadata or {},
            "timestamp": time.time(),
        }
        self.evidence_backed_flags[check_name] = {
            "trace_id": trace_id,
            "sha256": sha256,
            "provider": provider,
        }
        self.progress_checklist[check_name] = True
        # Emit realtime evidence_registration event (best-effort async)
        try:
            import asyncio
            from backend.realtime.events import emit

            payload = {
                "check_name": check_name,
                "provider": provider,
                "trace_id": trace_id,
                "sha256": sha256,
                "summary": summary,
                "metadata": metadata or {},
            }
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(emit("agent.evidence_registered", payload, session_id=self.session_id, severity="info"))
            except RuntimeError:
                import threading

                def _bg():
                    import asyncio as _asyncio
                    from backend.realtime.events import emit as _emit

                    try:
                        _asyncio.run(_emit("agent.evidence_registered", payload, session_id=self.session_id, severity="info"))
                    except Exception:
                        pass

                threading.Thread(target=_bg, daemon=True).start()
        except Exception:
            pass

    def has_verified_check(self, check_name: str) -> bool:
        artifact = self.verification_evidence.get(check_name) or {}
        return bool(artifact.get("trace_id") and artifact.get("sha256"))


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
    from backend.agent.tools import (
        build_record_search_queries,
        inspect_physical_boundaries,
        parse_kenyan_coordinates,
        validate_title_syntax,
    )
    from backend.services.cloud_storage_service import cloud_storage_service
    from backend.services.sync_service import FirebaseSyncService
    from backend.services.firebase import db
except ModuleNotFoundError:
    from repositories.session_repository import SessionRepository
    from agent.tools import (
        build_record_search_queries,
        inspect_physical_boundaries,
        parse_kenyan_coordinates,
        validate_title_syntax,
    )
    from services.cloud_storage_service import cloud_storage_service
    from services.sync_service import FirebaseSyncService
    from services.firebase import db


class SourceDocumentAccessError(Exception):
    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


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

    def analyze_image(self, image_uri: str, mime_type: str) -> Dict[str, Any]:
        """
        Uses Gemini Vision to extract details from the source document in Cloud Storage.
        """
        try:
            metadata = cloud_storage_service.stat_object(image_uri)
            self.logger.info(
                "Validated source document from cloud storage",
                extra={"session_id": self.session_id, "gcs_latency_ms": metadata["latency_ms"]},
            )
            
            # Simple Prompt for Vision
            prompt = """
            Analyze this land document. 
            Extract:
            1. Title Number / I.R. Number
            2. Registered Owner
            3. Approximate Acreage/Hectares
            4. Date of Issue
            5. Any Visual Verification anomalies (holograms, stamps, paper quality)
            6. Any coordinates in Decimal Degrees or UTM notation
            7. Stated land use, parcel description, county, and any Registry Index Map / survey references
            """
            
            response = self.client.models.generate_content(
                model=self.model_name, # Use Flash for vision speed
                contents=[
                    types.Part.from_uri(file_uri=image_uri, mime_type=mime_type),
                    prompt
                ]
            )
            self._log_usage("analyze_image", response)
            analysis_text = response.text or ""
            return {
                "status": "success",
                "analysis": analysis_text,
                "provider": "gemini_vision",
                "trace_id": self._new_trace_id("vision"),
                "evidence_sha256": self._hash_payload({"image_uri": image_uri, "analysis": analysis_text}),
            }
        except NotFound as exc:
            raise SourceDocumentAccessError(
                "The uploaded document could not be found in cloud storage. Please upload it again."
            ) from exc
        except PermissionDenied as exc:
            raise SourceDocumentAccessError(
                "The uploaded document could not be accessed due to a storage permission error."
            ) from exc
        except (DeadlineExceeded, ServiceUnavailable) as exc:
            raise SourceDocumentAccessError(
                "The uploaded document could not be read from cloud storage right now. Please try again."
            ) from exc
        except Exception as e:
            self.logger.error(f"Vision Analysis Failed: {e}")
            return {"status": "error", "error": str(e)}

    def perform_research(self, query: str) -> Dict[str, Any]:
        """
        Tools: Google Search Grounding
        """
        try:
            # Using Google Search Grounding via Gemini 3
            # We construct a prompt that forces the model to use the grounding tool
            tool = types.Tool(google_search=types.GoogleSearch())
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=(
                    f"Search Query: {query}. "
                    "Prioritize official or highly relevant Kenyan land-record evidence, especially "
                    "National Land Commission references, Kenya Gazette notices, Land Registration Act 2012 conversion context, "
                    "county zoning/planning records, and ownership continuity. "
                    "State clearly if no such evidence is found."
                ),
                config=types.GenerateContentConfig(tools=[tool])
            )
            text = response.text if response.text else "No specific text results found."
            text = text[:MAX_SEARCH_TEXT_LEN]
            self._log_usage("google_search", response, text_preview=text)
            return {
                "status": "success",
                "provider": "gemini_google_search",
                "query": query,
                "text": text,
                "trace_id": self._new_trace_id("search"),
                "evidence_sha256": self._hash_payload({"query": query, "text": text}),
            }
        except Exception as e:
            self.logger.error(f"Search Failed: {e}")
            return {
                "status": "error",
                "provider": "gemini_google_search",
                "query": query,
                "text": f"Search Error: {str(e)}",
            }

    def _log_usage(self, operation: str, response: Any, text_preview: Optional[str] = None) -> None:
        usage = getattr(response, "usage_metadata", None)
        if not usage:
            return
        self.logger.info(
            "Gemini usage",
            extra={
                "session_id": self.session_id,
                "operation": operation,
                "prompt_tokens": getattr(usage, "prompt_token_count", None),
                "candidates_tokens": getattr(usage, "candidates_token_count", None),
                "total_tokens": getattr(usage, "total_token_count", None),
                "text_preview_len": len(text_preview or ""),
            },
        )

    @staticmethod
    def _hash_payload(payload: Any) -> str:
        canonical = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _new_trace_id(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _contains_any(text: str, keywords: List[str]) -> bool:
        lowered = text.lower()
        return any(keyword in lowered for keyword in keywords)

    def _record_finding(
        self,
        state: MarathonState,
        *,
        category: str,
        severity: str,
        description: str,
        evidence: str,
        risk_code: Optional[str] = None,
    ) -> None:
        finding = {
            "category": category,
            "severity": severity,
            "description": description,
            "evidence": evidence,
        }
        if risk_code:
            finding["risk_code"] = risk_code
        state.findings.append(finding)

    def _sync_findings(self, state: MarathonState) -> None:
        self.sync_service.update_session_state(
            self.session_id,
            findings=state.findings,
        )

    def _enter_waiting_for_manual_pin(self, state: MarathonState, reason: str) -> Dict[str, Any]:
        state.status = AgentState.WAITING_FOR_USER
        message = (
            "A manual parcel location pin is required before physical boundary verification can continue. "
            f"{reason}"
        )
        state.memory.append(f"⚠️ {message}")
        self.sync_service.update_session_state(
            self.session_id,
            status="WAITING_FOR_USER",
            latest_thought=message,
            logs=[{"timestamp": time.time(), "message": message}],
        )
        self.save_state(state)
        return {"status": state.status, "next_tick_seconds": 0}

    def _fail_legal_dispute(self, state: MarathonState, evidence: str) -> Dict[str, Any]:
        state.status = AgentState.FAILED
        description = "LEGAL_DISPUTE_DETECTED: Gazette or registry records indicate the parcel is disputed."
        self._record_finding(
            state,
            category="Additional Records",
            severity="HIGH",
            description=description,
            evidence=evidence,
            risk_code="LEGAL_DISPUTE_DETECTED",
        )
        state.memory.append(f"🚨 {description}")
        self.sync_service.update_session_state(
            self.session_id,
            status="FAILED",
            latest_thought=description,
            audit_conclusion=description,
            findings=state.findings,
            logs=[{"timestamp": time.time(), "message": description}],
        )
        self.save_state(state)
        return {"status": state.status, "next_tick_seconds": 0}

    def _compose_final_conclusion(self, state: MarathonState, model_summary: str) -> str:
        findings = sorted(
            state.findings,
            key=lambda item: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(str(item.get("severity", "LOW")).upper(), 3),
        )
        encroachment = next(
            (item for item in findings if "encroach" in item.get("description", "").lower() or "encroach" in item.get("evidence", "").lower()),
            None,
        )
        conversion = next(
            (item for item in findings if item.get("risk_code") == "CONVERSION_STATUS_UNVERIFIED"),
            None,
        )
        lead = encroachment or (findings[0] if findings else None)
        if lead:
            conclusion = f"Primary risk: {lead['description']} Evidence: {lead['evidence']}"
            if conversion and conversion is not lead:
                conclusion += f" Additional risk: {conversion['description']} Evidence: {conversion['evidence']}"
            return f"{conclusion} Supporting synthesis: {model_summary}"
        return model_summary

    def _extract_case_context(self, state: MarathonState) -> Dict[str, Optional[str]]:
        joined = "\n".join(state.memory[-12:])
        title_match = re.search(r"(I\.R\.?\s?\d+|C\.R\.?\s?\d+|L\.R\.?\s?NO\.?\s?\d+(?:\/\d+)?|[A-Z\s]+\/[A-Z\s]+\/\d+)", joined, re.IGNORECASE)
        owner_match = re.search(r"(?:Registered Owner|Owner)\s*[:\-]\s*([A-Z][A-Z\s'.-]{3,})", joined, re.IGNORECASE)
        land_use_match = re.search(r"(?:land use|use|property type)\s*[:\-]\s*([A-Z][A-Z\s/-]{3,})", joined, re.IGNORECASE)
        county_match = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+County", joined)
        coord = parse_kenyan_coordinates(joined)
        return {
            "title_number": title_match.group(1).strip() if title_match else None,
            "owner_name": owner_match.group(1).strip() if owner_match else None,
            "expected_land_use": land_use_match.group(1).strip() if land_use_match else None,
            "county": county_match.group(1).strip() if county_match else None,
            "lat": str(coord.get("lat")) if "lat" in coord else None,
            "lng": str(coord.get("lng")) if "lng" in coord else None,
            "coordinate_format": str(coord.get("format")) if coord.get("format") else None,
            "coordinate_error": str(coord.get("error")) if coord.get("error") else None,
        }

    def _run_step5_record_checks(self, state: MarathonState, context: Dict[str, Optional[str]]) -> Optional[Dict[str, Any]]:
        title_number = context.get("title_number")
        if not title_number:
            raise SourceDocumentAccessError(
                "The deed analysis did not produce a valid title number, so mandatory records checks cannot continue."
            )

        queries = build_record_search_queries(
            title_number=title_number,
            owner_name=context.get("owner_name"),
            county=context.get("county"),
        )
        combined_results: List[str] = []
        evidence_hashes: List[str] = []
        trace_ids: List[str] = []
        zoning_evidence: Optional[Dict[str, Any]] = None
        continuity_evidence: Optional[Dict[str, Any]] = None
        conversion_risk_detected = False
        for query in queries:
            result = self.perform_research(query)
            if result.get("status") != "success" or not result.get("trace_id") or not result.get("evidence_sha256"):
                state.memory.append(f"❌ Step 5 query failed without verifiable evidence: {query}")
                return None

            result_text = str(result["text"])
            combined_results.append(f"Query: {query}\nTrace: {result['trace_id']}\nResult: {result_text}")
            evidence_hashes.append(str(result["evidence_sha256"]))
            trace_ids.append(str(result["trace_id"]))
            state.add_action("google_search", query)

            lower_query = query.lower()
            lower_text = result_text.lower()
            if "gazette" in lower_query and self._contains_any(lower_text, ["disputed", "dispute", "court order", "injunction", "restriction"]):
                return self._fail_legal_dispute(state, result_text)
            if self._contains_any(lower_text, ["undergoing conversion", "old register", "converted from", "conversion pending"]):
                conversion_risk_detected = True
            if "zoning" in lower_query or "physical planning" in lower_query:
                zoning_evidence = result

        state.memory.append("🔍 Step 5 Additional Records:\n" + "\n\n".join(combined_results))
        state.register_evidence(
            "title_searched",
            provider="gemini_google_search",
            trace_id="|".join(trace_ids),
            sha256=self._hash_payload(evidence_hashes),
            summary="Mandatory Step 5 title searches completed.",
        )
        state.register_evidence(
            "additional_records_checked",
            provider="gemini_google_search",
            trace_id="|".join(trace_ids),
            sha256=self._hash_payload(evidence_hashes + [title_number]),
            summary="National Land Commission, Gazette, conversion, zoning, and ownership search chain completed.",
        )
        if zoning_evidence:
            state.register_evidence(
                "zoning_checked",
                provider=str(zoning_evidence["provider"]),
                trace_id=str(zoning_evidence["trace_id"]),
                sha256=str(zoning_evidence["evidence_sha256"]),
                summary="County zoning and physical planning query completed.",
            )

        lower_blob = "\n".join(combined_results).lower()
        if any(keyword in lower_blob for keyword in ["conversion", "converted from", "old registry", "green card", "new registry"]):
            continuity_query = f'"{title_number}" previous owner chain conversion history Land Registration Act 2012 Kenya'
            continuity_result = self.perform_research(continuity_query)
            if continuity_result.get("status") != "success" or not continuity_result.get("trace_id") or not continuity_result.get("evidence_sha256"):
                state.memory.append(f"❌ Historical continuity verification failed without evidence: {continuity_query}")
                return None
            continuity_evidence = continuity_result
            state.memory.append(
                f"📚 Historical Continuity Trace:\nQuery: {continuity_query}\nTrace: {continuity_result['trace_id']}\nResult: {continuity_result['text']}"
            )
            state.add_action("google_search", continuity_query)
            state.register_evidence(
                "historical_chain_checked",
                provider=str(continuity_result["provider"]),
                trace_id=str(continuity_result["trace_id"]),
                sha256=str(continuity_result["evidence_sha256"]),
                summary="Historical continuity and conversion trail query completed.",
            )
        else:
            state.register_evidence(
                "historical_chain_checked",
                provider="gemini_google_search",
                trace_id="|".join(trace_ids),
                sha256=self._hash_payload({"title_number": title_number, "evidence_hashes": evidence_hashes}),
                summary="Combined Step 5 searches found no conversion-triggered continuity gap.",
            )

        if conversion_risk_detected:
            continuity_text = str((continuity_evidence or {}).get("text", "")).lower()
            if not self._contains_any(continuity_text, ["green card", "new register", "official register extract", "updated register"]):
                self._record_finding(
                    state,
                    category="Additional Records",
                    severity="MEDIUM",
                    description="Title appears to be undergoing Land Registration Act 2012 conversion or still references an old register.",
                    evidence=(continuity_evidence or {}).get("text", "Conversion-related search results did not verify a new register trail."),
                    risk_code="CONVERSION_STATUS_UNVERIFIED",
                )

        return None

    def _flag_session(self, state: MarathonState, description: str, evidence: str) -> Dict[str, Any]:
        state.status = AgentState.FLAGGED
        self._record_finding(
            state,
            category="Physical Boundary Verification",
            severity="HIGH",
            description=description,
            evidence=evidence,
        )
        state.memory.append(f"🚩 HIGH SEVERITY FLAG: {description}")
        self.sync_service.update_session_state(
            self.session_id,
            status="FLAGGED",
            latest_thought=description,
            findings=state.findings,
            audit_conclusion=description,
            logs=[{"timestamp": time.time(), "message": f"🚩 {description}"}],
        )
        self.save_state(state)
        return {"status": state.status, "next_tick_seconds": 0}

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
                mandatory_checks_complete = (
                    state.has_verified_check("title_searched")
                    and state.has_verified_check("physical_boundary_verified")
                    and state.has_verified_check("additional_records_checked")
                    and state.has_verified_check("zoning_checked")
                    and state.has_verified_check("historical_chain_checked")
                )
                if mandatory_checks_complete:
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
            self._log_usage("decision", response)
            
            if not response.parsed:
                if state.empty_response_count < self.config.EMPTY_RESPONSE_MAX_RETRIES:
                    state.empty_response_count += 1
                    self.logger.warning(f"Empty/Invalid JSON response (Attempt {state.empty_response_count})")
                    return None
            else:
                state.empty_response_count = 0 # Reset on success
            
            # Emit decision and selected tool for real-time UI
            try:
                import asyncio
                from backend.realtime.events import emit

                decision = response.parsed
                payload = {
                    "thought_process": getattr(decision, 'thought_process', None),
                    "next_tool": getattr(decision, 'next_tool', None),
                    "tool_input": getattr(decision, 'tool_input', None),
                    "confidence": getattr(decision, 'confidence', None),
                }
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(emit("agent.tool_selected", payload, session_id=state.session_id))
                except RuntimeError:
                    import threading

                    def _bg_dec():
                        import asyncio as _asyncio
                        from backend.realtime.events import emit as _emit
                        try:
                            _asyncio.run(_emit("agent.tool_selected", payload, session_id=state.session_id))
                        except Exception:
                            pass

                    threading.Thread(target=_bg_dec, daemon=True).start()
            except Exception:
                pass

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
            self.logger.warning(f"⚠️ Max steps reached ({MAX_STEPS}), evaluating mandatory-check completion")
            mandatory_checks_complete = (
                state.has_verified_check("image_analyzed")
                and state.has_verified_check("physical_boundary_verified")
                and state.has_verified_check("additional_records_checked")
                and state.has_verified_check("zoning_checked")
                and state.has_verified_check("historical_chain_checked")
            )

            if mandatory_checks_complete:
                state.status = AgentState.COMPLETED
                verdict = (
                    "Audit completed with available evidence after exhausting the maximum step budget. "
                    "Step 4 and Step 5 mandatory checks were completed before conclusion."
                )
                state.memory.append(f"✅ AUTO-CONCLUDED (Step {MAX_STEPS}): {verdict}")
                final_findings = [{
                    "category": "Auto-Concluded Audit",
                    "description": verdict,
                    "evidence": "See investigation logs. Maximum steps reached after mandatory verification.",
                    "confidence": "medium"
                }]
                state.findings = final_findings
                self.sync_service.update_session_state(
                    self.session_id,
                    status="COMPLETED",
                    latest_thought="Maximum steps reached after mandatory verification - concluding audit",
                    percent=100,
                    audit_conclusion=verdict,
                    findings=final_findings
                )
            else:
                state.status = AgentState.WAITING_FOR_USER
                missing_checks = [
                    key for key, done in state.progress_checklist.items()
                    if key in {"physical_boundary_verified", "additional_records_checked", "zoning_checked", "historical_chain_checked"} and not done
                ]
                verdict = (
                    "The audit stopped before mandatory Kenyan verification steps were completed. "
                    f"Outstanding checks: {', '.join(missing_checks)}."
                )
                state.memory.append(f"⏸️ STEP BUDGET EXHAUSTED: {verdict}")
                self.sync_service.update_session_state(
                    self.session_id,
                    status="WAITING_FOR_USER",
                    latest_thought=verdict,
                    logs=[{"timestamp": time.time(), "message": verdict}],
                )

            self.save_state(state)
            return {"status": state.status, "next_tick_seconds": 0}
        
        # Stop conditions
        if state.status in [AgentState.COMPLETED, AgentState.FLAGGED, AgentState.FAILED]:
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
            # === PHASE 1: CHECK FOR IMAGE ===
            # Run image analysis if pending
            if state.image_uri and self.config.IMAGE_ANALYSIS_ENABLED:
                has_analysis = any("Image Analysis:" in mem for mem in state.memory)
                if not has_analysis:
                    self.logger.info("🔍 Detected unanalyzed cloud document, processing...")
                    # Sync UI
                    self.sync_service.update_session_state(self.session_id, latest_thought="Analyzing Initial Document...", status="RUNNING")
                    
                    result = self.analyze_image(
                        state.image_uri,
                        state.image_mime_type or "application/octet-stream",
                    )
                    
                    if result["status"] == "success":
                        state.memory.append(f"📄 Image Analysis: {result['analysis']}")
                        self.logger.info("✅ Image processed successfully")
                        if result.get("trace_id") and result.get("evidence_sha256"):
                            state.register_evidence(
                                "image_analyzed",
                                provider=str(result.get("provider", "gemini_vision")),
                                trace_id=str(result["trace_id"]),
                                sha256=str(result["evidence_sha256"]),
                                summary="Initial source document analysis completed.",
                                metadata={"image_uri": state.image_uri},
                            )
                        else:
                            state.memory.append("❌ Image analysis lacked provenance and could not mark the step complete.")
                    else:
                        state.memory.append(f"❌ Image Analysis Failed: {result['error']}")
                    
                    state.status = AgentState.RUNNING  # Ensure status is updated in memory before save
                    if result["status"] != "success":
                        state.progress_checklist["image_analyzed"] = False
                    self.save_state(state)
                    # Return immediately to allow state to settle/UI update
                    return {"status": AgentState.RUNNING, "next_tick_seconds": 1}

            context = self._extract_case_context(state)
            if context.get("title_number"):
                validation = validate_title_syntax(context["title_number"])
                state.memory.append(f"🧾 Title Syntax Validation: {validation}")

            if (
                state.progress_checklist.get("image_analyzed")
                and not state.progress_checklist.get("physical_boundary_verified")
            ):
                if context.get("coordinate_error"):
                    return self._enter_waiting_for_manual_pin(
                        state,
                        f"Step 4 coordinate parsing failed: {context['coordinate_error']}",
                    )

                if not context.get("lat") or not context.get("lng"):
                    return self._enter_waiting_for_manual_pin(
                        state,
                        "Step 4 requires coordinates or a RIM reference; none were extracted from the deed.",
                    )

                boundary_result = inspect_physical_boundaries(
                    float(context["lat"]),
                    float(context["lng"]),
                    title_context="\n".join(state.memory[-8:]),
                    expected_land_use=context.get("expected_land_use"),
                )
                state.current_lat_lng = f'{context["lat"]},{context["lng"]}'
                state.memory.append(f"🛰️ Step 4 Boundary Verification: {json.dumps(boundary_result)}")
                state.progress_checklist["location_checked"] = True
                if boundary_result.get("status") != "success" or not boundary_result.get("trace_id") or not boundary_result.get("evidence_sha256"):
                    state.memory.append("❌ Step 4 boundary verification did not return valid provenance.")
                    self.save_state(state)
                    return {"status": AgentState.RUNNING, "next_tick_seconds": 1}

                state.register_evidence(
                    "physical_boundary_verified",
                    provider=str(boundary_result.get("provider", "gemini_vision")),
                    trace_id=str(boundary_result["trace_id"]),
                    sha256=str(boundary_result["evidence_sha256"]),
                    summary="Satellite boundary verification completed with provenance.",
                    metadata={"lat": context.get("lat"), "lng": context.get("lng")},
                )
                self.save_state(state)

                if boundary_result.get("discrepancy_detected") and boundary_result.get("severity") == "HIGH":
                    return self._flag_session(
                        state,
                        "Physical boundary verification detected a high-severity discrepancy between the deed and observed occupation.",
                        boundary_result.get("reasoning", "Satellite boundary analysis reported a contradiction."),
                    )
                return {"status": AgentState.RUNNING, "next_tick_seconds": 1}

            if (
                state.progress_checklist.get("physical_boundary_verified")
                and not state.progress_checklist.get("additional_records_checked")
            ):
                step5_result = self._run_step5_record_checks(state, context)
                self.save_state(state)
                if step5_result:
                    return step5_result
                return {"status": AgentState.RUNNING, "next_tick_seconds": 1}
            
            # === PHASE 2: BUILD CONTEXT ===

            # Check if we have enough data to conclude
            searches_done = len([a for a in state.action_history if a['tool'] == 'google_search'])
            has_image = any("Image Analysis:" in m for m in state.memory)
            title_searched = state.progress_checklist.get('title_searched', False)

            # Force conclusion criteria
            should_conclude = (
                title_searched
                and state.progress_checklist.get("physical_boundary_verified")
                and state.progress_checklist.get("additional_records_checked")
                and state.progress_checklist.get("historical_chain_checked")
                and state.progress_checklist.get("zoning_checked")
                and searches_done >= 1
                and state.total_steps >= 4
            ) or (
                searches_done >= 4
                and state.progress_checklist.get("physical_boundary_verified")
                and state.progress_checklist.get("zoning_checked")
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
                You MUST call 'finish_audit' now only because Step 4 Physical Boundary Verification and Step 5 Additional Records were already executed.
                
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
                Mission: Verify the land title/claim in the memory against Kenyan verification standard Step 4 and Step 5.
                
                <Progress Checklist>
                {json.dumps(state.progress_checklist, indent=2)}
                </Progress Checklist>

                <Action History (Last 5)>
                {json.dumps([f"{a['tool']}: {a['input_hash']}" for a in state.action_history[-5:]], indent=2)}
                </Action History>

                <Completion Rules - ENFORCE THESE>
                1. DO NOT conclude unless physical_boundary_verified, additional_records_checked, zoning_checked, and historical_chain_checked are true.
                2. Step 4 must explicitly verify beacons, Registry Index Map consistency, and encroachment.
                3. Step 5 must explicitly check National Land Commission records, Kenya Gazette notices, Land Registration Act 2012 conversion status, zoning compliance, and ownership continuity.
                4. DO NOT search for blob names or storage URIs - ONLY search for Title Numbers, Owner Names, registry terms, county zoning, and gazette/NLC records.
                5. Use Chain of Verification (CoVe): extract claims, verify them against evidence, and synthesize only from verified claims.
                </Completion Rules>
                
                <Current State>
                Step: {state.total_steps}/15 MAX
                Searches Done: {searches_done}
                Memory (last 6 entries):
                {json.dumps(state.memory[-6:], indent=2)}
                </Current State>
                
                <Available Tools>
                1. inspect_satellite: Only after valid coordinates are available.
                2. google_search: Only for the mandatory Step 5 queries.
                3. finish_audit: Use only after the mandatory Step 4 and Step 5 checks are complete.
                4. wait_user: If required data such as coordinates or RIM reference is missing.
                </Available Tools>
                
                <Decision Logic>
                IF physical_boundary_verified == False AND coordinates are available:
                    → call inspect_satellite
                ELIF additional_records_checked == False:
                    → call google_search with Step 5 record queries
                ELIF historical_chain_checked == False:
                    → trace ownership continuity before concluding
                ELIF all mandatory checks are complete:
                    → call finish_audit
                ELSE:
                    → Something is wrong, call wait_user
                </Decision Logic>
                
                Be DECISIVE. Do NOT loop. Progress toward finish_audit using Chain of Verification (CoVe).
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
                if state.image_uri:
                    # Sync
                    self.sync_service.update_session_state(self.session_id, latest_thought="Re-analyzing image for details...")
                    
                    result = self.analyze_image(
                        state.image_uri,
                        state.image_mime_type or "application/octet-stream",
                    )
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
                            if search_results.get("status") == "success" and search_results.get("trace_id") and search_results.get("evidence_sha256"):
                                state.register_evidence(
                                    "title_searched",
                                    provider=str(search_results.get("provider", "gemini_google_search")),
                                    trace_id=str(search_results["trace_id"]),
                                    sha256=str(search_results["evidence_sha256"]),
                                    summary=f"Manual search completed for {decision.tool_input}.",
                                    metadata={"query": decision.tool_input},
                                )
                            
                        # Truncate and store
                        result_text = search_results.get("text", "")
                        truncated_results = self.truncate_memory_item(result_text, max_chars=800)
                        state.memory.append(f"🔍 Search Results for '{decision.tool_input}':\n{truncated_results}")
                        self.logger.info(f"Search completed: {len(truncated_results)} chars")

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
                    parsed = parse_kenyan_coordinates(decision.tool_input)
                    if parsed.get("error"):
                        raise ValueError(parsed["error"])
                    lat = float(parsed["lat"])
                    lng = float(parsed["lng"])
                    state.current_lat_lng = f"{lat},{lng}"
                    state.memory.append(f"🛰️ Satellite check: ({lat}, {lng}) [{parsed.get('format', 'unknown')}]")
                    
                    # Sync
                    self.sync_service.update_session_state(
                        self.session_id, 
                        latest_thought=f"Checking Satellite imagery at {lat}, {lng}...",
                        logs=[{"timestamp": time.time(), "message": f"🛰️ Inspecting Satellite: {lat}, {lng}"}]
                    )
                    boundary_result = inspect_physical_boundaries(
                        lat,
                        lng,
                        title_context="\n".join(state.memory[-8:]),
                        expected_land_use=self._extract_case_context(state).get("expected_land_use"),
                    )
                    state.memory.append(f"🛰️ Boundary Inspection Result: {json.dumps(boundary_result)}")
                    state.progress_checklist["location_checked"] = True
                    if boundary_result.get("status") == "success" and boundary_result.get("trace_id") and boundary_result.get("evidence_sha256"):
                        state.register_evidence(
                            "physical_boundary_verified",
                            provider=str(boundary_result.get("provider", "gemini_vision")),
                            trace_id=str(boundary_result["trace_id"]),
                            sha256=str(boundary_result["evidence_sha256"]),
                            summary="Manual satellite boundary inspection completed with provenance.",
                            metadata={"lat": lat, "lng": lng},
                        )
                    self.sync_service.update_session_state(
                        self.session_id,
                        logs=[{"timestamp": time.time(), "message": "✅ Satellite boundary inspection complete."}]
                    )
                    if boundary_result.get("discrepancy_detected") and boundary_result.get("severity") == "HIGH":
                        return self._flag_session(
                            state,
                            "Physical boundary verification detected a high-severity discrepancy between the deed and observed occupation.",
                            boundary_result.get("reasoning", "Satellite boundary analysis reported a contradiction."),
                        )
                    
                except Exception as e:
                    state.memory.append(f"❌ Satellite error: {e}")
            
            elif decision.next_tool == "finish_audit":
                final_conclusion = self._compose_final_conclusion(state, decision.tool_input)
                high_risk_found = any(str(f.get("severity", "")).upper() == "HIGH" for f in state.findings)
                state.status = AgentState.FLAGGED if (state.status == AgentState.FLAGGED or high_risk_found) else AgentState.COMPLETED
                state.memory.append(f"✅ FINAL VERDICT: {final_conclusion}")
                self.logger.info("🎉 Audit completed successfully")
                
                # Generate structured findings for the report
                final_findings = state.findings or [
                    {
                        "category": "Audit Verdict",
                        "description": final_conclusion,
                        "evidence": "See detailed investigation logs for full analysis lineage."
                    }
                ]

                # Sync Completion
                self.sync_service.update_session_state(
                    self.session_id, 
                    status=state.status.value, 
                    latest_thought="Audit Complete. Generating Report.",
                    percent=100,
                    logs=[{"timestamp": time.time(), "message": f"✅ Verdict: {final_conclusion}"}],
                    audit_conclusion=final_conclusion,
                    findings=final_findings
                )
                if self.owner_id:
                    self.sync_service.send_push_notification(
                        self.owner_id, 
                        "Audit Complete", 
                        "Your Land Title Audit is ready.",
                        {"job_id": self.session_id, "route": f"/audit/{self.session_id}"}
                    )
            
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
        except SourceDocumentAccessError as exc:
            state.status = AgentState.FAILED
            state.memory.append(f"❌ {exc.user_message}")
            self.sync_service.update_session_state(
                self.session_id,
                status="FAILED",
                latest_thought=exc.user_message,
                logs=[{"timestamp": time.time(), "message": exc.user_message}],
            )
            self.save_state(state)
            return {"status": state.status, "next_tick_seconds": 0}

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
            
            self.save_state(state)
            # Retry immediately if not failed
            return {"status": state.status, "next_tick_seconds": 5}
