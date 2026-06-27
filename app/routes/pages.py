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
    ctx = get_template_context(request, title=get_text(lang, "nav.analysis"), report_date=date.today().isoformat())
    return templates.TemplateResponse(request=request, name="index.html", context=ctx)

@router.get("/{lang}/articles")
async def articles(request: Request, lang: str, sort: str = "date", page: int = 1):
    lang = validate_lang(lang)
    ctx = get_template_context(request, title=get_text(lang, "articles.title"), sort=sort, page=page)
    return templates.TemplateResponse(request=request, name="articles.html", context=ctx)


@router.get("/{lang}/events")
async def events(request: Request, lang: str, days: int = 7, category: str = None):
    lang = validate_lang(lang)
    ctx = get_template_context(request, title=get_text(lang, "nav.events"), days=days, category=category)
    return templates.TemplateResponse(request=request, name="events.html", context=ctx)


@router.get("/{lang}/events/{event_id}")
async def event_detail(request: Request, lang: str, event_id: str):
    lang = validate_lang(lang)
    ctx = get_template_context(request, title=get_text(lang, "nav.events"), event_id=event_id,
                              deep_analyst_enabled=settings.ENABLE_DEEP_ANALYST)
    return templates.TemplateResponse(request=request, name="event_detail.html", context=ctx)
