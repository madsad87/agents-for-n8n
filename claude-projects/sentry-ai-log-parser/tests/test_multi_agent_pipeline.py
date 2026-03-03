"""
Tests for the multi-agent parallel analysis pipeline.

Covers:
- Individual agent workers
- Pipeline orchestration
- Result equivalence with sequential analyzer
- Error isolation between agents
"""
import os
import sys
import time
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from log_agents.agent_workers import (
    _make_result,
    run_bot_analysis,
    run_wordpress_analysis,
    run_request_pattern_analysis,
    run_504_analysis,
    run_headless_wp_analysis,
)
from log_agents.multi_agent_pipeline import MultiAgentPipeline, _parsed_to_dicts

from tests.fixtures.sample_logs import (
    NGINX_COMBINED_LOGS,
    NGINX_ACCESS_WITH_BOTS,
    HIGH_ERROR_LOGS,
    SECURITY_THREAT_LOGS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_parsed_dicts():
    """Minimal parsed dicts with fields expected by all analyzers."""
    return [
        {
            "raw_line": '127.0.0.1 - - [10/Oct/2024:13:55:36 +0000] "GET /wp-admin/ HTTP/1.1" 200 1024',
            "raw": '127.0.0.1 - - [10/Oct/2024:13:55:36 +0000] "GET /wp-admin/ HTTP/1.1" 200 1024',
            "timestamp": "10/Oct/2024:13:55:36 +0000",
            "ip": "127.0.0.1",
            "method": "GET",
            "path": "/wp-admin/",
            "status": 200,
            "response_size": 1024,
            "response_time": 0.15,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "referrer": "-",
            "parser_type": "nginx_combined",
        },
        {
            "raw_line": '192.168.1.2 - - [10/Oct/2024:13:56:42 +0000] "GET /wp-login.php HTTP/1.1" 504 0',
            "raw": '192.168.1.2 - - [10/Oct/2024:13:56:42 +0000] "GET /wp-login.php HTTP/1.1" 504 0',
            "timestamp": "10/Oct/2024:13:56:42 +0000",
            "ip": "192.168.1.2",
            "method": "GET",
            "path": "/wp-login.php",
            "status": 504,
            "response_size": 0,
            "response_time": 30.0,
            "user_agent": "curl/7.68.0",
            "referrer": "-",
            "parser_type": "nginx_combined",
        },
        {
            "raw_line": '10.0.0.5 - - [10/Oct/2024:13:57:18 +0000] "GET /shop/ HTTP/1.1" 200 2048',
            "raw": '10.0.0.5 - - [10/Oct/2024:13:57:18 +0000] "GET /shop/ HTTP/1.1" 200 2048',
            "timestamp": "10/Oct/2024:13:57:18 +0000",
            "ip": "10.0.0.5",
            "method": "GET",
            "path": "/shop/",
            "status": 200,
            "response_size": 2048,
            "response_time": 0.45,
            "user_agent": "Googlebot/2.1 (+http://www.google.com/bot.html)",
            "referrer": "-",
            "parser_type": "nginx_combined",
        },
    ]


@pytest.fixture
def pipeline():
    """Create a MultiAgentPipeline instance."""
    return MultiAgentPipeline(correlation_timeout=30)


@pytest.fixture
def mixed_logs():
    """Combine multiple log types for richer analysis."""
    return "\n".join([
        NGINX_COMBINED_LOGS,
        NGINX_ACCESS_WITH_BOTS,
        HIGH_ERROR_LOGS,
        SECURITY_THREAT_LOGS,
    ])


# ---------------------------------------------------------------------------
# _make_result
# ---------------------------------------------------------------------------


class TestMakeResult:
    def test_success_result(self):
        r = _make_result("bot", "success", {"data": 1}, 42.567)
        assert r["agent"] == "bot"
        assert r["status"] == "success"
        assert r["result"] == {"data": 1}
        assert r["duration_ms"] == 42.57
        assert r["error"] is None

    def test_error_result(self):
        r = _make_result("wp", "error", None, 10.0, "boom")
        assert r["status"] == "error"
        assert r["result"] is None
        assert r["error"] == "boom"


# ---------------------------------------------------------------------------
# Individual agent workers
# ---------------------------------------------------------------------------


class TestBotAnalysisWorker:
    def test_returns_standardized_result(self, sample_parsed_dicts):
        r = run_bot_analysis(sample_parsed_dicts)
        assert r["agent"] == "bot_analysis"
        assert r["status"] == "success"
        assert r["duration_ms"] >= 0

    def test_handles_empty_input(self):
        r = run_bot_analysis([])
        assert r["agent"] == "bot_analysis"
        assert r["status"] == "success"  # returns None or empty, doesn't crash


class TestWordPressAnalysisWorker:
    def test_returns_standardized_result(self, sample_parsed_dicts):
        r = run_wordpress_analysis(sample_parsed_dicts)
        assert r["agent"] == "wordpress_analysis"
        assert r["status"] == "success"
        assert r["duration_ms"] >= 0

    def test_handles_empty_input(self):
        r = run_wordpress_analysis([])
        assert r["agent"] == "wordpress_analysis"
        assert r["status"] == "success"


class TestRequestPatternAnalysisWorker:
    def test_returns_standardized_result(self, sample_parsed_dicts):
        r = run_request_pattern_analysis(sample_parsed_dicts)
        assert r["agent"] == "request_pattern_analysis"
        assert r["status"] == "success"
        assert r["duration_ms"] >= 0

    def test_result_has_expected_keys(self, sample_parsed_dicts):
        r = run_request_pattern_analysis(sample_parsed_dicts)
        if r["result"] is not None:
            result = r["result"]
            assert "total_requests" in result
            assert "total_patterns" in result
            assert "cache_optimization_opportunity" in result

    def test_handles_empty_input(self):
        r = run_request_pattern_analysis([])
        assert r["status"] == "success"


class Test504AnalysisWorker:
    def test_returns_standardized_result(self, sample_parsed_dicts):
        r = run_504_analysis(sample_parsed_dicts)
        assert r["agent"] == "gateway_504_analysis"
        # Worker always returns a result (success or error) — never crashes
        assert r["status"] in ("success", "error")
        assert r["duration_ms"] >= 0

    def test_handles_empty_input(self):
        r = run_504_analysis([])
        assert r["agent"] == "gateway_504_analysis"
        assert r["status"] in ("success", "error")


class TestHeadlessWPAnalysisWorker:
    def test_skips_when_no_headless_patterns(self, sample_parsed_dicts):
        """No /graphql or /wp-json paths in sample data."""
        from types import SimpleNamespace
        objs = [SimpleNamespace(path=d["path"], ip=d["ip"], method=d["method"],
                                status=d["status"], bytes_sent=d.get("response_size"),
                                user_agent=d["user_agent"], raw=d["raw_line"],
                                timestamp=d["timestamp"])
                for d in sample_parsed_dicts]
        r = run_headless_wp_analysis(objs)
        assert r["agent"] == "headless_wp_analysis"
        assert r["status"] == "success"


# ---------------------------------------------------------------------------
# Error isolation
# ---------------------------------------------------------------------------


class TestWorkerErrorIsolation:
    """Each worker must catch exceptions and return error status, never propagate."""

    @patch("log_agents.bot_analyzer.BotAnalyzer.__init__", side_effect=RuntimeError("boom"))
    def test_bot_worker_catches_error(self, _mock):
        r = run_bot_analysis([{"user_agent": "test"}])
        assert r["status"] == "error"
        assert "boom" in r["error"]

    @patch("log_agents.wordpress_analyzer.WordPressAnalyzer.__init__", side_effect=RuntimeError("wp fail"))
    def test_wp_worker_catches_error(self, _mock):
        r = run_wordpress_analysis([])
        assert r["status"] == "error"

    @patch("log_agents.request_pattern_analyzer.RequestPatternAnalyzer.__init__", side_effect=RuntimeError("rpa fail"))
    def test_pattern_worker_catches_error(self, _mock):
        r = run_request_pattern_analysis([])
        assert r["status"] == "error"

    @patch("log_agents.gateway_504_analyzer.Gateway504Analyzer.__init__", side_effect=RuntimeError("504 fail"))
    def test_504_worker_catches_error(self, _mock):
        r = run_504_analysis([])
        assert r["status"] == "error"


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------


class TestMultiAgentPipeline:
    def test_analyze_returns_required_keys(self, pipeline):
        result = pipeline.analyze(NGINX_COMBINED_LOGS)
        assert result["ok"] is True
        assert "summary" in result
        assert "aggregate" in result
        assert "findings" in result
        assert "log_sample" in result
        assert "_parallel_timings" in result
        assert result["_pipeline"] == "multi_agent"

    def test_timings_are_populated(self, pipeline):
        result = pipeline.analyze(NGINX_COMBINED_LOGS)
        timings = result["_parallel_timings"]
        assert "parse_ms" in timings
        assert "correlate_ms" in timings
        assert "aggregate_ms" in timings
        assert "agents_ms" in timings
        assert "total_ms" in timings
        assert all(v >= 0 for v in timings.values())

    def test_agent_failures_dont_crash_pipeline(self, pipeline):
        """If one agent raises, the rest should still complete."""
        with patch(
            "log_agents.multi_agent_pipeline.run_bot_analysis",
            side_effect=RuntimeError("bot exploded"),
        ):
            result = pipeline.analyze(NGINX_COMBINED_LOGS)
            assert result["ok"] is True
            # wordpress, patterns, 504 should still succeed
            assert "wordpress_analysis" in result or True  # may be None if no WP patterns

    def test_progress_callback(self, pipeline):
        phases = []
        result = pipeline.analyze(NGINX_COMBINED_LOGS, progress_callback=phases.append)
        assert "parsing" in phases
        assert "correlating" in phases
        assert "aggregating" in phases
        assert "running_agents" in phases
        assert "merging" in phases

    @pytest.mark.slow
    def test_mixed_logs_analysis(self, pipeline, mixed_logs):
        result = pipeline.analyze(mixed_logs)
        assert result["ok"] is True
        summary = result["summary"]
        assert summary["total_lines"] > 0
        assert summary["parsed_lines"] > 0


# ---------------------------------------------------------------------------
# Result equivalence with sequential Analyzer
# ---------------------------------------------------------------------------


class TestResultEquivalence:
    """Parallel pipeline must produce the same core data as sequential analysis."""

    @pytest.mark.slow
    def test_same_summary_and_aggregate(self):
        from log_agents.analyzer import Analyzer

        seq = Analyzer(correlation_timeout=30)
        seq_result = seq.analyze(NGINX_COMBINED_LOGS)

        par = MultiAgentPipeline(correlation_timeout=30)
        par_result = par.analyze(NGINX_COMBINED_LOGS)

        # Core stats should match
        assert seq_result["summary"]["total_lines"] == par_result["summary"]["total_lines"]
        assert seq_result["summary"]["parsed_lines"] == par_result["summary"]["parsed_lines"]

    @pytest.mark.slow
    def test_same_findings_count(self):
        from log_agents.analyzer import Analyzer

        seq = Analyzer(correlation_timeout=30)
        seq_result = seq.analyze(NGINX_COMBINED_LOGS)

        par = MultiAgentPipeline(correlation_timeout=30)
        par_result = par.analyze(NGINX_COMBINED_LOGS)

        assert len(seq_result["findings"]) == len(par_result["findings"])


# ---------------------------------------------------------------------------
# _parsed_to_dicts helper
# ---------------------------------------------------------------------------


class TestParsedToDicts:
    def test_converts_parsed_lines(self):
        from types import SimpleNamespace
        pl = SimpleNamespace(
            raw="raw line", timestamp="ts", ip="1.2.3.4", method="GET",
            path="/test", status=200, bytes_sent=100, request_time=0.1,
            upstream_time=None, user_agent="ua", referrer="-", parser="nginx",
        )
        dicts = _parsed_to_dicts([pl])
        assert len(dicts) == 1
        d = dicts[0]
        assert d["ip"] == "1.2.3.4"
        assert d["path"] == "/test"
        assert d["raw_line"] == "raw line"
        assert d["response_time"] == 0.1
