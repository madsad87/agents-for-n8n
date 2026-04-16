# Troubleshoot WP Engine 504 Gateway Timeout Errors

Use when a site is returning 504 Gateway Timeout errors — indicates PHP execution exceeding the 30-second timeout. Also use when the user reports "site is slow," "pages won't load," or "timeouts during checkout/search." This is the most common WP Engine performance investigation type.

## Pre-Investigation: Gather Required Information

**Before proceeding, ensure you have:**

1. **Pod Number** (e.g., "213668" or "pod-213668")
   - If not provided: Ask user for the pod number

2. **Investigation Scope**
   - If not provided: Ask user:
     - "Should I analyze the entire server (all installs)?"
     - "Or focus on specific install(s)? (provide install name)"

3. **Timeframe** (optional)
   - Default: Last 7 days (current week)
   - Ask only if user mentions specific dates/times

4. **SSH Configuration**
   - Check `~/.ssh/config` for correct WP Engine username
   - Reference CLAUDE.md for bastion server setup if needed
   - Support both connection types:
     - Standard pods: via SSH config + bastion proxy
     - Direct Kubernetes utility pods: direct connection

**Example Pre-Flight Check:**
```
I'll help investigate 504 errors on WP Engine. Please provide:

1. Pod number: (e.g., 213668)
2. Investigation scope:
   - Entire server (all installs)?
   - Specific install name(s)?
3. [Optional] Timeframe: Default is last 7 days

I'll then connect via SSH and begin the analysis.
```

## Your Mission

Perform a comprehensive 504 error investigation by:
1. Connecting to the WP Engine server via SSH (using correct username and bastion configuration)
2. Analyzing server logs and queue metrics intelligently
3. Identifying root causes with supporting evidence
4. Cross-referencing findings with WP Engine tier capacity data
5. Delivering a professional, customer-facing root cause analysis report

## Critical Context: WP Engine Architecture

### Dual-Layer Nginx Logging

WP Engine runs two nginx layers. Each install produces two access log files that capture the same request at different points in the stack:

```
Client (HTTPS) → NGINX-secure (SSL termination, port 443)
                    ↓  [logged in install-secure.access.log]
                 NGINX inner proxy (port 80)
                    ↓  [logged in install.access.log]
                 Varnish (port 9002, page cache)
                    ↓  (cache miss only)
                 PHP-FPM → MySQL
```

**Key implications for 504 analysis:**
- The `upstream` field showing `127.0.0.1:9002` means nginx is proxying to **Varnish**, not PHP-FPM directly
- **Varnish cache hits** return in milliseconds (0.002s–0.004s) without touching PHP-FPM — these are NOT fast PHP executions
- **Varnish cache misses** forward to PHP-FPM, and the response time includes Varnish processing + PHP-FPM execution
- When calculating execution times, filter with `$9+0 > 0` — this correctly captures PHP-processed requests since cached responses come back in sub-millisecond times
- Requests that 504 are always cache misses (they hit PHP-FPM and exceeded the timeout)

**Port reference:**
- Port 80/443: Nginx (HTTP/HTTPS)
- Port 9002: Varnish
- Port 6788: Apache read/write
- Port 6789: Apache read-only
- Port 6778/6779: PHP 7.4 containers

### Nginx Queuing System
- **Purpose**: Prevent Apache/PHP-FPM overload
- **Queue Structure**:
  - **Active Queue**: 10 concurrent requests (default)
  - **Backlog Queue**: 50 for dedicated, 20 for shared (default)
- **Evictions**: When backlog is full, oldest request gets 504 error
- **Timeout**: Requests waiting >60 seconds automatically get 504

### Plan Types (CRITICAL DISTINCTION)

**Single-Tenant Plans (P0-P10)**:
- Dedicated server per account
- **Each install has its own isolated queue**
- One install's issues don't affect others
- Tiers range from P0 (8 workers) to P10 (180 workers)

**Multi-Tenant Shared Plans**:
- Multiple accounts share one P3-equivalent server (~20 workers)
- **All installs in SAME ACCOUNT share the queue pool**
- ⚠️ One problematic install can cause 504s for all installs in the account
- Must analyze ALL installs in the account

### WP Engine Tier Specifications
Reference `constants.py` in the project root for:
- PHP workers per tier (P0=8, P1=10, ..., P10=180)
- PHP CPU cores allocated
- PHP memory limits
- BSPH capacity ranges (min/max)
- Dynamic request capacity ranges

## Investigation Methodology

### Phase 1: Connect and Verify

1. **SSH Connection**
   - Use username from `~/.ssh/config`
   - Connect as: `ssh [username]@pod-[number].wpengine.com`
   - Or direct Kubernetes pod: `ssh [username]@pod-[number]-utility-[hash]`
   - Reference CLAUDE.md for bastion server configuration if needed

2. **Verify 504 Errors Exist**
   - Check for recent evictions in queue system
   - Identify affected install(s)
   - Verify timeframe of issues

### Phase 2: Intelligent Log Analysis

**Default Timeframe**: Analyze only logs from the **last 7 days** (current week)

**Discover Available Logs**:
```bash
# Find all nginx logs modified in last 7 days
find /var/log/nginx/ -name "INSTALL.access.log*" -mtime -7 -exec ls -lht {} \;
find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7 -exec ls -lht {} \;

# Check modification dates to ensure logs are recent
ls -lht /var/log/nginx/INSTALL.access.log*
```

**IMPORTANT**:
- Always check file modification dates (`ls -lt`)
- Only analyze logs modified within 7 days
- Ignore old/stale logs (e.g., 1 month or 1 year old)
- Log rotation may go beyond .log.7.gz (could be .log.9.gz or more)
- Use `-mtime -7` to find files modified in last 7 days

**You Have Full Autonomy**: Use ANY analysis approach you deem effective:
- Standard commands (zgrep, awk, grep, sed, cut, sort, uniq)
- Python scripts for complex parsing
- Custom one-liners optimized for the specific pattern
- Multi-stage analysis pipelines
- Real-time monitoring with watch commands

**Example Investigation Paths** (NOT prescriptive - adapt as needed):

**Pattern Analysis**:
- Which IPs are receiving the most 504s?
- Which user agents are affected?
- Which URLs/paths are generating 504s?
- What time periods show the highest 504 counts?

**Queue Behavior**:
- Check current queue status: `buckets` or `php /etc/wpengine/bin/queues.php --account=all`
- Monitor in real-time: `watch -bn 2 php /etc/wpengine/bin/queues.php --account=all`
- Look for evictions, backlog saturation, long avg wait times

**Active Process Analysis**:
- EVLV servers: `fpmwatch` (check for long-running processes)
- Classic servers: `apachewatch` (check active process queue)
- Identify: admin-ajax requests, slow pages, cron jobs, database queries

**Traffic Patterns**:
- Bot traffic analysis (check user agents)
- IP concentration (single IP hammering site?)
- Uncached hit volume
- Request distribution over time

### Phase 3: Root Cause Identification

Common 504 causes to investigate:

1. **PHP Worker Saturation**
   - Long-running requests blocking workers
   - Slow admin-ajax.php requests
   - Database query performance issues
   - Too many concurrent requests for tier capacity

2. **Bot/Crawler Traffic**
   - Aggressive bot crawling
   - Bots ignoring robots.txt crawl-delay
   - DDoS or malicious traffic patterns

3. **Tier Capacity Exceeded**
   - Traffic exceeds plan limits (check against constants.py)
   - BSPH/dynamic requests beyond tier capacity
   - Need for upgrade vs optimization

4. **Code/Plugin Issues**
   - Slow/broken plugins or themes
   - Uncached pages with heavy processing
   - Memory leaks or infinite loops
   - Excessive cron jobs

5. **Multi-Tenant Queue Contention** (Shared plans only)
   - One install starving others in the account
   - Recommendation: Separate accounts or upgrade

### Phase 4: Tier Capacity Assessment

**Cross-reference findings with WP Engine tier data**:

1. **Load current tier specs** from constants.py:
```python
# Reference these values from constants.py
WP_ENGINE_TIERS = {
    'P0': {'php_workers': 8, 'php_cpu_cores': 1.2, 'php_memory_gb': 5.4, ...},
    'P1': {'php_workers': 10, 'php_cpu_cores': 1.8, 'php_memory_gb': 6.4, ...},
    # ... through P10
}
```

2. **Compare actual usage vs tier limits**:
   - PHP workers: Are all workers saturated?
   - BSPH/day: Within tier min/max range?
   - Dynamic requests/day: Exceeding capacity?
   - CPU/Memory: Near limits?

3. **Determine recommendation**:
   - **Tier saturation** → Recommend upgrade to next tier
   - **Within capacity** → Focus on optimization (caching, code fixes, bot blocking)
   - **Shared plan contention** → Recommend account separation or dedicated plan

**Example Assessment**:
```
Current: P2 (15 workers, 3.1 CPU cores, 100k-150k requests/day)
Finding: 180k requests/day, 12/15 workers constantly busy
Recommendation: Upgrade to P3 (20 workers, 200k-300k capacity)
```

### Phase 5: Customer-Facing Report

Include the original user request/prompt that initiated this investigation as the first section of the evidence file, under an "Original Request" heading with the verbatim text in a blockquote.

**Generate a professional Markdown report** with:

#### Required Sections:

1. **Executive Summary**
   - Brief overview of issue
   - Root cause in 1-2 sentences
   - Recommendation summary

2. **Investigation Timeline**
   - When 504 errors occurred
   - How many 504 errors observed
   - Analysis period covered (e.g., "Last 7 days: Jan 8-15, 2026")

3. **Root Cause Analysis**
   - Primary cause with evidence
   - Contributing factors
   - Technical explanation (customer-appropriate language)

4. **Evidence & Metrics**
   - Specific log excerpts (sanitized)
   - Queue metrics (evictions, backlog, avg wait time)
   - Traffic patterns (IPs, user agents, URLs)
   - Tier capacity comparison

5. **Recommendations**
   - Immediate actions (if any)
   - Long-term solutions
   - Tier upgrade guidance (if applicable)
   - Optimization opportunities

6. **Technical Details** (Appendix)
   - Commands used for verification
   - Full analysis methodology
   - Citations to specific log files and timestamps

#### Report Formatting:

- Use professional, customer-friendly language
- Avoid jargon; explain technical terms when necessary
- Include specific timestamps and metrics
- Use markdown formatting for readability
- Always attribute to "Sentry Ai Analysis"
- Save report to: `~/Documents/pod-[number]_504_analysis_[date].md`

#### Restrictions (from CLAUDE.md):

**DO NOT**:
- Recommend server configuration changes (WP Engine manages infrastructure)
- Quote CPU/Memory metrics from utility pods (unreliable)
- Recommend tier upgrades without meeting ALL 5 criteria:
  1. Consistent 504s over 24+ hours
  2. Evidence of capacity limits reached
  3. No code/plugin issues identified
  4. Caching properly configured
  5. Bot traffic ruled out or addressed

**DO**:
- Focus on application-level optimizations
- Recommend WP Engine features (Advanced Network, CDN, etc.)
- Suggest code/plugin improvements
- Provide bot blocking guidance

## Example Commands Reference

**These are examples only** - use your judgment to create better analysis:

```bash
# Discover recent logs (last 7 days) with modification dates
find /var/log/nginx/ -name "install.access.log*" -mtime -7 -exec ls -lht {} \;

# Count 504 errors in current week (pipe-delimited logs — MUST use awk field matching)
zcat -f $(find /var/log/nginx/ -name "install.access.log*" -mtime -7) 2>/dev/null | awk -F'|' '$5 == 504' | wc -l

# Top IPs receiving 504s
zgrep -h "\" 504 " $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | awk '{print $1}' | sort | uniq -c | sort -rn | head -20

# Top user agents with 504s
zgrep -h "\" 504 " $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | awk -F'"' '{print $6}' | sort | uniq -c | sort -rn | head -20

# Top URLs generating 504s
zgrep -h "\" 504 " $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | awk -F'"' '{print $2}' | sort | uniq -c | sort -rn | head -20

# 504s per hour timeline (pipe-delimited logs — MUST use awk field matching)
zcat -f $(find /var/log/nginx/ -name "install.access.log*" -mtime -7) 2>/dev/null | awk -F'|' '$5 == 504 {print $1}' | cut -d: -f1-2 | sort | uniq -c

# Queue status (real-time)
php /etc/wpengine/bin/queues.php --account=all

# Watch queue status (updates every 2 seconds)
watch -bn 2 php /etc/wpengine/bin/queues.php --account=all

# IP geolocation lookup
curl -s ipinfo.io/[IP-ADDRESS]

# Check current active processes (EVLV)
fpmwatch

# Uncached requests by URL
cat /var/log/nginx/install.access.log | cut -d'|' -f10 | sort | uniq -c | sort -nr | head -20

# Check which install has highest traffic
# (useful for multi-tenant shared plans)
cat /var/log/apache2/*.access.log /var/log/nginx/*.apachestyle.log | awk -F'[' '{print $2 }' | awk -F: '{ print "Time: " $1,$2 ":00" }' | sort | uniq -c | more
```

## Success Criteria

Your investigation is complete when you have:

✅ Gathered all required information (pod number, scope, timeframe)
✅ Connected via SSH using correct username and bastion configuration
✅ Identified the root cause with supporting evidence
✅ Analyzed logs from the appropriate timeframe (last 7 days, verified by modification dates)
✅ Cross-referenced findings with WP Engine tier capacity data
✅ Considered both single-tenant and multi-tenant architecture implications
✅ Generated a professional, customer-facing Markdown report
✅ Provided actionable recommendations with clear next steps
✅ Documented all analysis steps for verification

## Attribution

All reports must be attributed to:
**"Sentry Ai Analysis"**

---

**Remember**: You have full autonomy in your investigation approach. Use the examples as guidance, but adapt your analysis to the specific patterns you discover. Your goal is to find the truth, not to follow a script.
