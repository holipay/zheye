import logging

logger = logging.getLogger(__name__)

CATEGORY_KEYWORDS = {
    "国际财经": ["economy", "finance", "market", "stock", "trade", "bank", "inflation", "gdp", "fed", "interest rate"],
    "股市与市场": ["stock", "equity", "nasdaq", "dow", "s&p", "bull", "bear", "ipo", "dividend", "trading"],
    "国际时事": ["war", "conflict", "election", "diplomacy", "sanction", "un", "nato", "government", "president"],
    "科技": ["tech", "ai", "artificial intelligence", "startup", "software", "hardware", "apple", "google", "microsoft", "crypto"],
    "社会": ["health", "education", "climate", "environment", "protest", "crime", "law", "rights"],
}


def classify_by_keywords(title: str, summary: str = "", default_category: str = "其他") -> str:
    text = (title + " " + summary).lower()
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[category] = score
    if scores:
        return max(scores, key=scores.get)
    return default_category
