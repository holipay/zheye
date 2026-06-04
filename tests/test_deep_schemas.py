"""deep_analyst/schemas.py Pydantic 验证测试"""

from tests.deep_analyst_test_helper import ensure_deep_analyst_imports
ensure_deep_analyst_imports()

from deep_analyst.schemas import (
    KnowledgeAnalysisSchema,
    KnowledgeGapSchema,
    CausalStepSchema,
    KeyConceptSchema,
    KnowledgeAtomSchema,
    CausalNodeSchema,
    CausalLinkSchema,
    CausalChainSchema,
    EventRepresentationSchema,
    AnalogyResultSchema,
    ScenarioAnalysisSchema,
    KeyVariableSchema,
    ScenarioSchema,
    ThinkingQuestionSchema,
    get_schema,
    SCHEMA_MAP,
)


class TestKnowledgeSchemas:
    def test_knowledge_gap_valid(self):
        gap = KnowledgeGapSchema(topic="什么是基点", why_needed="理解利率变化", priority="high")
        assert gap.topic == "什么是基点"

    def test_causal_step_valid(self):
        step = CausalStepSchema(step=1, cause="原因", effect="结果", evidence="证据")
        assert step.step == 1

    def test_key_concept_valid(self):
        concept = KeyConceptSchema(concept="基点", definition="利率单位", relevance="直接相关")
        assert concept.concept == "基点"

    def test_knowledge_atom_valid(self):
        atom = KnowledgeAtomSchema(
            atom_type="background",
            title="背景知识",
            content="详细内容",
            entities=["美联储"],
            keywords=["加息"],
        )
        assert atom.atom_type == "background"

    def test_knowledge_analysis_full(self):
        data = {
            "background_summary": "事件背景",
            "knowledge_gaps": [{"topic": "缺口1", "why_needed": "原因"}],
            "causal_chain": [{"step": 1, "cause": "原因", "effect": "结果"}],
            "key_concepts": [{"concept": "概念", "definition": "定义"}],
            "knowledge_atoms": [{"atom_type": "bg", "title": "标题", "content": "内容"}],
        }
        result = KnowledgeAnalysisSchema(**data)
        assert len(result.knowledge_gaps) == 1
        assert len(result.causal_chain) == 1

    def test_knowledge_analysis_empty(self):
        result = KnowledgeAnalysisSchema()
        assert result.background_summary == ""
        assert result.knowledge_gaps == []


class TestCausalChainSchemas:
    def test_causal_node_valid(self):
        node = CausalNodeSchema(
            id="node_1",
            node_type="cause",
            title="根本原因",
            description="详细描述",
            confidence=0.9,
        )
        assert node.id == "node_1"
        assert node.confidence == 0.9

    def test_causal_node_defaults(self):
        node = CausalNodeSchema(id="n1", title="test")
        assert node.node_type.value == "cause"
        assert node.confidence == 0.8

    def test_causal_link_valid(self):
        link = CausalLinkSchema(source="n1", target="n2", link_type="causes", strength=0.9)
        assert link.source == "n1"
        assert link.strength == 0.9

    def test_causal_chain_schema(self):
        data = {
            "nodes": [
                {"id": "n1", "title": "原因"},
                {"id": "n2", "title": "结果"},
            ],
            "links": [
                {"source": "n1", "target": "n2"},
            ],
        }
        result = CausalChainSchema(**data)
        assert len(result.nodes) == 2
        assert len(result.links) == 1


class TestAnalogySchemas:
    def test_event_representation_valid(self):
        data = {
            "surface": {"summary": "概述", "entities": ["美联储"]},
            "structural": {"causal_pattern": "tightening", "causal_pattern_desc": "紧缩周期"},
            "abstract": {"economic_principle": "phillips", "economic_principle_desc": "菲利普斯曲线"},
        }
        result = EventRepresentationSchema(**data)
        assert result.surface.summary == "概述"
        assert result.structural.causal_pattern == "tightening"

    def test_event_representation_empty(self):
        result = EventRepresentationSchema()
        assert result.surface.summary == ""
        assert result.structural.causal_pattern == ""

    def test_analogy_result_valid(self):
        data = {
            "causal_similarity": 0.8,
            "decision_similarity": 0.7,
            "overall_similarity": 0.75,
            "analogy_type": "structural",
            "analogy_summary": "相似的因果结构",
            "confidence": 0.85,
        }
        result = AnalogyResultSchema(**data)
        assert result.overall_similarity == 0.75

    def test_analogy_result_defaults(self):
        result = AnalogyResultSchema()
        assert result.causal_similarity == 0.0


class TestScenarioSchemas:
    def test_key_variable_valid(self):
        var = KeyVariableSchema(name="通胀走势", why_important="决定政策方向")
        assert var.name == "通胀走势"

    def test_scenario_valid(self):
        scenario = ScenarioSchema(
            name="软着陆",
            description="经济平稳放缓",
            trigger_conditions=["通胀回落"],
            observation_cues=["PMI稳定"],
        )
        assert scenario.name == "软着陆"

    def test_thinking_question_valid(self):
        q = ThinkingQuestionSchema(question="通胀会持续吗?", purpose="评估风险")
        assert q.question == "通胀会持续吗?"

    def test_scenario_analysis_full(self):
        data = {
            "key_variables": [{"name": "var1", "why_important": "reason"}],
            "observation_signals": [{"signal": "sig1", "what_to_watch": "watch"}],
            "scenarios": [{"name": "s1", "description": "desc"}],
            "thinking_questions": [{"question": "q1"}],
        }
        result = ScenarioAnalysisSchema(**data)
        assert len(result.key_variables) == 1
        assert len(result.scenarios) == 1


class TestSchemaMap:
    def test_get_schema_knowledge(self):
        schema = get_schema("knowledge")
        assert schema == KnowledgeAnalysisSchema

    def test_get_schema_causal_chain(self):
        schema = get_schema("causal_chain")
        assert schema == CausalChainSchema

    def test_get_schema_analogy(self):
        schema = get_schema("analogy")
        assert schema == AnalogyResultSchema

    def test_get_schema_scenario(self):
        schema = get_schema("scenario")
        assert schema == ScenarioAnalysisSchema

    def test_get_schema_unknown(self):
        schema = get_schema("nonexistent")
        assert schema is None

    def test_all_schemas_in_map(self):
        expected = ["article_analysis", "daily_report", "trend", "knowledge",
                     "causal_chain", "representation", "analogy", "scenario"]
        for name in expected:
            assert name in SCHEMA_MAP
