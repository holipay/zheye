"""事件追踪模块测试"""
from datetime import date
from scraper.pipeline.events import (
    generate_event_id,
    extract_event_type,
    calculate_event_similarity,
    is_same_event,
    find_related_event,
    detect_event_from_article,
)


class TestEventId:
    def test_generate_event_id_returns_string(self):
        result = generate_event_id("Fed raises interest rates", "央行与利率")
        assert isinstance(result, str)
        assert result.startswith("EVT-")

    def test_same_title_same_category_same_id(self):
        id1 = generate_event_id("Fed raises interest rates", "央行与利率")
        id2 = generate_event_id("Fed raises interest rates", "央行与利率")
        assert id1 == id2

    def test_different_category_different_id(self):
        id1 = generate_event_id("Fed raises interest rates", "央行与利率")
        id2 = generate_event_id("Fed raises interest rates", "股市与市场")
        assert id1 != id2


class TestEventType:
    def test_detect_rate_decision(self):
        result = extract_event_type("Fed raises interest rates by 25 basis points")
        assert result == "rate_decision"

    def test_detect_earnings_report(self):
        result = extract_event_type("Apple reports record Q2 earnings")
        assert result == "earnings_report"

    def test_detect_economic_data(self):
        result = extract_event_type("GDP growth exceeds expectations")
        assert result == "economic_data"

    def test_detect_market_move(self):
        result = extract_event_type("Nasdaq surges to record high")
        assert result == "market_move"

    def test_detect_geopolitical(self):
        result = extract_event_type("US imposes new tariffs on China")
        assert result == "geopolitical"

    def test_no_event_returns_none(self):
        result = extract_event_type("Local weather forecast")
        assert result is None


class TestEventSimilarity:
    def test_identical_titles(self):
        score = calculate_event_similarity("Fed raises rates", "Fed raises rates")
        assert score == 1.0

    def test_similar_titles(self):
        score = calculate_event_similarity(
            "Fed raises interest rates by 25 basis points",
            "Fed raises interest rates by 25 bps"
        )
        assert score > 0.6

    def test_different_titles(self):
        score = calculate_event_similarity("Fed raises rates", "Apple launches iPhone")
        assert score < 0.5

    def test_is_same_event_true(self):
        result = is_same_event(
            "Fed raises interest rates by 25 basis points",
            "Fed raises interest rates by 25 bps",
            threshold=0.6
        )
        assert result is True

    def test_is_same_event_false(self):
        result = is_same_event(
            "Fed raises rates",
            "Apple launches iPhone",
            threshold=0.6
        )
        assert result is False


class TestDetectEvent:
    def test_detect_rate_event(self):
        result = detect_event_from_article(
            "Fed raises interest rates by 25 basis points",
            "The Federal Reserve announced a rate hike",
            category="央行与利率"
        )
        assert result is not None
        assert result["event_type"] == "rate_decision"
        assert result["category"] == "央行与利率"

    def test_detect_no_event(self):
        result = detect_event_from_article(
            "Local weather forecast",
            "It will be sunny today"
        )
        assert result is None

    def test_detect_market_event(self):
        result = detect_event_from_article(
            "Nasdaq surges to record high on tech rally",
            category="股市与市场"
        )
        assert result is not None
        assert result["event_type"] == "market_move"
