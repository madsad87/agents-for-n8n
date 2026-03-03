"""
Agent Workers - Self-contained worker functions for parallel log analysis pipeline.

Each worker wraps a specialist analyzer, handles errors internally, and returns
a standardized result dict for the orchestrator to merge.
"""

import time
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def _make_result(agent: str, status: str, result: Any = None, duration_ms: float = 0, error: str = None) -> Dict[str, Any]:
    """Build standardized worker result."""
    return {
        "agent": agent,
        "status": status,
        "result": result,
        "duration_ms": round(duration_ms, 2),
        "error": error,
    }


def run_bot_analysis(parsed_dicts: List[Dict], correlated_requests: List = None) -> Dict[str, Any]:
    """Run bot traffic analysis as an independent agent worker."""
    start = time.monotonic()
    try:
        from .bot_analyzer import BotAnalyzer
        analyzer = BotAnalyzer()
        result = analyzer.analyze_bots(parsed_dicts, correlated_requests)
        elapsed = (time.monotonic() - start) * 1000
        logger.info(f"[agent:bot] completed in {elapsed:.0f}ms")
        return _make_result("bot_analysis", "success", result, elapsed)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        logger.error(f"[agent:bot] failed after {elapsed:.0f}ms: {e}")
        return _make_result("bot_analysis", "error", None, elapsed, str(e))


def run_wordpress_analysis(parsed_dicts: List[Dict]) -> Dict[str, Any]:
    """Run WordPress-specific analysis as an independent agent worker."""
    start = time.monotonic()
    try:
        from .wordpress_analyzer import WordPressAnalyzer
        analyzer = WordPressAnalyzer()
        result = analyzer.analyze_wordpress(parsed_dicts)
        elapsed = (time.monotonic() - start) * 1000
        logger.info(f"[agent:wordpress] completed in {elapsed:.0f}ms")
        return _make_result("wordpress_analysis", "success", result, elapsed)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        logger.error(f"[agent:wordpress] failed after {elapsed:.0f}ms: {e}")
        return _make_result("wordpress_analysis", "error", None, elapsed, str(e))


def run_request_pattern_analysis(parsed_dicts: List[Dict]) -> Dict[str, Any]:
    """Run request pattern and cache optimization analysis as an independent agent worker."""
    start = time.monotonic()
    try:
        from .request_pattern_analyzer import RequestPatternAnalyzer
        analyzer = RequestPatternAnalyzer()
        raw_result = analyzer.analyze_request_patterns(parsed_dicts)

        # Convert PatternAnalysisResult dataclass to dict for JSON serialization
        if raw_result is None:
            result = None
        else:
            result = {
                "total_requests": raw_result.total_requests,
                "total_patterns": raw_result.total_patterns,
                "cache_optimization_opportunity": raw_result.cache_optimization_opportunity,
                "patterns": [
                    {
                        "template": p.template,
                        "count": p.count,
                        "percentage": p.percentage,
                        "cache_hit_potential": p.cache_hit_potential,
                        "noise_parameters": p.noise_parameters,
                        "tracking_parameters": p.tracking_parameters,
                        "legitimate_parameters": p.legitimate_parameters,
                        "sample_urls": p.sample_urls,
                        "severity": p.severity,
                        "impact_score": p.impact_score,
                    }
                    for p in (raw_result.patterns or [])
                ],
                "parameter_analysis": {
                    name: {
                        "name": pa.name,
                        "total_requests": pa.total_requests,
                        "unique_values": pa.unique_values,
                        "uniqueness_ratio": pa.uniqueness_ratio,
                        "entropy": pa.entropy,
                        "classification": pa.classification,
                        "sample_values": pa.sample_values,
                        "description": pa.description,
                    }
                    for name, pa in (raw_result.parameter_analysis or {}).items()
                },
                "evercache_suggestions": raw_result.evercache_suggestions,
                "attack_patterns": raw_result.attack_patterns,
                "summary": raw_result.summary,
            }

        elapsed = (time.monotonic() - start) * 1000
        logger.info(f"[agent:patterns] completed in {elapsed:.0f}ms")
        return _make_result("request_pattern_analysis", "success", result, elapsed)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        logger.error(f"[agent:patterns] failed after {elapsed:.0f}ms: {e}")
        return _make_result("request_pattern_analysis", "error", None, elapsed, str(e))


def run_504_analysis(parsed_dicts: List[Dict]) -> Dict[str, Any]:
    """Run 504 gateway timeout root cause analysis as an independent agent worker."""
    start = time.monotonic()
    try:
        from .gateway_504_analyzer import Gateway504Analyzer
        analyzer = Gateway504Analyzer()
        result = analyzer.analyze(parsed_dicts)
        elapsed = (time.monotonic() - start) * 1000
        logger.info(f"[agent:504] completed in {elapsed:.0f}ms")
        return _make_result("gateway_504_analysis", "success", result, elapsed)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        logger.error(f"[agent:504] failed after {elapsed:.0f}ms: {e}")
        return _make_result("gateway_504_analysis", "error", None, elapsed, str(e))


def run_headless_wp_analysis(
    effective_parsed, analysis_focus: str = "performance"
) -> Dict[str, Any]:
    """Run headless WordPress (GraphQL/wp-json) analysis as an independent agent worker.

    Args:
        effective_parsed: List of ParsedLine objects (not dicts). The analyzer uses
            attribute access (.path, .ip, .method, .status, .bytes_sent, etc.).
        analysis_focus: One of 'performance', 'security', 'concurrency'.
    """
    start = time.monotonic()
    try:
        from .headless_wordpress_analyzer import HeadlessWordPressAnalyzer
        analyzer = HeadlessWordPressAnalyzer()
        result = analyzer.analyze_headless_from_parsed(effective_parsed, analysis_focus)
        elapsed = (time.monotonic() - start) * 1000
        logger.info(f"[agent:headless_wp] completed in {elapsed:.0f}ms")
        return _make_result("headless_wp_analysis", "success", result, elapsed)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        logger.error(f"[agent:headless_wp] failed after {elapsed:.0f}ms: {e}")
        return _make_result("headless_wp_analysis", "error", None, elapsed, str(e))
