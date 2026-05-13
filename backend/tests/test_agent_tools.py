from __future__ import annotations

from backend.agent.tools import build_record_search_queries, parse_kenyan_coordinates


def test_parse_kenyan_coordinates_supports_decimal_degrees() -> None:
    result = parse_kenyan_coordinates("Coordinates: -1.2921, 36.8219")

    assert result["format"] == "decimal"
    assert round(result["lat"], 4) == -1.2921
    assert round(result["lng"], 4) == 36.8219


def test_parse_kenyan_coordinates_supports_kenyan_utm() -> None:
    result = parse_kenyan_coordinates("UTM 37S 257634, 9851240")

    assert result["format"] == "utm"
    assert -5.5 <= result["lat"] <= 5.5
    assert 33.0 <= result["lng"] <= 42.5


def test_build_record_search_queries_enforces_step5_sources() -> None:
    queries = build_record_search_queries(
        title_number="I.R. 12345",
        owner_name="Jane Wanjiku",
        county="Nairobi",
    )

    joined = "\n".join(queries)
    assert "National Land Commission" in joined
    assert "Kenya Gazette" in joined
    assert "Land Registration Act 2012" in joined
    assert "Nairobi County" in joined
    assert "ownership history" in joined
