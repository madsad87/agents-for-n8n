# WordPress Endpoints — wp-login, XMLRPC, wp-cron, admin-ajax, REST API

Use when you need to analyze the 5 critical WordPress endpoints that commonly drive performance issues — wp-login (brute force), XMLRPC (abuse/blocking), wp-cron (runaway schedules), admin-ajax (plugin floods), and REST API (enumeration/abuse). Run as part of `/scout` or standalone when an AM reports login attacks or high admin-ajax volume.

## Required Input

**Pod number** — provided by the user (e.g., "213646")

## Pre-Flight: Load Pod Metadata

```bash
cat ~/Documents/"Sentry Reports"/{pod-id}/pod-metadata.json 2>/dev/null
```

---

## CRITICAL: Date Filtering & Ghost Install Protection

**Every command in this skill MUST filter log lines by date.** WP Engine does not clean up log files when installs are removed — stale logs from months/years ago will silently contaminate results if not filtered.

### Generate Date Filter (run once per SSH session)

```bash
DATE_FILTER_PATTERN=$(for I in $(seq 0 6); do date -d "$I days ago" +"%d/%b/%Y"; done | tr "\n" "|" | sed "s/|$//")
```

Or use the `date_filter_pattern` from `pod-metadata.json` if available.

### Apply to Every Pipeline

After every `cat`/`zcat` pipeline that reads log lines, add:
```bash
| LC_ALL=C grep -E "$DATE_FILTER_PATTERN"
```

### Exclude Ghost Installs

If `pod-metadata.json` lists `ghost_installs` or `orphan_installs`, skip those install log files entirely.

---

## Phase 1: Endpoint Volume & BSP Overview

Get total request counts AND BSP (Billable Server Processing) for each WordPress endpoint. BSP measures cumulative processing time in seconds — this tells you the actual PHP worker cost, not just hit counts.

### Request Counts (full week)

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "
  \$10 ~ /wp-login/ {login++}
  \$10 ~ /xmlrpc/ {xmlrpc++}
  \$10 ~ /wp-cron/ {cron++}
  \$10 ~ /admin-ajax/ {ajax++}
  \$10 ~ /wp-json/ {json++}
  END {print \"wp-login: \" login+0; print \"xmlrpc: \" xmlrpc+0; print \"wp-cron: \" cron+0; print \"admin-ajax: \" ajax+0; print \"wp-json: \" json+0}
"'

# Add gzipped rotations (exclude -secure logs)
ssh {host} 'for f in $(ls {log_base}*.access.log.{2,3,4,5,6,7}.gz 2>/dev/null | grep -v "\\-secure"); do zcat "$f" 2>/dev/null; done | awk -F"|" "
  \$10 ~ /wp-login/ {login++}
  \$10 ~ /xmlrpc/ {xmlrpc++}
  \$10 ~ /wp-cron/ {cron++}
  \$10 ~ /admin-ajax/ {ajax++}
  \$10 ~ /wp-json/ {json++}
  END {print \"wp-login: \" login+0; print \"xmlrpc: \" xmlrpc+0; print \"wp-cron: \" cron+0; print \"admin-ajax: \" ajax+0; print \"wp-json: \" json+0}
"'
```

Combine results.

### BSP per Endpoint (full week)

Sum field 8 (upstream response time) per endpoint to get processing cost:

```bash
ssh {host} 'DATE_FILTER_PATTERN=$(for I in $(seq 0 6); do date -d "$I days ago" +"%d/%b/%Y"; done | tr "\n" "|" | sed "s/|$//") && zcat -f {log_base}*.access.log* 2>/dev/null | grep -v "\\-secure" | LC_ALL=C grep -E "$DATE_FILTER_PATTERN" | awk -F"|" "
  \$10 ~ /wp-login/ {login+=\$8}
  \$10 ~ /xmlrpc/ {xmlrpc+=\$8}
  \$10 ~ /wp-cron/ {cron+=\$8}
  \$10 ~ /admin-ajax/ {ajax+=\$8}
  \$10 ~ /wp-json/ {json+=\$8}
  {total+=\$8}
  END {
    print \"TOTAL BSP: \" total+0 \"s\";
    print \"wp-login BSP: \" login+0 \"s (\" (total>0 ? login/total*100 : 0) \"%)\";
    print \"xmlrpc BSP: \" xmlrpc+0 \"s (\" (total>0 ? xmlrpc/total*100 : 0) \"%)\";
    print \"wp-cron BSP: \" cron+0 \"s (\" (total>0 ? cron/total*100 : 0) \"%)\";
    print \"admin-ajax BSP: \" ajax+0 \"s (\" (total>0 ? ajax/total*100 : 0) \"%)\";
    print \"wp-json BSP: \" json+0 \"s (\" (total>0 ? json/total*100 : 0) \"%)\"
  }
"'
```

**Why this matters:** An endpoint with low request count but high BSP is consuming disproportionate PHP worker time. For example, 962 wp-cron requests at 111-119 seconds each = ~107,000 seconds of BSP — far more costly than 691,000 wp-login requests at 0.01 seconds each (~6,900 seconds).

### BSP per Endpoint per Install (reseller pods)

For the dominant installs on each endpoint, break down BSP:

```bash
ssh {host} 'DATE_FILTER_PATTERN=$(for I in $(seq 0 6); do date -d "$I days ago" +"%d/%b/%Y"; done | tr "\n" "|" | sed "s/|$//") && zcat -f {log_base}*.access.log* 2>/dev/null | grep -v "\\-secure" | LC_ALL=C grep -E "$DATE_FILTER_PATTERN" | awk -F"|" "\$10 ~ /admin-ajax/ {bsp[\$4]+=\$8} END {for (d in bsp) printf \"%.1fs %s\\n\", bsp[d], d}" | sort -rn | head -15'
```

Repeat substituting `admin-ajax` with `wp-cron`, `wp-login`, etc. for each endpoint.

---

## Phase 2: wp-login.php — Brute Force Detection

### Request Volume by Method

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$10 ~ /wp-login/" | awk -F"|" "{split(\$10,m,\" \"); print m[1]}" | sort | uniq -c | sort -rn'
```

**Key threshold:** POST requests >10,000/week = brute force in progress.

### wp-login by Install (reseller pods)

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$10 ~ /wp-login/ {print \$4}" | sort | uniq -c | sort -rn | head -20'
```

If installs are uniformly targeted, this confirms automated botnet rather than targeted attack.

### Top Attacking IPs

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$10 ~ /POST.*wp-login/ {print \$3}" | sort | uniq -c | sort -rn | head -20'
```

### Cross-Pod IP Comparison

If analyzing multiple pods for the same customer, check if the same IPs appear on both pods. Shared attacking IPs = coordinated botnet.

### wp-login User Agents (botnet fingerprinting)

```bash
ssh {host} 'grep "wp-login" {log_base}*.apachestyle.log 2>/dev/null | grep "POST" | awk -F"\"" "{print \$(NF-1)}" | sort | uniq -c | sort -rn | head -15'
```

**Botnet signature:** Rotated Safari 14.x/15.x variants, MSIE 7.0, and Chrome 119-121 appearing in roughly equal quantities = credential-stuffing botnet.

### wp-login Status Codes

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$10 ~ /POST.*wp-login/ {print \$5}" | sort | uniq -c | sort -rn'
```

- 200 = login page loaded (failed attempt)
- 302 = successful login redirect
- 429 = rate limited by WP Engine

---

## Phase 3: xmlrpc.php — XMLRPC Abuse

### XMLRPC Volume

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$10 ~ /xmlrpc/ {print \$3}" | sort | uniq -c | sort -rn | head -15'
```

### XMLRPC by Install

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$10 ~ /xmlrpc/ {print \$4}" | sort | uniq -c | sort -rn | head -15'
```

### XMLRPC → 502 Correlation

Check if XMLRPC abuse is causing PHP-FPM crashes:

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$10 ~ /xmlrpc/ && \$5 == 502"  | wc -l'
```

If XMLRPC → 502 correlation is high, this is a critical finding (as seen on pod 213646 where 162/163 502s on delventhal-law.com were XMLRPC).

---

## Phase 4: wp-cron.php — Cron Health

### wp-cron by Install

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$10 ~ /wp-cron/ {print \$4}" | sort | uniq -c | sort -rn | head -15'
```

**Thresholds:**
- <1,000/week: Normal
- 1,000-5,000/week: Elevated — check for Action Scheduler or backup plugins
- 5,000-10,000/week: High — audit plugin cron schedules
- >10,000/week: Excessive — single install is cron-flooding (niftymarketing.com hit 13,682 on a real pod)

### wp-cron Execution Times

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$10 ~ /wp-cron/ && \$9+0 > 10 {printf \"%.3fs %s\\n\", \$9, \$4}" | sort -rn | head -15'
```

**Critical threshold:** wp-cron >60 seconds = exceeding PHP execution limit. wp-cron at 111-119 seconds (as seen on williamsacct.com) = severe resource drain.

### Action Scheduler Detection

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$10 ~ /as_async_request_queue_runner/ {print \$4}" | sort | uniq -c | sort -rn'
```

---

## Phase 5: admin-ajax.php — Ajax Floods

### admin-ajax by Install

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$10 ~ /admin-ajax/ {print \$4}" | sort | uniq -c | sort -rn | head -15'
```

### admin-ajax Action Breakdown

If one install dominates, drill into what actions it's calling:

```bash
ssh {host} 'grep "admin-ajax" {log_base}*.apachestyle.log 2>/dev/null | grep "{dominant_install}" | awk "{print \$7}" | grep -oP "action=\K[^& ]+" | sort | uniq -c | sort -rn | head -15'
```

Or from pipe-delimited logs (URL parameters):

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$10 ~ /admin-ajax/ && \$4 ~ /{dominant_install}/ {print \$10}" | grep -oP "action=\K[^& ]+" | sort | uniq -c | sort -rn | head -15'
```

**Known culprits:**
- `updraftplus_*` → UpdraftPlus backup polling
- `backupbuddy_*` → BackupBuddy status polling
- `ai1wm_export` → All-in-One WP Migration
- `heartbeat` → WordPress Heartbeat API (normal if <100/day)
- `as_async_request_queue_runner` → WooCommerce Action Scheduler

### Backup Plugin Conflict Detection

If multiple backup plugins are detected on a single install (UpdraftPlus + BackupBuddy + AOWM), flag as a critical finding. This was the root cause of livescounseling.com consuming 157K uncached hits on pod 212147.

---

## Phase 6: wp-json (REST API)

### REST API Volume

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$10 ~ /wp-json/ {print \$10}" | sed "s/ HTTP.*//" | sort | uniq -c | sort -rn | head -15'
```

### User Enumeration Detection

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$10 ~ /wp\\/v2\\/users/ {print \$3}" | sort | uniq -c | sort -rn | head -10'
```

User enumeration via `?rest_route=/wp/v2/users` or `/wp-json/wp/v2/users` is a security scan indicator.

---

## Output Format

Save to `~/Documents/Sentry Reports/{pod-id}/pod-{pod-id}-endpoints-evidence.md`.

```markdown
# WordPress Endpoint Evidence: Pod {pod-id}

**Analysis Period:** {date range}

## Endpoint Summary
| Endpoint | Weekly Requests | BSP (seconds) | % of Total BSP | Assessment |
|----------|----------------|---------------|----------------|------------|
| wp-login.php | X (Y POST) | X | X% | {Healthy/Brute Force/Severe} |
| xmlrpc.php | X | X | X% | {Healthy/Abuse/Severe} |
| wp-cron.php | X | X | X% | {Healthy/Elevated/Excessive} |
| admin-ajax.php | X | X | X% | {Healthy/Elevated/Flooding} |
| wp-json | X | X | X% | {Healthy/Enumeration} |

## wp-login Analysis
### Volume by Method
{POST vs GET counts}

### By Install
{ranked list}

### Top Attacking IPs
{ranked list — if brute force detected}

### Botnet Fingerprint
{user agent rotation pattern — if botnet detected}

## XMLRPC Analysis
### Volume by IP
{ranked list}

### XMLRPC → 502 Correlation
{count and affected installs}

## wp-cron Analysis
### By Install
{ranked list with thresholds}

### Slow Cron Executions
{any >10 second wp-cron requests}

## admin-ajax Analysis
### By Install
{ranked list}

### Action Breakdown (if flood detected)
{action names with counts}

## REST API Analysis
### Top Endpoints
{ranked list}

### User Enumeration
{IPs and count — if detected}
```

---

## Rules

- **ALWAYS filter by date** — Every command MUST include `LC_ALL=C grep -E "$DATE_FILTER_PATTERN"` after reading log lines. Generate `DATE_FILTER_PATTERN` at the start of each SSH session. This prevents ghost install contamination from stale logs left by removed installs.
- **wp-login POST = login attempt, GET = page load** — only POSTs indicate brute force
- **XMLRPC abuse often causes 502s, not 504s** — PHP-FPM crashes (instant, not timeout)
- **wp-cron >60s = PHP timeout territory** — always flag
- **Multiple backup plugins on one install = critical finding**
- **Uniform install targeting = automated botnet** — if all installs get similar wp-login counts
- **WP Engine Alternate Cron**: Some installs use `?doing_wp_cron=` in GET requests — this is WP Engine's alternate cron mechanism, NOT an attack
- **ALWAYS exclude `-secure` logs** — use `grep -q "\\-secure" && continue` in for loops and `grep -v "\\-secure"` on file lists. The `-secure` suffix is the outer SSL nginx layer; including it double-counts every request.
- **Never reference CPU/memory** — utility server metrics
- **Never use `sudo`**
