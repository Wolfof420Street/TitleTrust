from __future__ import annotations

from types import SimpleNamespace

from backend.agent.marathon_loop import AgentState, MarathonLoop, MarathonState
from backend.agent.tools import parse_kenyan_coordinates


class DummySyncService:
    def __init__(self) -> None:
        self.updates = []

    def update_session_state(self, session_id: str, **kwargs):
        self.updates.append((session_id, kwargs))

    def send_push_notification(self, *args, **kwargs):  # pragma: no cover - not used in these tests
        return None


def _build_loop() -> MarathonLoop:
    loop = MarathonLoop.__new__(MarathonLoop)
    stored_state = MarathonState(
        session_id="session-test",
        status=AgentState.RUNNING,
        memory=["Title Number: I.R. 12345", "Registered Owner: Jane Wanjiku", "Coordinates: 0.0, 0.0"],
        progress_checklist={
            "image_analyzed": True,
            "title_searched": False,
            "physical_boundary_verified": True,
            "additional_records_checked": False,
            "zoning_checked": False,
            "historical_chain_checked": False,
            "owner_verified": False,
            "location_checked": False,
        },
    )
    loop.session_id = "session-test"
    loop.config = SimpleNamespace(
        MAX_RETRIES=3,
        EMPTY_RESPONSE_MAX_RETRIES=2,
        STEP_DELAY_SECONDS=2,
        IMAGE_ANALYSIS_ENABLED=False,
    )
    loop.logger = SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None)
    loop.sync_service = DummySyncService()
    loop.save_state = lambda state: None
    loop.load_state = lambda: stored_state
    loop._stored_state = stored_state
    loop.perform_research = lambda query: {
        "status": "success",
        "provider": "gemini_google_search",
        "query": query,
        "text": "Disputed parcel pending litigation",
        "trace_id": "search-12345678",
        "evidence_sha256": "a" * 64,
    }
    return loop


def test_parse_kenyan_coordinates_rejects_out_of_bounds_decimal() -> None:
    result = parse_kenyan_coordinates("Coordinates: -9.0, 36.8")

    assert result["error"] == "Coordinates outside Kenya bounding box"
    assert result["format"] == "decimal"


def test_step5_disputed_gazette_forces_failed_state() -> None:
    loop = _build_loop()
    loop.generate_decision = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("generate_decision should not run after disputed gazette"))

    result = loop.run_single_step()

    assert result["status"] == AgentState.FAILED
    assert loop._stored_state.status == AgentState.FAILED
    assert any(update[1]["status"] == "FAILED" for update in loop.sync_service.updates)


def test_final_conclusion_prefers_encroachment_and_keeps_conversion_risk() -> None:
    loop = _build_loop()
    state = MarathonState(
        session_id="session-test",
        findings=[
            {
                "category": "Physical Boundary Verification",
                "severity": "HIGH",
                "description": "Encroachment detected along the northern boundary.",
                "evidence": "Satellite image shows a wall crossing the RIM line.",
            },
            {
                "category": "Additional Records",
                "severity": "MEDIUM",
                "description": "Title appears to be undergoing Land Registration Act 2012 conversion or still references an old register.",
                "evidence": "Old register trail found; new green card not yet verified.",
                "risk_code": "CONVERSION_STATUS_UNVERIFIED",
            },
        ],
    )

    conclusion = loop._compose_final_conclusion(state, "Model summary should not override evidence.")

    assert conclusion.startswith("Primary risk: Encroachment detected along the northern boundary.")
    assert "Additional risk:" in conclusion
    assert "Model summary should not override evidence." in conclusion