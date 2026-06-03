from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import logging
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

# 速率限制器
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="zheye", description="全球新闻聚合与 AI 分析平台")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

from app.routes import pages, api_news, api_analysis, api_events, admin, charts
app.include_router(api_news.router)
app.include_router(api_analysis.router)
app.include_router(api_events.router)
app.include_router(pages.router)
app.include_router(admin.router)
app.include_router(charts.router)


@app.get("/health")
@limiter.exempt  # 健康检查不限速
async def health(request: Request):
    """健康检查端点，检测数据库连接"""
    checks = {"status": "ok", "database": "unknown"}
    
    try:
        from models.base import async_session
        from sqlalchemy import text
        
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            checks["database"] = "connected"
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        checks["status"] = "degraded"
        checks["database"] = "error"
    
    status_code = 200 if checks["status"] == "ok" else 503
    return JSONResponse(content=checks, status_code=status_code)
