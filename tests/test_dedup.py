from scraper.pipeline.dedup import get_link_hash, similarity, is_duplicate


class TestGetLinkHash:
    def test_returns_sha256_hex(self):
        result = get_link_hash("https://example.com")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_url_same_hash(self):
        h1 = get_link_hash("https://example.com/test")
        h2 = get_link_hash("https://example.com/test")
        assert h1 == h2

    def test_different_url_different_hash(self):
        h1 = get_link_hash("https://example.com/a")
        h2 = get_link_hash("https://example.com/b")
        assert h1 != h2

    def test_empty_string(self):
        result = get_link_hash("")
        assert len(result) == 64

    def test_unicode_url(self):
        result = get_link_hash("https://例え.jp/テスト")
        assert len(result) == 64


class TestSimilarity:
    def test_identical_strings(self):
        assert similarity("hello", "hello") == 1.0

    def test_empty_strings(self):
        assert similarity("", "") == 0.0

    def test_one_empty(self):
        assert similarity("hello", "") == 0.0
        assert similarity("", "hello") == 0.0

    def test_case_insensitive(self):
        assert similarity("Hello", "hello") == 1.0

    def test_similar_strings(self):
        result = similarity("Fed raises rates", "Fed raises interest rates")
        assert 0.5 < result < 1.0

    def test_different_strings(self):
        result = similarity("Apple earnings", "Oil prices surge")
        assert result < 0.3


class TestIsDuplicate:
    def test_exact_match(self):
        existing = ["Fed raises rates", "Apple earnings"]
        assert is_duplicate("Fed raises rates", existing) is True

    def test_similar_match(self):
        existing = ["Fed raises interest rates by 25 basis points"]
        assert is_duplicate("Fed raises interest rates by 50 basis points", existing) is True

    def test_no_match(self):
        existing = ["Fed raises rates", "Apple earnings"]
        assert is_duplicate("Oil prices surge amid supply concerns", existing) is False

    def test_empty_title(self):
        existing = ["Fed raises rates"]
        assert is_duplicate("", existing) is False

    def test_empty_existing_list(self):
        assert is_duplicate("Fed raises rates", []) is False

    def test_custom_threshold(self):
        existing = ["Fed raises interest rates"]
        assert is_duplicate("Fed raises rates", existing, threshold=0.5) is True
        assert is_duplicate("Fed raises rates", existing, threshold=0.99) is False