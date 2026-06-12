"""页面路由测试"""
import pytest


class TestPageRoutes:
    def test_pages_root_redirect(self):
        from app.routes.pages import root
        assert callable(root)

    def test_pages_index(self):
        from app.routes.pages import index
        assert callable(index)

    def test_pages_news(self):
        from app.routes.pages import news
        assert callable(news)

    def test_pages_articles(self):
        from app.routes.pages import articles
        assert callable(articles)

    def test_pages_analysis(self):
        from app.routes.pages import analysis
        assert callable(analysis)

    def test_pages_news_detail(self):
        from app.routes.pages import news_detail
        assert callable(news_detail)

    def test_pages_events(self):
        from app.routes.pages import events
        assert callable(events)

    def test_pages_event_detail(self):
        from app.routes.pages import event_detail
        assert callable(event_detail)


class TestValidateLang:
    def test_validate_lang_en(self):
        from app.routes.pages import validate_lang
        assert validate_lang("en") == "en"

    def test_validate_lang_zh(self):
        from app.routes.pages import validate_lang
        assert validate_lang("zh") == "zh"

    def test_validate_lang_invalid(self):
        from app.routes.pages import validate_lang
        from app.i18n import DEFAULT_LANGUAGE
        assert validate_lang("fr") == DEFAULT_LANGUAGE
        assert validate_lang("de") == DEFAULT_LANGUAGE
        assert validate_lang("xx") == DEFAULT_LANGUAGE

    def test_validate_lang_case_sensitive(self):
        from app.routes.pages import validate_lang
        from app.i18n import DEFAULT_LANGUAGE
        assert validate_lang("EN") == DEFAULT_LANGUAGE
        assert validate_lang("ZH") == DEFAULT_LANGUAGE


class TestRouterStructure:
    def test_router_has_root_endpoint(self):
        from app.routes.pages import router
        routes = [r.path for r in router.routes]
        assert "/" in routes

    def test_router_has_lang_endpoint(self):
        from app.routes.pages import router
        routes = [r.path for r in router.routes]
        assert "/{lang}" in routes

    def test_router_has_news_endpoint(self):
        from app.routes.pages import router
        routes = [r.path for r in router.routes]
        assert "/{lang}/news" in routes

    def test_router_has_articles_endpoint(self):
        from app.routes.pages import router
        routes = [r.path for r in router.routes]
        assert "/{lang}/articles" in routes

    def test_router_has_analysis_endpoint(self):
        from app.routes.pages import router
        routes = [r.path for r in router.routes]
        assert "/{lang}/analysis" in routes

    def test_router_has_events_endpoint(self):
        from app.routes.pages import router
        routes = [r.path for r in router.routes]
        assert "/{lang}/events" in routes
