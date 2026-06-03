import pytest
from app.cache import get_cached, set_cached, clear_cache, invalidate_cache


@pytest.fixture(autouse=True)
def clean_cache():
    """每个测试前清空缓存"""
    clear_cache()
    yield
    clear_cache()


class TestGetCached:
    def test_returns_none_for_missing_key(self):
        assert get_cached("nonexistent") is None

    def test_returns_cached_value(self):
        set_cached("test_key", "test_value")
        assert get_cached("test_key") == "test_value"


class TestSetCached:
    def test_basic_set(self):
        set_cached("key1", "value1")
        assert get_cached("key1") == "value1"

    def test_overwrite(self):
        set_cached("key1", "value1")
        set_cached("key1", "value2")
        assert get_cached("key1") == "value2"

    def test_with_ttl(self):
        set_cached("key1", "value1", ttl=60)
        assert get_cached("key1") == "value1"

    def test_different_types(self):
        set_cached("str", "hello")
        set_cached("int", 42)
        set_cached("list", [1, 2, 3])
        set_cached("dict", {"a": 1})

        assert get_cached("str") == "hello"
        assert get_cached("int") == 42
        assert get_cached("list") == [1, 2, 3]
        assert get_cached("dict") == {"a": 1}


class TestClearCache:
    def test_clears_all(self):
        set_cached("key1", "value1")
        set_cached("key2", "value2")
        clear_cache()
        assert get_cached("key1") is None
        assert get_cached("key2") is None


class TestInvalidateCache:
    def test_invalidates_matching_prefix(self):
        set_cached("api:news:1", "data1")
        set_cached("api:news:2", "data2")
        set_cached("api:events:1", "data3")

        invalidate_cache("api:news:")

        assert get_cached("api:news:1") is None
        assert get_cached("api:news:2") is None
        assert get_cached("api:events:1") == "data3"

    def test_no_match(self):
        set_cached("api:news:1", "data1")
        invalidate_cache("api:events:")
        assert get_cached("api:news:1") == "data1"

    def test_empty_prefix(self):
        set_cached("key1", "value1")
        # 空前缀会匹配所有
        invalidate_cache("")
        assert get_cached("key1") is None
