"""
失败任务自动重试定时任务

功能：
1. 查询待重试的失败任务
2. 执行重试
3. 更新任务状态

使用方法：
    python scripts/retry_failed_tasks.py [--max-tasks 10] [--max-concurrent 3]

建议 crontab：
    # 每小时执行
    0 * * * * cd /opt/zheye && python scripts/retry_failed_tasks.py
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

from scraper.pipeline.retry_manager import get_retry_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description='失败任务自动重试')
    parser.add_argument('--max-tasks', type=int, default=10, help='最大重试任务数 (默认: 10)')
    parser.add_argument('--max-concurrent', type=int, default=3, help='最大并发数 (默认: 3)')
    args = parser.parse_args()
    
    logger.info(f"开始重试失败任务 (最大任务数: {args.max_tasks}, 最大并发: {args.max_concurrent})")
    
    manager = get_retry_manager()
    manager.max_concurrent = args.max_concurrent
    
    try:
        result = await manager.retry_pending_tasks(limit=args.max_tasks)
        
        logger.info(f"重试完成: "
                    f"成功={result.get('succeeded', 0)}, "
                    f"失败={result.get('failed', 0)}, "
                    f"跳过={result.get('skipped', 0)}")
                
    except Exception as e:
        logger.error(f"重试失败任务时出错: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
