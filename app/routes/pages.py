from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from pathlib import Path
from datetime import date
from app.i18n import get_text, DEFAULT_LANGUAGE
from app.context import get_template_context
from app.config import settings

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

VALID_LANGUAGES = {"en", "zh"}


def validate_lang(lang: str) -> str:
    """
    验证语言参数
    
    Args:
        lang: 语言代码
    
    Returns:
        有效的语言代码
    
    Raises:
        RedirectResponse: 语言无效时重定向到默认语言
    """
    if lang not in VALID_LANGUAGES:
        return DEFAULT_LANGUAGE
    return lang


@router.get("/")
async def root(request: Request):
    return RedirectResponse(url=f"/{DEFAULT_LANGUAGE}")


@router.get("/{lang}")
async def index(request: Request, lang: str):
    lang = validate_lang(lang)
    ctx = get_template_context(request, title=get_text(lang, "nav.home"))
    return templates.TemplateResponse(request=request, name="index.html", context=ctx)


@router.get("/{lang}/news")
async def news(request: Request, lang: str, category: str = "all", article_type: str = "all", keyword_id: int = None, sort: str = "date", page: int = 1):
    lang = validate_lang(lang)
    ctx = get_template_context(request, title=get_text(lang, "nav.news"), category=category, article_type=article_type, keyword_id=keyword_id, sort=sort, page=page)
    return templates.TemplateResponse(request=request, name="news.html", context=ctx)


@router.get("/{lang}/articles")
async def articles(request: Request, lang: str):
    lang = validate_lang(lang)
    ctx = get_template_context(request, title=get_text(lang, "nav.news"))
    return templates.TemplateResponse(request=request, name="articles.html", context=ctx)


@router.get("/{lang}/analysis")
async def analysis(request: Request, lang: str):
    lang = validate_lang(lang)
    ctx = get_template_context(request, title=get_text(lang, "nav.analysis"), report_date=date.today().isoformat())
    return templates.TemplateResponse(request=request, name="analysis.html", context=ctx)


@router.get("/{lang}/news/{news_id}")
async def news_detail(request: Request, lang: str, news_id: int):
    lang = validate_lang(lang)
    ctx = get_template_context(request, title=get_text(lang, "nav.news"), news_id=news_id)
    return templates.TemplateResponse(request=request, name="news_detail.html", context=ctx)


@router.get("/{lang}/events")
async def events(request: Request, lang: str):
    lang = validate_lang(lang)
    ctx = get_template_context(request, title=get_text(lang, "nav.events"))
    return templates.TemplateResponse(request=request, name="events.html", context=ctx)


@router.get("/{lang}/events/{event_id}")
async def event_detail(request: Request, lang: str, event_id: str):
    lang = validate_lang(lang)
    ctx = get_template_context(request, title=get_text(lang, "nav.events"), event_id=event_id,
                              deep_analyst_enabled=settings.ENABLE_DEEP_ANALYST)
    return templates.TemplateResponse(request=request, name="event_detail.html", context=ctx)
