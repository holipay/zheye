import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_session():
    """Mock database session"""
    mock = AsyncMock()
    mock.execute = AsyncMock()
    mock.commit = AsyncMock()
    return mock


@pytest.mark.anyio
async def test_health_endpoint():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert data["status"] in ["ok", "degraded"]


@pytest.mark.anyio
async def test_pages_index():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


@pytest.mark.anyio
async def test_pages_news():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/en/news")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


@pytest.mark.anyio
async def test_pages_articles():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/en/articles")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


@pytest.mark.anyio
async def test_pages_analysis():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/en/analysis")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


@pytest.mark.anyio
async def test_search_endpoint_empty_query():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/search")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


@pytest.mark.anyio
async def test_search_endpoint_short_query():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/search?q=a")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


@pytest.mark.anyio
async def test_analysis_daily_invalid_date():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/analysis/daily/invalid-date")
        assert response.status_code == 400


class TestCacheModule:
    def test_get_cached_returns_none_for_missing_key(self):
        from app.cache import get_cached, clear_cache
        clear_cache()
        result = get_cached("nonexistent:key")
        assert result is None

    def test_set_cached_and_get_cached(self):
        from app.cache import get_cached, set_cached, clear_cache
        clear_cache()
        set_cached("test:key", {"data": "value"})
        result = get_cached("test:key")
        assert result == {"data": "value"}

    def test_clear_cache(self):
        from app.cache import get_cached, set_cached, clear_cache
        set_cached("test:key1", "value1")
        set_cached("test:key2", "value2")
        clear_cache()
        assert get_cached("test:key1") is None
        assert get_cached("test:key2") is None

    def test_cache_overwrite(self):
        from app.cache import get_cached, set_cached, clear_cache
        clear_cache()
        set_cached("test:key", "original")
        set_cached("test:key", "updated")
        result = get_cached("test:key")
        assert result == "updated"


class TestModelsImport:
    def test_import_all_models(self):
        from models import (
            Base, engine, async_session, get_session,
            News, Analysis, TranslationCache, SourceHealth, RunMetrics,
            Keyword, ArticleKeyword, ArticleRelation,
            Entity, ArticleEntity,
            DailyReport, Trend, Event, MarketData
        )
        assert News.__tablename__ == "news"
        assert DailyReport.__tablename__ == "daily_reports"
        assert Trend.__tablename__ == "trends"
        assert Event.__tablename__ == "events"
        assert MarketData.__tablename__ == "market_data"

    def test_daily_report_model(self):
        from models.daily_report import DailyReport
        assert hasattr(DailyReport, 'date')
        assert hasattr(DailyReport, 'overview')
        assert hasattr(DailyReport, 'hot_topics')
        assert hasattr(DailyReport, 'market_sentiment')

    def test_trend_model(self):
        from models.trend import Trend
        assert hasattr(Trend, 'date')
        assert hasattr(Trend, 'keyword')
        assert hasattr(Trend, 'count')
        assert hasattr(Trend, 'sentiment')

    def test_event_model(self):
        from models.event import Event
        assert hasattr(Event, 'event_id')
        assert hasattr(Event, 'title')
        assert hasattr(Event, 'status')

    def test_market_data_model(self):
        from models.market_data import MarketData
        assert hasattr(MarketData, 'source')
        assert hasattr(MarketData, 'data_type')
        assert hasattr(MarketData, 'symbol')
        assert hasattr(MarketData, 'value')


class TestRunMetricsModel:
    def test_run_metrics_model(self):
        from models.run_metrics import RunMetrics
        assert hasattr(RunMetrics, 'run_type')
        assert hasattr(RunMetrics, 'started_at')
        assert hasattr(RunMetrics, 'finished_at')
        assert hasattr(RunMetrics, 'sources_attempted')
        assert hasattr(RunMetrics, 'sources_succeeded')
        assert hasattr(RunMetrics, 'sources_failed')
        assert hasattr(RunMetrics, 'items_fetched')
        assert hasattr(RunMetrics, 'items_final')
