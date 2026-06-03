"""
AI 指标监控模块
跟踪 Token 使用量、API 调用次数、成本估算
"""

import logging
from datetime import date, datetime
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# DeepSeek 定价（每 1000 tokens，单位：美元）
# 实际价格请参考 https://platform.deepseek.com/api-docs/pricing
PRICING = {
    "deepseek-chat": {
        "input": 0.00014,   # $0.14 / 1M tokens
        "output": 0.00028,  # $0.28 / 1M tokens
    }
}


@dataclass
class TokenUsage:
    """Token 使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    call_count: int = 0
    error_count: int = 0
    estimated_cost: float = 0.0


@dataclass
class DailyMetrics:
    """每日指标"""
    date: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    by_function: dict[str, TokenUsage] = field(default_factory=lambda: defaultdict(TokenUsage))


class AIMetrics:
    """
    AI 指标监控器
    
    功能：
    1. 记录每次 API 调用的 token 使用量
    2. 按日/按函数统计
    3. 成本估算
    4. 预算告警
    """
    
    def __init__(self, daily_budget: float = 10.0):
        """
        Args:
            daily_budget: 每日预算（美元），超过时发出警告
        """
        self._daily_metrics: dict[str, DailyMetrics] = {}
        self._daily_budget = daily_budget
        self._model = "deepseek-chat"
    
    def _get_today_metrics(self) -> DailyMetrics:
        """获取今日指标"""
        today = date.today().isoformat()
        if today not in self._daily_metrics:
            self._daily_metrics[today] = DailyMetrics(date=today)
        return self._daily_metrics[today]
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """计算成本"""
        pricing = PRICING.get(self._model, PRICING["deepseek-chat"])
        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]
        return input_cost + output_cost
    
    def record_usage(self, prompt_tokens: int, completion_tokens: int, 
                     function_name: str = "unknown"):
        """
        记录 API 调用
        
        Args:
            prompt_tokens: 输入 token 数
            completion_tokens: 输出 token 数
            function_name: 调用函数名（用于分类统计）
        """
        metrics = self._get_today_metrics()
        cost = self._calculate_cost(prompt_tokens, completion_tokens)
        total = prompt_tokens + completion_tokens
        
        # 更新总计
        metrics.usage.prompt_tokens += prompt_tokens
        metrics.usage.completion_tokens += completion_tokens
        metrics.usage.total_tokens += total
        metrics.usage.call_count += 1
        metrics.usage.estimated_cost += cost
        
        # 更新按函数统计
        func_usage = metrics.by_function[function_name]
        func_usage.prompt_tokens += prompt_tokens
        func_usage.completion_tokens += completion_tokens
        func_usage.total_tokens += total
        func_usage.call_count += 1
        func_usage.estimated_cost += cost
        
        # 检查预算
        self._check_budget(metrics)
        
        logger.debug(f"AI 调用记录: {function_name}, "
                    f"tokens={total}, cost=${cost:.4f}")
    
    def record_error(self, function_name: str = "unknown"):
        """记录 API 调用错误"""
        metrics = self._get_today_metrics()
        metrics.usage.error_count += 1
        metrics.by_function[function_name].error_count += 1
    
    def _check_budget(self, metrics: DailyMetrics):
        """检查预算告警"""
        if metrics.usage.estimated_cost >= self._daily_budget:
            logger.warning(
                f"⚠️ AI 预算告警: 今日已使用 ${metrics.usage.estimated_cost:.2f}，"
                f"超过预算 ${self._daily_budget:.2f}"
            )
        elif metrics.usage.estimated_cost >= self._daily_budget * 0.8:
            logger.info(
                f"💰 AI 预算提醒: 今日已使用 ${metrics.usage.estimated_cost:.2f}，"
                f"接近预算 ${self._daily_budget:.2f}"
            )
    
    def get_daily_report(self, day: str = None) -> dict:
        """
        获取每日报告
        
        Args:
            day: 日期字符串，默认今天
        
        Returns:
            报告字典
        """
        metrics = self._daily_metrics.get(day or date.today().isoformat())
        if not metrics:
            return {
                "date": day or date.today().isoformat(),
                "total": {"tokens": 0, "calls": 0, "cost": 0},
                "by_function": {}
            }
        
        return {
            "date": metrics.date,
            "total": {
                "prompt_tokens": metrics.usage.prompt_tokens,
                "completion_tokens": metrics.usage.completion_tokens,
                "total_tokens": metrics.usage.total_tokens,
                "call_count": metrics.usage.call_count,
                "error_count": metrics.usage.error_count,
                "estimated_cost": round(metrics.usage.estimated_cost, 4),
            },
            "by_function": {
                name: {
                    "tokens": usage.total_tokens,
                    "calls": usage.call_count,
                    "cost": round(usage.estimated_cost, 4),
                }
                for name, usage in metrics.by_function.items()
            },
            "budget": {
                "limit": self._daily_budget,
                "used": round(metrics.usage.estimated_cost, 4),
                "remaining": round(self._daily_budget - metrics.usage.estimated_cost, 4),
                "percent_used": round(
                    (metrics.usage.estimated_cost / self._daily_budget) * 100, 1
                ) if self._daily_budget > 0 else 0,
            }
        }
    
    def get_summary(self, days: int = 7) -> dict:
        """
        获取多日汇总
        
        Args:
            days: 天数
        
        Returns:
            汇总字典
        """
        from datetime import timedelta
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        
        total_tokens = 0
        total_cost = 0
        total_calls = 0
        
        for i in range(days):
            day = (start_date + timedelta(days=i)).isoformat()
            metrics = self._daily_metrics.get(day)
            if metrics:
                total_tokens += metrics.usage.total_tokens
                total_cost += metrics.usage.estimated_cost
                total_calls += metrics.usage.call_count
        
        return {
            "period": f"{start_date} ~ {end_date}",
            "days": days,
            "total_tokens": total_tokens,
            "total_calls": total_calls,
            "total_cost": round(total_cost, 4),
            "avg_daily_cost": round(total_cost / days, 4) if days > 0 else 0,
        }


# 全局实例
ai_metrics = AIMetrics()


def get_ai_metrics() -> AIMetrics:
    """获取 AI 指标实例"""
    return ai_metrics
