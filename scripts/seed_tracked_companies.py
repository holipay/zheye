"""
从 tracked_companies.yaml 读取企业配置，同步到数据库
需要在 entities.yaml 中已存在对应的企业实体
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from sqlalchemy import select

from business_tracker.bayesian import DEFAULT_DIMENSIONS
from business_tracker.models.company import TrackedCompany
from business_tracker.models.dimension import CompanyDimension
from business_tracker.priors import default_prior, prior_from_market_data
from models.base import async_session
from models.entity import Entity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _process_company(session, company_cfg):
    entity_name = company_cfg.get("entity_name")
    stock_symbol = company_cfg.get("stock_symbol", "")
    use_llm = company_cfg.get("use_llm", False)

    result = await session.execute(
        select(Entity).where(
            Entity.name == entity_name,
            Entity.entity_type == "company",
        )
    )
    entity = result.scalar_one_or_none()

    if not entity:
        logger.warning(f"Entity '{entity_name}' not found in database. Skip.")
        return

    existing = await session.execute(
        select(TrackedCompany).where(TrackedCompany.entity_id == entity.id)
    )
    tracked = existing.scalar_one_or_none()

    if tracked:
        tracked.is_active = True
        if stock_symbol or use_llm:
            cfg = tracked.config or {}
            if stock_symbol:
                cfg["stock_symbol"] = stock_symbol
            if use_llm:
                cfg["use_llm"] = use_llm
            tracked.config = cfg
        logger.info(f"Updated tracked company: {entity_name}")
    else:
        tracked = TrackedCompany(
            entity_id=entity.id,
            is_active=True,
            config={"stock_symbol": stock_symbol, "use_llm": use_llm},
        )
        session.add(tracked)
        await session.flush()

        priors = await prior_from_market_data(session, stock_symbol)
        for dim in DEFAULT_DIMENSIONS:
            state = priors.get(dim, default_prior(dim))
            cd = CompanyDimension(
                company_id=tracked.id,
                dimension=dim,
                alpha=state.alpha,
                beta=state.beta,
                mean=state.mean,
                variance=state.variance,
                updated_by="prior",
            )
            session.add(cd)

        logger.info(f"Created tracked company: {entity_name}")


async def main(config_path: str = "configs/tracked_companies.yaml"):
    config_file = Path(__file__).parent.parent / config_path
    if not config_file.exists():
        logger.warning(f"Config file not found: {config_file}")
        return

    with open(config_file) as f:
        config = yaml.safe_load(f)

    companies = config.get("companies", [])
    if not companies:
        logger.info("No companies in config")
        return

    async with async_session() as session:
        for company_cfg in companies:
            try:
                async with session.begin_nested():
                    await _process_company(session, company_cfg)
            except Exception as e:
                logger.warning(
                    f"Failed to process company {company_cfg.get('entity_name')}: {e}"
                )
                continue
        await session.commit()
        logger.info(f"Synced {len(companies)} companies from config")


if __name__ == "__main__":
    path_arg = sys.argv[1] if len(sys.argv) > 1 else "configs/tracked_companies.yaml"
    asyncio.run(main(path_arg))
