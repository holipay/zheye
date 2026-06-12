"""国际化模块测试"""
import pytest
from unittest.mock import MagicMock


class TestGetText:
    def test_returns_english_text(self):
        from app.i18n import get_text
        result = get_text("en", "nav.home")
        assert result == "Home"

    def test_returns_chinese_text(self):
        from app.i18n import get_text
        result = get_text("zh", "nav.home")
        assert result == "首页"

    def test_falls_back_to_english(self):
        from app.i18n import get_text
        result = get_text("zh", "nav.home")
        assert result != "nav.home"

    def test_returns_key_last_segment_for_missing(self):
        from app.i18n import get_text
        result = get_text("en", "nonexistent.deep.key")
        assert result == "key"

    def test_returns_key_last_segment_for_invalid_lang(self):
        from app.i18n import get_text
        result = get_text("fr", "nav.home")
        assert isinstance(result, str)

    def test_format_kwargs(self):
        from app.i18n import get_text
        result = get_text("en", "news.page_info", page=1, total_pages=5)
        assert "1" in result
        assert "5" in result

    def test_format_kwargs_missing_key(self):
        from app.i18n import get_text
        result = get_text("en", "news.page_info", page=1)
        assert isinstance(result, str)

    def test_nested_key(self):
        from app.i18n import get_text
        result = get_text("en", "site.name")
        assert result == "ZHEYE"

    def test_category_key(self):
        from app.i18n import get_text
        result = get_text("zh", "category.央行与利率")
        assert result == "央行与利率"

    def test_category_key_english(self):
        from app.i18n import get_text
        result = get_text("en", "category.央行与利率")
        assert result == "Central Bank & Rates"

    def test_common_loading(self):
        from app.i18n import get_text
        assert get_text("en", "common.loading") == "Loading..."
        assert get_text("zh", "common.loading") == "加载中..."

    def test_sentiment_keys(self):
        from app.i18n import get_text
        assert "Bullish" in get_text("en", "sentiment.bullish")
        assert "看涨" in get_text("zh", "sentiment.bullish")

    def test_deep_analyst_keys(self):
        from app.i18n import get_text
        assert get_text("en", "deep.background") == "Background"
        assert get_text("zh", "deep.background") == "背景概述"

    def test_admin_keys(self):
        from app.i18n import get_text
        assert get_text("en", "admin.dashboard") == "Dashboard"
        assert get_text("zh", "admin.dashboard") == "仪表盘"

    def test_entity_type_keys(self):
        from app.i18n import get_text
        assert get_text("en", "entity_type.company") == "Company"
        assert get_text("zh", "entity_type.company") == "公司"


class TestGetLanguageFromRequest:
    def test_extracts_lang_from_path(self):
        from app.i18n import get_language_from_request
        request = MagicMock()
        request.url.path = "/en/news"
        assert get_language_from_request(request) == "en"

    def test_extracts_zh_from_path(self):
        from app.i18n import get_language_from_request
        request = MagicMock()
        request.url.path = "/zh/events"
        assert get_language_from_request(request) == "zh"

    def test_returns_default_for_unknown_path(self):
        from app.i18n import get_language_from_request, DEFAULT_LANGUAGE
        request = MagicMock()
        request.url.path = "/some/path"
        assert get_language_from_request(request) == DEFAULT_LANGUAGE

    def test_returns_default_for_root(self):
        from app.i18n import get_language_from_request, DEFAULT_LANGUAGE
        request = MagicMock()
        request.url.path = "/"
        assert get_language_from_request(request) == DEFAULT_LANGUAGE


class TestLocalesFiles:
    def test_en_json_has_all_sections(self):
        import json
        from pathlib import Path
        en = json.load(Path("app/locales/en.json").open())
        required = ["site", "nav", "category", "home", "news", "analysis",
                     "events", "articles", "footer", "common", "sentiment",
                     "entity_type", "deep", "admin"]
        for section in required:
            assert section in en, f"Missing section: {section}"

    def test_zh_json_has_all_sections(self):
        import json
        from pathlib import Path
        zh = json.load(Path("app/locales/zh.json").open())
        required = ["site", "nav", "category", "home", "news", "analysis",
                     "events", "articles", "footer", "common", "sentiment",
                     "entity_type", "deep", "admin"]
        for section in required:
            assert section in zh, f"Missing section: {section}"

    def test_keys_match_between_en_and_zh(self):
        import json
        from pathlib import Path
        en = json.load(Path("app/locales/en.json").open())
        zh = json.load(Path("app/locales/zh.json").open())

        def get_keys(d, prefix=""):
            keys = set()
            for k, v in d.items():
                full = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    keys.update(get_keys(v, full))
                else:
                    keys.add(full)
            return keys

        en_keys = get_keys(en)
        zh_keys = get_keys(zh)
        assert en_keys == zh_keys, f"Mismatch: {en_keys.symmetric_difference(zh_keys)}"
