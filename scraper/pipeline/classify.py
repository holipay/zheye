import logging
import re
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)

OPINION_SIGNALS = [
    "opinion", "editorial", "commentary", "comment", "viewpoint", "perspective",
    "column", "op-ed", "op ed", "letter to", "why i", "why we",
    "观点", "评论", "社论", "专栏", "署名文章", "来信",
]

ANALYSIS_SIGNALS = [
    "analysis", "outlook", "forecast", "review", "assessment", "survey",
    "deep dive", "in-depth", "briefing", "white paper",
    "分析", "展望", "预测", "研判", "深度", "研究", "报告",
]

DATA_SIGNALS = [
    "report", "data", "statistics", "figures", "release", "index",
    "quarterly results", "earnings report", "annual report", "monthly report",
    "报告", "数据", "统计", "季报", "年报", "发布", "指数",
]

TYPE_PATTERNS = [
    ("opinion", [re.compile(r'\b' + re.escape(s) + r'\b', re.IGNORECASE) for s in OPINION_SIGNALS]),
    ("analysis", [re.compile(r'\b' + re.escape(s) + r'\b', re.IGNORECASE) for s in ANALYSIS_SIGNALS]),
    ("data", [re.compile(r'\b' + re.escape(s) + r'\b', re.IGNORECASE) for s in DATA_SIGNALS]),
]

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


def detect_article_type(title: str, summary: str = "", content: str = "") -> str:
    text = " ".join(filter(None, [title, summary]))

    for article_type, patterns in TYPE_PATTERNS:
        for pattern in patterns:
            if pattern.search(text):
                return article_type

    return "news"
