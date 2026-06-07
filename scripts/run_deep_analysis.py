"""
深度分析批处理脚本

功能：
1. 扫描未分析或分析过时的事件
2. 按优先级排序，逐个执行深度分析（知识框架→因果链→历史类比→情景推演）
3. 支持单事件分析和批量分析模式

使用方法：
    # 批量分析（默认最多 10 个事件）
    python scripts/run_deep_analysis.py

    # 指定数量
    python scripts/run_deep_analysis.py --max-events 5

    # 分析单个事件
    python scripts/run_deep_analysis.py --event-id EVT-a1b2c3d4

    # 调整冷却时间（默认 24 小时内不重复分析）
    python scripts/run_deep_analysis.py --cooldown-hours 12

    # 试运行（只显示待分析事件，不执行分析）
    python scripts/run_deep_analysis.py --dry-run
"""

import os
import sys
import asyncio
import argparse
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, func
from models.base import async_session
from models.event import Event
from deep_analyst.models.knowledge import EventKnowledge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def list_pending_events(max_events: int = None, cooldown_hours: int = None):
    """列出待分析的事件"""
    from deep_analyst.pipeline import get_events_needing_analysis
    from app.config import settings

    if max_events is None:
        max_events = settings.DEEP_ANALYSIS_MAX_EVENTS
    if cooldown_hours is None:
        cooldown_hours = settings.DEEP_ANALYSIS_COOLDOWN_HOURS

    async with async_session() as session:
        events = await get_events_needing_analysis(session, max_events, cooldown_hours)
        return events


async def run_analysis(
    max_events: int = None,
    cooldown_hours: int = None,
    event_id: str = None,
):
    """执行深度分析"""
    from deep_analyst.pipeline import run_deep_analysis
    from app.config import settings

    if max_events is None:
        max_events = settings.DEEP_ANALYSIS_MAX_EVENTS
    if cooldown_hours is None:
        cooldown_hours = settings.DEEP_ANALYSIS_COOLDOWN_HOURS

    logger.info("=" * 60)
    logger.info("深度分析任务开始")
    logger.info("=" * 60)

    # 检查 AI 配置
    from deep_analyst.ai_analysis import DeepSeekClient
    client = DeepSeekClient()
    if not client.enabled:
        logger.error("DeepSeek API 未启用，请配置 DEEPSEEK_API_KEY")
        return

    async with async_session() as session:
        try:
            if event_id:
                logger.info(f"单事件分析模式: {event_id}")
            else:
                logger.info(f"批量分析模式: 最多 {max_events} 个事件, 冷却 {cooldown_hours}h")

            result = await run_deep_analysis(
                session=session,
                max_events=max_events,
                cooldown_hours=cooldown_hours,
                event_id=event_id,
            )

            # 输出汇总
            logger.info("")
            logger.info("=" * 60)
            logger.info("分析完成")
            logger.info("=" * 60)
            logger.info(f"  总计: {result.total}")
            logger.info(f"  成功: {result.success}")
            logger.info(f"  失败: {result.failed}")
            logger.info(f"  耗时: {result.duration_seconds:.1f}s")

            if result.results:
                logger.info("")
                logger.info("详细结果:")
                for r in result.results:
                    status = "OK" if r.success else "FAIL"
                    steps = ", ".join(r.steps_completed) if r.steps_completed else "none"
                logger.info(f"  [{status}] {r.event_id}: {steps} ({r.duration_seconds:.1f}s)")
                if r.error:
                    logger.info(f"         错误: {r.error}")
        except Exception as e:
            await session.rollback()
            logger.error(f"深度分析失败: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(description="深度分析批处理脚本")
    parser.add_argument(
        "--max-events", type=int, default=None,
        help="最多分析的事件数 (默认: 从配置读取，10)",
    )
    parser.add_argument(
        "--cooldown-hours", type=int, default=None,
        help="同一事件的分析冷却时间，小时 (默认: 从配置读取，24)",
    )
    parser.add_argument(
        "--event-id", type=str, default=None,
        help="分析指定事件 ID（单事件模式）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="试运行：只列出待分析事件，不执行分析",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="列出待分析事件（等同 --dry-run）",
    )

    args = parser.parse_args()

    if args.dry_run or args.list:
        events = asyncio.run(list_pending_events(args.max_events, args.cooldown_hours))
        if events:
            print(f"\n找到 {len(events)} 个待分析事件:\n")
            for i, e in enumerate(events, 1):
                print(f"  {i}. [{e['event_id']}] {e['title'][:60]}")
                print(f"     分类: {e['category']}, 文章数: {len(e.get('related_articles', []))}")
        else:
            print("没有需要分析的事件")
        return

    asyncio.run(run_analysis(
        max_events=args.max_events,
        cooldown_hours=args.cooldown_hours,
        event_id=args.event_id,
    ))


if __name__ == "__main__":
    main()
