"""
公共工具模块
抽取各 pipeline 模块的重复逻辑
"""

import re
import json
import logging
from difflib import SequenceMatcher
from typing import Optional, List, Dict, Type
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


# ============================================================
# 文本处理
# ============================================================

def smart_truncate(text: str, max_len: int = 3000, threshold: float = 0.6) -> str:
    """
    在句子边界智能截断文本
    
    Args:
        text: 要截断的文本
        max_len: 最大长度
        threshold: 最小保留比例（相对于 max_len）
    
    Returns:
        截断后的文本
    """
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    # 在句子边界截断
    for sep in ['。', '.\n', '.', '；', '\n']:
        last_sep = truncated.rfind(sep)
        if last_sep > max_len * threshold:
            return truncated[:last_sep + len(sep)]
    return truncated


# ============================================================
# AI 响应解析
# ============================================================

def parse_ai_response(response: str, schema: Type[BaseModel] = None) -> Optional[dict]:
    """
    解析AI返回的JSON，支持多种格式和可选的 Schema 验证
    
    Args:
        response: AI返回的原始文本
        schema: Pydantic Schema 类（可选），用于验证数据结构
    
    Returns:
        解析后的字典，或 None
    """
    if not response:
        return None
    
    try:
        # 方法1: 从 markdown 代码块提取
        code_blocks = re.findall(r'```(?:json)?\s*\n(.*?)```', response, re.DOTALL)
        if code_blocks:
            json_str = code_blocks[-1].strip()  # 取最后一个代码块
        else:
            # 方法2: 提取裸 JSON（支持 {} 和 []）
            json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', response)
            if json_match:
                json_str = json_match.group(1)
            else:
                logger.error(f"AI 响应中未找到 JSON: {response[:200]}...")
                return None
        
        # 清理常见问题
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)  # 移除尾部逗号
        json_str = re.sub(r'//.*?\n', '\n', json_str)  # 移除单行注释
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)  # 移除多行注释
        
        result = json.loads(json_str)
        
        # Schema 验证
        if schema and result:
            try:
                validated = schema(**result)
                return validated.model_dump()
            except ValidationError as e:
                logger.warning(f"Schema 验证失败，使用原始数据: {e}")
                # 验证失败时仍返回原始数据，但记录警告
                return result
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}, 原文前200字: {response[:200]}...")
        return None
    except Exception as e:
        logger.error(f"解析AI响应异常: {e}")
        return None


async def ai_analyze(prompt: str, ai_client, *, 
                     temperature: float = 0.3,
                     max_tokens: int = 3000,
                     system_message: str = None,
                     schema: Type[BaseModel] = None,
                     function_name: str = "ai_analyze") -> Optional[dict]:
    """
    通用 AI 分析调用器
    
    Args:
        prompt: 用户提示词
        ai_client: AI 客户端实例
        temperature: 温度参数
        max_tokens: 最大 token 数
        system_message: 系统消息（可选）
        schema: Pydantic Schema 类（可选），用于验证返回数据
        function_name: 调用函数名（用于指标统计）
    
    Returns:
        解析后的结果字典，或 None
    """
    if not ai_client or not ai_client.enabled:
        logger.warning("AI 未启用")
        return None
    
    # 构建消息
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})
    
    try:
        # 使用公共 chat 方法
        response = await ai_client.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            function_name=function_name
        )
        
        if not response:
            return None
        
        result = parse_ai_response(response, schema=schema)
        if result:
            result['ai_model'] = 'deepseek-chat'
            result['ai_confidence'] = 0.8
        
        return result
        
    except Exception as e:
        logger.error(f"AI 分析失败: {e}")
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
