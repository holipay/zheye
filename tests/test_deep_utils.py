"""deep_analyst/utils.py 工具函数测试"""

from tests.deep_analyst_test_helper import ensure_deep_analyst_imports
ensure_deep_analyst_imports()

from deep_analyst.utils import smart_truncate, parse_ai_response, format_article_summaries, text_similarity
from deep_analyst.knowledge import _format_existing_atoms


class TestSmartTruncate:
    def test_short_text_unchanged(self):
        text = "这是一段短文本。"
        assert smart_truncate(text, max_len=100) == text

    def test_truncate_at_sentence_boundary(self):
        text = "第一句话。第二句话。第三句话需要被截断因为超过了长度限制。"
        result = smart_truncate(text, max_len=20)
        assert len(result) <= 20
        # Should find a sentence boundary (。) and cut there
        # If no good boundary found, falls back to exact truncation

    def test_truncate_at_period(self):
        text = "First sentence. Second sentence. Third sentence is too long."
        result = smart_truncate(text, max_len=30)
        assert len(result) <= 30

    def test_truncate_at_newline(self):
        text = "Line one\nLine two\nLine three that is very long and needs cutting"
        result = smart_truncate(text, max_len=25)
        assert len(result) <= 25

    def test_empty_text(self):
        assert smart_truncate("", max_len=100) == ""

    def test_exact_length(self):
        text = "a" * 100
        assert smart_truncate(text, max_len=100) == text

    def test_threshold_parameter(self):
        text = "。" + "b" * 50 + "。" + "c" * 50
        result = smart_truncate(text, max_len=30, threshold=0.6)
        assert len(result) <= 30


class TestParseAiResponse:
    def test_none_input(self):
        assert parse_ai_response(None) is None

    def test_empty_string(self):
        assert parse_ai_response("") is None

    def test_json_in_code_block(self):
        response = '```json\n{"key": "value"}\n```'
        result = parse_ai_response(response)
        assert result == {"key": "value"}

    def test_json_in_code_block_no_lang(self):
        response = '```\n{"key": "value"}\n```'
        result = parse_ai_response(response)
        assert result == {"key": "value"}

    def test_bare_json_object(self):
        response = 'Here is the result: {"key": "value"} done.'
        result = parse_ai_response(response)
        assert result == {"key": "value"}

    def test_bare_json_array(self):
        response = 'Result: [1, 2, 3]'
        result = parse_ai_response(response)
        assert result == [1, 2, 3]

    def test_trailing_comma_removal(self):
        response = '{"key": "value", "list": [1, 2,],}'
        result = parse_ai_response(response)
        assert result is not None
        assert result["key"] == "value"

    def test_single_line_comment_removal(self):
        response = '{\n"key": "value" // comment\n}'
        result = parse_ai_response(response)
        assert result is not None
        assert result["key"] == "value"

    def test_invalid_json_returns_none(self):
        response = "This is not JSON at all"
        result = parse_ai_response(response)
        assert result is None

    def test_multiple_code_blocks_takes_last(self):
        response = '```json\n{"old": true}\n```\nSome text\n```json\n{"new": true}\n```'
        result = parse_ai_response(response)
        assert result == {"new": True}


class TestFormatArticleSummaries:
    def test_basic_formatting(self):
        articles = [
            {"title": "Article 1", "summary": "Summary 1"},
            {"title": "Article 2", "summary": "Summary 2"},
        ]
        result = format_article_summaries(articles)
        assert "1. Article 1 - Summary 1" in result
        assert "2. Article 2 - Summary 2" in result

    def test_max_articles_limit(self):
        articles = [{"title": f"Article {i}", "summary": f"Summary {i}"} for i in range(10)]
        result = format_article_summaries(articles, max_articles=3)
        assert "Article 0" in result
        assert "Article 3" not in result

    def test_empty_articles(self):
        result = format_article_summaries([])
        assert result == "无相关文章"

    def test_missing_summary_uses_title(self):
        articles = [{"title": "Only Title"}]
        result = format_article_summaries(articles)
        assert "Only Title" in result


class TestTextSimilarity:
    def test_identical_strings(self):
        assert text_similarity("hello", "hello") == 1.0

    def test_case_insensitive(self):
        assert text_similarity("Hello", "hello") == 1.0

    def test_whitespace_handling(self):
        assert text_similarity("  hello  ", "hello") == 1.0

    def test_empty_strings(self):
        assert text_similarity("", "hello") == 0.0
        assert text_similarity(None, "hello") == 0.0

    def test_similar_strings(self):
        score = text_similarity("Fed raises rates", "Fed raises interest rates")
        assert 0.5 < score < 1.0

    def test_different_strings(self):
        score = text_similarity("hello", "world")
        assert score < 0.5


class TestFormatExistingAtoms:
    def test_basic_formatting(self):
        atoms = [
            {"id": 1, "atom_type": "definition", "title": "什么是基点", "content": "基点是利率的计量单位...", "entities": ["美联储"], "keywords": ["利率"], "relevance_score": 0.5},
        ]
        result = _format_existing_atoms(atoms)
        assert "ID:1" in result
        assert "什么是基点" in result
        assert "definition" in result

    def test_filters_low_relevance(self):
        atoms = [
            {"id": 1, "atom_type": "definition", "title": "高相关", "content": "内容", "entities": [], "keywords": [], "relevance_score": 0.5},
            {"id": 2, "atom_type": "definition", "title": "低相关", "content": "内容", "entities": [], "keywords": [], "relevance_score": 0.1},
        ]
        result = _format_existing_atoms(atoms)
        assert "高相关" in result
        assert "低相关" not in result

    def test_empty_list(self):
        result = _format_existing_atoms([])
        assert result == "无"

    def test_entities_display(self):
        atoms = [
            {"id": 1, "atom_type": "background", "title": "美联储政策", "content": "详细内容...", "entities": ["美联储", "鲍威尔"], "keywords": [], "relevance_score": 0.6},
        ]
        result = _format_existing_atoms(atoms)
        assert "美联储" in result
        assert "鲍威尔" in result

    def test_content_truncation(self):
        atoms = [
            {"id": 1, "atom_type": "context", "title": "标题", "content": "A" * 500, "entities": [], "keywords": [], "relevance_score": 0.5},
        ]
        result = _format_existing_atoms(atoms)
        # Content should be truncated to 150 chars + "..."
        assert "A" * 200 not in result
        assert "..." in result
