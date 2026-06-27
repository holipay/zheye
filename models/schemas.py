"""
AI 响应数据验证 Schema
使用 Pydantic 验证 AI 返回的数据结构
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from enum import Enum


# ============================================================
# 枚举类型
# ============================================================

class SentimentType(str, Enum):
    """情感类型"""
    positive = "positive"
    negative = "negative"
    neutral = "neutral"


class Priority(str, Enum):
    """优先级"""
    high = "high"
    medium = "medium"
    low = "low"


class TrendType(str, Enum):
    """趋势类型"""
    rising = "rising"
    stable = "stable"
    declining = "declining"


# ============================================================
# 基础 Schema
# ============================================================

class KeyPoint(BaseModel):
    """关键要点"""
    point: str = Field(max_length=500)
    importance: Optional[float] = Field(None, ge=0.0, le=1.0)


class HotTopic(BaseModel):
    """热门话题"""
    topic: str = Field(max_length=200)
    count: Optional[int] = Field(None, ge=0)
    sentiment: Optional[SentimentType] = None
    description: Optional[str] = Field(None, max_length=500)
    impact: Optional[str] = Field(None, max_length=200)


class KeyEvent(BaseModel):
    """关键事件"""
    event: str = Field(max_length=500)
    impact: Optional[str] = Field(None, max_length=200)
    significance: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=100)


# ============================================================
# 文章分析 Schema
# ============================================================

class ArticleAnalysisSchema(BaseModel):
    """单条文章分析结果"""
    sentiment: SentimentType = Field(default=SentimentType.neutral)
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    summary_zh: str = Field(default="", max_length=1000)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


# ============================================================
# 每日报告 Schema
# ============================================================

class DailyReportSchema(BaseModel):
    """每日分析报告"""
    overview: str = Field(default="", max_length=2000)
    hot_topics: List[HotTopic] = Field(default_factory=list, max_length=10)
    market_sentiment: str = Field(default="neutral", max_length=100)
    key_events: List[KeyEvent] = Field(default_factory=list, max_length=10)
    trend_analysis: str = Field(default="", max_length=2000)

    @field_validator('hot_topics', 'key_events', mode='before')
    @classmethod
    def ensure_list(cls, v):
        return v or []


# ============================================================
# 趋势分析 Schema
# ============================================================

class TrendSchema(BaseModel):
    """趋势分析"""
    keyword: str = Field(max_length=100)
    trend: TrendType = Field(default=TrendType.stable)
    analysis: str = Field(default="", max_length=1000)
    related_topics: List[str] = Field(default_factory=list, max_length=10)
    prediction: Optional[str] = Field(None, max_length=500)


# ============================================================
# Schema 映射表
# ============================================================

SCHEMA_MAP = {
    "article_analysis": ArticleAnalysisSchema,
    "daily_report": DailyReportSchema,
    "trend": TrendSchema,
}


def get_schema(name: str) -> Optional[BaseModel]:
    """获取 Schema 类"""
    return SCHEMA_MAP.get(name)
