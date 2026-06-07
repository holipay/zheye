"""
数据管道健康检查

功能：
1. 检查最近一次抓取的数据是否实际入库
2. 检查数据时间连续性
3. 检查源健康状态
4. 输出诊断报告

使用方法：
    python scripts/check_pipeline.py
    python scripts/check_pipeline.py --hours 24  # 检查最近24小时
"""

import os
import sys
import asyncio
import argparse
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, func, text
from models.base import async_session
from models.news import News
from models.run_metrics import RunMetrics
from models.source_health import SourceHealth

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


async def check_recent_insertions(hours: int = 2):
    """检查最近N小时是否有新数据入库"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    async with async_session() as session:
        result = await session.execute(
            select(func.count(News.id)).where(News.created_at >= cutoff)
        )
        count = result.scalar()
        
        status = "OK" if count > 0 else "FAIL"
        logger.info(f"[{status}] 最近{hours}小时入库数据: {count} 条")
        return count > 0


async def check_latest_run_consistency():
    """检查最近一次运行的指标与实际数据是否一致"""
    async with async_session() as session:
        # 获取最近一次运行指标
        result = await session.execute(
            select(RunMetrics).order_by(RunMetrics.started_at.desc()).limit(1)
        )
        latest_run = result.scalar_one_or_none()
        
        if not latest_run:
            logger.info("[SKIP] 无运行记录")
            return True
        
        run_time = latest_run.started_at
        expected = latest_run.items_final
        duration = latest_run.duration_seconds
        
        # 检查该时间段内实际入库数据
        run_end = run_time + timedelta(seconds=duration + 60)  # 加60秒缓冲
        result = await session.execute(
            select(func.count(News.id)).where(
                News.created_at >= run_time,
                News.created_at <= run_end
            )
        )
        actual = result.scalar()
        
        # 由于 on_conflict_do_nothing，actual 可能小于 expected
        # 但 actual 应该 > 0（除非所有数据都已存在）
        if expected > 0 and actual == 0:
            logger.info(f"[FAIL] 运行 {run_time}: 指标显示保存 {expected} 条, 实际入库 0 条")
            return False
        elif expected > 0 and actual < expected:
            logger.info(f"[WARN] 运行 {run_time}: 指标显示保存 {expected} 条, 实际入库 {actual} 条 (可能有重复)")
        else:
            logger.info(f"[OK] 运行 {run_time}: 入库 {actual} 条")
        return True


async def check_data_continuity(hours: int = 48):
    """检查数据时间连续性，发现数据断层"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM news
                WHERE created_at >= :cutoff
                GROUP BY DATE(created_at)
                ORDER BY date
            """),
            {"cutoff": cutoff}
        )
        rows = result.fetchall()
        
        if not rows:
            logger.info(f"[FAIL] 最近{hours}小时无数据")
            return False
        
        logger.info(f"[INFO] 最近{hours}小时数据分布:")
        for row in rows:
            logger.info(f"  {row[0]}: {row[1]} 条")
        
        # 检查是否有断层
        dates = [row[0] for row in rows]
        expected_dates = []
        current = dates[0]
        while current <= dates[-1]:
            expected_dates.append(current)
            current += timedelta(days=1)
        
        missing = set(expected_dates) - set(dates)
        if missing:
            logger.info(f"[WARN] 数据断层: {sorted(missing)}")
            return False
        
        return True


async def check_source_health():
    """检查源健康状态"""
    async with async_session() as session:
        result = await session.execute(
            select(SourceHealth)
            .where(SourceHealth.consecutive_failures >= 3)
            .order_by(SourceHealth.consecutive_failures.desc())
        )
        unhealthy = result.scalars().all()
        
        if unhealthy:
            logger.info(f"[WARN] {len(unhealthy)} 个源连续失败 >= 3 次:")
            for h in unhealthy:
                logger.info(f"  {h.source_name}: {h.consecutive_failures} 次, 错误: {(h.last_error or '')[:60]}")
        else:
            logger.info("[OK] 所有源健康")
        
        return len(unhealthy) == 0


async def check_max_id_gap():
    """检查ID间隙，判断是否有数据被删除"""
    async with async_session() as session:
        result = await session.execute(text("SELECT MAX(id), MIN(id), COUNT(*) FROM news"))
        row = result.fetchone()
        max_id, min_id, count = row
        
        gap = max_id - min_id + 1 - count
        if gap > count * 0.5:  # 间隙超过数据量的50%
            logger.info(f"[WARN] ID间隙异常: max_id={max_id}, min_id={min_id}, count={count}, gap={gap}")
            logger.info("  可能原因: 数据被删除或大量插入后回滚")
            return False
        
        logger.info(f"[OK] ID连续性正常: {count} 条数据, 间隙 {gap}")
        return True


async def main():
    parser = argparse.ArgumentParser(description='数据管道健康检查')
    parser.add_argument('--hours', type=int, default=2, help='检查最近N小时的数据')
    args = parser.parse_args()
    
    logger.info("=" * 50)
    logger.info("数据管道健康检查")
    logger.info("=" * 50)
    
    checks = [
        ("最近入库检查", check_recent_insertions(args.hours)),
        ("运行指标一致性", check_latest_run_consistency()),
        ("数据时间连续性", check_data_continuity()),
        ("源健康状态", check_source_health()),
        ("ID连续性", check_max_id_gap()),
    ]
    
    results = []
    for name, coro in checks:
        logger.info(f"\n--- {name} ---")
        try:
            ok = await coro
            results.append((name, ok))
        except Exception as e:
            logger.info(f"[ERROR] {e}")
            results.append((name, False))
    
    logger.info("\n" + "=" * 50)
    logger.info("检查结果汇总:")
    all_ok = True
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        logger.info(f"  [{status}] {name}")
        if not ok:
            all_ok = False
    
    if all_ok:
        logger.info("\n结论: 数据管道正常")
    else:
        logger.info("\n结论: 数据管道存在问题，请检查上方详情")
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
