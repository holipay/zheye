from scraper.sources.rss_parser import parse_feed, parse_date, RSSItem


class TestParseFeed:
    def test_parses_valid_rss(self, sample_rss_content):
        items = parse_feed(sample_rss_content, source_name="TestSource", category="测试")
        assert len(items) == 2
        assert items[0].title == "Fed raises interest rates by 25 basis points"
        assert items[0].link == "https://example.com/fed-rate-hike"
        assert items[0].source == "TestSource"
        assert items[0].category == "测试"

    def test_empty_feed(self, sample_rss_empty):
        items = parse_feed(sample_rss_empty)
        assert items == []

    def test_missing_title_or_link(self, sample_rss_no_links):
        items = parse_feed(sample_rss_no_links)
        assert items == []

    def test_summary_truncated(self):
        long_summary = "x" * 2000
        content = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel>
            <item>
                <title>Test</title>
                <link>https://example.com</link>
                <summary>{long_summary}</summary>
            </item>
        </channel></rss>"""
        items = parse_feed(content)
        assert len(items[0].summary) == 1000

    def test_lang_and_source_set(self, sample_rss_content):
        items = parse_feed(sample_rss_content, source_name="Reuters", lang="en")
        assert items[0].lang == "en"
        assert items[0].source == "Reuters"

    def test_invalid_content(self):
        items = parse_feed("not valid xml at all")
        assert items == []

    def test_date_parsed(self, sample_rss_content):
        items = parse_feed(sample_rss_content)
        assert items[0].date is not None

    def test_returns_rssitem_instances(self, sample_rss_content):
        items = parse_feed(sample_rss_content)
        assert all(isinstance(item, RSSItem) for item in items)