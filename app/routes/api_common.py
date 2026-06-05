from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
from models.base import get_session
from models.event import Event
from app.context import get_api_context
from app.config import settings
from app.errors import ErrorMessages as Err
from app.main import limiter

router = APIRouter(prefix="/api")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# 为了向后兼容，保留旧的函数名
_get_api_context = get_api_context


async def _get_event_and_articles(session: AsyncSession, event_id: str, max_articles: int = 5):
    """
    获取事件及其关联文章（公共辅助函数）
    
    Returns:
        (event, event_data, articles) 或抛出 HTTPException
    """
    result = await session.execute(select(Event).where(Event.event_id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail=Err.EVENT_NOT_FOUND)
    
    articles = []
    if event.related_articles:
        for article_ref in event.related_articles[:max_articles]:
            if isinstance(article_ref, dict):
                articles.append(article_ref)
    
    event_data = {
        "title": event.title,
        "description": event.description,
        "category": event.category,
    }
    
    return event, event_data, articles
