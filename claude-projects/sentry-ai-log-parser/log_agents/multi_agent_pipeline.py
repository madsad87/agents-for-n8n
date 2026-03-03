"""
Multi-Agent Pipeline - Parallel log analysis orchestrator.

Runs the sequential parsing/correlation phases, then fans out to 5 specialist
analyzers concurrently using a thread pool.  Output structure is identical to
``Analyzer.analyze()`` so the API can swap in transparently.

Pipeline phases:
    1. Parse lines  (sequential — CPU, single pass)
    2. Correlate     (sequential — needs all parsed lines)
    3. Aggregate     (sequential — needs correlated data)
    4. Specialists   (PARALLEL — bot, WP, patterns, 504, headless WP)
    5. Merge         (sequential — assemble final dict)
"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Callable

from .analyzer import Analyzer
from .agent_workers import (
    run_bot_analysis,
    run_wordpress_analysis,
    run_request_pattern_analysis,
    run_504_analysis,
    run_headless_wp_analysis,
)

logger = logging.getLogger(__name__)


def _parsed_to_dicts(effective_parsed) -> List[Dict]:
    """Convert ParsedLine objects to dicts for analyzers that expect dicts."""
    parsed_dicts = []
    for pl in effective_parsed:
        parsed_dicts.append(
            {
                "raw_line": pl.raw,
                "raw": pl.raw,
                "timestamp": pl.timestamp,
                "ip": pl.ip,
                "method": pl.method,
                "path": pl.path,
                "status": pl.status,
                "response_size": pl.bytes_sent,
                "response_time": pl.request_time or pl.upstream_time,
                "user_agent": pl.user_agent,
                "referrer": pl.referrer,
                "parser_type": pl.parser,
            }
        )
    return parsed_dicts


class MultiAgentPipeline:
    """Orchestrates parallel log analysis across specialist agent workers.

    Usage::

        pipeline = MultiAgentPipeline()
        result = pipeline.analyze(raw_text)
        # result has the same shape as Analyzer.analyze()
    """

    def __init__(
        self,
        max_workers: int = 5,
        correlation_timeout: int = 120,
        slow_request_threshold: float = 1.0,
        high_error_ratio: float = 0.15,
    ):
        self.max_workers = max_workers
        self.correlation_timeout = correlation_timeout
        self._analyzer = Analyzer(
            slow_request_threshold=slow_request_threshold,
            high_error_ratio=high_error_ratio,
            correlation_timeout=correlation_timeout,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        raw_text: str,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Run full analysis with parallel specialist phase.

        Returns the same dict structure as ``Analyzer.analyze()``, plus:
        - ``_parallel_timings``: per-phase and per-agent timing breakdown
        - ``_pipeline``: ``"multi_agent"``
        """
        timings: Dict[str, float] = {}
        pipeline_start = time.monotonic()

        # ── Phase 1: Parse ────────────────────────────────────────────
        self._emit(progress_callback, "parsing")
        t0 = time.monotonic()
        log_sample = self._analyzer._generate_log_sample(raw_text)
        parsed = self._analyzer.parse_lines(raw_text)
        timings["parse_ms"] = (time.monotonic() - t0) * 1000
        logger.info(
            f"[pipeline] Phase 1 — parsed {len(parsed):,} lines in "
            f"{timings['parse_ms']:.0f}ms"
        )

        # ── Phase 2: Correlate ────────────────────────────────────────
        self._emit(progress_callback, "correlating")
        t0 = time.monotonic()
        correlated_requests, correlation_stats = self._correlate(
            parsed, progress_callback
        )
        effective_parsed = [cr.primary_entry for cr in correlated_requests]
        timings["correlate_ms"] = (time.monotonic() - t0) * 1000
        logger.info(
            f"[pipeline] Phase 2 — correlated {len(effective_parsed):,} lines in "
            f"{timings['correlate_ms']:.0f}ms"
        )

        # ── Phase 3: Aggregate + Findings ─────────────────────────────
        self._emit(progress_callback, "aggregating")
        t0 = time.monotonic()
        agg = self._analyzer.aggregate(effective_parsed)
        findings = self._analyzer.build_findings(agg)
        self._attach_correlation_stats(
            agg, correlation_stats, correlated_requests, parsed
        )
        timings["aggregate_ms"] = (time.monotonic() - t0) * 1000
        logger.info(
            f"[pipeline] Phase 3 — aggregated in {timings['aggregate_ms']:.0f}ms"
        )

        # ── Phase 4: Parallel Specialists ─────────────────────────────
        self._emit(progress_callback, "running_agents")
        parsed_dicts = _parsed_to_dicts(effective_parsed)

        t0 = time.monotonic()
        agent_results = self._run_agents_parallel(
            parsed_dicts, effective_parsed, correlated_requests
        )
        timings["agents_ms"] = (time.monotonic() - t0) * 1000

        # Record per-agent timings
        for ar in agent_results:
            timings[f"{ar['agent']}_ms"] = ar["duration_ms"]

        agent_summary = ", ".join(
            f"{ar['agent']}={ar['status']}({ar['duration_ms']:.0f}ms)"
            for ar in agent_results
        )
        logger.info(
            f"[pipeline] Phase 4 — agents done in {timings['agents_ms']:.0f}ms "
            f"[{agent_summary}]"
        )

        # ── Phase 5: Merge ────────────────────────────────────────────
        self._emit(progress_callback, "merging")
        result = self._merge(
            agg,
            findings,
            log_sample,
            correlation_stats,
            agent_results,
        )

        timings["total_ms"] = (time.monotonic() - pipeline_start) * 1000
        result["_parallel_timings"] = timings
        result["_pipeline"] = "multi_agent"

        logger.info(
            f"[pipeline] Complete — total {timings['total_ms']:.0f}ms "
            f"(parse={timings['parse_ms']:.0f}, correlate={timings['correlate_ms']:.0f}, "
            f"agg={timings['aggregate_ms']:.0f}, agents={timings['agents_ms']:.0f})"
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _emit(callback: Optional[Callable], phase: str):
        if callback:
            try:
                callback(phase)
            except Exception:
                pass

    def _correlate(self, parsed, progress_callback):
        """Run correlation with timeout, returning fallback on failure."""
        try:
            return self._analyzer._safe_correlation_with_timeout(
                parsed, progress_callback
            )
        except Exception as e:
            logger.warning(f"[pipeline] Correlation failed: {e} — using direct mode")
            from .log_correlator import CorrelatedRequest, CorrelationStats

            fallback = []
            for line in parsed:
                cid = f"{line.ip}_{line.timestamp}_{line.path}_{id(line)}"
                req = CorrelatedRequest(
                    correlation_id=cid,
                    nginx_entry=line,
                    correlation_confidence="high",
                    request_type="unknown",
                )
                fallback.append(req)

            stats = CorrelationStats(
                analysis_mode="error_fallback",
                correlated_requests=len(fallback),
                correlation_rate=100.0,
            )
            return fallback, stats

    def _attach_correlation_stats(
        self, agg, correlation_stats, correlated_requests, parsed
    ):
        """Attach correlation metadata to the aggregate dict."""
        if correlation_stats.analysis_mode == "correlation":
            agg["correlation_stats"] = {
                "analysis_mode": correlation_stats.analysis_mode,
                "total_nginx_requests": correlation_stats.total_nginx_requests,
                "total_fmp_requests": correlation_stats.total_fmp_requests,
                "total_apache2_requests": correlation_stats.total_apache2_requests,
                "correlated_requests": correlation_stats.correlated_requests,
                "static_file_requests": correlation_stats.static_file_requests,
                "uncorrelated_nginx": correlation_stats.uncorrelated_nginx,
                "uncorrelated_fmp": correlation_stats.uncorrelated_fmp,
                "uncorrelated_apache2": correlation_stats.uncorrelated_apache2,
                "correlation_rate": correlation_stats.correlation_rate,
            }
            performance_insights = self._analyzer._extract_performance_insights(
                correlated_requests
            )
            agg["performance_insights"] = performance_insights
        else:
            agg["correlation_stats"] = {
                "analysis_mode": "direct",
                "total_requests": len(parsed),
            }

    def _run_agents_parallel(
        self,
        parsed_dicts: List[Dict],
        effective_parsed,
        correlated_requests,
    ) -> List[Dict[str, Any]]:
        """Submit all specialist workers to a thread pool, collect results."""
        results: List[Dict[str, Any]] = []

        with ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="agent"
        ) as pool:
            futures = {
                pool.submit(run_bot_analysis, parsed_dicts, correlated_requests): "bot",
                pool.submit(run_wordpress_analysis, parsed_dicts): "wordpress",
                pool.submit(run_request_pattern_analysis, parsed_dicts): "patterns",
                pool.submit(run_504_analysis, parsed_dicts): "504",
                pool.submit(run_headless_wp_analysis, effective_parsed): "headless_wp",
            }

            for future in as_completed(futures):
                agent_label = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    logger.error(
                        f"[pipeline] Agent '{agent_label}' raised: {exc}"
                    )
                    results.append(
                        {
                            "agent": agent_label,
                            "status": "error",
                            "result": None,
                            "duration_ms": 0,
                            "error": str(exc),
                        }
                    )
        return results

    @staticmethod
    def _merge(
        agg: Dict,
        findings: List,
        log_sample: Dict,
        correlation_stats,
        agent_results: List[Dict],
    ) -> Dict[str, Any]:
        """Assemble the final result dict from aggregate + agent outputs."""
        result = {
            "ok": True,
            "summary": agg.get("summary"),
            "aggregate": agg,
            "findings": findings,
            "log_sample": log_sample,
            "_analysis_mode": (
                correlation_stats.analysis_mode
                if correlation_stats
                else "unknown"
            ),
        }

        # Map agent worker output into the expected top-level keys
        key_map = {
            "bot_analysis": "bot_analysis",
            "wordpress_analysis": "wordpress_analysis",
            "request_pattern_analysis": "request_pattern_analysis",
            "gateway_504_analysis": "gateway_504_analysis",
            "headless_wp_analysis": "headless_wp_analysis",
        }

        for ar in agent_results:
            agent_name = ar["agent"]
            response_key = key_map.get(agent_name)
            if response_key and ar["status"] == "success" and ar["result"] is not None:
                result[response_key] = ar["result"]

        return result
