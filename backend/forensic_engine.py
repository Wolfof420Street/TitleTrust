"""
Kenyan Land Forensics Agent - Production Version
Detects fraudulent title deeds through multi-step investigation.
"""

import os
import logging
import json
import hashlib
import time
import traceback
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime
from contextlib import contextmanager
from functools import wraps

# Third-party imports
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

# Local imports with proper error handling
try:
    from backend.config import settings
    from backend.core.gemini_api_manager import gemini_api_manager
    from backend.models import ForensicReport, VisualAnomaly, VerificationStep
except ImportError as e:
    try:
        from config import settings
        from core.gemini_api_manager import gemini_api_manager
        from models import ForensicReport, VisualAnomaly, VerificationStep
    except ImportError:
        logging.critical(f"Failed to import required modules: {e}")
        raise SystemExit(f"Cannot start without required dependencies: {e}")


# --- CONFIGURATION ---
class ForensicConfig:
    """Centralized configuration for forensic analysis."""
    MAX_FILE_SIZE_MB = int(os.getenv('FORENSIC_MAX_FILE_SIZE_MB', 10))
    INVESTIGATION_TIMEOUT_SECONDS = int(os.getenv('FORENSIC_TIMEOUT_SECONDS', 120))
    MAX_RETRIES = int(os.getenv('FORENSIC_MAX_RETRIES', 3))
    ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.tiff'}
    TEMPERATURE = float(os.getenv('FORENSIC_TEMPERATURE', 0.7))
    MAX_THOUGHT_LOG_LENGTH = 200
    RATE_LIMIT_CALLS = int(os.getenv('FORENSIC_RATE_LIMIT_CALLS', 10))
    RATE_LIMIT_PERIOD = int(os.getenv('FORENSIC_RATE_LIMIT_PERIOD', 60))
    CACHE_ENABLED = os.getenv('FORENSIC_CACHE_ENABLED', 'true').lower() == 'true'
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'


# --- LOGGING SETUP ---
def setup_logging():
    """Configure structured logging with appropriate handlers."""
    log_format = "%(asctime)s - [%(levelname)s] - [FORENSICS] - %(message)s"
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # File handler (production)
    if not ForensicConfig.DEBUG:
        file_handler = logging.FileHandler('forensics.log')
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers = [console_handler, file_handler]
    else:
        handlers = [console_handler]
    
    logging.basicConfig(
        level=logging.INFO if not ForensicConfig.DEBUG else logging.DEBUG,
        format=log_format,
        handlers=handlers
    )
    return logging.getLogger(__name__)


logger = setup_logging()


# --- CUSTOM EXCEPTIONS ---
class ForensicException(Exception):
    """Base exception for forensic analysis errors."""
    pass


class FileValidationError(ForensicException):
    """Raised when file validation fails."""
    pass


class InvestigationError(ForensicException):
    """Raised when investigation process fails."""
    pass


class APIError(ForensicException):
    """Raised when API interaction fails."""
    pass


# --- METRICS ---
@dataclass
class InvestigationMetrics:
    """Metrics for tracking investigation performance."""
    file_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    success: bool = False
    error: Optional[str] = None
    risk_score: Optional[int] = None
    error_type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return asdict(self)


# --- UTILITIES ---
class SecurityUtils:
    """Security-related utilities."""
    
    @staticmethod
    def sanitize_path(file_path: str) -> str:
        """
        Sanitize file path to prevent path traversal attacks.
        
        Args:
            file_path: Input file path
            
        Returns:
            Sanitized path
            
        Raises:
            FileValidationError: If path traversal detected
        """
        clean_path = os.path.abspath(file_path)
        if '..' in clean_path:
            raise FileValidationError(f"Path traversal detected: {file_path}")
        return clean_path
    
    @staticmethod
    def hash_file_path(file_path: str) -> str:
        """
        Generate anonymized hash of file path for logging.
        
        Args:
            file_path: File path to hash
            
        Returns:
            12-character hash
        """
        return hashlib.sha256(file_path.encode()).hexdigest()[:12]
    
    @staticmethod
    def hash_file_content(file_path: str) -> str:
        """
        Generate hash of file contents for caching.
        
        Args:
            file_path: Path to file
            
        Returns:
            SHA256 hash of file contents
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()





class RateLimiter:
    """Thread-safe rate limiter for API calls."""
    
    def __init__(self, max_calls: int, period: int):
        """
        Initialize rate limiter.
        
        Args:
            max_calls: Maximum number of calls allowed
            period: Time period in seconds
        """
        self.max_calls = max_calls
        self.period = period
        self.calls: List[float] = []
        
        from threading import Lock
        self.lock = Lock()
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.lock:
                now = time.time()
                # Remove old calls outside the period
                self.calls = [c for c in self.calls if c > now - self.period]
                
                if len(self.calls) >= self.max_calls:
                    sleep_time = self.period - (now - self.calls[0])
                    logger.warning(
                        f"Rate limit reached ({self.max_calls}/{self.period}s), "
                        f"sleeping {sleep_time:.2f}s"
                    )
                    time.sleep(sleep_time)
                    self.calls = []
                
                self.calls.append(time.time())
            
            return func(*args, **kwargs)
        return wrapper


def get_api_key() -> str:
    """
    Retrieve API key with secure fallback chain.
    
    Returns:
        API key string
        
    Raises:
        ValueError: If API key not found
    """
    # Priority: Environment variable > Settings file
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
    
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found. Set it as environment variable or in settings."
        )
    
    return api_key


# --- FILE HANDLER ---
class FileHandler:
    """Handles file validation and upload operations."""
    
    @staticmethod
    def validate_file(file_path: str) -> Path:
        """
        Validate file exists, has correct size and type.
        
        Args:
            file_path: Path to file
            
        Returns:
            Validated Path object
            
        Raises:
            FileValidationError: If validation fails
        """
        # Sanitize path
        clean_path = SecurityUtils.sanitize_path(file_path)
        path = Path(clean_path)
        
        # Check existence
        if not path.exists():
            raise FileValidationError(f"File not found: {file_path}")
        
        if not path.is_file():
            raise FileValidationError(f"Path is not a file: {file_path}")
        
        # Check size
        max_size = ForensicConfig.MAX_FILE_SIZE_MB * 1024 * 1024
        file_size = path.stat().st_size
        
        if file_size > max_size:
            raise FileValidationError(
                f"File exceeds {ForensicConfig.MAX_FILE_SIZE_MB}MB limit. "
                f"Size: {file_size / 1024 / 1024:.2f}MB"
            )
        
        # Check extension
        if path.suffix.lower() not in ForensicConfig.ALLOWED_EXTENSIONS:
            raise FileValidationError(
                f"Unsupported file type: {path.suffix}. "
                f"Allowed: {', '.join(ForensicConfig.ALLOWED_EXTENSIONS)}"
            )
        
        logger.debug(f"File validation passed: {SecurityUtils.hash_file_path(file_path)}")
        return path
    
    @staticmethod
    @retry(
        stop=stop_after_attempt(ForensicConfig.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        reraise=True
    )
    def upload_file(client: genai.Client, file_path: Path):
        """
        Upload file with retry logic.
        
        Args:
            client: Gemini client instance
            file_path: Validated file path
            
        Returns:
            File reference from upload
            
        Raises:
            APIError: If upload fails after retries
        """
        try:
            logger.info(f"Uploading file: {SecurityUtils.hash_file_path(str(file_path))}")
            file_ref = client.files.upload(file=str(file_path))
            logger.debug(f"Upload successful: {file_ref.uri}")
            return file_ref
        except Exception as e:
            logger.error(f"File upload failed: {e}", exc_info=ForensicConfig.DEBUG)
            raise APIError(f"Failed to upload file: {e}")


# --- INVESTIGATION ENGINE ---
class InvestigationEngine:
    """Core forensic investigation logic."""
    
    SYSTEM_INSTRUCTION = """
You are the Chief Forensic Examiner for the Kenyan Ministry of Lands. 
Your goal is to detect fraudulent title deeds through a rigorous, multi-step investigation.

<Investigation Protocol>
1. **Visual Inspection**: Scrutinize the image for digital manipulation (different fonts, clean stamps on dirty paper, pixelation, inconsistent lighting, cloning artifacts).
2. **Fact Checking (Google Search)**: 
   - Extract the Registrar's name and the date of issue. Use Google Search to verify if that person held office on that date.
   - Search for the Title Number in public gazette notices or auction listings to see if it's flagged.
   - Verify location names and coordinates against official records.
3. **Mathematical Verification (Code Execution)**:
   - If coordinates or acreage are visible, write Python code to verify conversions (e.g., Hectares to Acres) match the document text.
   - Validate calculated areas against stated values.
4. **Synthesis**: Combine visual flaws with external factual inconsistencies to determine a Risk Score (0-100).
</Investigation Protocol>

<Chain of Verification>
Use CoVe: extract each claim, verify it against at least one grounded source, and only synthesize from verified claims.
If a claim is contradicted by evidence, keep the contradiction visible in the final reasoning instead of softening it.
</Chain of Verification>

<Output Format>
Provide a structured ForensicReport with:
- title_number: Extracted title number
- risk_score: 0-100 (0=genuine, 100=definitely fraudulent)
- final_verdict: "GENUINE" | "SUSPICIOUS" | "FRAUDULENT" | "INCONCLUSIVE"
- reasoning_summary: Brief explanation of conclusion
- visual_anomalies: List of detected visual issues
- investigation_steps: List of verification steps performed
</Output Format>

<Tone>
Objective, skeptical, and legally precise. Focus on evidence-based conclusions.
</Tone>
"""
    
    def __init__(self, client: genai.Client):
        """
        Initialize investigation engine.
        
        Args:
            client: Gemini API client
        """
        self.client = client
    
    @RateLimiter(
        max_calls=ForensicConfig.RATE_LIMIT_CALLS,
        period=ForensicConfig.RATE_LIMIT_PERIOD
    )
    def investigate(self, file_ref, file_path: str) -> Dict[str, Any]:
        """
        Perform forensic investigation on uploaded file.
        
        Args:
            file_ref: Uploaded file reference
            file_path: Original file path (for logging)
            
        Returns:
            Investigation results as dictionary
            
        Raises:
            InvestigationError: If investigation fails
        """
        file_hash = SecurityUtils.hash_file_path(file_path)
        logger.info(f"🕵️ Starting investigation: {file_hash}")
        
        try:
            # Configure tools
            tools = [
                types.Tool(
                    google_search=types.GoogleSearch(),
                    code_execution=types.ToolCodeExecution()
                )
            ]
            
            # Configure thinking (for transparency)
            thinking_config = types.ThinkingConfig(include_thoughts=True)
            
            # Generate content (timeout removed for thread safety)
            response = self.client.models.generate_content(
                model=settings.FORENSIC_MODEL_NAME,
                contents=[
                    types.Part.from_uri(
                        file_uri=file_ref.uri,
                        mime_type=file_ref.mime_type
                    ),
                    "Investigate this title deed. Verify the registrar, check for "
                    "gazette notices, validate any mathematical calculations, and "
                    "detect visual anomalies. Generate a complete ForensicReport."
                ],
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_INSTRUCTION,
                    tools=tools,
                    thinking_config=thinking_config,
                    response_mime_type="application/json",
                    response_schema=ForensicReport,
                    temperature=ForensicConfig.TEMPERATURE
                )
            )
            
            # Log thinking process (sanitized)
            self._log_thoughts(response, file_hash)
            
            # Parse response
            if response.parsed:
                result = response.parsed.model_dump()
                result["trace_id"] = f"forensic-{uuid.uuid4().hex[:12]}"
                hash_payload = {
                    "file_uri": getattr(file_ref, "uri", file_path),
                    "file_mime_type": getattr(file_ref, "mime_type", None),
                    "response": {k: v for k, v in result.items() if k != "trace_id"},
                    "response_text": response.text if hasattr(response, "text") else None,
                }
                result["evidence_sha256"] = hashlib.sha256(
                    json.dumps(
                        hash_payload,
                        sort_keys=True,
                        default=str,
                    ).encode("utf-8")
                ).hexdigest()
                logger.info(
                    f"Investigation complete: {file_hash} - "
                    f"Verdict: {result.get('final_verdict', 'UNKNOWN')} - "
                    f"Risk: {result.get('risk_score', 0)}/100"
                )
                return result
            else:
                logger.warning(f"Failed to parse structured report for {file_hash}")
                return self._create_error_report(
                    "Failed to parse response",
                    response.text if hasattr(response, 'text') else None
                )
        
        except TimeoutError as e:
            logger.error(f"Investigation timeout for {file_hash}: {e}")
            raise InvestigationError(f"Investigation exceeded timeout: {e}")
        
        except Exception as e:
            logger.error(
                f"Investigation failed for {file_hash}: {e}",
                exc_info=ForensicConfig.DEBUG
            )
            raise InvestigationError(f"Investigation failed: {e}")
    
    def _log_thoughts(self, response, file_hash: str) -> None:
        """
        Log model's reasoning process (sanitized).
        
        Args:
            response: API response
            file_hash: Anonymized file identifier
        """
        logger.debug(f"\n🧠 --- REASONING PROCESS ({file_hash}) ---")
        
        try:
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if hasattr(part, 'thought') and part.thought:
                        thought_snippet = part.thought[:ForensicConfig.MAX_THOUGHT_LOG_LENGTH]
                        logger.debug(f"Thought: {thought_snippet}...")
                        # Stream sanitized thought to realtime (best-effort)
                        try:
                            import asyncio
                            from backend.realtime.events import emit

                            payload = {
                                "file_hash": file_hash,
                                "thought_snippet": thought_snippet,
                            }
                            try:
                                loop = asyncio.get_running_loop()
                                loop.create_task(emit("agent.thought", payload, session_id=file_hash, severity="debug"))
                            except RuntimeError:
                                import threading

                                def _bg():
                                    import asyncio as _asyncio
                                    from backend.realtime.events import emit as _emit
                                    try:
                                        _asyncio.run(_emit("agent.thought", payload, session_id=file_hash, severity="debug"))
                                    except Exception:
                                        pass

                                threading.Thread(target=_bg, daemon=True).start()
                        except Exception:
                            pass
                    
                    if hasattr(part, 'text') and part.text and "I should" in part.text:
                        text_snippet = part.text[:ForensicConfig.MAX_THOUGHT_LOG_LENGTH]
                        logger.debug(f"Step: {text_snippet}...")
        
        except Exception as e:
            logger.warning(f"Could not extract reasoning: {e}")
        
        logger.debug("--- END REASONING ---\n")
    
    @staticmethod
    def _create_error_report(error_msg: str, raw_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Create standardized error report.
        
        Args:
            error_msg: Error message
            raw_text: Optional raw response text
            
        Returns:
            Error report dictionary
        """
        return {
            "title_number": "UNKNOWN",
            "risk_score": 0,
            "final_verdict": "ERROR",
            "reasoning_summary": error_msg,
            "visual_anomalies": [],
            "investigation_steps": [],
            "raw_response": raw_text if ForensicConfig.DEBUG else None
        }


# --- MAIN AGENT ---
class KenyanLandForensicsAgent:
    """
    Production-ready forensic analysis agent for Kenyan land title deeds.
    
    Features:
    - File validation and security checks
    - Retry logic with exponential backoff
    - Rate limiting
    - Comprehensive error handling
    - Metrics tracking
    - Secure logging
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize forensic agent.
        
        Args:
            api_key: Optional API key (uses env/settings if not provided)
        """
        try:
            key = api_key or get_api_key()
            self.client = genai.Client(api_key=key)
            self.file_handler = FileHandler()
            self.engine = InvestigationEngine(self.client)
            self.gemini_manager = gemini_api_manager
            self.metrics_history: List[InvestigationMetrics] = []
            
            logger.info("Forensics Agent initialized successfully")
        
        except Exception as e:
            logger.critical(f"Failed to initialize agent: {e}")
            raise
    
    def investigate_deed(self, file_path: str) -> Dict[str, Any]:
        """
        Investigate a title deed for fraud indicators.
        
        Args:
            file_path: Path to the deed document
            
        Returns:
            Dict containing forensic report data
            
        Raises:
            FileValidationError: If file validation fails
            InvestigationError: If investigation process fails
            APIError: If API interaction fails
        """
        start_time = time.time()
        file_hash = SecurityUtils.hash_file_path(file_path)
        
        # Initialize metrics
        metrics = InvestigationMetrics(
            file_id=file_hash,
            start_time=datetime.now()
        )
        
        try:
            # Step 1: Validate file
            validated_path = self.file_handler.validate_file(file_path)

            result = self.gemini_manager.execute_forensic_analysis(
                str(validated_path),
                lambda: self._run_live_investigation(validated_path, file_path),
            )
            
            # Update metrics
            metrics.success = True
            metrics.risk_score = result.get('risk_score')
            
            return result
        
        except (FileValidationError, InvestigationError, APIError) as e:
            metrics.error = str(e)
            metrics.error_type = type(e).__name__
            logger.error(f"Investigation failed for {file_hash}: {e}")
            
            return {
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc() if ForensicConfig.DEBUG else None,
                "title_number": "UNKNOWN",
                "risk_score": 0,
                "final_verdict": "ERROR",
                "reasoning_summary": f"Investigation failed: {str(e)}"
            }
        
        except Exception as e:
            metrics.error = str(e)
            metrics.error_type = "UnexpectedError"
            logger.error(
                f"Unexpected error for {file_hash}: {e}",
                exc_info=True
            )
            
            return {
                "error": f"Unexpected error: {str(e)}",
                "error_type": "UnexpectedError",
                "traceback": traceback.format_exc() if ForensicConfig.DEBUG else None
            }
        
        finally:
            # Finalize metrics
            metrics.end_time = datetime.now()
            metrics.duration_seconds = time.time() - start_time
            self._record_metrics(metrics)
    
    def _record_metrics(self, metrics: InvestigationMetrics) -> None:
        """
        Record investigation metrics for monitoring.
        
        Args:
            metrics: Metrics object to record
        """
        self.metrics_history.append(metrics)
        
        # Log metrics
        logger.info(
            f"Metrics - File: {metrics.file_id}, "
            f"Duration: {metrics.duration_seconds:.2f}s, "
            f"Success: {metrics.success}, "
            f"Risk: {metrics.risk_score}"
        )
        
        # In production, send to monitoring system (Prometheus, CloudWatch, etc.)
        # self._send_to_monitoring(metrics)

    def _run_live_investigation(self, validated_path: Path, file_path: str) -> Dict[str, Any]:
        file_ref = self.file_handler.upload_file(self.client, validated_path)
        return self.engine.investigate(file_ref, file_path)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of investigation metrics.
        
        Returns:
            Summary statistics
        """
        if not self.metrics_history:
            return {"message": "No investigations performed yet"}
        
        total = len(self.metrics_history)
        successful = sum(1 for m in self.metrics_history if m.success)
        avg_duration = sum(m.duration_seconds for m in self.metrics_history) / total
        
        return {
            "total_investigations": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": f"{(successful/total)*100:.2f}%",
            "average_duration_seconds": f"{avg_duration:.2f}",
            "high_risk_count": sum(
                1 for m in self.metrics_history 
                if m.risk_score and m.risk_score >= 70
            )
        }


# --- LEGACY ADAPTER ---
def perform_forensic_audit(
    audit_request: Any,
    file_paths: Optional[List[str]] = None
) -> List[str]:
    """
    Legacy adapter function for backward compatibility with main.py.
    
    Args:
        audit_request: Audit request object (unused in current implementation)
        file_paths: List of file paths to investigate
        
    Returns:
        List of finding strings
    """
    if not file_paths:
        logger.warning("No files provided for audit")
        return ["No evidence provided for forensic analysis."]
    
    agent = KenyanLandForensicsAgent()
    findings_summary: List[str] = []
    
    for idx, f_path in enumerate(file_paths, 1):
        logger.info(f"Processing document {idx}/{len(file_paths)}")
        
        try:
            report_data = agent.investigate_deed(f_path)
            
            if "error" in report_data:
                findings_summary.append(
                    f"\n📄 Document {idx}: ERROR"
                )
                findings_summary.append(f"  ❌ {report_data['error']}")
                continue
            
            # Format findings
            findings_summary.append(f"\n📄 Document {idx}: {report_data.get('title_number', 'N/A')}")
            findings_summary.append(f"  ⚖️ Verdict: {report_data.get('final_verdict', 'UNKNOWN')}")
            findings_summary.append(f"  📊 Risk Score: {report_data.get('risk_score', 0)}/100")
            findings_summary.append(f"  📝 Summary: {report_data.get('reasoning_summary', 'N/A')}")
            
            # Visual anomalies
            anomalies = report_data.get('visual_anomalies', [])
            if anomalies:
                findings_summary.append(f"  🔍 Visual Anomalies ({len(anomalies)}):")
                for anomaly in anomalies:
                    desc = (
                        anomaly.get('description')
                        if isinstance(anomaly, dict)
                        else getattr(anomaly, 'description', str(anomaly))
                    )
                    findings_summary.append(f"    • {desc}")
            
            # Investigation steps
            steps = report_data.get('investigation_steps', [])
            if steps:
                findings_summary.append(f"  ✅ Verification Steps ({len(steps)}):")
                for step in steps:
                    name = (
                        step.get('step_name')
                        if isinstance(step, dict)
                        else getattr(step, 'step_name', 'Unknown')
                    )
                    status = (
                        step.get('status')
                        if isinstance(step, dict)
                        else getattr(step, 'status', 'Unknown')
                    )
                    evidence = (
                        step.get('evidence_found')
                        if isinstance(step, dict)
                        else getattr(step, 'evidence_found', 'None')
                    )
                    findings_summary.append(f"    • {name} [{status}]: {evidence}")
        
        except Exception as e:
            logger.error(f"Failed to process document {idx}: {e}", exc_info=ForensicConfig.DEBUG)
            findings_summary.append(f"\n📄 Document {idx}: PROCESSING ERROR")
            findings_summary.append(f"  ❌ {str(e)}")
    
    # Add metrics summary
    try:
        metrics = agent.get_metrics_summary()
        findings_summary.append("\n📊 Investigation Summary:")
        findings_summary.append(f"  Total: {metrics['total_investigations']}")
        findings_summary.append(f"  Success Rate: {metrics['success_rate']}")
        findings_summary.append(f"  Avg Duration: {metrics['average_duration_seconds']}s")
    except Exception as e:
        logger.warning(f"Could not generate metrics summary: {e}")
    
    return findings_summary
