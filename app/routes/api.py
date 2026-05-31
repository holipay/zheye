from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import select, func, desc
from models.base import async_session
from models.news import News

router = APIRouter(prefix="/api")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/news", response_class=HTMLResponse)
async def get_news(request: Request, category: str = "all", page: int = 1):
    page_size = 20
    offset = (page - 1) * page_size
    
    async with async_session() as session:
        query = select(News).order_by(desc(News.created_at))
        
        if category and category != "all":
            query = query.where(News.category == category)
        
        count_query = select(func.count(News.id))
        if category and category != "all":
            count_query = count_query.where(News.category == category)
        
        total_result = await session.execute(count_query)
        total = total_result.scalar()
        
        query = query.offset(offset).limit(page_size)
        result = await session.execute(query)
        news_items = result.scalars().all()
        
        total_pages = (total + page_size - 1) // page_size
    
    return templates.TemplateResponse("partials/news_list.html", {
        "request": request,
        "news_items": news_items,
        "category": category,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@router.get("/categories", response_class=HTMLResponse)
async def get_categories(request: Request):
    async with async_session() as session:
        query = select(News.category, func.count(News.id)).group_by(News.category).order_by(desc(func.count(News.id)))
        result = await session.execute(query)
        categories = result.all()
    
    return templates.TemplateResponse("partials/categories.html", {
        "request": request,
        "categories": categories,
    })


@router.get("/latest", response_class=HTMLResponse)
async def get_latest(request: Request, limit: int = 10):
    async with async_session() as session:
        query = select(News).order_by(desc(News.created_at)).limit(limit)
        result = await session.execute(query)
        news_items = result.scalars().all()
    
    return templates.TemplateResponse("partials/news_list.html", {
        "request": request,
        "news_items": news_items,
        "category": "all",
        "page": 1,
        "total_pages": 1,
        "total": len(news_items),
    })


@router.get("/meta")
async def get_meta():
    async with async_session() as session:
        count_result = await session.execute(select(func.count(News.id)))
        total = count_result.scalar()
        
        source_query = select(News.source, func.count(News.id)).group_by(News.source).order_by(desc(func.count(News.id)))
        source_result = await session.execute(source_query)
        sources = [{"name": row[0], "count": row[1]} for row in source_result.all()]
        
        category_query = select(News.category, func.count(News.id)).group_by(News.category).order_by(desc(func.count(News.id)))
        category_result = await session.execute(category_query)
        categories = [{"name": row[0], "count": row[1]} for row in category_result.all()]
    
    return {
        "total": total,
        "sources": sources,
        "categories": categories,
    }
