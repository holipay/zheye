"""deep_analyst/models/causal_chain.py 纯函数测试"""

from tests.deep_analyst_test_helper import ensure_deep_analyst_imports
ensure_deep_analyst_imports()

from deep_analyst.models.causal_chain import NodeType


class TestNodeType:
    def test_constants_exist(self):
        assert NodeType.ROOT_CAUSE == "root_cause"
        assert NodeType.TRIGGER == "trigger"
        assert NodeType.IMMEDIATE == "immediate"
        assert NodeType.SHORT_TERM == "short_term"
        assert NodeType.LONG_TERM == "long_term"
        assert NodeType.SCENARIO == "scenario"

    def test_get_label_zh(self):
        assert NodeType.get_label("root_cause", "zh") == "根本原因"
        assert NodeType.get_label("trigger", "zh") == "触发因素"
        assert NodeType.get_label("immediate", "zh") == "即时影响"
        assert NodeType.get_label("short_term", "zh") == "短期效应"
        assert NodeType.get_label("long_term", "zh") == "长期走向"
        assert NodeType.get_label("scenario", "zh") == "可能情景"

    def test_get_label_en(self):
        assert NodeType.get_label("root_cause", "en") == "Root Cause"
        assert NodeType.get_label("trigger", "en") == "Trigger"
        assert NodeType.get_label("scenario", "en") == "Scenario"

    def test_get_label_unknown_type(self):
        assert NodeType.get_label("unknown") == "unknown"

    def test_get_label_default_lang_is_zh(self):
        assert NodeType.get_label("root_cause") == "根本原因"

    def test_get_icon_known_types(self):
        assert NodeType.get_icon("root_cause") == "🌱"
        assert NodeType.get_icon("trigger") == "⚡"
        assert NodeType.get_icon("immediate") == "💥"
        assert NodeType.get_icon("short_term") == "📈"
        assert NodeType.get_icon("long_term") == "🔮"
        assert NodeType.get_icon("scenario") == "🎯"

    def test_get_icon_unknown_type(self):
        assert NodeType.get_icon("unknown") == "•"
