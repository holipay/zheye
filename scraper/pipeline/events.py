"""
事件追踪模块
从新闻中提取事件，识别同一事件的后续报道

功能：
1. 事件提取 - 从新闻标题/摘要中识别事件
2. 事件关联 - 通过相似度匹配关联同一事件
3. 事件更新 - 追踪事件发展
"""

import hashlib
import logging
import re
from datetime import date, datetime
from typing import Optional
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# 事件关键词模式 - 用于快速识别事件类型
EVENT_PATTERNS = {
    "rate_decision": {
        "keywords": ["rate hike", "rate cut", "interest rate", "加息", "降息", "利率决议", "FOMC", "ECB", "BOJ"],
        "category": "央行与利率"
    },
    "earnings_report": {
        "keywords": ["earnings", "revenue", "profit", "财报", "营收", "利润", "quarterly results", "Q1", "Q2", "Q3", "Q4"],
        "category": "股市与市场"
    },
    "economic_data": {
        "keywords": ["GDP", "CPI", "inflation", "unemployment", "PMI", "零售", "非农", "就业"],
        "category": "宏观经济"
    },
    "geopolitical": {
        "keywords": ["sanctions", "tariff", "trade war", "制裁", "关税", "贸易战", "war", "conflict"],
        "category": "国际财经"
    },
    "market_move": {
        "keywords": ["surge", "plunge", "rally", "selloff", "crash", "暴涨", "暴跌", "大涨", "大跌", "新高", "新低"],
        "category": "股市与市场"
    },
    "policy_change": {
        "keywords": ["regulation", "policy", "reform", "监管", "政策", "改革", "立法", "legislation"],
        "category": "政治与治理"
    },
    "company_news": {
        "keywords": ["merger", "acquisition", "IPO", "CEO", "layoff", "并购", "收购", "上市", "裁员"],
        "category": "科技与企业"
    },
    "commodity": {
        "keywords": ["oil", "gold", "OPEC", "原油", "黄金", "大宗商品", "copper", "iron ore"],
        "category": "大宗商品与能源"
    }
}


def generate_event_id(title: str, category: str, pub_date: date = None) -> str:
    """
    生成事件 ID
    基于标题关键信息和分类，同一事件的后续报道应有相同 ID
    
    Args:
        title: 新闻标题
        category: 分类
        pub_date: 发布日期
    
    Returns:
        事件 ID (16 字符)
    """
    # 清理标题，移除时间词和无关词汇
    cleaned = title.lower()
    # 移除常见时间词
    time_words = ["today", "yesterday", "this week", "last week", "monday", "tuesday", "wednesday", 
                  "thursday", "friday", "saturday", "sunday", "今天", "昨天", "本周", "上周"]
    for word in time_words:
        cleaned = cleaned.replace(word, "")
    
    # 提取核心名词短语
    # 简单实现：取标题前30个字符作为事件特征
    event_key = f"{category}:{cleaned[:30].strip()}"
    
    # 生成哈希
    hash_str = hashlib.md5(event_key.encode()).hexdigest()[:16]
    return f"EVT-{hash_str[:8]}"


def extract_event_type(title: str, summary: str = None) -> Optional[str]:
    """
    从标题和摘要中提取事件类型
    
    Args:
        title: 新闻标题
        summary: 摘要
    
    Returns:
        事件类型或 None
    """
    text = f"{title} {summary or ''}".lower()
    
    for event_type, config in EVENT_PATTERNS.items():
        for keyword in config["keywords"]:
            if keyword.lower() in text:
                return event_type
    
    return None


def calculate_event_similarity(title1: str, title2: str) -> float:
    """
    计算两个标题的相似度，用于判断是否为同一事件
    
    Args:
        title1: 标题1
        title2: 标题2
    
    Returns:
        相似度分数 0-1
    """
    # 转换为小写并清理
    t1 = title1.lower().strip()
    t2 = title2.lower().strip()
    
    # 使用 SequenceMatcher 计算相似度
    similarity = SequenceMatcher(None, t1, t2).ratio()
    
    return similarity


def is_same_event(title1: str, title2: str, threshold: float = 0.6) -> bool:
    """
    判断两个标题是否描述同一事件
    
    Args:
        title1: 标题1
        title2: 标题2
        threshold: 相似度阈值
    
    Returns:
        是否同一事件
    """
    similarity = calculate_event_similarity(title1, title2)
    return similarity >= threshold


def find_related_event(title: str, category: str, existing_events: list[dict], 
                       threshold: float = 0.6) -> Optional[dict]:
    """
    在已有事件中查找相关事件
    
    Args:
        title: 新标题
        category: 分类
        existing_events: 已有事件列表
        threshold: 相似度阈值
    
    Returns:
        相关事件或 None
    """
    for event in existing_events:
        if event.get("category") != category:
            continue
        
        # 计算与事件标题的相似度
        similarity = calculate_event_similarity(title, event.get("title", ""))
        if similarity >= threshold:
            return event
        
        # 检查与事件关联文章的相似度
        related_articles = event.get("related_articles", [])
        if isinstance(related_articles, list):
            for article in related_articles[:5]:  # 只检查最近5篇
                article_title = article.get("title", "") if isinstance(article, dict) else ""
                if article_title:
                    similarity = calculate_event_similarity(title, article_title)
                    if similarity >= threshold:
                        return event
    
    return None


def extract_event_summary(title: str, summary: str = None, content: str = None) -> str:
    """
    提取事件摘要
    
    Args:
        title: 标题
        summary: RSS 摘要
        content: 正文
    
    Returns:
        事件摘要
    """
    if summary:
        # 取摘要前200字
        return summary[:200]
    elif content:
        # 取正文前200字
        return content[:200]
    else:
        return title


def detect_event_from_article(title: str, summary: str = None, content: str = None, 
                              category: str = "其他", pub_date: date = None) -> Optional[dict]:
    """
    从文章中检测事件
    
    Args:
        title: 标题
        summary: 摘要
        content: 正文
        category: 分类
        pub_date: 发布日期
    
    Returns:
        事件信息字典或 None
    """
    # 提取事件类型
    event_type = extract_event_type(title, summary)
    if not event_type:
        return None
    
    # 生成事件 ID
    event_id = generate_event_id(title, category, pub_date)
    
    # 提取事件摘要
    event_summary = extract_event_summary(title, summary, content)
    
    return {
        "event_id": event_id,
        "title": title,
        "description": event_summary,
        "category": category,
        "event_type": event_type,
        "first_seen": pub_date or date.today(),
        "last_updated": pub_date or date.today(),
        "update_count": 1,
        "status": "active",
        "related_articles": []
    }


def update_event_with_article(event: dict, title: str, pub_date: date = None, 
                              summary: str = None) -> dict:
    """
    用新文章更新事件
    
    Args:
        event: 原事件
        title: 新文章标题
        pub_date: 发布日期
        summary: 摘要
    
    Returns:
        更新后的事件
    """
    # 添加到关联文章
    related = event.get("related_articles", [])
    if not isinstance(related, list):
        related = []
    
    related.insert(0, {
        "title": title,
        "date": str(pub_date) if pub_date else str(date.today()),
        "summary": summary[:100] if summary else None
    })
    
    # 只保留最近20篇
    related = related[:20]
    
    # 更新事件
    event["related_articles"] = related
    event["update_count"] = event.get("update_count", 0) + 1
    event["last_updated"] = pub_date or date.today()
    
    # 如果标题更长或更新，更新事件标题
    if len(title) > len(event.get("title", "")):
        event["title"] = title
    
    return event


class EventTracker:
    """事件追踪器"""
    
    def __init__(self):
        self._events_cache: dict[str, dict] = {}
    
    def process_article(self, title: str, summary: str = None, content: str = None,
                       category: str = "其他", pub_date: date = None) -> Optional[dict]:
        """
        处理文章，检测或更新事件
        
        Args:
            title: 标题
            summary: 摘要
            content: 正文
            category: 分类
            pub_date: 发布日期
        
        Returns:
            新建或更新的事件，或 None
        """
        # 检测事件
        event_info = detect_event_from_article(title, summary, content, category, pub_date)
        if not event_info:
            return None
        
        event_id = event_info["event_id"]
        
        # 检查是否已有此事件
        if event_id in self._events_cache:
            # 更新已有事件
            self._events_cache[event_id] = update_event_with_article(
                self._events_cache[event_id], title, pub_date, summary
            )
            return self._events_cache[event_id]
        else:
            # 新建事件
            self._events_cache[event_id] = event_info
            return event_info
    
    def get_event(self, event_id: str) -> Optional[dict]:
        """获取事件"""
        return self._events_cache.get(event_id)
    
    def get_all_events(self, category: str = None, status: str = None, 
                       limit: int = 50) -> list[dict]:
        """获取所有事件"""
        events = list(self._events_cache.values())
        
        if category:
            events = [e for e in events if e.get("category") == category]
        if status:
            events = [e for e in events if e.get("status") == status]
        
        # 按更新时间排序
        events.sort(key=lambda x: x.get("last_updated", ""), reverse=True)
        
        return events[:limit]
    
    def clear_cache(self):
        """清空缓存"""
        self._events_cache.clear()


# 全局事件追踪器实例
_event_tracker = EventTracker()


def get_event_tracker() -> EventTracker:
    """获取事件追踪器实例"""
    return _event_tracker
