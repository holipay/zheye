from scraper.pipeline.classify import classify_by_keywords


class TestClassifyByKeywords:
    def test_stock_market_keyword(self):
        result = classify_by_keywords("Nasdaq hits record high")
        assert result == "股市与市场"

    def test_central_bank_keyword(self):
        result = classify_by_keywords("Fed raises interest rates")
        assert result == "央行与利率"

    def test_macro_keyword(self):
        result = classify_by_keywords("GDP growth exceeds expectations")
        assert result == "宏观经济"

    def test_commodity_keyword(self):
        result = classify_by_keywords("Oil prices surge amid supply concerns")
        assert result == "大宗商品与能源"

    def test_tech_keyword(self):
        result = classify_by_keywords("Apple launches new iPhone")
        assert result == "科技与企业"

    def test_international_keyword(self):
        result = classify_by_keywords("US imposes new tariffs on China")
        assert result == "国际财经"

    def test_summary_used(self):
        result = classify_by_keywords("Markets update", summary="The S&P 500 and Nasdaq rose sharply")
        assert result == "股市与市场"

    def test_no_match_returns_default(self):
        result = classify_by_keywords("Local weather forecast")
        assert result == "其他资讯"

    def test_custom_default(self):
        result = classify_by_keywords("Local weather forecast", default_category="未分类")
        assert result == "未分类"

    def test_empty_title(self):
        result = classify_by_keywords("")
        assert result == "其他资讯"

    def test_case_insensitive(self):
        result = classify_by_keywords("FED raises RATES")
        assert result == "央行与利率"

    def test_multiple_categories_highest_score_wins(self):
        result = classify_by_keywords("Fed stock market rate hike trading")
        assert result == "央行与利率" or result == "股市与市场"