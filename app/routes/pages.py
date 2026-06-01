from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"title": "AI 分析"})


@router.get("/news")
async def news(request: Request, category: str = "all", keyword_id: int = None, sort: str = "date", page: int = 1):
    return templates.TemplateResponse(request=request, name="news.html", context={
        "title": "新闻",
        "category": category,
        "keyword_id": keyword_id,
        "sort": sort,
        "page": page,
    })


@router.get("/articles")
async def articles(request: Request):
    return templates.TemplateResponse(request=request, name="articles.html", context={"title": "文章"})
