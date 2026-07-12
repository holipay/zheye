"""
证据量化
将新闻 sentiment/importance 映射为贝叶斯更新的似然值
支持混合模式：先 sentiment 快速映射，高 importance 文章触发 LLM 精细分析
"""

import logging

from business_tracker.bayesian import DEFAULT_DIMENSIONS
from models.news import News
from scraper.pipeline.ai_analysis import DeepSeekClient

logger = logging.getLogger(__name__)

SENTIMENT_WEIGHTS = {
    "positive": 0.8,
    "negative": 0.2,
    "neutral": 0.5,
}

SENTIMENT_EVIDENCE = {
    "financial_health": {"positive": (0.7, 0.3), "negative": (0.2, 0.8), "neutral": (0.5, 0.5)},
    "brand_reputation": {"positive": (0.8, 0.2), "negative": (0.1, 0.9), "neutral": (0.5, 0.5)},
    "competitive_position": {"positive": (0.75, 0.25), "negative": (0.15, 0.85), "neutral": (0.5, 0.5)},
    "compliance_risk": {"positive": (0.85, 0.15), "negative": (0.1, 0.9), "neutral": (0.5, 0.5)},
}

LLM_IMPORTANCE_THRESHOLD = 0.6


def compute_evidence_from_sentiment(
    sentiment: str,
    sentiment_score: float,
    importance: float,
) -> dict[str, tuple[float, float]]:
    result = {}
    for dim in DEFAULT_DIMENSIONS:
        profile = SENTIMENT_EVIDENCE.get(dim, SENTIMENT_EVIDENCE["financial_health"])
        pos, neg = profile.get(sentiment, (0.5, 0.5))
        strength = importance * 2.0
        result[dim] = (strength, pos, neg)
    return result


async def llm_compute_evidence(
    ai_client: DeepSeekClient,
    article: News,
    company_name: str,
) -> dict[str, dict] | None:
    try:
        prompt = (
            f"Analyze how the following news article affects {company_name}'s business performance "
            f"across these dimensions:\n"
            f"- financial_health: financial condition\n"
            f"- brand_reputation: brand and public image\n"
            f"- competitive_position: market competitiveness\n"
            f"- compliance_risk: regulatory and compliance status\n\n"
            f"Title: {article.title}\n"
            f"Summary: {article.summary or ''}\n\n"
            f"For each dimension, return:\n"
            f"- direction: 'positive', 'negative', or 'neutral'\n"
            f"- strength: 0.0 to 1.0\n"
            f"- confidence: 0.0 to 1.0\n\n"
            f"Return as JSON: {{dimension: {{direction, strength, confidence}} }}"
        )
        response = await ai_client.client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        import json
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logger.warning(f"LLM evidence analysis failed for article {article.id}: {e}")
        return None


def parse_llm_evidence(
    llm_result: dict,
) -> dict[str, tuple[float, float, float]]:
    result = {}
    for dim in DEFAULT_DIMENSIONS:
        dim_data = llm_result.get(dim, {})
        direction = dim_data.get("direction", "neutral")
        strength = float(dim_data.get("strength", 0.5))
        confidence = float(dim_data.get("confidence", 0.5))

        if direction == "positive":
            pos_ratio, neg_ratio = 0.9, 0.1
        elif direction == "negative":
            pos_ratio, neg_ratio = 0.1, 0.9
        else:
            pos_ratio, neg_ratio = 0.5, 0.5

        effective_strength = strength * confidence
        result[dim] = (effective_strength, pos_ratio, neg_ratio)
    return result


async def process_article_evidence(
    article: News,
    company_name: str,
    ai_client: DeepSeekClient | None = None,
    use_llm: bool = False,
) -> dict[str, tuple[float, float, float]]:
    importance = article.ai_importance or 0.5
    sentiment = article.ai_sentiment or "neutral"
    sentiment_score = article.ai_sentiment_score or 0.0

    evidence = compute_evidence_from_sentiment(sentiment, sentiment_score, importance)

    if use_llm and ai_client and importance >= LLM_IMPORTANCE_THRESHOLD:
        llm_result = await llm_compute_evidence(ai_client, article, company_name)
        if llm_result:
            llm_evidence = parse_llm_evidence(llm_result)
            evidence = llm_evidence

    return evidence
