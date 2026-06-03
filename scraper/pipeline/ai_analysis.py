"""
AI 分析服务模块
使用 DeepSeek API 进行新闻分析

功能：
1. 单条文章分析（情感、摘要、标签）
2. 每日综合分析报告
3. 趋势分析
"""

import os
import re
import time
import json
import logging
from datetime import datetime, date
from typing import Optional
from dataclasses import dataclass

from scraper.pipeline.utils import parse_ai_response, smart_truncate
from app.ai_metrics import get_ai_metrics
from app.config import settings
from models.schemas import ArticleAnalysisSchema, DailyReportSchema, TrendSchema

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


@dataclass
class DailyReport:
    """每日分析报告"""
    date: date
    overview: str  # 总体概述
    hot_topics: list[dict]  # 热门话题
    market_sentiment: str  # 市场情绪
    key_events: list[dict]  # 关键事件
    trend_analysis: str  # 趋势分析
    news_count: int  # 分析的新闻数量


class DeepSeekClient:
    """
    DeepSeek API 客户端
    使用 OpenAI SDK 兼容接口
    """
    
    # 可重试的异常类型
    RETRYABLE_ERRORS = (
        "RateLimitError",
        "APITimeoutError", 
        "APIConnectionError",
        "APIStatusError",
    )
    
    def __init__(self, max_retries: int = None, timeout: int = None):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.api_base = settings.DEEPSEEK_API_BASE
        self.enabled = bool(self.api_key)
        self.max_retries = max_retries or settings.AI_MAX_RETRIES
        self.timeout = timeout or settings.AI_TIMEOUT_SECONDS
        
        if not self.enabled:
            logger.info("DeepSeek API: 未配置 API Key，AI 分析功能已禁用")
            self.client = None
            return
        
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_base,
                timeout=self.timeout
            )
            logger.info(f"DeepSeek API: 已连接 {self.api_base}")
        except ImportError:
            logger.warning("openai 包未安装，无法使用 AI 分析功能")
            self.enabled = False
            self.client = None
    
    def _call_api(self, messages: list[dict], temperature: float = 0.7, 
                  max_tokens: int = 2000, function_name: str = "unknown") -> Optional[str]:
        """
        调用 API（带重试机制和指标监控）
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            function_name: 调用函数名（用于指标统计）
        
        Returns:
            API 响应内容或 None
        """
        if not self.enabled or not self.client:
            return None
        
        metrics = get_ai_metrics()
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=self.timeout
                )
                
                # 记录 token 使用量
                if hasattr(response, 'usage') and response.usage:
                    usage = response.usage
                    metrics.record_usage(
                        prompt_tokens=usage.prompt_tokens,
                        completion_tokens=usage.completion_tokens,
                        function_name=function_name
                    )
                    logger.debug(f"API 调用: prompt={usage.prompt_tokens}, "
                               f"completion={usage.completion_tokens}, "
                               f"total={usage.total_tokens}")
                
                return response.choices[0].message.content
                
            except Exception as e:
                error_type = type(e).__name__
                last_error = e
                
                # 检查是否为可重试错误
                if error_type in self.RETRYABLE_ERRORS:
                    wait_time = (2 ** attempt) * 1.0  # 指数退避
                    logger.warning(f"API 调用失败 ({error_type}), {wait_time}s 后重试 "
                                 f"(第{attempt + 1}/{self.max_retries}次): {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    # 不可重试错误，直接失败
                    logger.error(f"API 调用异常 ({error_type}): {e}")
                    metrics.record_error(function_name)
                    return None
        
        # 所有重试都失败
        logger.error(f"API 调用失败，已重试{self.max_retries}次: {last_error}")
        metrics.record_error(function_name)
        return None
    
    def chat(self, messages: list[dict], temperature: float = 0.7, 
             max_tokens: int = 2000, function_name: str = "chat") -> Optional[str]:
        """
        公共 API 调用接口
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            function_name: 调用函数名（用于指标统计）
        
        Returns:
            API 响应内容或 None
        """
        return self._call_api(messages, temperature, max_tokens, function_name)
    
    def analyze_article(self, title: str, content: str = None, summary: str = None, 
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
        
        result = self._call_api(messages, temperature=0.3, function_name="analyze_article")
        if not result:
            return None
        
        try:
            # 使用 Schema 验证
            data = parse_ai_response(result, schema=ArticleAnalysisSchema)
            if not data:
                return None
            
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
    
    def generate_daily_report(self, articles: list[dict], target_date: date = None) -> Optional[DailyReport]:
        """
        生成每日分析报告
        
        Args:
            articles: 当日文章列表，每篇文章包含 title, summary, category 等
            target_date: 目标日期，默认今天
        
        Returns:
            DailyReport 或 None
        """
        if target_date is None:
            target_date = date.today()
        
        # 构建文章摘要列表
        article_summaries = []
        for i, article in enumerate(articles[:50], 1):  # 限制最多50篇
            summary = f"{i}. [{article.get('category', '未分类')}] {article['title']}"
            if article.get('summary'):
                summary += f" - {article['summary'][:100]}"
            article_summaries.append(summary)
        
        articles_text = "\n".join(article_summaries)
        
        messages = [
            {
                "role": "system",
                "content": """你是一个资深的财经分析师。请根据今日新闻生成专业的财经分析报告。

返回 JSON 格式：
{
    "overview": "今日财经形势概述，200字以内",
    "hot_topics": [
        {"topic": "话题名称", "count": 5, "sentiment": "positive/negative/neutral", "description": "简要描述"}
    ],
    "market_sentiment": "整体市场情绪描述，如：谨慎乐观、悲观、中性等",
    "key_events": [
        {"event": "事件描述", "impact": "high/medium/low", "category": "相关分类"}
    ],
    "trend_analysis": "趋势分析，150字以内，分析近期动向和未来可能走向"
}

注意：
1. overview 要宏观概括今日要点
2. hot_topics 按重要性排序，列出3-5个
3. key_events 重点关注央行政策、重大并购、地缘政治等
4. trend_analysis 要有前瞻性"""
            },
            {
                "role": "user",
                "content": f"日期: {target_date.isoformat()}\n新闻数量: {len(articles)}\n\n今日新闻列表:\n{articles_text}"
            }
        ]
        
        result = self._call_api(messages, temperature=0.5, max_tokens=3000, function_name="generate_daily_report")
        if not result:
            return None
        
        try:
            # 使用 Schema 验证
            data = parse_ai_response(result, schema=DailyReportSchema)
            if not data:
                return None
            
            return DailyReport(
                date=target_date,
                overview=data.get("overview", ""),
                hot_topics=data.get("hot_topics", []),
                market_sentiment=data.get("market_sentiment", ""),
                key_events=data.get("key_events", []),
                trend_analysis=data.get("trend_analysis", ""),
                news_count=len(articles)
            )
        except (ValueError, TypeError) as e:
            logger.error(f"解析每日报告失败: {e}")
            return None
    
    def analyze_keyword_trend(self, keyword: str, articles: list[dict]) -> Optional[dict]:
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
        
        result = self._call_api(messages, temperature=0.5, function_name="analyze_keyword_trend")
        if not result:
            return None
        
        # 使用 Schema 验证
        return parse_ai_response(result, schema=TrendSchema)
    
    def generate_period_report(self, articles: list[dict], stats_summary: dict, period: str = "weekly") -> Optional[dict]:
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
        
        result = self._call_api(messages, temperature=0.5, max_tokens=3000)
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
