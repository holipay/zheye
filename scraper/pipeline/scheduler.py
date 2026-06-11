"""
智能调度模块
根据源的健康状态动态调整抓取优先级和批次大小

策略：
1. 成功率高的源优先抓取
2. 连续失败的源降低优先级
3. 连续失败超过阈值的源暂时禁用
4. 使用 weight 字段作为基础权重
5. 按健康度分层：健康源大并发，不健康源小并发
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from dataclasses import dataclass

from sqlalchemy import select
from models.base import async_session
from models.source_health import SourceHealth

logger = logging.getLogger(__name__)

# 调度配置
MAX_CONSECUTIVE_FAILURES = 5  # 连续失败超过此数量暂时禁用
MIN_SUCCESS_RATE = 30.0  # 最低成功率阈值
PRIORITY_BOOST_HOURS = 2  # 成功抓取后优先级提升时间（小时）
PRIORITY_DECAY_FACTOR = 0.5  # 优先级衰减因子

# 分层并发配置
TIER_HEALTHY_CONCURRENCY = 10    # 健康源并发数
TIER_HEALTHY_DELAY = 2.0         # 健康源批次间延迟（秒）
TIER_UNHEALTHY_CONCURRENCY = 3   # 不健康源并发数
TIER_UNHEALTHY_DELAY = 15.0      # 不健康源批次间延迟（秒）
HEALTHY_THRESHOLD = 0.8          # 健康源阈值（健康分数）


@dataclass
class SourcePriority:
    """源优先级信息"""
    name: str
    base_weight: float
    health_score: float
    final_priority: float
    is_disabled: bool
    reason: str


def calculate_health_score(
    success_rate: float,
    consecutive_failures: int,
    last_success: Optional[datetime],
    total_checks: int,
) -> float:
    """
    计算健康分数
    
    Args:
        success_rate: 成功率 (0-100)
        consecutive_failures: 连续失败次数
        last_success: 上次成功时间
        total_checks: 总检查次数
        
    Returns:
        健康分数 (0-1)
    """
    # 基础分数：成功率
    base_score = success_rate / 100.0
    
    # 连续失败惩罚
    if consecutive_failures > 0:
        failure_penalty = min(consecutive_failures * 0.1, 0.5)
        base_score *= (1 - failure_penalty)
    
    # 时间衰减：长时间未成功的源降低优先级
    if last_success:
        hours_since_success = (datetime.now(timezone.utc) - last_success).total_seconds() / 3600
        if hours_since_success > 24:
            time_decay = min(hours_since_success / 168, 0.5)  # 最多衰减50%
            base_score *= (1 - time_decay)
    
    # 新源保护：检查次数少的源给予一定保护
    if total_checks < 10:
        base_score = max(base_score, 0.5)
    
    return max(0.0, min(1.0, base_score))


def should_disable_source(
    consecutive_failures: int,
    success_rate: float,
    total_checks: int,
) -> tuple[bool, str]:
    """
    判断是否应该禁用源
    
    Args:
        consecutive_failures: 连续失败次数
        success_rate: 成功率
        total_checks: 总检查次数
        
    Returns:
        (是否禁用, 原因)
    """
    # 连续失败过多
    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        return True, f"连续失败 {consecutive_failures} 次"
    
    # 成功率过低（需要足够的检查次数）
    if total_checks >= 20 and success_rate < MIN_SUCCESS_RATE:
        return True, f"成功率过低: {success_rate:.1f}%"
    
    return False, ""


async def get_source_priorities(sources: list[dict]) -> list[tuple[dict, SourcePriority]]:
    """
    获取源的优先级列表
    
    Args:
        sources: 源配置列表
        
    Returns:
        (源配置, 优先级信息) 元组列表，按优先级降序排列
    """
    # 获取所有源的健康状态
    health_map = {}
    async with async_session() as session:
        result = await session.execute(select(SourceHealth))
        for health in result.scalars():
            health_map[health.source_name] = health
    
    priorities = []
    
    for source in sources:
        name = source["name"]
        base_weight = source.get("weight", 1.0)
        
        # 获取健康状态
        health = health_map.get(name)
        
        if health:
            success_rate = float(health.success_rate or 0)
            consecutive_failures = health.consecutive_failures or 0
            last_success = health.last_success
            total_checks = health.total_checks or 0
            
            # 计算健康分数
            health_score = calculate_health_score(
                success_rate, consecutive_failures, last_success, total_checks
            )
            
            # 判断是否禁用
            is_disabled, reason = should_disable_source(
                consecutive_failures, success_rate, total_checks
            )
        else:
            # 新源：给予默认分数
            health_score = 0.7
            is_disabled = False
            reason = "新源"
        
        # 计算最终优先级
        final_priority = base_weight * health_score
        
        priority = SourcePriority(
            name=name,
            base_weight=base_weight,
            health_score=health_score,
            final_priority=final_priority,
            is_disabled=is_disabled,
            reason=reason,
        )
        
        priorities.append((source, priority))
    
    # 按优先级降序排列
    priorities.sort(key=lambda x: x[1].final_priority, reverse=True)
    
    return priorities


async def filter_and_sort_sources(sources: list[dict]) -> list[dict]:
    """
    过滤和排序源
    
    根据健康状态过滤禁用的源，按优先级排序
    
    Args:
        sources: 源配置列表
        
    Returns:
        过滤和排序后的源列表
    """
    priorities = await get_source_priorities(sources)
    
    filtered = []
    disabled_count = 0
    
    for source, priority in priorities:
        if priority.is_disabled:
            disabled_count += 1
            logger.warning(f"禁用源 {priority.name}: {priority.reason}")
            continue
        
        filtered.append(source)
    
    if disabled_count > 0:
        logger.info(f"禁用了 {disabled_count} 个源")
    
    logger.info(f"源优先级排序完成: {len(filtered)} 个可用源")
    
    return filtered


async def get_health_summary() -> dict:
    """
    获取健康状态摘要
    
    Returns:
        健康状态摘要
    """
    async with async_session() as session:
        result = await session.execute(select(SourceHealth))
        health_records = result.scalars().all()
    
    total = len(health_records)
    healthy = sum(1 for h in health_records if float(h.success_rate or 0) >= MIN_SUCCESS_RATE)
    disabled = sum(1 for h in health_records if (h.consecutive_failures or 0) >= MAX_CONSECUTIVE_FAILURES)
    
    return {
        "total_sources": total,
        "healthy_sources": healthy,
        "disabled_sources": disabled,
        "health_rate": healthy / total * 100 if total > 0 else 0,
    }


def get_tiered_schedule_params(health_score: float) -> tuple[int, float]:
    """
    根据健康分数返回分层调度参数
    
    Args:
        health_score: 健康分数 (0-1)
    
    Returns:
        (concurrency, delay) 并发数和批次间延迟
    """
    if health_score >= HEALTHY_THRESHOLD:
        return TIER_HEALTHY_CONCURRENCY, TIER_HEALTHY_DELAY
    else:
        return TIER_UNHEALTHY_CONCURRENCY, TIER_UNHEALTHY_DELAY


def split_sources_by_health(priorities: list[tuple[dict, SourcePriority]]) -> tuple[list, list]:
    """
    将源按健康度分为两组：健康源和不健康源
    
    Args:
        priorities: (源配置, 优先级信息) 元组列表
    
    Returns:
        (healthy_sources, unhealthy_sources) 两个列表
    """
    healthy = []
    unhealthy = []
    
    for source, priority in priorities:
        if priority.health_score >= HEALTHY_THRESHOLD:
            healthy.append(source)
        else:
            unhealthy.append(source)
    
    return healthy, unhealthy
