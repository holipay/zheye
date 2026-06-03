import json
from pathlib import Path
from typing import Dict, Any

LOCALES_DIR = Path(__file__).parent / "locales"
SUPPORTED_LANGUAGES = {"en", "zh"}
DEFAULT_LANGUAGE = "en"

_translations: Dict[str, Dict[str, Any]] = {}


def _load_translations():
    global _translations
    for lang in SUPPORTED_LANGUAGES:
        file_path = LOCALES_DIR / f"{lang}.json"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                _translations[lang] = json.load(f)


def get_text(lang: str, key: str, **kwargs) -> str:
    if not _translations:
        _load_translations()

    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    keys = key.split(".")
    value = _translations.get(lang, {})

    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
            if value is None:
                # 如果翻译不存在，返回键的最后一部分（如分类名称本身）
                return keys[-1]
        else:
            return keys[-1]

    if isinstance(value, str) and kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError):
            return value

    return value if isinstance(value, str) else keys[-1]


def get_language_from_request(request) -> str:
    path = request.url.path
    for lang in SUPPORTED_LANGUAGES:
        if path.startswith(f"/{lang}/") or path == f"/{lang}":
            return lang
    return DEFAULT_LANGUAGE
