"""
企业经营状况跟踪路由
提供 Dashboard 页面和 JSON API
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_admin_credentials
from app.cache import get_cached, invalidate_cache, set_cached
from app.context import get_template_context
from business_tracker.bayesian import (
    DIMENSION_LABELS,
    DIMENSION_LABELS_EN,
    beta_credible_interval,
    beta_std,
)
from business_tracker.models.company import TrackedCompany
from business_tracker.models.dimension import CompanyDimension
from business_tracker.models.evidence import EvidenceRecord
from business_tracker.models.history import BeliefHistory
from business_tracker.pipeline import process_company
from models.base import get_session
from models.entity import Entity
from models.news import News

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/business-tracker", tags=["business-tracker"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _build_dimension_dict(dim: CompanyDimension) -> dict:
    lower, upper = beta_credible_interval(dim.alpha, dim.beta)
    return {
        "dimension": dim.dimension,
        "label": DIMENSION_LABELS.get(dim.dimension, dim.dimension),
        "label_en": DIMENSION_LABELS_EN.get(dim.dimension, dim.dimension),
        "alpha": round(dim.alpha, 4),
        "beta": round(dim.beta, 4),
        "mean": round(dim.mean, 4),
        "mean_pct": round(dim.mean * 100, 1),
        "variance": round(dim.variance, 6),
        "std": round(beta_std(dim.alpha, dim.beta), 4),
        "ci_lower": round(lower, 4),
        "ci_upper": round(upper, 4),
        "ci_lower_pct": round(lower * 100, 1),
        "ci_upper_pct": round(upper * 100, 1),
        "updated_at": dim.updated_at,
        "updated_by": dim.updated_by,
    }


# ============================================================
# 页面路由
# ============================================================

@router.get("/companies", response_class=HTMLResponse)
async def companies_dashboard(
    request: Request,
    session: AsyncSession = Depends(get_session),
    lang: str = "zh",
):
    """企业经营状况 Dashboard 页面"""
    cache_key = f"bt:dashboard:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    result = await session.execute(
        select(TrackedCompany).where(TrackedCompany.is_active.is_(True))
    )
    companies = result.scalars().all()

    companies_data = []
    for tc in companies:
        entity_result = await session.execute(
            select(Entity).where(Entity.id == tc.entity_id)
        )
        entity = entity_result.scalar_one_or_none()
        company_name = entity.name if entity else f"Company({tc.entity_id})"

        dim_result = await session.execute(
            select(CompanyDimension).where(CompanyDimension.company_id == tc.id)
        )
        dims = dim_result.scalars().all()

        companies_data.append({
            "id": tc.id,
            "entity_id": tc.entity_id,
            "company_name": company_name,
            "dimensions": [_build_dimension_dict(d) for d in dims],
            "updated_at": tc.updated_at,
        })

    ctx = get_template_context(request,
        companies=companies_data,
    )
    response = templates.TemplateResponse(
        request=request,
        name="business_tracker/dashboard.html",
        context=ctx,
    )
    set_cached(cache_key, response.body.decode(), ttl=120)
    return response


@router.get("/companies/{company_id}", response_class=HTMLResponse)
async def company_detail(
    request: Request,
    company_id: int,
    session: AsyncSession = Depends(get_session),
    lang: str = "zh",
):
    """单个企业经营状况详情页面"""
    cache_key = f"bt:company:{company_id}:{lang}"
    cached = get_cached(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    result = await session.execute(
        select(TrackedCompany).where(TrackedCompany.id == company_id)
    )
    tc = result.scalar_one_or_none()
    if not tc:
        raise HTTPException(status_code=404, detail="Company not found")

    entity_result = await session.execute(
        select(Entity).where(Entity.id == tc.entity_id)
    )
    entity = entity_result.scalar_one_or_none()
    company_name = entity.name if entity else f"Company({tc.entity_id})"

    dim_result = await session.execute(
        select(CompanyDimension).where(CompanyDimension.company_id == company_id)
    )
    dims = dim_result.scalars().all()

    # 获取信念历史用于图表
    history_data = {}
    for dim in dims:
        hist_result = await session.execute(
            select(BeliefHistory)
            .where(
                BeliefHistory.company_id == company_id,
                BeliefHistory.dimension == dim.dimension,
            )
            .order_by(BeliefHistory.recorded_at.asc())
            .limit(500)
        )
        history_data[dim.dimension] = [
            {
                "recorded_at": h.recorded_at.isoformat() if h.recorded_at else "",
                "mean": round(h.mean, 4),
                "variance": round(h.variance, 6),
                "ci_lower": round(beta_credible_interval(h.alpha, h.beta)[0], 4),
                "ci_upper": round(beta_credible_interval(h.alpha, h.beta)[1], 4),
            }
            for h in hist_result.scalars().all()
        ]

    # 获取最近证据
    ev_result = await session.execute(
        select(EvidenceRecord)
        .where(EvidenceRecord.company_id == company_id)
        .order_by(desc(EvidenceRecord.created_at))
        .limit(50)
    )
    evidence_list = []
    for ev in ev_result.scalars().all():
        news_result = await session.execute(
            select(News).where(News.id == ev.news_id)
        )
        news = news_result.scalar_one_or_none()
        evidence_list.append({
            "id": ev.id,
            "news_id": ev.news_id,
            "news_title": news.title if news else "",
            "dimension": ev.dimension,
            "dimension_label": DIMENSION_LABELS.get(ev.dimension, ev.dimension),
            "direction": ev.direction,
            "strength": round(ev.strength, 3),
            "confidence": round(ev.confidence, 3),
            "source": ev.source,
            "created_at": ev.created_at,
        })

    dims_data = [_build_dimension_dict(d) for d in dims]

    ctx = get_template_context(request, include_csrf=True,
        company_id=company_id,
        company_name=company_name,
        dimensions=dims_data,
        history=history_data,
        recent_evidence=evidence_list,
    )
    response = templates.TemplateResponse(
        request=request,
        name="business_tracker/company_detail.html",
        context=ctx,
    )
    set_cached(cache_key, response.body.decode(), ttl=120)
    return response


# ============================================================
# JSON API
# ============================================================

@router.get("/api/companies")
async def api_companies(
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(TrackedCompany).where(TrackedCompany.is_active.is_(True))
    )
    companies = result.scalars().all()

    data = []
    for tc in companies:
        entity_result = await session.execute(
            select(Entity).where(Entity.id == tc.entity_id)
        )
        entity = entity_result.scalar_one_or_none()

        dim_result = await session.execute(
            select(CompanyDimension).where(CompanyDimension.company_id == tc.id)
        )
        dims = dim_result.scalars().all()

        data.append({
            "id": tc.id,
            "entity_id": tc.entity_id,
            "company_name": entity.name if entity else None,
            "dimensions": [_build_dimension_dict(d) for d in dims],
            "updated_at": tc.updated_at.isoformat() if tc.updated_at else None,
        })

    return {"companies": data}


@router.get("/api/companies/{company_id}/belief-history")
async def api_belief_history(
    company_id: int,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=500, le=1000),
):
    result = await session.execute(
        select(TrackedCompany).where(TrackedCompany.id == company_id)
    )
    tc = result.scalar_one_or_none()
    if not tc:
        raise HTTPException(status_code=404, detail="Company not found")

    dim_result = await session.execute(
        select(CompanyDimension).where(CompanyDimension.company_id == company_id)
    )
    dims = dim_result.scalars().all()

    history = {}
    for dim in dims:
        hist_result = await session.execute(
            select(BeliefHistory)
            .where(
                BeliefHistory.company_id == company_id,
                BeliefHistory.dimension == dim.dimension,
            )
            .order_by(BeliefHistory.recorded_at.asc())
            .limit(limit)
        )
        history[dim.dimension] = [
            {
                "recorded_at": h.recorded_at.isoformat() if h.recorded_at else "",
                "mean": round(h.mean, 4),
                "variance": round(h.variance, 6),
                "alpha": round(h.alpha, 4),
                "beta": round(h.beta, 4),
            }
            for h in hist_result.scalars().all()
        ]

    return {"company_id": company_id, "history": history}


# ============================================================
# 管理操作
# ============================================================

@router.post("/api/companies/{company_id}/update")
async def trigger_company_update(
    company_id: int,
    _: bool = Depends(verify_admin_credentials),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(TrackedCompany).where(TrackedCompany.id == company_id)
    )
    tc = result.scalar_one_or_none()
    if not tc:
        raise HTTPException(status_code=404, detail="Company not found")

    await process_company(session, tc)
    await session.commit()
    invalidate_cache(f"bt:company:{company_id}")
    invalidate_cache("bt:dashboard")

    return {"status": "ok", "company_id": company_id}
