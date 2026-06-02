from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path

app = FastAPI(title="zheye", description="全球新闻聚合与 AI 分析平台")

app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

from app.routes import pages, api, admin, charts
app.include_router(pages.router)
app.include_router(api.router)
app.include_router(admin.router)
app.include_router(charts.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
