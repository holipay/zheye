from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import logging
import warnings
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.lifespan import lifespan

# 统一日志配置
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# 启动配置检查
if not settings.ADMIN_PASSWORD:
    warnings.warn(
        "ADMIN_PASSWORD is not set. Admin panel will be disabled. "
        "Set ADMIN_PASSWORD environment variable to enable admin features.",
        UserWarning,
        stacklevel=1,
    )
    logger.warning("ADMIN_PASSWORD is not set. Admin panel will be disabled.")

if not settings.CSRF_SECRET_KEY and not settings.ADMIN_PASSWORD:
    warnings.warn(
        "CSRF_SECRET_KEY and ADMIN_PASSWORD are both not set. "
        "CSRF protection will not work properly. "
        "Set at least one of these environment variables.",
        UserWarning,
        stacklevel=1,
    )
    logger.warning("CSRF_SECRET_KEY and ADMIN_PASSWORD are both not set.")

# 速率限制器
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="zheye", description="全球新闻聚合与 AI 分析平台", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

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

from app.routes import pages, api_news, api_analysis, api_events, admin, charts
app.include_router(api_news.router)
app.include_router(api_analysis.router)
app.include_router(api_events.router)
app.include_router(pages.router)
app.include_router(admin.router)
app.include_router(charts.router)

# 深度分析模块（可选）
if settings.ENABLE_DEEP_ANALYST:
    try:
        from deep_analyst.router import router as deep_analyst_router
        app.include_router(deep_analyst_router)
        logger.info("Deep Analyst module enabled")
    except Exception as e:
        logger.warning(f"Failed to load Deep Analyst module: {e}")

# 企业经营状况跟踪模块（可选）
if settings.ENABLE_BUSINESS_TRACKER:
    try:
        from business_tracker.router import router as business_tracker_router
        app.include_router(business_tracker_router)
        logger.info("Business Tracker module enabled")
    except Exception as e:
        logger.warning(f"Failed to load Business Tracker module: {e}")
