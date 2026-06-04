"""deep_analyst/analogy.py 纯函数测试"""

from tests.deep_analyst_test_helper import ensure_deep_analyst_imports
ensure_deep_analyst_imports()

from deep_analyst.analogy import compute_structural_similarity, get_analogy_type_label


class TestComputeStructuralSimilarity:
    def test_identical_patterns(self):
        source = {
            "structural": {"causal_pattern": "tightening_cycle", "constraint_conditions": ["inflation"]},
            "abstract": {"economic_principle": "phillips_curve"},
        }
        target = {
            "structural": {"causal_pattern": "tightening_cycle", "constraint_conditions": ["inflation"]},
            "abstract": {"economic_principle": "phillips_curve"},
        }
        scores = compute_structural_similarity(source, target)
        assert scores["causal"] == 1.0
        assert scores["principle"] == 1.0
        assert scores["constraint"] == 1.0
        assert scores["overall"] == 1.0

    def test_completely_different(self):
        source = {
            "structural": {"causal_pattern": "pattern_a", "constraint_conditions": ["x"]},
            "abstract": {"economic_principle": "principle_a"},
        }
        target = {
            "structural": {"causal_pattern": "pattern_b", "constraint_conditions": ["y"]},
            "abstract": {"economic_principle": "principle_b"},
        }
        scores = compute_structural_similarity(source, target)
        assert scores["causal"] == 0.0
        assert scores["principle"] == 0.0
        assert scores["constraint"] == 0.0
        assert scores["overall"] == 0.0

    def test_partial_match_causal_only(self):
        source = {
            "structural": {"causal_pattern": "same_pattern", "constraint_conditions": ["a"]},
            "abstract": {"economic_principle": "principle_x"},
        }
        target = {
            "structural": {"causal_pattern": "same_pattern", "constraint_conditions": ["b"]},
            "abstract": {"economic_principle": "principle_y"},
        }
        scores = compute_structural_similarity(source, target)
        assert scores["causal"] == 1.0
        assert scores["principle"] == 0.0
        # overall = 1.0 * 0.4 + 0.0 * 0.3 + 0.0 * 0.3 = 0.4
        assert abs(scores["overall"] - 0.4) < 0.01

    def test_constraint_overlap(self):
        source = {
            "structural": {"causal_pattern": "", "constraint_conditions": ["a", "b", "c"]},
            "abstract": {"economic_principle": ""},
        }
        target = {
            "structural": {"causal_pattern": "", "constraint_conditions": ["b", "c", "d"]},
            "abstract": {"economic_principle": ""},
        }
        scores = compute_structural_similarity(source, target)
        # overlap = {b, c}, union = {a, b, c, d} -> 2/4 = 0.5
        assert scores["constraint"] == 0.5

    def test_empty_constraints(self):
        source = {
            "structural": {"causal_pattern": "p", "constraint_conditions": []},
            "abstract": {"economic_principle": ""},
        }
        target = {
            "structural": {"causal_pattern": "p", "constraint_conditions": []},
            "abstract": {"economic_principle": ""},
        }
        scores = compute_structural_similarity(source, target)
        assert scores["constraint"] == 0.0

    def test_missing_keys_graceful(self):
        source = {}
        target = {}
        scores = compute_structural_similarity(source, target)
        # Empty strings match each other, so causal/principle are 1.0
        assert scores["causal"] == 1.0
        assert scores["principle"] == 1.0
        assert scores["constraint"] == 0.0

    def test_overall_weights(self):
        source = {
            "structural": {"causal_pattern": "a", "constraint_conditions": ["x"]},
            "abstract": {"economic_principle": "p"},
        }
        target = {
            "structural": {"causal_pattern": "a", "constraint_conditions": ["x"]},
            "abstract": {"economic_principle": "p"},
        }
        scores = compute_structural_similarity(source, target)
        assert scores["overall"] == 1.0


class TestGetAnalogyTypeLabel:
    def test_structural_zh(self):
        assert get_analogy_type_label("structural", "zh") == "结构性类比"

    def test_pattern_zh(self):
        assert get_analogy_type_label("pattern", "zh") == "模式类比"

    def test_principle_zh(self):
        assert get_analogy_type_label("principle", "zh") == "原理类比"

    def test_structural_en(self):
        assert get_analogy_type_label("structural", "en") == "Structural Analogy"

    def test_unknown_type_returns_original(self):
        assert get_analogy_type_label("unknown_type") == "unknown_type"

    def test_default_lang_is_zh(self):
        assert get_analogy_type_label("structural") == "结构性类比"
