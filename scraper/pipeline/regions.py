import logging
import re

logger = logging.getLogger(__name__)

COUNTRY_TO_REGION = {
    "US": "Americas",
    "U.S.": "Americas",
    "USA": "Americas",
    "United States": "Americas",
    "美国": "Americas",
    "Canada": "Americas",
    "加拿大": "Americas",
    "Brazil": "Americas",
    "巴西": "Americas",
    "Mexico": "Americas",
    "UK": "Europe",
    "U.K.": "Europe",
    "United Kingdom": "Europe",
    "英国": "Europe",
    "Germany": "Europe",
    "德国": "Europe",
    "France": "Europe",
    "法国": "Europe",
    "Europe": "Europe",
    "欧盟": "Europe",
    "EU": "Europe",
    "欧元区": "Europe",
    "Japan": "Asia-Pacific",
    "日本": "Asia-Pacific",
    "South Korea": "Asia-Pacific",
    "韩国": "Asia-Pacific",
    "India": "Asia-Pacific",
    "印度": "Asia-Pacific",
    "Australia": "Asia-Pacific",
    "澳大利亚": "Asia-Pacific",
    "澳洲": "Asia-Pacific",
    "中国": "Greater China",
    "China": "Greater China",
    "Hong Kong": "Greater China",
    "香港": "Greater China",
    "Taiwan": "Greater China",
    "台湾": "Greater China",
    "Russia": "EMEA",
    "俄罗斯": "EMEA",
    "中东": "Middle East",
    "Middle East": "Middle East",
    "Saudi Arabia": "Middle East",
    "沙特": "Middle East",
    "UAE": "Middle East",
    "Africa": "Africa",
    "非洲": "Africa",
}

COUNTRY_PATTERNS = []
for country, region in COUNTRY_TO_REGION.items():
    if len(country) >= 2:
        COUNTRY_PATTERNS.append((country, region))


def extract_regions(title: str, summary: str = "", content: str = "") -> list[str]:
    text = " ".join(filter(None, [title, summary, content]))
    if not text.strip():
        return []

    found_regions = set()

    for country, region in COUNTRY_PATTERNS:
        if "." in country or len(country) <= 3:
            if re.search(r'(?<![a-zA-Z])' + re.escape(country) + r'(?![a-zA-Z])', text, re.IGNORECASE):
                found_regions.add(region)
        elif country.lower() in text.lower():
            found_regions.add(region)

    return sorted(found_regions)
