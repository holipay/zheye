"""图表 API 测试"""
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestChartAPIFunctions:
    def test_get_daily_trend_is_callable(self):
        from app.routes.charts import get_daily_trend
        assert callable(get_daily_trend)

    def test_get_sentiment_distribution_is_callable(self):
        from app.routes.charts import get_sentiment_distribution
        assert callable(get_sentiment_distribution)

    def test_get_sentiment_trend_is_callable(self):
        from app.routes.charts import get_sentiment_trend
        assert callable(get_sentiment_trend)

    def test_get_category_stats_is_callable(self):
        from app.routes.charts import get_category_stats
        assert callable(get_category_stats)

    def test_get_keyword_trends_is_callable(self):
        from app.routes.charts import get_keyword_trends
        assert callable(get_keyword_trends)

    def test_get_source_stats_is_callable(self):
        from app.routes.charts import get_source_stats
        assert callable(get_source_stats)

    def test_get_region_stats_is_callable(self):
        from app.routes.charts import get_region_stats
        assert callable(get_region_stats)

    def test_get_importance_distribution_is_callable(self):
        from app.routes.charts import get_importance_distribution
        assert callable(get_importance_distribution)

    def test_router_has_all_endpoints(self):
        from app.routes.charts import router
        routes = [r.path for r in router.routes]
        assert "/api/charts/daily-trend" in routes
        assert "/api/charts/sentiment" in routes
        assert "/api/charts/sentiment-trend" in routes
        assert "/api/charts/categories" in routes
        assert "/api/charts/keywords" in routes
        assert "/api/charts/sources" in routes
        assert "/api/charts/regions" in routes
        assert "/api/charts/importance" in routes
