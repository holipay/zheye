import logging
import re
from pathlib import Path
from typing import Optional, Tuple
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
    config_path = Path(__file__).parent.parent / "sources" / "config.yaml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config.get("categories", {})
    except Exception as e:
        logger.error(f"Error loading categories config: {e}")
        return {}

CATEGORIES = load_categories()

# 需要过滤掉的分类（与财经金融无关）
FILTERED_CATEGORIES = {"体育"}

# 短词保护：这些词必须使用严格边界匹配，避免误匹配
# 例如 "AI" 匹配 "said", "US" 匹配 "industry"
SHORT_WORD_STRICT_BOUNDARY = True
SHORT_WORD_MAX_LENGTH = 3

DEFAULT_KEYWORDS = {
    "股市与市场": ["stock", "equity", "nasdaq", "s&p", "dow", "ipo", "trading", "market"],
    "央行与利率": ["fed", "ecb", "interest rate", "rate cut", "rate hike", "bond", "yield"],
    "宏观经济": ["gdp", "cpi", "inflation", "pmi", "unemployment", "recession", "trade"],
    "大宗商品与能源": ["oil", "gold", "copper", "commodity", "opec", "natural gas"],
    "科技与企业": ["apple", "google", "microsoft", "tesla", "nvidia", "ai", "chip", "tech"],
    "国际财经": ["tariff", "sanctions", "forex", "geopolitics", "imf", "world bank"],
}


def _match_keyword(keyword: str, text: str) -> bool:
    """
    检查关键词是否在文本中匹配
    
    对短词（<=3字符）使用严格边界匹配，避免误匹配：
    - "AI" 不会匹配 "said", "paid", "main"
    - "US" 不会匹配 "industry", "bonus"
    - "ECB" 不会匹配 "ECBC" (某个缩写)
    
    对长词使用标准 \b 词边界匹配
    """
    kw_lower = keyword.lower()
    
    # 中文关键词使用简单包含（中文没有词边界概念）
    if any('\u4e00' <= c <= '\u9fff' for c in keyword):
        return kw_lower in text
    
    # 短词使用严格边界
    if SHORT_WORD_STRICT_BOUNDARY and len(keyword) <= SHORT_WORD_MAX_LENGTH:
        # 使用负向前瞻和后瞻确保不是更长单词的一部分
        # (?<![a-zA-Z]) 表示前面不是字母
        # (?![a-zA-Z]) 表示后面不是字母
        pattern = re.compile(r'(?<![a-zA-Z])' + re.escape(kw_lower) + r'(?![a-zA-Z])', re.IGNORECASE)
        return bool(pattern.search(text))
    
    # 长词使用标准词边界
    pattern = re.compile(r'\b' + re.escape(kw_lower) + r'\b', re.IGNORECASE)
    return bool(pattern.search(text))


def classify_by_keywords(title: str, summary: str = "", default_category: str = "其他资讯") -> Optional[str]:
    text = (title + " " + summary).lower()
    
    categories_to_use = CATEGORIES if CATEGORIES else DEFAULT_KEYWORDS
    
    scores = {}
    for category, config in categories_to_use.items():
        keywords = config.get("keywords", config) if isinstance(config, dict) else config
        if not isinstance(keywords, list):
            continue
        score = sum(1 for kw in keywords if _match_keyword(kw, text))
        if score > 0:
            scores[category] = score
    
    if scores:
        best_category = max(scores, key=scores.get)
        # 如果匹配到需要过滤的分类，返回 None
        if best_category in FILTERED_CATEGORIES:
            return None
        return best_category
    return default_category


def detect_article_type(title: str, summary: str = "", content: str = "") -> str:
    text = " ".join(filter(None, [title, summary]))

    for article_type, patterns in TYPE_PATTERNS:
        for pattern in patterns:
            if pattern.search(text):
                return article_type

    return "news"


def _classify_by_llm(title: str, summary: str, scores: dict) -> Tuple[Optional[str], float, str]:
    """内部函数：使用 LLM 进行分类"""
    try:
        from scraper.pipeline.llm_classifier import classify_with_llm
        result = classify_with_llm(title, summary)
        
        if result is None:
            # LLM 调用失败，降级到关键词结果
            logger.warning(f"LLM 分类失败，降级到关键词结果")
            if scores:
                best_category = max(scores, key=scores.get)
                if best_category in FILTERED_CATEGORIES:
                    return None, 0.5, "keywords"
                return best_category, 0.5, "keywords"
            return "其他资讯", 0.3, "keywords"
        
        if result.category == "体育":
            logger.debug(f"LLM 过滤: '{title[:50]}...' -> 体育 (置信度: {result.confidence})")
            return None, result.confidence, "llm"
        
        logger.debug(f"LLM 分类: '{title[:50]}...' -> {result.category} (置信度: {result.confidence})")
        return result.category, result.confidence, "llm"
        
    except Exception as e:
        logger.warning(f"LLM 分类异常: {e}")
        # 降级到关键词结果
        if scores:
            best_category = max(scores, key=scores.get)
            if best_category in FILTERED_CATEGORIES:
                return None, 0.5, "keywords"
            return best_category, 0.5, "keywords"
        return "其他资讯", 0.3, "keywords"


async def _classify_by_llm_async(title: str, summary: str, scores: dict) -> Tuple[Optional[str], float, str]:
    """内部函数：异步使用 LLM 进行分类"""
    try:
        from scraper.pipeline.llm_classifier import classify_with_llm_async
        result = await classify_with_llm_async(title, summary)
        
        if result is None:
            # LLM 调用失败，降级到关键词结果
            logger.warning(f"LLM 分类失败，降级到关键词结果")
            if scores:
                best_category = max(scores, key=scores.get)
                if best_category in FILTERED_CATEGORIES:
                    return None, 0.5, "keywords"
                return best_category, 0.5, "keywords"
            return "其他资讯", 0.3, "keywords"
        
        if result.category == "体育":
            logger.debug(f"LLM 过滤: '{title[:50]}...' -> 体育 (置信度: {result.confidence})")
            return None, result.confidence, "llm"
        
        logger.debug(f"LLM 分类: '{title[:50]}...' -> {result.category} (置信度: {result.confidence})")
        return result.category, result.confidence, "llm"
        
    except Exception as e:
        logger.warning(f"LLM 分类异常: {e}")
        # 降级到关键词结果
        if scores:
            best_category = max(scores, key=scores.get)
            if best_category in FILTERED_CATEGORIES:
                return None, 0.5, "keywords"
            return best_category, 0.5, "keywords"
        return "其他资讯", 0.3, "keywords"


def classify_hybrid(title: str, summary: str = "", use_llm: bool = True) -> Tuple[Optional[str], float, str]:
    """
    混合分类方法：关键词快速过滤 + LLM 语义分类
    
    流程：
    1. 关键词匹配：如果明确匹配到有效分类，直接返回
    2. 关键词匹配：如果明确匹配到过滤分类，直接过滤
    3. LLM 分类：处理不确定的边缘情况
    
    Args:
        title: 文章标题
        summary: 文章摘要
        use_llm: 是否使用 LLM（可关闭）
        
    Returns:
        (category, confidence, method) 元组
        - category: 分类名，None 表示需要过滤
        - confidence: 置信度 0-1
        - method: 使用的方法 ("keywords" 或 "llm")
    """
    text = (title + " " + summary).lower()
    categories_to_use = CATEGORIES if CATEGORIES else DEFAULT_KEYWORDS
    
    # 第一层：关键词快速匹配
    scores = {}
    for category, config in categories_to_use.items():
        keywords = config.get("keywords", config) if isinstance(config, dict) else config
        if not isinstance(keywords, list):
            continue
        score = sum(1 for kw in keywords if _match_keyword(kw, text))
        if score > 0:
            scores[category] = score
    
    # 如果有明确的关键词匹配
    if scores:
        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]
        
        # 匹配到过滤分类，直接过滤
        if best_category in FILTERED_CATEGORIES:
            logger.debug(f"关键词过滤: '{title[:50]}...' -> {best_category} (得分: {best_score})")
            return None, 1.0, "keywords"
        
        # 匹配到有效分类，且得分较高（>=2 个关键词命中），直接通过
        if best_score >= 2:
            confidence = min(0.9, 0.6 + best_score * 0.1)
            logger.debug(f"关键词分类: '{title[:50]}...' -> {best_category} (得分: {best_score}, 置信度: {confidence})")
            return best_category, confidence, "keywords"
        
        # 得分较低（1 个关键词），需要 LLM 确认
        logger.debug(f"关键词不确定: '{title[:50]}...' -> {best_category} (得分: {best_score})，需要 LLM 确认")
    else:
        logger.debug(f"关键词无匹配: '{title[:50]}...'，需要 LLM 分类")
    
    # 第二层：LLM 语义分类
    if not use_llm:
        # 不使用 LLM，返回默认分类
        if scores:
            best_category = max(scores, key=scores.get)
            if best_category in FILTERED_CATEGORIES:
                return None, 0.5, "keywords"
            return best_category, 0.5, "keywords"
        return "其他资讯", 0.3, "keywords"
    
    return _classify_by_llm(title, summary, scores)


async def classify_hybrid_async(title: str, summary: str = "", use_llm: bool = True) -> Tuple[Optional[str], float, str]:
    """
    混合分类方法（异步版本）
    
    使用 asyncio.to_thread 将同步 LLM 调用转为异步，避免阻塞事件循环
    
    Args:
        title: 文章标题
        summary: 文章摘要
        use_llm: 是否使用 LLM（可关闭）
        
    Returns:
        (category, confidence, method) 元组
    """
    text = (title + " " + summary).lower()
    categories_to_use = CATEGORIES if CATEGORIES else DEFAULT_KEYWORDS
    
    # 第一层：关键词快速匹配
    scores = {}
    for category, config in categories_to_use.items():
        keywords = config.get("keywords", config) if isinstance(config, dict) else config
        if not isinstance(keywords, list):
            continue
        score = sum(1 for kw in keywords if _match_keyword(kw, text))
        if score > 0:
            scores[category] = score
    
    # 如果有明确的关键词匹配
    if scores:
        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]
        
        # 匹配到过滤分类，直接过滤
        if best_category in FILTERED_CATEGORIES:
            logger.debug(f"关键词过滤: '{title[:50]}...' -> {best_category} (得分: {best_score})")
            return None, 1.0, "keywords"
        
        # 匹配到有效分类，且得分较高（>=2 个关键词命中），直接通过
        if best_score >= 2:
            confidence = min(0.9, 0.6 + best_score * 0.1)
            logger.debug(f"关键词分类: '{title[:50]}...' -> {best_category} (得分: {best_score}, 置信度: {confidence})")
            return best_category, confidence, "keywords"
        
        # 得分较低（1 个关键词），需要 LLM 确认
        logger.debug(f"关键词不确定: '{title[:50]}...' -> {best_category} (得分: {best_score})，需要 LLM 确认")
    else:
        logger.debug(f"关键词无匹配: '{title[:50]}...'，需要 LLM 分类")
    
    # 第二层：LLM 语义分类（异步）
    if not use_llm:
        # 不使用 LLM，返回默认分类
        if scores:
            best_category = max(scores, key=scores.get)
            if best_category in FILTERED_CATEGORIES:
                return None, 0.5, "keywords"
            return best_category, 0.5, "keywords"
        return "其他资讯", 0.3, "keywords"
    
    return await _classify_by_llm_async(title, summary, scores)
