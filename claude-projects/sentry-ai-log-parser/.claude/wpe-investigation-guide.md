# WP Engine Investigation Guide — Detailed Reference

This file contains detailed failure cases, investigation examples, and methodology deep-dives referenced by `CLAUDE.md`. Read this file when performing WP Engine pod investigations.

## Failure Case #1: Server Tier Misidentification

**Incident:** User stated server was "P1.5" — accepted without verification. Built entire analysis on wrong tier.
**Reality:** `wpeapi server-meta 228552 sales_offering historical=True` showed P3 (not P1.5).
**Impact:** Reported "P3 has ~4-6 workers" (guessed) vs actual 20 workers. 3x error in capacity calculations. Complete rework required.
**Rule:** ALWAYS verify with `wpeapi` before analysis.

## Failure Case #2: PHP Worker Count Estimation (Pod 225190)

**Incident:** Reported "P0 plan has 4-6 PHP workers" — estimated without checking constants.py.
**Reality:** P0 has exactly 8 workers (from `constants.py` WP_ENGINE_TIERS).
**Impact:** All capacity calculations wrong by 25-33%. 11 separate edits needed. User caught the error.
**Rule:** ALWAYS read `constants.py` for exact worker count. NEVER estimate or use ranges.

## Failure Case #3: MySQL Slow Query Log Missed (Pod 212005)

**Incident:** Reported "0 slow queries" using `sudo find /var/log/mysql/` which fails silently.
**Reality:** 503 slow queries over 7 days. Included 104 WP Offload Media queries (6-10s), 71 WordPress Popular Posts queries (17-28s), slowest at 79.2 seconds.
**Impact:** Fundamentally wrong root cause. Missed critical database optimization opportunities.

**WRONG command:**
```bash
# Fails silently, returns 0
sudo find /var/log/mysql/ -name "mysql-slow.log*" -mtime -7 -exec zcat -f {} \; 2>/dev/null | grep -c "# Time:"
```

**CORRECT commands:**
```bash
# Count slow queries
zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -c "# Time:"

# Full analysis
zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -A 10 "# Time:" | head -100
```

## Failure Case #4: Bot Attack Misdiagnosis (Pod 402850)

**Incident:** Concluded "distributed botnet attack" targeting WordPress REST API based on:
- 371,663 requests to `/wp-json/wp/v2/users/me`
- 59,602 unique IPs
- OPTIONS + GET pattern

**Reality (after checking User-Agents in apachestyle logs):**
- 186,889 requests had real browser User-Agents (Chrome, Safari, Edge)
- 99% of traffic came from homepage visits (HTTP Referer: silvergoldbull.ca)
- Root cause: JavaScript bug making auth check for ALL visitors, not just logged-in users

**Impact:** Completely wrong root cause. Would have blocked legitimate user functionality. Required complete rework.

**Rule:** ALWAYS check User-Agent data before labeling traffic as malicious.

## Failure Case #5: Pricing in Technical Report (Pod 213364)

**Incident:** Included "P3 upgrade cost: ~$200-300/month" with ROI calculations in technical report.
**Rule:** NEVER include pricing, costs, or financial analysis. You are a technical support engineer. Pricing is account management's responsibility.

**Correct approach:**
```markdown
**Implementation:** Contact WP Engine Support to evaluate server plan options
if performance does not improve after optimizations.
```

## Failure Case #6: Grep on Pipe-Delimited Logs (Pod 222321-era)

**Incident:** Used `grep -c ' 504 '` on pipe-delimited `.access.log` files. Grep searches for the literal string ` 504 ` (with spaces on both sides). In pipe-delimited logs, the status code appears as `|504|` — no spaces surround it. The grep silently returned 0 matches.

**Reality:** The server had 553,663 real 504 errors. The `grep` pattern found none of them because it was designed for Apache Combined (space-delimited) log format, not WP Engine's pipe-delimited format.

**Impact:** Would have reported "0 504 errors" on a server experiencing critical 8.75% error rates. Completely wrong conclusion, missed the entire problem.

**WRONG commands (space-delimited grep on pipe-delimited logs):**
```bash
grep " 504 " /var/log/nginx/install.access.log | wc -l          # Returns 0
zgrep -h " 504 " /var/log/nginx/install.access.log* | wc -l     # Returns 0
grep -c ' 502 ' /var/log/nginx/install.access.log                # Returns 0
```

**CORRECT commands (field-level awk on pipe-delimited logs):**
```bash
awk -F'|' '$5 == 504' /var/log/nginx/install.access.log | wc -l
zcat -f /var/log/nginx/install.access.log* 2>/dev/null | awk -F'|' '$5 == 504' | wc -l
zcat -f /var/log/nginx/install.access.log* 2>/dev/null | awk -F'|' '$5 == 502' | wc -l
```

**Rule:** ALWAYS use `awk -F'|'` with field-level matching on pipe-delimited `.access.log` files. NEVER use `grep " STATUS "` — it only works on space-delimited (`.apachestyle.log`) files. When in doubt, run `head -1` on the log file to check if fields are separated by `|` or spaces.

## User-Agent Analysis Methodology

### Where to Find User-Agent Data

```bash
# Regular nginx logs do NOT contain User-Agent data
/var/log/nginx/{install}.access.log       # Pipe-delimited, no UA field

# Apache-style logs contain User-Agent data
/var/log/nginx/{install}.apachestyle.log  # Full Apache combined format

# Extract User-Agents for specific endpoint
grep "wp-json/wp/v2/users/me" /var/log/nginx/{install}.apachestyle.log | \
  awk -F'"' '{print $(NF-1)}' | sort | uniq -c | sort -rn | head -25

# Check HTTP Referer
grep "wp-json/wp/v2/users/me" /var/log/nginx/{install}.apachestyle.log | \
  awk -F'"' '{print $(NF-3)}' | sort | uniq -c | sort -rn | head -15
```

### Apache-Style Log Format

```
IP DOMAIN - [TIMESTAMP] "REQUEST" STATUS BYTES "REFERER" "USER-AGENT"

Example:
2a06:98c0:3600::103 example.com - [30/Jan/2026:17:08:10 +0000] "GET /page HTTP/1.0" 200 424234 "https://example.com/" "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15"
```

### Bot vs Legitimate Traffic Indicators

**Bot User-Agents:**
```
curl/7.68.0, python-requests/2.28.1, Go-http-client/1.1, Wget/1.20.3,
Apache-HttpClient/4.5.13, Scrapy/2.5.0
```

**Legitimate Browser User-Agents:**
```
Mozilla/5.0 ... Chrome/144.0.0.0 Safari/537.36
Mozilla/5.0 (iPhone; ...) AppleWebKit/605.1.15 ... Safari/604.1
Mozilla/5.0 (Macintosh; ...) Version/26.2 Safari/605.1.15
```

### Traffic Investigation Methodology

1. See unusual traffic pattern
2. **FIRST:** Check User-Agent data in apachestyle logs
3. Analyze User-Agent distribution (real browsers vs bot signatures)
4. Check HTTP Referer data (where requests originated)
5. **THEN** determine if bot traffic or code/configuration issue
6. Write report with evidence

**NEVER conclude "bot attack" based solely on:**
- High request volume alone
- Distributed IP addresses alone
- OPTIONS + GET pattern alone (legitimate CORS preflight + API call)
- Any request pattern without User-Agent verification

## WP Engine Container Architecture Details

### Production Request Flow

Each component runs in its own container:

```
Client Request → NGINX (SSL termination, routing)
    → NGINX Queuing Layer / WPEngine X (throttling, protection)
    → Varnish (page caching, bypassed for logged-in users)
    → PHP-FPM (WordPress execution, fixed worker pool)
    → MySQL (database queries)
```

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

**Key implications:**
- The `upstream` field showing `127.0.0.1:9002` means nginx is proxying to **Varnish**, not PHP-FPM directly
- **Varnish cache hits** return in milliseconds (0.002s–0.004s) without touching PHP-FPM — these are NOT fast PHP executions
- **Varnish cache misses** forward to PHP-FPM, and the response time includes Varnish processing + PHP-FPM execution
- The `-secure` suffix in log file names indicates the outer SSL-terminating nginx layer; the non-secure log is the inner proxy layer
- Both logs capture the same request with matching request IDs

**Port reference:**
- Port 80/443: Nginx (HTTP/HTTPS)
- Port 9002: Varnish
- Port 6788: Apache read/write
- Port 6789: Apache read-only
- Port 6778/6779: PHP 7.4 containers

### Container Behavior Details

**NGINX Queuing Layer (WPEngine X):**
- Proprietary request queuing system
- 503 errors originate here when capacity limits reached
- Protects backend from overload
- Not directly observable — infer from NGINX logs and error patterns

**Varnish:**
- Cached pages bypass PHP-FPM and MySQL entirely
- Logged-in users and dynamic content always hit PHP-FPM
- Cache hit rate significantly affects PHP-FPM load

**PHP Worker Pool Exhaustion:**
- Manifests as 503 errors (queuing layer rejects requests)
- Also manifests as 504 errors (workers busy, requests timeout)
- Both error types can indicate the same underlying capacity issue

### Observable vs Unobservable

- **Observable:** NGINX logs, PHP-FPM logs, MySQL slow query logs
- **NOT Observable:** Queuing layer metrics, Varnish hit rates, container resource usage
- Must infer queuing layer behavior from NGINX logs and error patterns

### Utility Server Architecture

SSH connections go to utility servers, not production. The utility server manages the production pod.

```
You → SSH → Utility Server (pod-XXXXXX.wpengine.com)
                 ↓
      Manages → Production Pod (web, PHP-FPM, MySQL containers)
```

**Key facts:**
- `cluster_id` from `wpeapi site-data` = pod_id (1:1 mapping)
- Standard naming: `pod-XXXXXX.wpengine.com`
- K8s naming: `pod-XXXXXX-utility-XXXXXXXXX-XXXXX` (direct connection, no SSH config)
- Multi-tenant: utility servers may show installs from different cluster IDs
- Logs are accurate reflections of production activity
- System metrics (top, htop, free) show utility server only — NEVER use in reports

**Correct commands (log-based, reflects production):**
```bash
zcat -f /var/log/nginx/install.access.log* 2>/dev/null | awk -F'|' '$5 == 504' | wc -l
zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -c "# Time:"
awk -F'|' '{sum+=$9; count++} END {print sum/count}' /var/log/nginx/install.access.log
```

**WRONG commands (utility server metrics, irrelevant):**
```bash
top -bn1 | head -20   # Utility server CPU
free -m                # Utility server memory
iostat                 # Utility server disk I/O
```
