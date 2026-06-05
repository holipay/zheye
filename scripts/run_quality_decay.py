"""
知识原子质量衰减定时任务

功能：
1. 对知识原子执行质量衰减
2. 根据时间和复用次数自动调整质量分数

使用方法：
    python scripts/run_quality_decay.py [--decay-rate 0.1] [--min-quality 0.1]

建议 crontab：
    # 每天凌晨3点执行
    0 3 * * * cd /opt/zheye && python scripts/run_quality_decay.py
"""

import os
import sys
import asyncio
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import AsyncSession
from models.base import async_session
from deep_analyst.knowledge import apply_quality_decay

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description='知识原子质量衰减')
    parser.add_argument('--decay-rate', type=float, default=0.1, help='衰减率 (默认: 0.1)')
    parser.add_argument('--min-quality', type=float, default=0.1, help='最低质量分数 (默认: 0.1)')
    args = parser.parse_args()
    
    logger.info(f"开始质量衰减 (衰减率: {args.decay_rate}, 最低质量: {args.min_quality})")
    
    async with async_session() as session:
        try:
            affected = await apply_quality_decay(
                session,
                decay_rate=args.decay_rate,
                min_quality=args.min_quality
            )
            
            await session.commit()
            logger.info(f"质量衰减完成，影响 {affected} 个知识原子")
                
        except Exception as e:
            await session.rollback()
            logger.error(f"质量衰减失败: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
