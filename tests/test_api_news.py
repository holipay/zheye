"""新闻 API 测试"""
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestNewsAPIFunctions:
    def test_get_news_is_callable(self):
        from app.routes.api_news import get_news
        assert callable(get_news)

    def test_get_latest_is_callable(self):
        from app.routes.api_news import get_latest
        assert callable(get_latest)

    def test_get_articles_is_callable(self):
        from app.routes.api_news import get_articles
        assert callable(get_articles)

    def test_get_categories_is_callable(self):
        from app.routes.api_news import get_categories
        assert callable(get_categories)

    def test_get_article_types_is_callable(self):
        from app.routes.api_news import get_article_types
        assert callable(get_article_types)

    def test_get_meta_is_callable(self):
        from app.routes.api_news import get_meta
        assert callable(get_meta)

    def test_get_popular_keywords_is_callable(self):
        from app.routes.api_news import get_popular_keywords
        assert callable(get_popular_keywords)

    def test_get_popular_entities_is_callable(self):
        from app.routes.api_news import get_popular_entities
        assert callable(get_popular_entities)

    def test_get_entity_types_is_callable(self):
        from app.routes.api_news import get_entity_types
        assert callable(get_entity_types)

    def test_get_news_detail_is_callable(self):
        from app.routes.api_news import get_news_detail
        assert callable(get_news_detail)

    def test_search_news_is_callable(self):
        from app.routes.api_news import search_news
        assert callable(search_news)

    def test_get_related_news_is_callable(self):
        from app.routes.api_news import get_related_news
        assert callable(get_related_news)

    def test_get_keywords_is_callable(self):
        from app.routes.api_news import get_keywords
        assert callable(get_keywords)

    def test_get_articles_by_keyword_is_callable(self):
        from app.routes.api_news import get_articles_by_keyword
        assert callable(get_articles_by_keyword)

    def test_get_news_by_entity_is_callable(self):
        from app.routes.api_news import get_news_by_entity
        assert callable(get_news_by_entity)

    def test_router_has_all_endpoints(self):
        from app.routes.api_news import router
        routes = [r.path for r in router.routes]
        assert "/api/news" in routes
        assert "/api/latest" in routes
        assert "/api/articles" in routes
        assert "/api/categories" in routes
        assert "/api/article-types" in routes
        assert "/api/meta" in routes
        assert "/api/keywords/popular" in routes
        assert "/api/entities/popular" in routes
        assert "/api/entities/types" in routes
        assert "/api/news/{news_id}" in routes
        assert "/api/search" in routes
