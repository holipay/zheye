import pytest
from unittest.mock import MagicMock
from app.context import get_template_context, get_api_context


@pytest.fixture
def mock_request():
    """创建模拟的 Request 对象"""
    request = MagicMock()
    request.query_params = {}
    request.headers = {"accept-language": "zh-CN,zh;q=0.9"}
    return request


class TestGetTemplateContext:
    def test_basic_context(self, mock_request):
        result = get_template_context(mock_request)
        assert "lang" in result
        assert "t" in result
        assert "request" in result
        assert callable(result["t"])

    def test_with_kwargs(self, mock_request):
        result = get_template_context(mock_request, title="Test", page=1)
        assert result["title"] == "Test"
        assert result["page"] == 1

    def test_lang_from_query_params(self, mock_request):
        mock_request.query_params = {"lang": "en"}
        result = get_template_context(mock_request)
        assert result["lang"] == "en"

    def test_csrf_token(self, mock_request):
        result = get_template_context(mock_request, include_csrf=True)
        assert "csrf_token" in result
        assert isinstance(result["csrf_token"], str)
        assert len(result["csrf_token"]) > 0

    def test_no_csrf_token_by_default(self, mock_request):
        result = get_template_context(mock_request)
        assert "csrf_token" not in result


class TestGetApiContext:
    def test_basic_context(self, mock_request):
        result = get_api_context(mock_request)
        assert "lang" in result
        assert "t" in result
        assert "request" not in result  # API context 不包含 request

    def test_with_kwargs(self, mock_request):
        result = get_api_context(mock_request, items=[1, 2, 3])
        assert result["items"] == [1, 2, 3]

    def test_t_function(self, mock_request):
        result = get_api_context(mock_request)
        t = result["t"]
        # 测试翻译函数可调用
        assert callable(t)
