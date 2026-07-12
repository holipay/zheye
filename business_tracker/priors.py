"""
先验概率计算
支持从市场数据推导先验，以及默认先验
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_tracker.bayesian import DEFAULT_DIMENSIONS, BeliefState
from models.market_data import MarketData

logger = logging.getLogger(__name__)


async def prior_from_market_data(
    session: AsyncSession,
    stock_symbol: str,
) -> dict[str, BeliefState]:
    priors = {}
    for dim in DEFAULT_DIMENSIONS:
        priors[dim] = default_prior(dim)

    if not stock_symbol:
        return priors

    try:
        async with session.begin_nested():
            result = await session.execute(
                select(MarketData)
                .where(MarketData.data_type == "stock")
                .where(MarketData.symbol == stock_symbol)
                .order_by(MarketData.timestamp.desc())
                .limit(30)
            )
            rows = result.scalars().all()

            if len(rows) >= 2:
                values = [float(r.value) for r in rows]
                recent_avg = sum(values[:5]) / min(len(values[:5]), 5)
                overall_avg = sum(values) / len(values)

                if overall_avg > 0 and recent_avg > 0:
                    ratio = recent_avg / overall_avg
                    if ratio > 1.05:
                        alpha, beta = 6.0, 2.0
                    elif ratio > 0.95:
                        alpha, beta = 4.0, 3.0
                    else:
                        alpha, beta = 3.0, 5.0
                    priors["financial_health"] = BeliefState(alpha=alpha, beta=beta)
                    logger.info(
                        f"Prior for {stock_symbol}: financial_health=({alpha}, {beta}), "
                        f"mean={alpha/(alpha+beta):.3f}"
                    )
    except Exception as e:
        logger.warning(f"Failed to compute market prior for {stock_symbol}: {e}")

    return priors


def default_prior(dimension: str) -> BeliefState:
    params = {
        "financial_health": (3.0, 3.0),
        "brand_reputation": (2.5, 2.5),
        "competitive_position": (2.5, 2.5),
        "compliance_risk": (2.0, 3.0),
    }
    a, b = params.get(dimension, (2.0, 2.0))
    return BeliefState(alpha=a, beta=b)
