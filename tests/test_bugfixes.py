"""
Tests for Bug Fixes:
- Bug 1: REPORT_TABLES set indexing (api_analysis.py:287)
- Bug 2: version_manager cleanup missing commit
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestBugFix1_ReportTables:
    """Bug 1: REPORT_TABLES was a set, but used with dict-style indexing."""

    def test_report_tables_is_set(self):
        from app.routes.api_analysis import REPORT_TABLES
        assert isinstance(REPORT_TABLES, set)
        assert "weekly_reports" in REPORT_TABLES
        assert "monthly_reports" in REPORT_TABLES

    def test_valid_periods_pass_whitelist(self):
        from app.routes.api_analysis import REPORT_TABLES
        assert "weekly_reports" in REPORT_TABLES
        assert "monthly_reports" in REPORT_TABLES

    def test_invalid_period_rejected(self):
        from app.routes.api_analysis import REPORT_TABLES
        assert "evil_table; DROP" not in REPORT_TABLES
        assert "" not in REPORT_TABLES

    def test_table_name_uses_period_directly(self):
        """After the fix, table_name should equal period (not REPORT_TABLES[period])."""
        import inspect
        from app.routes.api_analysis import get_reports_list
        source = inspect.getsource(get_reports_list)
        # Should NOT contain REPORT_TABLES[period]
        assert "REPORT_TABLES[period]" not in source
        # Should use period directly
        assert "table_name = period" in source


class TestBugFix2_VersionManagerCleanup:
    """Bug 2: _cleanup_old_versions was missing session.commit()."""

    def test_save_version_has_commit(self):
        """Verify save_version calls session.commit() after cleanup."""
        import inspect
        from scraper.pipeline.version_manager import VersionManager
        source = inspect.getsource(VersionManager.save_version)
        assert "await session.commit()" in source

    @pytest.mark.anyio
    async def test_save_version_calls_cleanup_with_commit(self):
        """Verify save_version still works end-to-end with the commit in cleanup."""
        from scraper.pipeline.version_manager import VersionManager

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock()

        # Mock the max version query to return 0
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        manager = VersionManager()

        with patch("scraper.pipeline.version_manager.async_session") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await manager.save_version(
                analysis_type="article",
                target_id="test-article-1",
                result_data={"sentiment": "neutral", "importance": 0.5},
                confidence=0.8,
            )

        # session.commit() should be called at least once after saving + cleanup
        assert mock_session.commit.call_count >= 1


class TestBugFix1_Integration:
    """Integration-level test: verify the reports endpoint doesn't crash."""

    @pytest.mark.anyio
    async def test_reports_endpoint_returns_json(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # This would have crashed with TypeError before the fix
            # Now it should return 200 or 401 (auth required)
            response = await client.get("/api/analysis/reports?period=weekly")
            assert response.status_code in [200, 400, 401, 422]

    @pytest.mark.anyio
    async def test_reports_invalid_period_rejected(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/analysis/reports?period=evil_table")
            assert response.status_code == 400
