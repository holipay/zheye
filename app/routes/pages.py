from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "AI 分析"})


@router.get("/news")
async def news(request: Request, category: str = "all", page: int = 1):
    return templates.TemplateResponse("news.html", {
        "request": request,
        "title": "新闻",
        "category": category,
        "page": page,
    })


@router.get("/articles")
async def articles(request: Request):
    return templates.TemplateResponse("articles.html", {"request": request, "title": "文章"})
