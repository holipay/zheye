"""
AI 分析服务模块
使用 DeepSeek API 进行新闻分析

功能：
1. 单条文章分析（情感、摘要、标签）
2. 每日综合分析报告
3. 趋势分析
"""

import os
import json
import logging
from datetime import datetime, date
from typing import Optional
from dataclasses import dataclass

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
    
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        self.enabled = bool(self.api_key)
        
        if not self.enabled:
            logger.info("DeepSeek API: 未配置 API Key，AI 分析功能已禁用")
            self.client = None
            return
        
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
            logger.info(f"DeepSeek API: 已连接 {self.api_base}")
        except ImportError:
            logger.warning("openai 包未安装，无法使用 AI 分析功能")
            self.enabled = False
            self.client = None
    
    def _call_api(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 2000) -> Optional[str]:
        """调用 API"""
        if not self.enabled or not self.client:
            return None
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"DeepSeek API 调用失败: {e}")
            return None
    
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
            # 限制内容长度，避免 token 超限
            text += f"正文: {content[:3000]}\n"
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
        
        result = self._call_api(messages, temperature=0.3)
        if not result:
            return None
        
        try:
            # 提取 JSON 部分
            json_start = result.find("{")
            json_end = result.rfind("}") + 1
            if json_start == -1 or json_end == 0:
                logger.error(f"无法解析 AI 返回结果: {result}")
                return None
            
            data = json.loads(result[json_start:json_end])
            
            return ArticleAnalysis(
                sentiment=data.get("sentiment", "neutral"),
                sentiment_score=float(data.get("sentiment_score", 0)),
                summary_zh=data.get("summary_zh", ""),
                key_points=data.get("key_points", []),
                tags=data.get("tags", []),
                importance=float(data.get("importance", 0.5))
            )
        except (json.JSONDecodeError, ValueError) as e:
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
        
        result = self._call_api(messages, temperature=0.5, max_tokens=3000)
        if not result:
            return None
        
        try:
            json_start = result.find("{")
            json_end = result.rfind("}") + 1
            data = json.loads(result[json_start:json_end])
            
            return DailyReport(
                date=target_date,
                overview=data.get("overview", ""),
                hot_topics=data.get("hot_topics", []),
                market_sentiment=data.get("market_sentiment", ""),
                key_events=data.get("key_events", []),
                trend_analysis=data.get("trend_analysis", ""),
                news_count=len(articles)
            )
        except (json.JSONDecodeError, ValueError) as e:
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
        
        result = self._call_api(messages, temperature=0.5)
        if not result:
            return None
        
        try:
            json_start = result.find("{")
            json_end = result.rfind("}") + 1
            return json.loads(result[json_start:json_end])
        except json.JSONDecodeError:
            return None


# 全局实例
ai_client = DeepSeekClient()


def get_ai_client() -> DeepSeekClient:
    """获取 AI 客户端实例"""
    return ai_client


def is_ai_enabled() -> bool:
    """检查 AI 功能是否可用"""
    return ai_client.enabled
