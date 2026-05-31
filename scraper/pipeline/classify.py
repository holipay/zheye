import logging
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)

def load_categories() -> dict:
    config_path = Path(__file__).parent / "sources" / "config.yaml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config.get("categories", {})
    except Exception as e:
        logger.error(f"Error loading categories config: {e}")
        return {}

CATEGORIES = load_categories()

DEFAULT_KEYWORDS = {
    "股市与市场": ["stock", "equity", "nasdaq", "s&p", "dow", "ipo", "trading", "market"],
    "央行与利率": ["fed", "ecb", "interest rate", "rate cut", "rate hike", "bond", "yield"],
    "宏观经济": ["gdp", "cpi", "inflation", "pmi", "unemployment", "recession", "trade"],
    "大宗商品与能源": ["oil", "gold", "copper", "commodity", "opec", "natural gas"],
    "科技与企业": ["apple", "google", "microsoft", "tesla", "nvidia", "ai", "chip", "tech"],
    "国际财经": ["tariff", "sanctions", "forex", "geopolitics", "imf", "world bank"],
}


def classify_by_keywords(title: str, summary: str = "", default_category: str = "其他资讯") -> str:
    text = (title + " " + summary).lower()
    
    categories_to_use = CATEGORIES if CATEGORIES else DEFAULT_KEYWORDS
    
    scores = {}
    for category, config in categories_to_use.items():
        keywords = config.get("keywords", config) if isinstance(config, dict) else config
        if not isinstance(keywords, list):
            continue
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[category] = score
    
    if scores:
        return max(scores, key=scores.get)
    return default_category
