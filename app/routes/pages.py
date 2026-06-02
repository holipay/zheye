from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import date

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"title": "AI 分析"})


@router.get("/news")
async def news(request: Request, category: str = "all", article_type: str = "all", keyword_id: int = None, sort: str = "date", page: int = 1):
    return templates.TemplateResponse(request=request, name="news.html", context={
        "title": "新闻",
        "category": category,
        "article_type": article_type,
        "keyword_id": keyword_id,
        "sort": sort,
        "page": page,
    })


@router.get("/articles")
async def articles(request: Request):
    return templates.TemplateResponse(request=request, name="articles.html", context={"title": "文章"})


@router.get("/analysis")
async def analysis(request: Request):
    return templates.TemplateResponse(request=request, name="analysis.html", context={
        "title": "每日分析报告",
        "report_date": date.today().isoformat(),
    })


@router.get("/news/{news_id}")
async def news_detail(request: Request, news_id: int):
    return templates.TemplateResponse(request=request, name="news_detail.html", context={
        "title": "新闻详情",
        "news_id": news_id,
    })
