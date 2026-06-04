"""
NER (Named Entity Recognition) 模块
使用 spaCy 进行命名实体识别

功能：
1. 支持中英文实体识别
2. 识别组织、人名、地名、货币等
3. 与正则匹配结果合并
"""

import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# spaCy 模型缓存
_nlp_zh: Optional[object] = None
_nlp_en: Optional[object] = None

# spaCy 实体类型到自定义类型的映射
SPACY_TYPE_MAP = {
    "ORG": "organization",      # 组织/公司
    "PERSON": "person",         # 人名
    "GPE": "country",           # 地理政治实体（国家、城市）
    "LOC": "location",          # 地点
    "MONEY": "currency",        # 货币
    "PERCENT": "percentage",    # 百分比
    "DATE": "date",             # 日期
    "PRODUCT": "product",       # 产品
    "EVENT": "event",           # 事件
    "WORK_OF_ART": "work",      # 作品
}

# 需要过滤的实体类型（噪音）
FILTERED_TYPES = {"CARDINAL", "ORDINAL", "QUANTITY", "TIME"}


def _get_nlp(lang: str = "en"):
    """获取 spaCy 模型（懒加载）"""
    global _nlp_zh, _nlp_en
    
    if lang == "zh":
        if _nlp_zh is None:
            try:
                import spacy
                _nlp_zh = spacy.load("zh_core_web_sm")
                logger.info("Loaded spaCy Chinese model")
            except Exception as e:
                logger.warning(f"Failed to load spaCy Chinese model: {e}")
                return None
        return _nlp_zh
    else:
        if _nlp_en is None:
            try:
                import spacy
                _nlp_en = spacy.load("en_core_web_sm")
                logger.info("Loaded spaCy English model")
            except Exception as e:
                logger.warning(f"Failed to load spaCy English model: {e}")
                return None
        return _nlp_en


def _detect_language(text: str) -> str:
    """检测文本语言（简单启发式）"""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    if chinese_chars > len(text) * 0.1:
        return "zh"
    return "en"


def _get_context(text: str, start: int, end: int, max_len: int = 100) -> str:
    """获取实体上下文"""
    ctx_start = max(0, start - 30)
    ctx_end = min(len(text), end + 30)
    return text[ctx_start:ctx_end].strip()[:max_len]


def extract_entities_ner(text: str) -> list[dict]:
    """
    使用 spaCy NER 提取实体
    
    Args:
        text: 输入文本
        
    Returns:
        实体列表 [{"name": "...", "entity_type": "...", "context": "..."}, ...]
    """
    if not text or len(text.strip()) < 5:
        return []
    
    # 检测语言
    lang = _detect_language(text)
    nlp = _get_nlp(lang)
    
    if nlp is None:
        return []
    
    try:
        doc = nlp(text)
    except Exception as e:
        logger.warning(f"spaCy NER failed: {e}")
        return []
    
    results = []
    seen = set()
    
    for ent in doc.ents:
        # 过滤噪音类型
        if ent.label_ in FILTERED_TYPES:
            continue
        
        # 映射实体类型
        entity_type = SPACY_TYPE_MAP.get(ent.label_)
        if not entity_type:
            continue
        
        # 去重
        name = ent.text.strip()
        if not name or len(name) < 2:
            continue
        
        key = f"{name.lower()}:{entity_type}"
        if key in seen:
            continue
        seen.add(key)
        
        results.append({
            "name": name,
            "entity_type": entity_type,
            "context": _get_context(text, ent.start_char, ent.end_char),
        })
    
    return results


def extract_entities_hybrid(text: str, regex_entities: list[dict]) -> list[dict]:
    """
    混合实体提取：NER + 正则
    
    策略：
    1. NER 提取命名实体（组织、人名、地名）
    2. 正则提取数值实体（货币、百分比）
    3. 合并结果，NER 优先
    
    Args:
        text: 输入文本
        regex_entities: 正则匹配的实体
        
    Returns:
        合并后的实体列表
    """
    # NER 提取
    ner_entities = extract_entities_ner(text)
    
    # 构建 NER 实体索引（用于去重）
    ner_keys = set()
    ner_names = set()  # 用于模糊去重
    for ent in ner_entities:
        key = f"{ent['name'].lower()}:{ent['entity_type']}"
        ner_keys.add(key)
        ner_names.add(ent['name'].lower())
    
    # 合并结果，NER 优先
    results = list(ner_entities)
    
    # 添加正则匹配的数值实体（如果 NER 没有覆盖）
    for ent in regex_entities:
        entity_type = ent.get("entity_type", "")
        name = ent.get("name", "")
        
        # 数值实体类型（正则更准确）
        if entity_type in ("currency", "percentage", "basis_point", "large_number"):
            # 检查是否与 NER 实体重叠
            name_lower = name.lower().replace('$', '').replace('%', '').strip()
            if not any(name_lower in ner_name or ner_name in name_lower for ner_name in ner_names):
                results.append(ent)
            continue
        
        # 命名实体类型（NER 优先）
        key = f"{name.lower()}:{entity_type}"
        if key not in ner_keys:
            # 模糊去重：检查名称是否已存在
            name_lower = name.lower()
            if not any(name_lower in ner_name or ner_name in name_lower for ner_name in ner_names):
                results.append(ent)
    
    return results


def close_models():
    """释放模型资源"""
    global _nlp_zh, _nlp_en
    _nlp_zh = None
    _nlp_en = None
    logger.info("Released spaCy models")
