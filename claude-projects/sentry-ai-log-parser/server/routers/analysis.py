"""
Analysis Router - Core log analysis endpoints

This module contains all log analysis related endpoints including:
- Basic log analysis (/webhook-test/log-analysis)
- 504 Gateway analysis (/api/504-analysis)
- Headless WordPress analysis (/api/headless-wordpress-analysis)
- RAG chat (/api/rag-chat)
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

# Import constants
from constants import (
    HIGH_ERROR_RATE_PERCENTAGE, ANALYSIS_STATUS, ERROR_TYPES, 
    MIN_ENTRIES_FOR_ANALYSIS, DEFAULT_REQUEST_TIMEOUT_SECONDS
)

# Import analysis components
from log_agents import Analyzer
from log_agents.model_interface import ModelInterface
from log_agents.gateway_504_analyzer import Gateway504Analyzer
from log_agents.headless_wordpress_analyzer import HeadlessWordPressAnalyzer
from log_agents.multi_agent_pipeline import MultiAgentPipeline

# Import shared utilities
from server.redis_stub import analysis_cache
from shared_utils import get_default_system_prompt
from server.response_builders import APIResponse, AnalysisResponseBuilder, ValidationErrorBuilder

# Database integration
from server.database.integration import get_database, is_database_available
from server.models.ssh import SSHConnectionConfig

# Initialize router
router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================================
# Request/Response Models
# ============================================================================

class LogAnalysisRequest(BaseModel):
    log_data: str = Field(..., description="Raw log lines")

class ChatMessage(BaseModel):
    role: str
    content: str

class Attachment(BaseModel):
    name: str
    size: int
    original_chars: Optional[int] = None
    compressed_chars: Optional[int] = None
    truncated: bool = False
    mode: str = Field(..., description="content | summary")
    content: Optional[str] = Field(None, description="Inline text content or summary")

class ChatRequest(BaseModel):
    model: str = "gemini-2.5-flash"
    messages: List[ChatMessage]
    logs: Optional[str] = Field(None, description="Condensed log findings context")
    attachments: List[Attachment] = Field(default_factory=list)
    attachments_meta: Optional[str] = Field(None, description="Client-side meta string for attachments")

class HeadlessWordPressAnalysisRequest(BaseModel):
    log_data: str = Field(..., description="Raw log data to analyze for GraphQL/wp-json patterns")
    connection: Optional[SSHConnectionConfig] = Field(None, description="Optional SSH connection for log source tracking")
    analysis_focus: str = Field(default="performance", description="Analysis focus: performance, security, concurrency")

# ============================================================================
# Helper Functions
# ============================================================================

def maybe_explain_findings(findings: List[Dict[str, Any]], model_name: str | None, summary_data: Dict = None) -> Optional[str]:
    """
    Build an optional AI-written explanation of findings and log summary.

    Behavior:
    - If LOG_SUMMARY_MODEL is set, use it.
    - Else if GOOGLE_CLOUD_PROJECT is set, use a Gemini model (gemini-2.5-flash) via Vertex AI.
    - Else fall back to a lightweight debug summary (no [DEBUG ECHO] prefix).
    """
    # Generate summary if we have findings OR meaningful log data
    has_meaningful_data = (
        findings and len(findings) > 0
    ) or (
        summary_data and (
            summary_data.get("total_lines", 0) > 0 or
            summary_data.get("error_4xx_lines", 0) > 0 or 
            summary_data.get("error_5xx_lines", 0) > 0 or
            summary_data.get("unique_ips", 0) > 1
        )
    )
    
    if not has_meaningful_data:
        return None

    # Choose model: explicit env > vertex ai project > debug
    model_env = (model_name or os.getenv("LOG_SUMMARY_MODEL") or "").strip()
    if model_env:
        chosen_model = model_env
    else:
        chosen_model = "gemini-2.5-flash" if os.getenv("GOOGLE_CLOUD_PROJECT") else "debug-echo"

    # Build compact list for the prompt or debug fallback
    bullet_lines: List[str] = []
    for f in findings[:12]:
        sev = (f.get("severity") or f.get("level") or "info")
        issue = f.get("issue") or f.get("summary") or f.get("message") or "Finding"
        path = f.get("path") or ""
        status = f.get("status") or ""
        extra_bits = []
        if path:
            extra_bits.append(f"path={path}")
        if status:
            extra_bits.append(f"status={status}")
        suffix = f" ({', '.join(extra_bits)})" if extra_bits else ""
        bullet_lines.append(f"- [{sev}] {issue}{suffix}")

    # If we're in pure debug mode, avoid invoking the echo model (which prefixes with [DEBUG ECHO])
    # and just return a readable debug block.
    if chosen_model == "debug-echo":
        return "[DEBUG SUMMARY]\n" + "\n".join(bullet_lines)

    try:
        iface = ModelInterface(chosen_model)
        
        # Build context with both findings and summary data
        prompt_parts = []
        if bullet_lines:
            prompt_parts.append("Log Analysis Findings:\n" + "\n".join(bullet_lines))
        
        if summary_data:
            summary_text = []
            if summary_data.get("total_lines"):
                summary_text.append(f"Total log lines: {summary_data['total_lines']}")
            if summary_data.get("error_4xx_lines"):
                summary_text.append(f"4xx errors: {summary_data['error_4xx_lines']}")
            if summary_data.get("error_5xx_lines"):
                summary_text.append(f"5xx errors: {summary_data['error_5xx_lines']}")
            if summary_data.get("error_ratio"):
                summary_text.append(f"Error ratio: {summary_data['error_ratio']*100:.1f}%")
            if summary_data.get("unique_ips"):
                summary_text.append(f"Unique IPs: {summary_data['unique_ips']}")
            if summary_data.get("bot_percentage"):
                summary_text.append(f"Bot traffic: {summary_data['bot_percentage']*100:.1f}%")
            
            if summary_text:
                prompt_parts.append("Log Summary Statistics:\n" + "; ".join(summary_text))
        
        context = "\n\n".join(prompt_parts)
        prompt = f"""You are a system that analyzes web server logs and produces blended summaries 
that serve both business stakeholders and technical teams. 

Your output should contain two layers: 

1. Executive Summary (business-focused)
   - High-level description of the issue in plain language.
   - Emphasize customer experience and business impact (e.g., login failures, purchase issues, revenue risk).
   - Use simple, non-technical wording that could be shared with sales or client teams.

2. Key Findings (business-centric view)
   - Summarize unusual traffic, spikes, or errors in plain terms.
   - Explain what these patterns suggest without heavy technical jargon.

3. Business Impact
   - Describe real-world outcomes for users or clients.
   - Assign a severity level: Low, Medium, High, Critical.

---

4. Technical Detail (for engineers)
   - Error Rate: [percentage, affected endpoints, severity]
   - Anomalous Traffic: [IP list, abnormal volume, suspected cause, severity]
   - Traffic Spikes: [time(s), magnitude, severity]
   - Potential Root Cause: [possible explanations: brute force, scaling limits, code issues]

5. Recommended Actions
   - For Engineering: concrete steps (block IPs, review scaling, debug services).
   - For Stakeholders: reassurance and business-friendly phrasing (e.g., "monitoring in place," "issue isolated").

6. Overall Severity
   - Final rating: Low / Medium / High / Critical.
   - Phrase what this means in both technical and business terms.

Output should always follow this structure.

Analyze this log data:

{context}"""
        
        # Use a simple one-turn chat for summary
        return iface.chat([{"role": "user", "content": prompt}], extra_context=None)
    except Exception:
        # Any model failures should not break analysis endpoint; fall back to debug block
        return "[DEBUG SUMMARY]\n" + "\n".join(bullet_lines)

def build_attachments_context(
    attachments: List[Attachment],
    total_cap: int = 2_000_000,  # Increased from 200K to 2M
    per_file_cap: int = 500_000,  # Increased from 50K to 500K
) -> str:
    """
    Produce a bounded context string from attachments:
    [ATTACHMENT name=..., mode=..., len=...]
    <content or summary (capped)>
    """
    if not attachments:
        return ""

    remaining = max(0, total_cap)
    parts: List[str] = []

    for a in attachments:
        text = (a.content or "").strip()
        if not text:
            continue

        header = f"[ATTACHMENT name={a.name} mode={a.mode} chars={len(text)} truncated={a.truncated}]\n"
        header_len = len(header)

        if remaining <= header_len:
            break

        allowed = min(per_file_cap, remaining - header_len)
        if allowed <= 0:
            break

        chunk = text[:allowed]
        
        # Sanitize attachment content for security (OWASP LLM protection)
        try:
            from server.prompt_security import prompt_security
            safe_chunk = prompt_security.sanitize_log_context(chunk, max_length=allowed)
        except ImportError:
            # Fallback sanitization
            import html
            safe_chunk = f"<ATTACHMENT_DATA>\n{html.escape(chunk, quote=True)}\n</ATTACHMENT_DATA>"
        
        parts.append(header)
        parts.append(safe_chunk)
        parts.append("\n\n")
        remaining -= header_len + len(safe_chunk) + 2  # include spacing

        if remaining <= 0:
            break

    return "".join(parts).strip()

def merge_system_messages(messages: List[ChatMessage]) -> List[Dict[str, str]]:
    """
    Merge GUI-provided system messages with an optional server-side default prompt.
    Returns a list of dict messages with a single combined system message first (if any),
    followed by the dialog turns (user/assistant).
    """
    default_sys = get_default_system_prompt()
    gui_sys = [m.content.strip() for m in messages if m.role == "system" and isinstance(m.content, str) and m.content.strip()]

    sys_parts: List[str] = []
    if default_sys:
        sys_parts.append(default_sys)
    if gui_sys:
        sys_parts.extend(gui_sys)

    combined_system = "\n\n---\n".join(sys_parts).strip() if sys_parts else None

    dialog = [{"role": m.role, "content": m.content} for m in messages if m.role in ("user", "assistant")]

    if combined_system:
        return [{"role": "system", "content": combined_system}] + dialog
    return dialog

# ============================================================================
# Analysis Helper Functions (SonarQube Complexity Reduction)
# ============================================================================

def _build_cached_response(cached_result: Dict[str, Any], log_data: str) -> Dict[str, Any]:
    """Build response from cached analysis data (SonarQube complexity reduction)"""
    cached_analysis = cached_result.get("result", {})
    cached_analysis["_cache_hit"] = True
    cached_analysis["_cached_at"] = cached_result.get("cached_at")
    return {
        "ok": True,
        "summary": cached_analysis.get("summary"),
        "aggregate": cached_analysis.get("aggregate"),
        "findings": cached_analysis.get("findings"),
        "explanation": cached_analysis.get("explanation"),
        "user_agent_insights": cached_analysis.get("aggregate", {}).get("user_agent_insights"),
        "wordpress_analysis": cached_analysis.get("wordpress_analysis"),
        "bot_analysis": cached_analysis.get("bot_analysis"),
        "request_pattern_analysis": cached_analysis.get("request_pattern_analysis"),
        "gateway_504_analysis": cached_analysis.get("gateway_504_analysis"),
        "log_sample": cached_analysis.get("log_sample"),
        "raw_log_data": log_data,
        "_cache_hit": True,
        "_cached_at": cached_result.get("cached_at")
    }


def _perform_database_save(analysis_db, final_result: Dict[str, Any], log_data: str) -> tuple[bool, Optional[str]]:
    """Execute the database save operation and process the result (SonarQube complexity reduction)"""
    database_saved = False
    database_hash = None
    try:
        save_result = analysis_db.save_analysis(
            analysis_data=final_result,
            source_info="file_upload",
            analysis_type="log_analysis",
            tags=["file_upload"],
            raw_log_data=log_data  # Pass raw logs for session-based deduplication
        )
        if save_result.success:
            database_hash = save_result.data.get('content_hash')
            was_duplicate = save_result.data.get('already_exists', False)
            if was_duplicate:
                logger.info(f"Analysis already exists in database (deduplicated): {database_hash}")
            else:
                logger.info(f"Saved new analysis to database: {database_hash}")
                database_saved = True
        else:
            logger.error(f"Failed to save analysis to database: {save_result.error}")
    except Exception as db_error:
        logger.error(f"Exception during database save operation: {db_error}")
        import traceback
        logger.error(f"Database save traceback: {traceback.format_exc()}")
    return database_saved, database_hash


def _save_analysis_to_database(final_result: Dict[str, Any], log_data: str) -> tuple[bool, Optional[str]]:
    """Save analysis to database if available (SonarQube complexity reduction)"""
    # Use functions instead of global variables for lazy initialization
    if not is_database_available():
        logger.warning("Database not available - analysis not saved")
        return False, None

    analysis_db = get_database()
    if not analysis_db:
        logger.warning("Database instance not initialized - analysis not saved")
        return False, None

    return _perform_database_save(analysis_db, final_result, log_data)

def _build_final_response(final_result: Dict[str, Any], log_data: str, database_saved: bool, database_hash: Optional[str]) -> Dict[str, Any]:
    """Build final response with all analysis results (SonarQube complexity reduction)"""
    return {
        "ok": True,
        "summary": final_result["summary"],
        "aggregate": final_result["aggregate"],
        "findings": final_result["findings"],
        "explanation": final_result["explanation"],
        "user_agent_insights": final_result["user_agent_insights"],
        "wordpress_analysis": final_result["wordpress_analysis"],
        "bot_analysis": final_result.get("bot_analysis"),
        "request_pattern_analysis": final_result.get("request_pattern_analysis"),
        "gateway_504_analysis": final_result.get("gateway_504_analysis"),
        "headless_wp_analysis": final_result.get("headless_wp_analysis"),
        "log_sample": final_result.get("log_sample"),
        "raw_log_data": log_data,  # Include raw log data for 504 analysis
        "_cache_hit": False,
        "_analysis_time": datetime.now().isoformat(),
        "_database_saved": database_saved,  # Indicates if saved to database
        "_database_hash": database_hash  # Hash for retrieving from database
    }

# ============================================================================
# Analysis Endpoints
# ============================================================================

@router.post("/webhook-test/log-analysis")
def analyze_logs(req: LogAnalysisRequest):
    """Main log analysis endpoint — uses multi-agent parallel pipeline."""
    cached_result = analysis_cache.get_cached_analysis(req.log_data)
    if cached_result:
        return _build_cached_response(cached_result, req.log_data)

    return _analyze_parallel(req.log_data)


def _analyze_parallel(log_data: str) -> Dict[str, Any]:
    """Run analysis through the multi-agent parallel pipeline."""
    logger.info(f"Starting PARALLEL analysis of {len(log_data):,} characters")
    pipeline = MultiAgentPipeline(correlation_timeout=90)
    result = pipeline.analyze(log_data)
    logger.info(
        f"Parallel analysis completed in {result.get('_parallel_timings', {}).get('total_ms', 0):.0f}ms "
        f"using {result.get('_analysis_mode', 'unknown')} mode"
    )

    # Optional LLM explanation
    explanation = maybe_explain_findings(
        result.get("findings", []),
        model_name=os.getenv("LOG_SUMMARY_MODEL"),
        summary_data=result.get("summary", {}),
    )

    final_result = {
        "summary": result.get("summary"),
        "aggregate": result.get("aggregate"),
        "findings": result.get("findings"),
        "explanation": explanation,
        "user_agent_insights": result.get("aggregate", {}).get("user_agent_insights"),
        "wordpress_analysis": result.get("wordpress_analysis"),
        "bot_analysis": result.get("bot_analysis"),
        "request_pattern_analysis": result.get("request_pattern_analysis"),
        "gateway_504_analysis": result.get("gateway_504_analysis"),
        "headless_wp_analysis": result.get("headless_wp_analysis"),
        "log_sample": result.get("log_sample"),
    }

    analysis_cache.cache_analysis(log_data, final_result)
    database_saved, database_hash = _save_analysis_to_database(final_result, log_data)
    response = _build_final_response(final_result, log_data, database_saved, database_hash)
    response["_parallel_timings"] = result.get("_parallel_timings")
    response["_pipeline"] = "multi_agent"
    return response


@router.post("/api/504-analysis")
def analyze_504_gateway_errors(req: LogAnalysisRequest):
    """
    Specialized endpoint for 504 Gateway Timeout root cause analysis.
    Focuses on identifying concurrency issues and root causes rather than just symptoms.
    """
    # Parse the logs first
    analyzer = Analyzer()
    parsed_lines = analyzer.parse_lines(req.log_data)
    
    # Run 504-specific analysis
    gateway_analyzer = Gateway504Analyzer()
    analysis = gateway_analyzer.analyze_504_root_causes(parsed_lines)
    
    # Convert to JSON-serializable format
    result = {
        "ok": True,
        "analysis_type": "504_root_cause",
        "total_504_errors": analysis.total_504_errors,
        "time_range": {
            "start": analysis.time_range[0].isoformat() if analysis.time_range[0] else None,
            "end": analysis.time_range[1].isoformat() if analysis.time_range[1] else None
        },
        "top_affected_ips": analysis.top_affected_ips,
        "top_affected_paths": analysis.top_affected_paths,
        "top_affected_user_agents": analysis.top_affected_user_agents,
        "concurrency_analysis": analysis.concurrency_analysis,
        "root_causes": analysis.root_causes,
        "recommendations": analysis.recommendations,
        "timeline_events": analysis.timeline_events
    }
    
    return result

@router.post("/api/headless-wordpress-analysis")
async def analyze_headless_wordpress(req: HeadlessWordPressAnalysisRequest, background_tasks: BackgroundTasks):
    """
    Headless WordPress API analysis for GraphQL and wp-json requests.
    Analyzes concurrency patterns and security threats in headless WordPress deployments.
    
    Based on atlas_logs function and AWK scripts for GraphQL/wp-json analysis:
    - Detects GraphQL and wp-json API requests from FPM/Apache logs
    - Calculates per-second concurrency levels
    - Identifies peak traffic periods (top 20 like AWK script)
    - Performs security analysis for GraphQL query patterns
    """
    try:
        # Check cache first
        cached_result = analysis_cache.get_cached_analysis(req.log_data)
        if cached_result:
            logger.info("Returning cached headless WordPress analysis")
            return {
                **cached_result.get("result", cached_result),
                "_cache_hit": True,
                "_cached_at": cached_result.get("cached_at", datetime.now().isoformat())
            }
        
        # Create headless WordPress analyzer
        hw_analyzer = HeadlessWordPressAnalyzer()
        
        # Run the analysis (the analyzer will check if API requests exist internally)
        logger.info("Starting headless WordPress analysis")
        start_time = datetime.now()
        
        analysis_result = hw_analyzer.analyze_headless_requests(req.log_data, req.analysis_focus)
        
        # Add metadata
        analysis_result.update({
            "analysis_focus": req.analysis_focus,
            "connection_source": req.connection.model_dump() if req.connection else None,
            "analysis_duration": (datetime.now() - start_time).total_seconds(),
            "timestamp": datetime.now().isoformat()
        })
        
        # Cache the result
        analysis_cache.cache_analysis(req.log_data, analysis_result)
        
        # Note: Database storage removed for simplified architecture
        # Analysis results are returned directly without persistence
        
        return {
            **analysis_result,
            "_cache_hit": False
        }
        
    except Exception as e:
        logger.error(f"Headless WordPress analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Headless WordPress analysis failed: {str(e)}")

@router.post("/api/rag-chat")
async def rag_chat(req: ChatRequest):
    """RAG-enabled chat endpoint for log analysis assistance"""
    model = req.model or "debug-echo"

    # Security: Validate user input for prompt injection attempts (OWASP LLM compliance)
    try:
        from server.prompt_security import prompt_security
        
        # Validate all user messages for injection attempts
        for message in req.messages:
            if message.role == "user":
                is_safe, warning = prompt_security.validate_user_input(message.content)
                if not is_safe:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Potential prompt injection detected: {warning}"
                    )
    except ImportError:
        # Fallback if prompt security not available
        logger.warning("Prompt security module not available - basic validation only")
        for message in req.messages:
            if message.role == "user" and len(message.content) > 10000:
                raise HTTPException(status_code=400, detail="Input too long")
    
    # Merge system messages with DEFAULT_SYSTEM_PROMPT (env) and keep dialog turns
    messages_payload = merge_system_messages(req.messages)

    # Combine attachments + logs into a bounded extra_context
    context_parts: List[str] = []
    if req.attachments_meta:
        context_parts.append(f"[ATTACHMENTS META]\n{req.attachments_meta}")

    att_ctx = build_attachments_context(req.attachments)
    if att_ctx:
        context_parts.append(att_ctx)

    if req.logs:
        # Sanitize log data before adding to context (OWASP LLM protection)
        try:
            from server.prompt_security import prompt_security
            sanitized_logs = prompt_security.sanitize_log_context(req.logs, max_length=4000)
            context_parts.append(f"[RECENT FINDINGS]\n{sanitized_logs}")
        except ImportError:
            # Fallback sanitization if prompt security not available
            import html
            safe_logs = html.escape(req.logs[:4000], quote=True)
            context_parts.append(f"[RECENT FINDINGS]\n<LOG_DATA>\n{safe_logs}\n</LOG_DATA>")

    # Note: Database historical context removed for simplified architecture
    # Chat now works with current analysis context only (req.logs and attachments)
    # All context is properly sanitized with XML tag isolation

    extra_context = "\n\n".join(context_parts) if context_parts else None

    try:
        iface = ModelInterface(model)
        answer = iface.chat(messages_payload, extra_context=extra_context)
    except Exception as e:
        answer = f"Error invoking model: {e}"

    return {"response": answer}

@router.get("/api/simple-test")
def simple_test():
    """Simple test endpoint"""
    return {"message": "Simple test works"}