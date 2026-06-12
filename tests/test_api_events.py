"""事件 API 测试"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_session():
    mock = AsyncMock(spec=AsyncSession)
    mock.execute = AsyncMock()
    mock.commit = AsyncMock()
    return mock


class TestEventAPIFunctions:
    def test_get_events_is_callable(self):
        from app.routes.api_events import get_events
        assert callable(get_events)

    def test_get_events_timeline_is_callable(self):
        from app.routes.api_events import get_events_timeline
        assert callable(get_events_timeline)

    def test_get_event_categories_is_callable(self):
        from app.routes.api_events import get_event_categories
        assert callable(get_event_categories)

    def test_get_event_detail_is_callable(self):
        from app.routes.api_events import get_event_detail
        assert callable(get_event_detail)

    def test_causal_chain_function_exists(self):
        from app.routes.api_events import _get_causal_chain
        assert callable(_get_causal_chain)

    def test_generate_mermaid_function_exists(self):
        from app.routes.api_events import _generate_mermaid
        assert callable(_generate_mermaid)

    def test_router_has_events_endpoint(self):
        from app.routes.api_events import router
        routes = [r.path for r in router.routes]
        assert "/api/events" in routes

    def test_router_has_events_timeline_endpoint(self):
        from app.routes.api_events import router
        routes = [r.path for r in router.routes]
        assert "/api/events/timeline" in routes

    def test_router_has_events_categories_endpoint(self):
        from app.routes.api_events import router
        routes = [r.path for r in router.routes]
        assert "/api/events/categories" in routes

    def test_router_has_event_detail_endpoint(self):
        from app.routes.api_events import router
        routes = [r.path for r in router.routes]
        assert "/api/events/{event_id}" in routes
