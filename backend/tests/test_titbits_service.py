from backend.services.titbits_service import DEFAULT_TITBITS, TitbitsService


def test_titbits_service_falls_back_without_api_key(monkeypatch):
    monkeypatch.setattr("backend.services.titbits_service.settings.GEMINI_API_KEY", None)
    service = TitbitsService()
    result = service.generate()
    assert result["titbits"] == DEFAULT_TITBITS
