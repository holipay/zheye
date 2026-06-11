"""
事件追踪模块
从新闻中提取事件，识别同一事件的后续报道

功能：
1. 事件提取 - 从新闻标题/摘要中识别事件
2. 事件关联 - 通过相似度匹配关联同一事件
3. 事件更新 - 追踪事件发展

事件检测策略（3级匹配）：
1. 精确匹配：清理标题后的完全一致
2. 关键实体匹配：提取实体后进行集合匹配
3. 语义相似度：文本相似度兜底（仅对未匹配的）
"""

import hashlib
import logging
import re
from datetime import date
from typing import Optional

from scraper.pipeline.utils import text_similarity

logger = logging.getLogger(__name__)

# 关键实体提取模式
_ENTITY_PATTERNS = [
    # 数字+bp/bps（如 25bp, 50bps）
    re.compile(r'\b\d+(?:\.\d+)?\s*bp(?:s)?\b', re.IGNORECASE),
    # 数字+%（如 5%, 0.25%）- 不用 \b 结尾
    re.compile(r'\b\d+(?:\.\d+)?\s*%', re.IGNORECASE),
    # 数字+percent/basis points
    re.compile(r'\b\d+(?:\.\d+)?\s*(?:percent|basis\s*points?)\b', re.IGNORECASE),
    # 数字+中文单位
    re.compile(r'\d+(?:\.\d+)?(?:万亿|亿|百万)'),
    # 货币符号+数字
    re.compile(r'[$€£¥]\s*\d+(?:\.\d+)?(?:\s*[MBT]?)?'),
    # 机构名称
    re.compile(r'\b(?:Fed|ECB|BOJ|BOE|PBOC|IMF|World\s*Bank|OPEC|SEC|FDA)\b', re.IGNORECASE),
    re.compile(r'(?:美联储|欧央行|日本央行|英国央行|央行|证监会|银保监会)'),
    # 国家/地区
    re.compile(r'\b(?:US|China|Japan|EU|UK|Russia|Ukraine|India)\b', re.IGNORECASE),
    re.compile(r'(?:美国|中国|日本|欧洲|英国|俄罗斯|乌克兰|印度)'),
    # 公司名（常见）
    re.compile(r'\b(?:Apple|Google|Microsoft|Amazon|Tesla|Nvidia|OpenAI)\b', re.IGNORECASE),
    re.compile(r'(?:苹果|谷歌|微软|亚马逊|特斯拉|英伟达)'),
]

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
    基于关键实体和分类，同一事件的后续报道应有相同 ID
    
    Args:
        title: 新闻标题
        category: 分类
        pub_date: 发布日期
    
    Returns:
        事件 ID (16 字符)
    """
    # 提取关键实体
    entities = extract_key_entities(title)
    
    # 生成事件特征：分类 + 排序后的实体
    event_key = f"{category}:{'|'.join(sorted(entities))}"
    
    # 生成哈希
    hash_str = hashlib.md5(event_key.encode()).hexdigest()[:16]
    return f"EVT-{hash_str[:8]}"


def extract_key_entities(title: str) -> list[str]:
    """
    从标题中提取关键实体（带归一化）
    
    Args:
        title: 新闻标题
    
    Returns:
        实体列表（已去重、归一化、排序）
    """
    entities = set()
    for pattern in _ENTITY_PATTERNS:
        for match in pattern.finditer(title):
            entity = match.group().strip().lower()
            if len(entity) >= 2:
                entity = _normalize_entity(entity)
                entities.add(entity)
    return list(entities)


def _normalize_entity(entity: str) -> str:
    """
    归一化实体名称
    将常见变体统一为标准形式
    """
    # 数值归一化：25bp = 25 basis points = 0.25%
    bp_match = re.match(r'^(\d+(?:\.\d+)?)\s*bp(?:s)?$', entity)
    if bp_match:
        return f"{bp_match.group(1)}bp"
    
    # 百分比转基点：0.25% = 25bp
    pct_match = re.match(r'^(\d+(?:\.\d+)?)\s*(?:%|percent)$', entity)
    if pct_match:
        value = float(pct_match.group(1))
        # 如果是小数百分比（< 1%），转换为基点
        if value < 1 and value > 0:
            return f"{int(value * 100)}bp"
        return f"{pct_match.group(1)}%"
    
    # 基点文字归一化
    basis_match = re.match(r'^(\d+(?:\.\d+)?)\s*basis\s*points?$', entity)
    if basis_match:
        return f"{basis_match.group(1)}bp"
    
    # 货币符号归一化
    currency_map = {'$': 'usd', '€': 'eur', '£': 'gbp', '¥': 'cny/jpy'}
    for symbol, code in currency_map.items():
        if entity.startswith(symbol):
            return entity.replace(symbol, code + ' ')
    
    return entity


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
    return text_similarity(title1, title2)


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
    在已有事件中查找相关事件（3级匹配）
    
    Level 1: 精确匹配（清理标题后完全一致）
    Level 2: 关键实体匹配（实体集合重叠度）
    Level 3: 语义相似度（文本相似度兜底）
    
    Args:
        title: 新标题
        category: 分类
        existing_events: 已有事件列表
        threshold: 相似度阈值
    
    Returns:
        相关事件或 None
    """
    new_entities = set(extract_key_entities(title))
    cleaned_new = _clean_title(title)
    
    for event in existing_events:
        if event.get("category") != category:
            continue
        
        event_title = event.get("title", "")
        
        # Level 1: 精确匹配
        cleaned_event = _clean_title(event_title)
        if cleaned_new == cleaned_event:
            return event
        
        # Level 2: 关键实体匹配
        event_entities = set(extract_key_entities(event_title))
        if new_entities and event_entities:
            overlap = len(new_entities & event_entities) / max(len(new_entities | event_entities), 1)
            if overlap >= 0.5:  # 实体重叠度 >= 50%
                return event
        
        # Level 3: 检查与事件关联文章的相似度
        related_articles = event.get("related_articles", [])
        if isinstance(related_articles, list):
            for article in related_articles[:5]:
                article_title = article.get("title", "") if isinstance(article, dict) else ""
                if article_title:
                    # 也对关联文章做实体匹配
                    article_entities = set(extract_key_entities(article_title))
                    if new_entities and article_entities:
                        overlap = len(new_entities & article_entities) / max(len(new_entities | article_entities), 1)
                        if overlap >= 0.5:
                            return event
                    
                    # 语义相似度兜底
                    similarity = calculate_event_similarity(title, article_title)
                    if similarity >= threshold:
                        return event
    
    return None


def _clean_title(title: str) -> str:
    """
    清理标题用于比较
    移除时间词、标点、多余空格
    """
    cleaned = title.lower()
    # 移除常见时间词
    time_words = ["today", "yesterday", "this week", "last week", "monday", "tuesday", "wednesday", 
                  "thursday", "friday", "saturday", "sunday", "今天", "昨天", "本周", "上周",
                  "mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    for word in time_words:
        cleaned = cleaned.replace(word, "")
    # 移除标点和多余空格
    cleaned = re.sub(r'[^\w\s]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


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
    event_summary = (summary or content or title)[:200]
    
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
