from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from pathlib import Path
from datetime import date
from app.i18n import get_text, get_language_from_request, DEFAULT_LANGUAGE

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _get_template_context(request: Request, **kwargs):
    lang = get_language_from_request(request)
    def t(key: str, **fmt_kwargs) -> str:
        return get_text(lang, key, **fmt_kwargs)
    return {"lang": lang, "t": t, "request": request, **kwargs}


@router.get("/")
async def root(request: Request):
    return RedirectResponse(url=f"/{DEFAULT_LANGUAGE}")


@router.get("/{lang}")
async def index(request: Request, lang: str):
    if lang not in {"en", "zh"}:
        return RedirectResponse(url=f"/{DEFAULT_LANGUAGE}")
    ctx = _get_template_context(request, title=get_text(lang, "nav.home"))
    return templates.TemplateResponse(request=request, name="index.html", context=ctx)


@router.get("/{lang}/news")
async def news(request: Request, lang: str, category: str = "all", article_type: str = "all", keyword_id: int = None, sort: str = "date", page: int = 1):
    if lang not in {"en", "zh"}:
        return RedirectResponse(url=f"/{DEFAULT_LANGUAGE}/news")
    ctx = _get_template_context(request, title=get_text(lang, "nav.news"), category=category, article_type=article_type, keyword_id=keyword_id, sort=sort, page=page)
    return templates.TemplateResponse(request=request, name="news.html", context=ctx)


@router.get("/{lang}/articles")
async def articles(request: Request, lang: str):
    if lang not in {"en", "zh"}:
        return RedirectResponse(url=f"/{DEFAULT_LANGUAGE}/articles")
    ctx = _get_template_context(request, title=get_text(lang, "nav.news"))
    return templates.TemplateResponse(request=request, name="articles.html", context=ctx)


@router.get("/{lang}/analysis")
async def analysis(request: Request, lang: str):
    if lang not in {"en", "zh"}:
        return RedirectResponse(url=f"/{DEFAULT_LANGUAGE}/analysis")
    ctx = _get_template_context(request, title=get_text(lang, "nav.analysis"), report_date=date.today().isoformat())
    return templates.TemplateResponse(request=request, name="analysis.html", context=ctx)


@router.get("/{lang}/news/{news_id}")
async def news_detail(request: Request, lang: str, news_id: int):
    if lang not in {"en", "zh"}:
        return RedirectResponse(url=f"/{DEFAULT_LANGUAGE}/news/{news_id}")
    ctx = _get_template_context(request, title=get_text(lang, "nav.news"), news_id=news_id)
    return templates.TemplateResponse(request=request, name="news_detail.html", context=ctx)


@router.get("/{lang}/events")
async def events(request: Request, lang: str, category: str = None, days: int = 7):
    if lang not in {"en", "zh"}:
        return RedirectResponse(url=f"/{DEFAULT_LANGUAGE}/events")
    ctx = _get_template_context(request, title=get_text(lang, "nav.events"), category=category, days=days)
    return templates.TemplateResponse(request=request, name="events.html", context=ctx)


@router.get("/{lang}/events/{event_id}")
async def event_detail(request: Request, lang: str, event_id: str):
    if lang not in {"en", "zh"}:
        return RedirectResponse(url=f"/{DEFAULT_LANGUAGE}/events/{event_id}")
    ctx = _get_template_context(request, title=get_text(lang, "nav.events"), event_id=event_id)
    return templates.TemplateResponse(request=request, name="event_detail.html", context=ctx)
