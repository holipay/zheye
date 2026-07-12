"""
信念更新脚本
定时运行，遍历所有活跃的跟踪企业，拉取未处理的新闻并执行贝叶斯更新
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from business_tracker.pipeline import process_all_companies

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting belief update for all tracked companies")
    try:
        await process_all_companies()
        logger.info("Belief update completed successfully")
    except Exception as e:
        logger.error(f"Belief update failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
