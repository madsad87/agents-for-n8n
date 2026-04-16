# CLAUDE.md

Guidance for Claude Code working with the SEntry Log Analysis Application.

## Quick Start

### Prerequisites

- **Python 3.8+** and **Node.js 20+**
- **Google Cloud CLI** — authenticated via `gcloud auth application-default login`
- **SSH keys** in `~/.ssh/` registered with WP Engine (for log analysis features)
- **Claude Code** — the `.claude/commands/` directory contains investigation workflows (e.g., `/investigate`)

### First-Time Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt
cd pyagent-react-gui && npm install && cd ..

# 2. Set up environment (copy and review — defaults work for internal use)
cp .env.example .env

# 3. Authenticate with Google Cloud
gcloud auth application-default login
```

### Running

```bash
./start-dev.sh
# Frontend: http://localhost:3002
# Backend:  http://localhost:8787
```

## Git Branch Policy (CRITICAL)

**ALWAYS work on `main` branch.** Never use feature branches unless the user explicitly requests it.

Before ANY work: `git checkout main && git pull`

This applies to all tasks: code changes, builds, commits, PRs. A past incident where a feature branch was used for a build resulted in missing critical features and required redistribution.

## Architecture Overview

**Browser app:** Python FastAPI backend + React frontend (Material-UI) + SQLite database.

**Core directories:**
- `log_agents/` — Python analysis engine (parsers, analyzers, SSH, bots)
- `server/` — FastAPI backend (REST API, database)
- `pyagent-react-gui/` — React frontend

**Pipeline:** `Log Source → Parsers → Aggregation → Findings → Optional AI → JSON Response`

**Key features:** SSH log downloading, bot analysis (70+ patterns), AI vectorization, load balancing (TST metrics), 504/502 analysis, WordPress intelligence, Press Runner (Newsroom load testing), SSE progress tracking, in-memory job storage.

## Existing Modules

| Module | Frontend Component | Backend Router | Description |
|--------|--------------------|----------------|-------------|
| Log Analysis | `components/v2/analysis/ModernLogAnalysis.jsx` | `server/routers/analysis.py` | Parse nginx/PHP-FPM/MySQL logs, 504/BSPH analysis |
| Load Balancing | `components/v2/tools/ModernLoadBalancing.jsx` | `server/routers/load_balancing.py` | TST metrics, server load distribution |
| Headless WP | `components/v2/tools/ModernHeadlessWordPress.jsx` | (via analysis router) | Detect headless WordPress usage |
| WP Intelligence | `components/v2/tools/ModernWordPressIntelligence.jsx` | `server/routers/wordpress.py` | WordPress-specific analysis, PageSpeed |
| Reports | `components/v2/reports/ReportBrowser.jsx` | `server/routers/reports.py` | Report browsing, WordPress sync, reviews |
| Press Runner | `components/v2/tools/ModernPressRunner.jsx` | `server/routers/pressrunner.py` | Newsroom/MediaPress load testing agents |

## Adding a New Sidebar Tab

Sidebar navigation is defined in `pyagent-react-gui/src/App.v2.jsx`.

1. **Add nav item** to the `navItems` array (~line 209):
   ```javascript
   const navItems = [
     { id: 'home', label: 'Home', icon: <HomeIcon /> },
     { id: 'analysis', label: 'Log Analysis', icon: <Analytics /> },
     // ... existing items ...
     { id: 'new-feature', label: 'New Feature', icon: <NewIcon /> },
   ];
   ```

2. **Add view rendering** in the main content area (~line 380+):
   ```javascript
   {currentView === 'new-feature' && (
     <NewFeatureComponent />
   )}
   ```

3. **Create component** at `pyagent-react-gui/src/components/v2/[category]/ModernNewFeature.jsx` using Material-UI, matching existing component patterns (WP Engine teal/navy theme, light/dark support).

## Adding a New Backend Router

Routers live in `server/routers/` and are registered in `server/app.py`.

1. **Create router** at `server/routers/new_feature.py`:
   ```python
   import logging
   from fastapi import APIRouter, HTTPException
   from pydantic import BaseModel, Field

   router = APIRouter()
   logger = logging.getLogger(__name__)

   class FeatureRequest(BaseModel):
       param1: str = Field(..., description="Description")

   @router.post("/api/new-feature")
   def process_feature(req: FeatureRequest):
       try:
           return {"status": "success", "data": result}
       except Exception as e:
           logger.error(f"Feature error: {e}")
           raise HTTPException(status_code=500, detail=str(e))
   ```

2. **Register in `server/app.py`** (~line 36 for import, ~line 133 for include):
   ```python
   from server.routers.new_feature import router as new_feature_router
   app.include_router(new_feature_router, tags=["New Feature"])
   ```

## Press Runner / Newsroom

### What It Is

Press Runner is SEntry's load testing module for **Newsroom** (MediaPress), a WP Engine product for enterprise content publishing on WordPress. It uses automated agents to simulate real editorial workflows — writing articles, editing posts, reviewing content — to generate realistic server load and evaluate how WP Engine environments handle the Newsroom workload.

### MediaPress (Newsroom) Plugin

The Newsroom product is the **MediaPress** plugin (`mediapress-core`, v4.0.3). Key packages:

| Package | Purpose |
|---------|---------|
| Workflow | Draft copy system — clone published posts, edit offline, merge back |
| Checklist | Pre-publish rules (e.g., "has featured image", "excerpt filled") |
| Authors | Multi-author/byline support with Gutenberg blocks |
| Fields | Custom field framework |
| Comments | Comment workflow enhancements |
| Revisions | Enhanced revision tracking |

**MediaPress REST API** (registered at `mediapress-workflow/v1`):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/create` | POST | Create a draft copy of a published post |
| `/{post_type}/{id}` | GET | List draft copies for a post |
| `/restore` | POST | Merge draft copy back into the original |

### Agent Roles

| Role | Simulates | Actions Per Cycle |
|------|-----------|-------------------|
| Writer | Journalist drafting a new article | Creates draft, revises 2-3 times, sets featured image, publishes |
| Editor | Editor revising existing content | Opens draft copy of published post, edits, merges changes back |
| Reviewer | Reviewer leaving feedback | Reads post, checks fields/checklists, leaves comments |
| Publisher | Senior editor (creation + editorial) | Publishes new article, then edits an existing one via MediaPress |

### Load Profiles

| Profile | Agents | Composition |
|---------|--------|-------------|
| Light | 2 | 1 writer, 1 reviewer |
| Standard | 4 | 1 of each role |
| Heavy | 8 | 2 of each role |
| Stress | 12 | 3 of each role |
| Custom | Any | User-defined mix |

### How Orchestration Works

1. Orchestrator launches with a chosen load profile
2. Spawns each agent as an independent parallel process
3. Each agent runs its workflow in a loop for configured iterations
4. Randomized delay (3-15s) before every API call to mimic human pacing
5. All requests carry `PressRunnerAgent/1.0` user-agent for log isolation
6. Orchestrator reports success/failure counts when all agents finish

### Press Runner File Locations (Planned)

| Component | Location |
|-----------|----------|
| Agent framework (Python) | `server/pressrunner/` |
| Backend router | `server/routers/pressrunner.py` |
| React component | `pyagent-react-gui/src/components/v2/tools/ModernPressRunner.jsx` |
| WordPress operational files | `pressrunner/` (top-level) |
| Sidebar entry | `pyagent-react-gui/src/App.v2.jsx` navItems array |

### WordPress Test Environment Setup

When configuring a WordPress site for Press Runner testing:
- Use WP-CLI for efficient configuration
- Install and activate the MediaPress plugin
- Create application passwords for REST API auth
- Configure themes, settings, and sample data
- Track operation types/volume for correlation with server logs

## Security Guidelines

### SSRF Prevention (CRITICAL)

Always validate domains before URL construction:
```python
# CORRECT: Use secure URL construction
secure_url = self._construct_secure_url(domain, "/api/endpoint")

# NEVER: Use f-strings with user domains
url = f"https://{domain}/api/endpoint"  # VULNERABLE
```

Reference: `log_agents/wp_reconnaissance.py`, `docs/SECURITY.md`

## WP Engine Support Investigation Best Practices (CRITICAL)

For detailed failure cases and examples, see `.claude/wpe-investigation-guide.md`.

### Investigation Methodology

1. **Verify Server Tier FIRST**: `wpeapi server-meta <pod-id> sales_offering historical=True`
   - NEVER trust user-provided tier without verification
2. **Verify PHP Workers from constants.py**: Read `WP_ENGINE_TIERS` for exact worker counts
   - NEVER estimate, guess, or use ranges (e.g., "4-6 workers")
   - Use exact values only (e.g., "P0 has 8 workers")
3. **Manual SSH for Log Analysis**: Parse logs server-side with `awk`, `grep`
4. **Check MySQL Slow Queries**: `zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -c "# Time:"`
   - NEVER use `sudo` (fails silently, returns 0)
   - NEVER skip this step
5. **Check User-Agent Data FIRST**: Before concluding "bot attack", verify User-Agents in apachestyle logs
   - NEVER conclude bot/malicious traffic based solely on volume, IP distribution, or request patterns
6. **Reference Sentry tool** for all WP Engine plan specifications

### Nginx Log Parsing Rules (CRITICAL)

WP Engine has **two different log formats**. Using the wrong parsing method produces incorrect results.

**Pipe-delimited access logs** (`{install}.access.log`):
```
timestamp|v1|ip|domain|STATUS|bytes|upstream|time1|exec_time|REQUEST|...|trace
```
- Fields are separated by `|` — ALWAYS use `awk -F'|'` with field-level matching
- Status code = field 5, execution time = field 9, request = field 10
- NEVER use `grep " 504 "` or `grep " 502 "` — spaces do not surround status codes in pipe-delimited logs
- CORRECT: `awk -F'|' '$5 == 504'` or `awk -F'|' '$5 == "504"'`
- WRONG: `grep " 504 "`, `grep -c ' 504 '`, `zgrep " 504 "`

**Apache Combined access logs** (`{install}.apachestyle.log`):
```
IP DOMAIN - [TIMESTAMP] "REQUEST" STATUS BYTES "REFERER" "USER-AGENT"
```
- Fields are space/quote-delimited — `grep " 504 "` works here but prefer `awk` for precision
- Use these logs for User-Agent and Referer analysis (not available in pipe-delimited logs)
- User-Agent extraction: `awk -F'"' '{print $(NF-1)}'`

**Verification step**: ALWAYS check log format before parsing:
```bash
head -1 /var/log/nginx/{install}.access.log
# If output contains | delimiters → use awk -F'|'
# If output is Apache Combined format → use space/quote parsing
```

### PHP Worker Counts (Source of Truth: constants.py)

P0=8, P1=10, P1.5=12, P2=15, P3=20, P4=40, P5=60, P6=80, P7=100, P8=120, P9=160, P10=180

### WP Engine Log Locations

| Log Type | Path | Notes |
|----------|------|-------|
| Nginx access | `/var/log/nginx/{install}.access.log` | Pipe-delimited, field 8 = BSP time (upstream), field 9 = exec time |
| Nginx apachestyle | `/var/log/nginx/{install}.apachestyle.log` | ALL traffic (cached + uncached), has User-Agent and Referer |
| Apache access | `/var/log/apache2/{install}.access.log` | ONLY dynamic/PHP requests (cache misses) — true PHP worker demand |
| PHP-FPM errors | `/nas/log/fpm/{install}.error.log` | NOT `/var/log/fpm/` |
| MySQL slow query | `/var/log/mysql/mysql-slow.log` | Use `zcat -f`, no `sudo` |

**High Availability (HA) Clusters** use a different log path prefix:

| Log Type | Standard Path | HA Cluster Path |
|----------|--------------|-----------------|
| Nginx access | `/var/log/nginx/{install}.access.log` | `/var/log/synced/nginx/{install}.access.log` |
| Nginx apachestyle | `/var/log/nginx/{install}.apachestyle.log` | `/var/log/synced/nginx/{install}.apachestyle.log` |

HA cluster IDs are typically shorter numbers (e.g., `97471`) compared to standard pod IDs. To detect which path to use:
```bash
# Check if synced log path exists (HA cluster)
ls /var/log/synced/nginx/ 2>/dev/null && echo "HA cluster" || echo "Standard pod"
```

Rotated logs: `.log.1` (yesterday), `.log.2.gz` through `.log.7.gz` (2-7 days ago).

### Log Analysis Timeframe

**Default: 7 days (current week).** Analyze `.log` through `.log.7.gz` only. Do not include older logs unless explicitly requested. Always document the analysis period in reports.

### WP Engine Platform Architecture

**Request flow (with dual-layer nginx logging):**

```
Client (HTTPS) → NGINX-secure (SSL termination, port 443)
                    ↓  [logged in install-secure.access.log]
                 NGINX inner proxy (port 80)
                    ↓  [logged in install.access.log + install.apachestyle.log = ALL traffic]
                 Varnish (port 9002, page cache)
                    ↓  (cache miss only)
                 Apache (port 6788/6789)
                    ↓  [logged in /var/log/apache2/install.access.log = DYNAMIC traffic only]
                 PHP-FPM → MySQL
```

- **Nginx apachestyle logs** = ALL traffic (cached + uncached) — total request volume
- **Apache access logs** = ONLY cache misses that required PHP — true PHP worker demand
- **Difference** = Varnish cache hits (served without PHP)
- The `upstream` field `127.0.0.1:9002` = **Varnish**, not PHP-FPM
- Cache hits return in milliseconds without touching PHP-FPM
- The `-secure` log suffix = outer SSL nginx layer; non-secure = inner proxy layer

**Error code origins:**
- **502**: PHP-FPM container crash/unavailable (NGINX cannot reach PHP-FPM)
- **503**: Queuing layer capacity limits reached (platform protection)
- **504**: PHP execution timeout (>30 seconds)

Do NOT conflate 503 and 504 — they have different root causes.

### Utility Servers vs Production Servers

SSH always connects to **utility servers**, NOT production. Key rules:
- Logs on utility servers accurately reflect production activity
- NEVER reference system metrics (CPU, memory, disk I/O) — they show utility server, not production
- Verify install cluster_id: `wpeapi site-data <install>` (cluster_id = pod_id)
- Utility servers may show installs from multiple production pods — always verify
- Naming: `pod-XXXXXX.wpengine.com` (standard) or `pod-XXXXXX-utility-*` (k8s, no SSH config needed)
- **HA clusters**: Use cluster IDs (shorter numbers, e.g., `97471`) and logs are under `/var/log/synced/` instead of `/var/log/`

### Master Investigation Checklist

- [ ] Run `wpeapi server-meta <pod-id> sales_offering historical=True` to verify server tier
- [ ] Read `constants.py` for exact PHP worker count (NEVER estimate)
- [ ] Verify install's `cluster_id` with `wpeapi site-data <install>`
- [ ] **Check GES status via DNS** before recommending GES (see GES Detection below)
- [ ] Check MySQL slow queries: `zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -c "# Time:"`
- [ ] Analyze slow query patterns if found (query times, installs, query types)
- [ ] Check User-Agent data in apachestyle logs before bot/attack conclusions
- [ ] Check HTTP Referer data to understand request origins
- [ ] Use manual SSH for direct log parsing
- [ ] NEVER reference system resource metrics (CPU, memory) from utility server
- [ ] Base all analysis on log files reflecting production activity
- [ ] Create folder: `mkdir -p ~/Documents/"Sentry Reports"/{pod-id}/`
- [ ] Save reports in pod folder with naming: `pod-[ID]-[issue]-{rootcause|evidence}.md`
- [ ] Attribute all reports to "Sentry Ai Analysis" (never "Claude" or "AI Analysis")
- [ ] Document analysis period, data sources, and total requests analyzed

### GES Detection (CRITICAL — Check Before Recommending)

**NEVER recommend "Enable GES" without first verifying GES status via DNS.** Two investigations in a row incorrectly recommended GES when it was already active.

**Method:** Extract domains from nginx log field $4, then run DNS lookup from local machine (no SSH needed):

```bash
# Get domains from nginx logs
ssh pod-XXXXXX.wpengine.com 'awk -F"|" "{print \$4}" /var/log/nginx/{install}.access.log.1 | sort -u | head -5'

# Check each domain for GES CNAME
dig +short CNAME www.example.com
```

**GES Signatures:**
- **GES active:** CNAME to `*.wpeproxy.com` → resolves to `141.193.213.x` IPs
- **No GES (customer Cloudflare):** No CNAME, A records point to `104.21.x.x` / `172.67.x.x` (Cloudflare IPs)
- **No GES (direct to WPE):** CNAME to `*.wpengine.com` or `*.wpenginepowered.com`

**Check per-install** — GES may not be active on all installs in an account.

**If GES is active but unwanted traffic still reaches PHP:** Recommend configuring custom **GES WebRules** to block specific attack patterns (scanner IPs, wp-login rate limiting, bot challenges). This is a configuration conversation, not a new purchase.

**If GES is NOT active:** Recommend enabling GES with `[O]` in the addon grid.

### Root Cause Report Rules

For templates and detailed format guidelines, see `.claude/report-templates.md`.

**DO NOT include in customer-facing reports:**
- System resource metrics (CPU, memory, disk I/O) — utility server data, irrelevant
- Pod configuration details (worker counts, CPU cores, memory allocations, BSPH, capacity ranges)
- Pricing, costs, ROI calculations, or financial analysis
- Recommendations for WP Engine managed infrastructure (rate limiting, Redis, object cache, CDN, PHP-FPM config, Nginx config, database tuning)

**DO include:**
- Plan tier name only (e.g., "P3 plan")
- Observable metrics: HTTP request counts, error rates, execution times, traffic patterns
- PHP-FPM and database query errors from logs
- Actionable recommendations: plugin updates, code optimization, WooCommerce optimization, plan upgrade (if justified)

**Server upgrade recommendations require ALL of:**
1. Evidence of PHP worker pool exhaustion
2. Gateway timeout errors (504/502) correlating with traffic spikes
3. Request execution times showing queue backup (>1s waits)
4. Traffic consistently exceeding plan capacity
5. No code-level issues causing the degradation

### Report Attribution

Always: `**Report Prepared By:** Sentry Ai Analysis`
Never: "Claude Code", "Claude", "AI Analysis", or generic attributions.

Every report MUST end with the full structured attribution block (not inline italic footnotes). See `.claude/report-templates.md` "Report Footer (Full Attribution)" for the required format including error totals and analysis tools.

### Report File Organization

Save all reports to: `~/Documents/Sentry Reports/{pod-id}/`
- Customer report: `pod-[ID]-[issue]-rootcause.md`
- Evidence file: `pod-[ID]-[issue]-evidence.md`

## Code Quality Standards

### SonarQube Compliance

**Cognitive Complexity:** Maximum 15 per function. Extract helper functions when exceeded.

**Previously refactored files (DO NOT reintroduce complexity):**
- `server/routers/ssh.py`: `ssh_download_logs()` (34→10) — keep helpers: `_run_ssh_log_analysis()`, `_save_ssh_analysis_to_db()`, `_enhance_ssh_download_error_message()`
- `server/routers/ssh.py`: `ssh_progress_stream()` (29→12) — keep helper: `_handle_session_data()`
- `server/routers/analysis.py`: `analyze_logs()` (23→8) — keep helpers: `_build_cached_response()`, `_run_504_analysis()`, `_save_analysis_to_database()`, `_build_final_response()`
- `pyagent-react-gui/src/components/LogAnalysis/AnalysisResults.js` (27→10) — keep sub-components: `SummaryChips.js`, `MetaBlocks.js`, `ResourceAnalysis.js`, `AISummarySection.js`, `FindingsSection.js`

**Other rules:**
- No duplicated string literals — use constants
- Always capture asyncio task references to prevent GC
- Run: `ruff check .`, `black .`, `isort .` before commits

## Environment Variables

```bash
GOOGLE_CLOUD_PROJECT=wp-engine-ai          # Required for AI features
GOOGLE_CLOUD_REGION=us-central1            # Optional
LOG_SUMMARY_MODEL=gemini-2.5-flash         # Optional
DATABASE_PATH=./data/sentry.db             # Optional
```

## Key File Locations

**Core Analysis:** `log_agents/analyzer.py`, `log_agents/gateway_504_analyzer.py`, `log_agents/ssh_manager.py`, `log_agents/load_balancer.py`

**API:** `server/app.py`, `server/routers/analysis.py`, `server/routers/ssh.py`, `server/routers/load_balancing.py`, `server/routers/wordpress.py`, `server/routers/system.py`, `server/routers/reports.py`, `server/database.py`

**Frontend (v2 — current):** `pyagent-react-gui/src/App.v2.jsx` (sidebar + view routing), `components/v2/analysis/ModernLogAnalysis.jsx`, `components/v2/tools/ModernLoadBalancing.jsx`, `components/v2/tools/ModernWordPressIntelligence.jsx`, `components/v2/tools/ModernHeadlessWordPress.jsx`, `components/v2/reports/ReportBrowser.jsx`

**Frontend (v1 — legacy):** `pyagent-react-gui/src/App.v1.jsx`, `components/LogAnalysis.js`, `LoadBalancing.js`, `WordPressIntelligence.js`

**Press Runner:** `server/routers/pressrunner.py`, `server/pressrunner/`, `pyagent-react-gui/src/components/v2/tools/ModernPressRunner.jsx`, `pressrunner/`

**API Client:** `pyagent-react-gui/src/utils/api.js` (centralized fetch wrapper, base URL: `http://localhost:8787`)

## Important Notes

- **Security First**: Always follow SSRF prevention patterns
- **Browser-Only**: This is a local browser app, not a web service (no Redis, in-memory storage)
- **Hot Reload**: `./start-dev.sh` launches React dev server on port 3002 with hot reload
- **Troubleshooting**: See `README.md`
