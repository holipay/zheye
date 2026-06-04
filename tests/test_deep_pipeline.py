"""deep_analyst/pipeline.py 数据类测试（不依赖数据库）"""

from tests.deep_analyst_test_helper import ensure_pipeline_imports
ensure_pipeline_imports()

from deep_analyst.pipeline import AnalysisResult, PipelineResult


class TestAnalysisResult:
    def test_default_values(self):
        result = AnalysisResult(event_id="EVT-123", success=False)
        assert result.event_id == "EVT-123"
        assert result.success is False
        assert result.steps_completed == []
        assert result.steps_failed == []
        assert result.error is None
        assert result.duration_seconds == 0.0

    def test_success_with_steps(self):
        result = AnalysisResult(
            event_id="EVT-123",
            success=True,
            steps_completed=["knowledge", "causal_chain"],
        )
        assert result.success is True
        assert len(result.steps_completed) == 2

    def test_failure_with_error(self):
        result = AnalysisResult(
            event_id="EVT-123",
            success=False,
            steps_failed=["knowledge"],
            error="API timeout",
        )
        assert result.success is False
        assert result.error == "API timeout"


class TestPipelineResult:
    def test_default_values(self):
        result = PipelineResult()
        assert result.total == 0
        assert result.success == 0
        assert result.failed == 0
        assert result.skipped == 0
        assert result.results == []
        assert result.duration_seconds == 0.0

    def test_accumulate_results(self):
        result = PipelineResult()
        result.total = 5
        result.success = 3
        result.failed = 2
        result.results.append(AnalysisResult(event_id="EVT-1", success=True))
        result.results.append(AnalysisResult(event_id="EVT-2", success=False))
        assert len(result.results) == 2
        assert result.success + result.failed == result.total
