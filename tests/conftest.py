import pytest


@pytest.fixture
def sample_rss_content():
    return """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel>
        <title>Test Feed</title>
        <item>
            <title>Fed raises interest rates by 25 basis points</title>
            <link>https://example.com/fed-rate-hike</link>
            <summary>The Federal Reserve announced a rate hike.</summary>
            <pubDate>Mon, 01 Jun 2026 12:00:00 GMT</pubDate>
        </item>
        <item>
            <title>Apple reports record Q2 earnings</title>
            <link>https://example.com/apple-earnings</link>
            <summary>Apple Inc. reported strong quarterly results.</summary>
        </item>
    </channel></rss>"""


@pytest.fixture
def sample_rss_empty():
    return """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel>
        <title>Empty Feed</title>
    </channel></rss>"""


@pytest.fixture
def sample_rss_no_links():
    return """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel>
        <title>Bad Feed</title>
        <item>
            <title>Article without link</title>
        </item>
        <item>
            <link>https://example.com/no-title</link>
        </item>
    </channel></rss>"""


@pytest.fixture
def sample_news_titles():
    return [
        "Fed raises interest rates by 25 basis points",
        "Apple reports record Q2 earnings",
        "Oil prices surge amid supply concerns",
    ]