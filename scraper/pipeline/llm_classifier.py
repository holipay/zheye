"""
LLM 分类器模块
使用 DeepSeek API 进行文章语义分类

用于处理关键词匹配无法确定的边缘情况
"""

import json
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """分类结果"""
    category: str  # 分类名称
    confidence: float  # 置信度 0-1
    reason: str  # 分类理由（可选）


# 允许的分类列表（与 config.yaml 中的 categories 对应）
VALID_CATEGORIES = [
    "股市与市场",
    "央行与利率",
    "宏观经济",
    "大宗商品与能源",
    "科技与企业",
    "国际财经",
    "社会与人口",
    "政治与治理",
    "心理学与认知",
    "科技与研究",
    "健康与公共卫生",
    "环境与能源",
    "教育与媒体",
    "法律与伦理",
    "其他资讯",
]

# 需要过滤掉的分类
FILTERED_CATEGORIES = {"体育"}

# 分类提示词模板
CLASSIFY_PROMPT = """你是一个新闻分类专家。请将以下文章分类到最合适的类别中。

## 可选分类
{categories}

## 分类规则
1. 只从上述分类中选择最匹配的一个
2. 如果文章与财经、金融、经济、科技、政治、社会等主题无关（如体育、娱乐、八卦等），返回 "体育"（表示需要过滤）
3. 返回 JSON 格式：{{"category": "分类名", "confidence": 0.0-1.0}}

## 文章信息
标题: {title}
摘要: {summary}

请直接返回 JSON，不要有其他内容。"""


def _get_client():
    """获取共享 AI 客户端单例"""
    from scraper.pipeline.ai_analysis import get_ai_client
    return get_ai_client()


async def classify_with_llm(title: str, summary: str = "") -> Optional[ClassificationResult]:
    """
    使用 LLM 对文章进行分类（异步版本）
    
    Args:
        title: 文章标题
        summary: 文章摘要
        
    Returns:
        ClassificationResult 或 None（如果 API 调用失败）
    """
    client = _get_client()
    if not client.enabled:
        logger.debug("LLM 分类器未启用（缺少 API Key）")
        return None
    
    # 构建提示词
    categories_text = "\n".join(f"- {cat}" for cat in VALID_CATEGORIES + ["体育（表示需要过滤）"])
    prompt = CLASSIFY_PROMPT.format(
        categories=categories_text,
        title=title,
        summary=summary or "无"
    )
    
    messages = [
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = await client.chat(
            messages=messages,
            temperature=0.1,  # 低温度，确保结果稳定
            max_tokens=200,
            function_name="classify_article"
        )
        
        if not response:
            return None
        
        # 解析 JSON 响应
        result = _parse_response(response)
        if result:
            logger.debug(f"LLM 分类: '{title[:50]}...' -> {result.category} (置信度: {result.confidence})")
        return result
        
    except Exception as e:
        logger.warning(f"LLM 分类失败: {e}")
        return None


def _parse_response(response: str) -> Optional[ClassificationResult]:
    """
    解析 LLM 返回的 JSON 响应
    
    Args:
        response: LLM 返回的文本
        
    Returns:
        ClassificationResult 或 None
    """
    try:
        # 尝试提取 JSON
        response = response.strip()
        
        # 处理可能的 markdown 代码块
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])
        
        data = json.loads(response)
        
        category = data.get("category", "").strip()
        confidence = float(data.get("confidence", 0.5))
        
        # 验证分类是否有效
        if category in FILTERED_CATEGORIES:
            return ClassificationResult(
                category="体育",
                confidence=confidence,
                reason="文章与财经金融无关"
            )
        
        if category not in VALID_CATEGORIES:
            logger.warning(f"LLM 返回了无效的分类: {category}")
            return None
        
        # 限制置信度范围
        confidence = max(0.0, min(1.0, confidence))
        
        return ClassificationResult(
            category=category,
            confidence=confidence,
            reason=""
        )
        
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning(f"解析 LLM 响应失败: {response[:200]}..., 错误: {e}")
        return None
