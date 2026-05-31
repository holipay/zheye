import hashlib
import logging
import os
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

MYMEMORY_URL = "https://api.mymemory.translated.net/get"


async def translate_text(text: str, source_lang: str = "en", target_lang: str = "zh") -> Optional[str]:
    if not text or len(text.strip()) == 0:
        return text
    if source_lang == target_lang:
        return text
    try:
        email = os.getenv("MYMEMORY_EMAIL", "user@example.com")
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(MYMEMORY_URL, params={
                "q": text[:500],
                "langpair": f"{source_lang}|{target_lang}",
                "de": email,
            })
            response.raise_for_status()
            data = response.json()
            if data.get("responseStatus") == 200:
                translated = data["responseData"]["translatedText"]
                if translated and translated != text:
                    return translated
    except Exception as e:
        logger.error(f"Translation error: {e}")
    return None


def get_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
