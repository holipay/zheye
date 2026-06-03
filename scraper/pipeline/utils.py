"""
公共工具模块
抽取各 pipeline 模块的重复逻辑
"""

import json
import logging
from difflib import SequenceMatcher
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


# ============================================================
# AI 响应解析
# ============================================================

def parse_ai_response(response: str) -> Optional[dict]:
    """
    解析AI返回的JSON，支持 ```json 代码块和裸JSON
    
    Args:
        response: AI返回的原始文本
    
    Returns:
        解析后的字典，或 None
    """
    try:
        if "```json" in response:
            start = response.index("```json") + 7
            end = response.index("```", start)
            json_str = response[start:end].strip()
        elif "```" in response:
            start = response.index("```") + 3
            end = response.index("```", start)
            json_str = response[start:end].strip()
        else:
            json_str = response.strip()
        
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"解析AI响应失败: {e}")
        return None


# ============================================================
# 文章摘要格式化
# ============================================================

def format_article_summaries(articles: list, max_articles: int = 5, max_summary_len: int = 200) -> str:
    """
    将文章列表格式化为编号摘要文本，用于AI提示词
    
    Args:
        articles: 文章列表 [{title, summary, ...}, ...]
        max_articles: 最多取前N篇
        max_summary_len: 每篇摘要最大长度
    
    Returns:
        格式化的文本，如 "1. 标题 - 摘要\n2. ..."
    """
    summaries = []
    for i, article in enumerate(articles[:max_articles], 1):
        summary = article.get('summary', article.get('title', ''))
        summaries.append(f"{i}. {article.get('title', '')} - {summary[:max_summary_len]}")
    
    return "\n".join(summaries) if summaries else "无相关文章"


# ============================================================
# 文本相似度计算
# ============================================================

def text_similarity(a: str, b: str) -> float:
    """
    计算两个字符串的相似度（忽略大小写）
    
    Args:
        a: 字符串1
        b: 字符串2
    
    Returns:
        相似度分数 0.0-1.0
    """
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()
