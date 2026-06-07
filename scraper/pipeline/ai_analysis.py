"""
AI 分析服务模块
使用 DeepSeek API 进行新闻分析

功能：
1. 单条文章分析（情感、摘要、标签）
2. 趋势分析
3. 周期报告生成
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass

from common.ai_client import BaseDeepSeekClient
from common.utils import parse_ai_response, smart_truncate, calculate_confidence
from app.config import settings
from models.schemas import ArticleAnalysisSchema, TrendSchema

logger = logging.getLogger(__name__)


@dataclass
class ArticleAnalysis:
    """单条文章分析结果"""
    sentiment: str  # positive, negative, neutral
    sentiment_score: float  # -1.0 到 1.0
    summary_zh: str  # 中文摘要
    key_points: list[str]  # 关键要点
    tags: list[str]  # 标签
    importance: float  # 重要性评分 0-1


class DeepSeekClient(BaseDeepSeekClient):
    """
    DeepSeek API 客户端（scraper 版本）
    继承基础客户端，添加文章分析和报告生成功能
    """
    
    def __init__(self, max_retries: int = None, timeout: int = None):
        super().__init__(max_retries, timeout)
    
    
    async def analyze_article(self, title: str, content: str = None, summary: str = None, 
                       category: str = None, lang: str = "en") -> Optional[ArticleAnalysis]:
        """
        分析单条文章
        
        Args:
            title: 文章标题
            content: 文章正文
            summary: RSS 摘要
            category: 文章分类
            lang: 原文语言
        
        Returns:
            ArticleAnalysis 或 None
        """
        # 构建分析文本
        text = f"标题: {title}\n"
        if summary:
            text += f"摘要: {summary}\n"
        if content:
            # 使用智能截断，在句子边界断开
            text += f"正文: {smart_truncate(content, 3000)}\n"
        if category:
            text += f"分类: {category}\n"
        
        messages = [
            {
                "role": "system",
                "content": """你是一个专业的财经新闻分析师。请分析以下新闻文章，返回 JSON 格式的分析结果。

返回格式：
{
    "sentiment": "positive/negative/neutral",
    "sentiment_score": 0.0,  // -1.0 到 1.0，负数表示消极，正数表示积极
    "summary_zh": "中文摘要，100字以内",
    "key_points": ["要点1", "要点2", "要点3"],
    "tags": ["标签1", "标签2"],
    "importance": 0.8  // 重要性评分 0-1，考虑市场影响、政策影响、历史意义等
}

注意：
1. sentiment_score 要准确反映市场情绪
2. summary_zh 要简洁准确
3. key_points 提取3-5个核心要点
4. tags 包含相关的人名、机构、国家、政策等
5. importance 根据对金融市场的影响程度评分"""
            },
            {
                "role": "user",
                "content": text
            }
        ]
        
        result = await self._call_api(messages, temperature=0.3, function_name="analyze_article")
        if not result:
            return None
        
        try:
            # 使用 Schema 验证
            data = parse_ai_response(result, schema=ArticleAnalysisSchema)
            if not data:
                return None
            
            # 动态计算置信度
            confidence = calculate_confidence(
                data, 
                response_text=result,
                required_fields=["sentiment", "sentiment_score", "summary_zh", "key_points", "importance"],
                field_validators={
                    "sentiment": lambda x: x in ("positive", "negative", "neutral"),
                    "sentiment_score": lambda x: -1.0 <= float(x) <= 1.0,
                    "importance": lambda x: 0.0 <= float(x) <= 1.0,
                }
            )
            
            # 置信度过滤
            if settings.AI_CONFIDENCE_ENABLED and confidence < settings.AI_CONFIDENCE_THRESHOLD:
                logger.warning(f"AI 分析置信度过低 ({confidence:.2f} < {settings.AI_CONFIDENCE_THRESHOLD}): {title[:50]}...")
                # 记录失败任务
                await self._record_failed_task(
                    task_type="article_analysis",
                    target_id=title[:200],
                    input_data={"title": title, "content": content, "summary": summary, "category": category},
                    failure_reason="low_confidence",
                    error_message=f"置信度 {confidence:.2f} 低于阈值 {settings.AI_CONFIDENCE_THRESHOLD}",
                    error_details={"confidence": confidence, "result": data}
                )
                return None
            
            # 保存分析版本
            await self._save_analysis_version(
                analysis_type="article",
                target_id=title[:200],
                result_data=data,
                confidence=confidence,
            )
            
            return ArticleAnalysis(
                sentiment=data.get("sentiment", "neutral"),
                sentiment_score=float(data.get("sentiment_score", 0)),
                summary_zh=data.get("summary_zh", ""),
                key_points=data.get("key_points", []),
                tags=data.get("tags", []),
                importance=float(data.get("importance", 0.5))
            )
        except (ValueError, TypeError) as e:
            logger.error(f"解析 AI 返回结果失败: {e}")
            return None
    
    async def _record_failed_task(self, task_type: str, target_id: str, input_data: dict,
                           failure_reason: str, error_message: str = None, 
                           error_details: dict = None):
        """记录失败的分析任务到数据库"""
        try:
            from models.base import async_session
            from models.failed_task import FailedAnalysisTask
            from datetime import datetime, timedelta
            from sqlalchemy import select
            
            async with async_session() as session:
                # 检查是否已存在相同任务
                stmt = select(FailedAnalysisTask).filter(
                    FailedAnalysisTask.task_type == task_type,
                    FailedAnalysisTask.target_id == target_id,
                    FailedAnalysisTask.status.in_(["pending", "retrying"])
                ).limit(1)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                
                if existing:
                    # 更新现有任务
                    existing.retry_count += 1
                    existing.last_retry_at = datetime.now(timezone.utc)
                    existing.error_message = error_message
                    existing.error_details = error_details
                    if existing.retry_count >= existing.max_retries:
                        existing.status = "abandoned"
                else:
                    # 创建新任务
                    task = FailedAnalysisTask(
                        task_type=task_type,
                        target_id=target_id,
                        input_data=input_data,
                        failure_reason=failure_reason,
                        error_message=error_message,
                        error_details=error_details,
                        next_retry_at=datetime.now(timezone.utc) + timedelta(seconds=settings.AI_RETRY_BASE_DELAY)
                    )
                    session.add(task)
                
                await session.commit()
        except Exception as e:
            logger.error(f"记录失败任务时出错: {e}")
    
    async def _save_analysis_version(self, analysis_type: str, target_id: str, 
                              result_data: dict, confidence: float = None,
                              analysis_duration_ms: int = None):
        """异步保存分析结果版本"""
        try:
            from scraper.pipeline.version_manager import get_version_manager
            
            manager = get_version_manager()
            await manager.save_version(
                analysis_type=analysis_type,
                target_id=target_id,
                result_data=result_data,
                confidence=confidence,
                ai_model="deepseek-chat",
                analysis_duration_ms=analysis_duration_ms,
            )
        except Exception as e:
            logger.error(f"保存分析版本时出错: {e}")
    
    async def analyze_keyword_trend(self, keyword: str, articles: list[dict]) -> Optional[dict]:
        """
        分析关键词趋势
        
        Args:
            keyword: 关键词
            articles: 相关文章列表
        
        Returns:
            趋势分析结果
        """
        articles_text = "\n".join([
            f"- {a['title']} ({a.get('date', 'N/A')})" 
            for a in articles[:20]
        ])
        
        messages = [
            {
                "role": "system",
                "content": """分析关键词在近期新闻中的趋势。返回 JSON 格式：
{
    "keyword": "关键词",
    "trend": "rising/stable/declining",
    "analysis": "趋势分析，100字以内",
    "related_topics": ["相关话题1", "相关话题2"],
    "prediction": "未来可能走势，50字以内"
}"""
            },
            {
                "role": "user",
                "content": f"关键词: {keyword}\n相关文章:\n{articles_text}"
            }
        ]
        
        result = await self._call_api(messages, temperature=0.5, function_name="analyze_keyword_trend")
        if not result:
            return None
        
        # 使用 Schema 验证
        return parse_ai_response(result, schema=TrendSchema)
    
    async def generate_period_report(self, articles: list[dict], stats_summary: dict, period: str = "weekly") -> Optional[dict]:
        """
        生成周报/月报
        
        Args:
            articles: 文章列表
            stats_summary: 统计摘要
            period: 周期类型 (weekly/monthly)
        
        Returns:
            报告内容
        """
        period_cn = "周" if period == "weekly" else "月"
        
        # 构建文章摘要列表
        article_summaries = []
        for i, article in enumerate(articles[:50], 1):
            summary = f"{i}. [{article.get('category', '未分类')}] {article['title']}"
            if article.get('summary'):
                summary += f" - {article['summary'][:100]}"
            article_summaries.append(summary)
        
        articles_text = "\n".join(article_summaries)
        
        # 构建统计信息
        stats_text = f"""
统计信息：
- 时间范围：{stats_summary.get('start_date', '')} ~ {stats_summary.get('end_date', '')}
- 文章总数：{stats_summary.get('total_articles', 0)}
- 分类分布：{json.dumps(stats_summary.get('category_stats', []), ensure_ascii=False)}
- 情感分布：{json.dumps(stats_summary.get('sentiment_distribution', {}), ensure_ascii=False)}
"""
        
        messages = [
            {
                "role": "system",
                "content": f"""你是一个资深的财经分析师。请根据近{period_cn}的新闻数据生成专业的财经分析报告。

返回 JSON 格式：
{{
    "overview": "本{period_cn}财经形势概述，300字以内",
    "hot_topics": [
        {{"topic": "话题名称", "description": "描述", "impact": "影响评估"}}
    ],
    "market_sentiment": "bullish/bearish/neutral/mixed",
    "key_events": [
        {{"event": "事件描述", "significance": "重要性说明", "category": "分类"}}
    ],
    "trend_analysis": "趋势分析，包括短期和中期展望，500字以内"
}}

注意：
1. overview 要全面概括本{period_cn}财经动态
2. hot_topics 提取 3-5 个最热门话题
3. key_events 提取 3-5 个最关键事件
4. trend_analysis 要深入分析趋势并给出展望"""
            },
            {
                "role": "user",
                "content": f"{stats_text}\n\n文章列表：\n{articles_text}"
            }
        ]
        
        result = await self._call_api(messages, temperature=0.5, max_tokens=3000)
        if not result:
            return None
        
        data = parse_ai_response(result)
        if not data:
            logger.error(f"无法解析 AI 返回结果")
            return None
        
        return data


# 全局实例
ai_client = DeepSeekClient()


def get_ai_client() -> DeepSeekClient:
    """获取 AI 客户端实例"""
    return ai_client


def is_ai_enabled() -> bool:
    """检查 AI 功能是否可用"""
    return ai_client.enabled
