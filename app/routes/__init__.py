from app.routes.pages import router as pages_router
from app.routes.api_news import router as api_news_router
from app.routes.api_analysis import router as api_analysis_router
from app.routes.api_events import router as api_events_router

__all__ = ["pages_router", "api_news_router", "api_analysis_router", "api_events_router"]
