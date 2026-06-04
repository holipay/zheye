from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Text, DateTime, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


class FailedAnalysisTask(Base):
    """失败分析任务队列"""
    __tablename__ = "failed_analysis_tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 任务标识
    task_type = Column(String(50), nullable=False)  # article_analysis, daily_report, keyword_trend, deep_analysis
    target_id = Column(String(200), nullable=False)  # 目标ID
    target_type = Column(String(50))  # news, event, keyword
    
    # 任务数据
    input_data = Column(JSONB, nullable=False)  # 原始输入数据
    
    # 失败信息
    failure_reason = Column(String(100))  # api_error, parse_error, low_confidence, timeout, rate_limit
    error_message = Column(Text)
    error_details = Column(JSONB)
    
    # 重试配置
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry_at = Column(DateTime(timezone=True))
    last_retry_at = Column(DateTime(timezone=True))
    
    # 状态
    status = Column(String(20), default="pending")  # pending, retrying, failed, resolved, abandoned
    
    # 元数据
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    resolved_at = Column(DateTime(timezone=True))

    def __repr__(self):
        return f"<FailedAnalysisTask(id={self.id}, type={self.task_type}, target={self.target_id}, status={self.status})>"

    @property
    def is_retryable(self):
        """判断是否可重试"""
        return (
            self.status in ("pending", "retrying") 
            and self.retry_count < self.max_retries
        )

    @property
    def should_retry_now(self):
        """判断是否应该立即重试"""
        if not self.is_retryable:
            return False
        if self.next_retry_at is None:
            return True
        return datetime.utcnow() >= self.next_retry_at
