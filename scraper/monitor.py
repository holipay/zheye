"""
监控告警模块
提供运行状态监控和告警功能

功能：
1. 运行指标监控
2. 异常告警
3. 健康检查
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """告警信息"""
    level: str  # info, warning, error, critical
    message: str
    source: str
    timestamp: datetime
    details: dict = None


class Monitor:
    """
    运行监控器
    
    收集运行指标，检测异常，发送告警
    """
    
    def __init__(self):
        self.alerts: list[Alert] = []
        self.metrics: dict = {
            "sources_attempted": 0,
            "sources_succeeded": 0,
            "sources_failed": 0,
            "items_fetched": 0,
            "items_saved": 0,
            "errors": [],
        }
    
    def record_source_result(self, source_name: str, success: bool, items_count: int = 0, error: str = None):
        """记录源处理结果"""
        self.metrics["sources_attempted"] += 1
        
        if success:
            self.metrics["sources_succeeded"] += 1
            self.metrics["items_fetched"] += items_count
        else:
            self.metrics["sources_failed"] += 1
            if error:
                self.metrics["errors"].append({
                    "source": source_name,
                    "error": error,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
    
    def record_save_result(self, saved_count: int):
        """记录保存结果"""
        self.metrics["items_saved"] += saved_count
    
    def check_alerts(self) -> list[Alert]:
        """检查是否需要告警"""
        alerts = []
        
        # 检查失败率
        total = self.metrics["sources_attempted"]
        if total > 0:
            failure_rate = self.metrics["sources_failed"] / total
            if failure_rate > 0.5:
                alerts.append(Alert(
                    level="error",
                    message=f"源失败率过高: {failure_rate:.1%}",
                    source="monitor",
                    timestamp=datetime.now(timezone.utc),
                    details={"failure_rate": failure_rate, "failed": self.metrics["sources_failed"], "total": total},
                ))
            elif failure_rate > 0.2:
                alerts.append(Alert(
                    level="warning",
                    message=f"源失败率较高: {failure_rate:.1%}",
                    source="monitor",
                    timestamp=datetime.now(timezone.utc),
                    details={"failure_rate": failure_rate, "failed": self.metrics["sources_failed"], "total": total},
                ))
        
        # 检查数据量
        if self.metrics["items_fetched"] == 0 and total > 0:
            alerts.append(Alert(
                level="warning",
                message="未抓取到任何数据",
                source="monitor",
                timestamp=datetime.now(timezone.utc),
            ))
        
        # 检查保存率
        if self.metrics["items_fetched"] > 0:
            save_rate = self.metrics["items_saved"] / self.metrics["items_fetched"]
            if save_rate < 0.1:
                alerts.append(Alert(
                    level="warning",
                    message=f"数据保存率过低: {save_rate:.1%}",
                    source="monitor",
                    timestamp=datetime.now(timezone.utc),
                    details={"save_rate": save_rate, "saved": self.metrics["items_saved"], "fetched": self.metrics["items_fetched"]},
                ))
        
        self.alerts.extend(alerts)
        return alerts
    
    def get_summary(self) -> dict:
        """获取运行摘要"""
        total = self.metrics["sources_attempted"]
        success_rate = self.metrics["sources_succeeded"] / total if total > 0 else 0
        
        return {
            "sources": {
                "attempted": total,
                "succeeded": self.metrics["sources_succeeded"],
                "failed": self.metrics["sources_failed"],
                "success_rate": f"{success_rate:.1%}",
            },
            "items": {
                "fetched": self.metrics["items_fetched"],
                "saved": self.metrics["items_saved"],
                "deduped": self.metrics["items_fetched"] - self.metrics["items_saved"],
            },
            "alerts": len(self.alerts),
            "errors": len(self.metrics["errors"]),
        }
    
    def log_summary(self):
        """记录运行摘要"""
        summary = self.get_summary()
        
        logger.info("=" * 50)
        logger.info("运行摘要")
        logger.info("=" * 50)
        logger.info(f"源: {summary['sources']['attempted']} 尝试, "
                    f"{summary['sources']['succeeded']} 成功, "
                    f"{summary['sources']['failed']} 失败 "
                    f"({summary['sources']['success_rate']})")
        logger.info(f"数据: {summary['items']['fetched']} 抓取, "
                    f"{summary['items']['saved']} 保存, "
                    f"{summary['items']['deduped']} 去重")
        
        if self.alerts:
            logger.warning(f"告警: {len(self.alerts)} 条")
            for alert in self.alerts:
                logger.warning(f"  [{alert.level.upper()}] {alert.message}")
        
        if self.metrics["errors"]:
            logger.error(f"错误: {len(self.metrics['errors'])} 条")
            for error in self.metrics["errors"][-5:]:  # 只显示最近5条
                logger.error(f"  {error['source']}: {error['error']}")
        
        logger.info("=" * 50)


# 全局监控器实例
_monitor: Optional[Monitor] = None


def get_monitor() -> Monitor:
    """获取全局监控器实例"""
    global _monitor
    if _monitor is None:
        _monitor = Monitor()
    return _monitor


def reset_monitor():
    """重置监控器"""
    global _monitor
    _monitor = Monitor()
