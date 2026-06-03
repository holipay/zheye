"""
共享模板上下文构建模块
统一各路由模块的上下文构建逻辑
"""

from fastapi import Request
from app.i18n import get_text, get_language_from_request
from app.csrf import generate_csrf_token, sign_token


def get_template_context(request: Request, include_csrf: bool = False, **kwargs):
    """
    构建模板上下文
    
    Args:
        request: FastAPI 请求对象
        include_csrf: 是否包含 CSRF token（管理后台需要）
        **kwargs: 额外的上下文变量
    
    Returns:
        模板上下文字典
    """
    # 优先从查询参数中获取语言
    lang = request.query_params.get("lang")
    if not lang:
        lang = get_language_from_request(request)
    
    def t(key: str, **fmt_kwargs) -> str:
        return get_text(lang, key, **fmt_kwargs)
    
    context = {"lang": lang, "t": t, "request": request, **kwargs}
    
    if include_csrf:
        context["csrf_token"] = sign_token(generate_csrf_token())
    
    return context


def get_api_context(request: Request, **kwargs):
    """
    构建 API 模板上下文（不含 request）
    
    Args:
        request: FastAPI 请求对象
        **kwargs: 额外的上下文变量
    
    Returns:
        模板上下文字典
    """
    # 优先从查询参数中获取语言
    lang = request.query_params.get("lang")
    if not lang:
        lang = get_language_from_request(request)
    
    def t(key: str, **fmt_kwargs) -> str:
        return get_text(lang, key, **fmt_kwargs)
    
    return {"lang": lang, "t": t, **kwargs}
