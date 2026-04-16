# Traffic Profile — Volume, User-Agents, Uncached Hits & Anomaly Detection

Use when you need a comprehensive traffic breakdown — daily volume trends, user agent distribution, uncached request ratios, and anomaly detection (bot floods, brute force, AI crawlers). This is the standalone deep-dive traffic skill. For a quicker bot-vs-human split, use `/bot-audit`. For cache-specific analysis, use `/cache-audit`.

## Required Input

**Pod number** — provided by the user (e.g., "213646")

Optional: specific install name, date range.

## Pre-Flight: Load Pod Metadata

```bash
cat ~/Documents/"Sentry Reports"/{pod-id}/pod-metadata.json 2>/dev/null
```

Use `ssh_host`, `log_base_path`, `field_offset`, and `installs` from metadata. If missing, run `/pod-recon` first.

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

## Phase 1: Total Traffic Volume

### Full Week Request Count

```bash
# Current + uncompressed rotation
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; [ -f "$f" ] && cat "$f"; done | grep -v "\\-secure" | wc -l'

# Compressed rotations
ssh {host} 'for f in $(ls {log_base}*.access.log.{2,3,4,5,6,7}.gz 2>/dev/null | grep -v "\\-secure"); do zcat "$f" 2>/dev/null; done | wc -l'
```

Add both counts for full-week total. **Divide by 2** if you're counting both secure and non-secure logs — or better, filter to only non-secure logs (without `-secure` in filename).

### Traffic by Day

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "{split(\$1,d,\"/\"); print d[1]\"/\"d[2]\"/\"d[3]}" | grep -E "(Mar|Apr)/2026" | sort | uniq -c | sort -k2'
```

Repeat with `zcat -f` for compressed rotations. Combine results.

### Traffic by Install (reseller pods)

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "{print \$4}" | sort | uniq -c | sort -rn | head -30'
```

---

## Phase 1B: Dynamic (PHP) Traffic — Apache Logs

Apache access logs at `/var/log/apache2/` contain ONLY requests that went through to Apache/PHP (Varnish cache misses). This is the true measure of PHP worker demand.

### Dynamic Requests by Install (current rotation)

```bash
ssh {host} 'wc -l /var/log/apache2/*.access.log 2>/dev/null | grep -v total | sort -rn | head -20'
```

### Dynamic vs Total Ratio — Cache Hit Rate (CRITICAL: Use Rotated Logs)

**NEVER calculate cache hit rate from current (partial-day) `.access.log` files.** The current nginx and apache rotations cover different durations and are not time-aligned. Comparing them produces wildly inaccurate results (e.g., 86% when the real rate is 20%).

**Correct method:** Compare full-day rotated logs aligned by date.

```bash
# Step 1: Get apache rotation dates and counts
ssh {host} 'for rot in .1 .2 .3 .4 .5; do f=$(ls /var/log/apache2/*.access.log${rot}* 2>/dev/null | head -1); [ -z "$f" ] && continue; if echo "$f" | grep -q ".gz"; then date=$(zcat "$f" 2>/dev/null | head -1 | awk "{print \$4}" | cut -d"[" -f2 | cut -d":" -f1); count=$(zcat /var/log/apache2/*.access.log${rot}.gz 2>/dev/null | wc -l); else date=$(head -1 "$f" 2>/dev/null | awk "{print \$4}" | cut -d"[" -f2 | cut -d":" -f1); count=$(cat /var/log/apache2/*.access.log${rot} 2>/dev/null | wc -l); fi; echo "$date apache=$count"; done'
```

```bash
# Step 2: Compare against nginx daily counts from Phase 1 (date-filtered)
# For each date, cache hit rate = 1 - (apache_count / nginx_count)
```

Build a per-day comparison table:

```markdown
| Date | Nginx (all) | Apache (dynamic) | Cache Hit Rate |
|------|-------------|------------------|----------------|
| {date} | {nginx_count} | {apache_count} | {1 - apache/nginx} |
```

Average the per-day cache hit rates for the overall number.

**Interpretation:**
- **>70% cache hit rate** — healthy caching, most traffic served from Varnish
- **30–70%** — moderate, check for cache-busting patterns (query strings, cookies, logged-in users)
- **<30%** — low, likely driven by bot traffic, wp-login, wp-cron, or admin-heavy usage that bypasses cache. This is expected on servers with heavy brute force or excessive cron.

A low cache hit rate means more requests are consuming PHP workers than necessary — this is an optimization opportunity before recommending an upgrade. However, if the low rate is driven by bot/brute-force traffic, the fix is blocking that traffic (GES, Web Rules Engine), not cache optimization.

### Dynamic Requests by Day

```bash
ssh {host} 'cat /var/log/apache2/*.access.log 2>/dev/null | awk "{print \$4}" | cut -d"[" -f2 | cut -d":" -f1 | sort | uniq -c | sort -k2'
```

Check for rotated apache logs too:
```bash
ssh {host} 'ls /var/log/apache2/*.access.log.* 2>/dev/null | head -10'
```

---

## Phase 1C: BSP (Billable Server Processing) Analysis

BSP measures **cumulative server processing time** — the actual PHP worker cost of traffic. This is fundamentally different from request counts: 1,000 requests at 0.001s each cost far less than 10 requests at 30s each.

Field 8 in the pipe-delimited nginx access log contains the upstream response time. Summing this field gives total BSP in seconds.

### Total BSP (7-day, single install)

For a single-install pod, run from the install's working directory on the server:

```bash
ssh {host} 'cd /nas/content/live/{install} && DIR="$(basename $PWD)" && DATE_FILTER_PATTERN=$(for I in $(seq 0 6); do date -d "$I days ago" +"%d/%b/%Y"; done | tr "\n" "|" | sed "s/|$//") && zcat -f /var/log/nginx/$DIR.access.log* 2>/dev/null | LC_ALL=C grep -E "$DATE_FILTER_PATTERN" | LC_ALL=C cut -d"|" -f8 | awk "{total+=\$1}END{print total}" total=0'
```

### Total BSP (reseller pod, all installs)

For multi-install pods, sum field 8 across all access logs:

```bash
ssh {host} 'DATE_FILTER_PATTERN=$(for I in $(seq 0 6); do date -d "$I days ago" +"%d/%b/%Y"; done | tr "\n" "|" | sed "s/|$//") && zcat -f {log_base}*.access.log* 2>/dev/null | grep -v "\\-secure" | LC_ALL=C grep -E "$DATE_FILTER_PATTERN" | LC_ALL=C cut -d"|" -f8 | awk "{total+=\$1}END{print total}" total=0'
```

### BSP by Install (reseller pods)

```bash
ssh {host} 'DATE_FILTER_PATTERN=$(for I in $(seq 0 6); do date -d "$I days ago" +"%d/%b/%Y"; done | tr "\n" "|" | sed "s/|$//") && for f in {log_base}*.access.log; do name=$(basename "$f" .access.log); echo "$name" | grep -q "\\-secure" && continue; bsp=$(zcat -f ${f}* 2>/dev/null | LC_ALL=C grep -E "$DATE_FILTER_PATTERN" | LC_ALL=C cut -d"|" -f8 | awk "{total+=\$1}END{print total}" total=0); echo "$bsp $name"; done | sort -rn | head -20'
```

### BSP Breakdown by Request Type

This is the most valuable view — it shows WHERE the server is spending its processing time:

```bash
ssh {host} 'cd /nas/content/live/{install} && DIR="$(basename $PWD)" && DATE_FILTER_PATTERN=$(for I in $(seq 0 6); do date -d "$I days ago" +"%d/%b/%Y"; done | tr "\n" "|" | sed "s/|$//") && TMPACCESS=$(mktemp) && zcat -f /var/log/nginx/$DIR.access.log* 2>/dev/null | LC_ALL=C grep -E "$DATE_FILTER_PATTERN" > "$TMPACCESS" && echo "=====" && echo "TOTAL BSP:" && LC_ALL=C cut -d"|" -f8 "$TMPACCESS" | awk "{total+=\$1}END{print total}" total=0 && for search in xmlrpc admin-ajax wc-ajax wc-api wc-analytics get_refreshed_fragment wp-admin load-styles load-scripts wp-cron "wp/v2" "wc/v2" "wc/v3" wp-json /feed "?s=" /my-account /cart /wp-login /store /shop /product /event; do count=$(LC_ALL=C grep -F "$search" "$TMPACCESS" | cut -d"|" -f8 | awk "{sum+=\$1}END{print sum+0}"); echo "BSPs for Request: $search"; echo "$count"; done && rm -f "$TMPACCESS"'
```

### Interpreting BSP Results

- **Total BSP / 3600 = BSPH (Billable Server Processing Hours)** — the metric WP Engine uses for capacity planning
- **BSP / 7 = daily BSP** — compare against tier limits
- **BSP percentage per endpoint** tells you what's actually consuming the server:
  - High `admin-ajax` BSP → plugin overhead (backup polling, heartbeat abuse)
  - High `wp-admin` BSP → admin-heavy usage or admin-facing plugins
  - High `wp-cron` BSP → scheduled tasks consuming disproportionate processing time
  - High `/product` or `/shop` BSP → WooCommerce page generation cost
  - High `/feed` BSP → RSS feed generation (often crawled by bots)
  - High `wp-login` BSP → brute force attempts consuming PHP workers

### BSP by Day (trend analysis)

```bash
ssh {host} 'for f in {log_base}{install}.access.log{,.1}; do cat "$f" 2>/dev/null; done | awk -F"|" "{split(\$1,d,\"/\"); day=d[1]\"/\"d[2]\"/\"d[3]; bsp[day]+=\$8} END {for (d in bsp) print bsp[d], d}" | sort -k2'
```

---

## Phase 2: HTTP Status Code Distribution

### Full Week Status Codes

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "{print \$5}" | sort | uniq -c | sort -rn'

ssh {host} 'for f in $(ls {log_base}*.access.log.{2,3,4,5,6,7}.gz 2>/dev/null | grep -v "\\-secure"); do zcat "$f" 2>/dev/null; done | awk -F"|" "{print \$5}" | sort | uniq -c | sort -rn'
```

Combine results. Key ratios:
- **304 vs 200:** High 304 ratio indicates conditional GET traffic (email clients, bots with caching)
- **403:** Rate limiting or WAF blocks
- **429:** WP Engine rate limiting applied

---

## Phase 3: User Agent Analysis

User agents are only available in **apachestyle logs** (not pipe-delimited access logs).

### Top User Agents (current logs)

```bash
ssh {host} 'cat {log_base}*.apachestyle.log 2>/dev/null | grep -v "\\-secure" | awk -F"\"" "{print \$(NF-1)}" | sort | uniq -c | sort -rn | head -30'
```

**Do NOT run this against `.gz` files first** — apachestyle logs can be very large. Start with current rotation only. If the user needs full-week UA data, process one `.gz` file at a time.

### Categorize User Agents

Classify the top agents into these categories:

| Category | Examples | Concern Level |
|----------|----------|---------------|
| **Email clients** | MSOffice 16, Microsoft Office Outlook, iPhone Mobile, GoogleImageProxy | Check if email signature images are on the server |
| **Legitimate browsers** | Chrome/146, Safari/26, Firefox/140 | Normal |
| **Search engines** | Googlebot, bingbot | Normal |
| **AI crawlers** | ChatGPT-User, ClaudeBot, Amazonbot, meta-externalagent | Medium — review robots.txt |
| **SEO tools** | AhrefsBot, Barkrowler, SemrushBot | Medium — review robots.txt |
| **Suspicious bots** | Go-http-client, empty UA, Chrome/119-120 Linux, curl | High — probe for backdoors |
| **Monitoring** | UptimeRobot, Pingdom | Normal |
| **Migration tools** | SiteGround WordPress Migrator | High — active migration consuming resources |
| **WordPress internal** | WordPress/{version} | Normal |

### Suspicious UA Deep Dive

For suspicious agents, check what URLs they're hitting:

```bash
# Empty user agent URLs
ssh {host} 'grep "\" \"\"" {log_base}*.apachestyle.log 2>/dev/null | awk "{print \$7}" | sort | uniq -c | sort -rn | head -20'

# Go-http-client URLs
ssh {host} 'grep "Go-http-client" {log_base}*.apachestyle.log 2>/dev/null | awk "{print \$7}" | sort | uniq -c | sort -rn | head -20'
```

---

## Phase 4: Uncached vs Cached Traffic

The pipe-delimited log field 11 (standard) or 12 (HA) contains cache status.

```bash
# Uncached requests (HIT vs MISS)
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "{print \$11}" | sort | uniq -c | sort -rn'
```

### Uncached by Install (reseller pods)

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$11 !~ /HIT/ {print \$4}" | sort | uniq -c | sort -rn | head -20'
```

An install with disproportionately high uncached traffic is likely running admin operations, backup plugins, or receiving bot attacks.

---

## Phase 5: Anomaly Detection

### Weekday vs Weekend Pattern

```bash
# If weekend traffic is dramatically lower, it may indicate business-hour-driven traffic (email clients, office workers)
# If weekend traffic is similar, it's automated/bot traffic
```

Compare the daily traffic numbers from Phase 1. Flag:
- **>80% drop on weekends** → likely email signature images or business-app traffic
- **Flat 7-day pattern** → bot-heavy or automated traffic
- **Single-day spike** → incident, attack, or runaway process

### Request Rate Concentration

```bash
# Hourly distribution for peak day
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "/27\\/Mar\\/2026/ {split(\$1,t,\":\"); print t[2]\":00\"}" | sort | uniq -c | sort -rn | head -10'
```

### Top Requesting IPs

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "{print \$3}" | sort | uniq -c | sort -rn | head -20'
```

Cross-reference top IPs with their user agents:
```bash
ssh {host} 'grep "{top_ip}" {log_base}*.apachestyle.log 2>/dev/null | awk -F"\"" "{print \$(NF-1)}" | sort | uniq -c | sort -rn | head -5'
```

---

## Phase 6: Email Signature Detection

If MSOffice/Outlook user agents dominate, check for email signature image patterns:

```bash
# Look for repeated image requests to a static path
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$10 ~ /\\.(gif|png|jpg)/ && \$10 ~ /signature|brand|email/" | awk -F"|" "{print \$10}" | sed "s/ HTTP.*//" | sort | uniq -c | sort -rn | head -15'
```

If found, calculate what percentage of total traffic these represent. This pattern drove 88.6% of traffic on a real pod (217862/oiaglobal.com).

---

## Output Format

Save to `~/Documents/Sentry Reports/{pod-id}/pod-{pod-id}-traffic-evidence.md`.

```markdown
# Traffic Evidence: Pod {pod-id}

**Analysis Period:** {date range}
**Total Requests:** {full week count}

## Daily Traffic Volume
{table with day, count, day-of-week}

## HTTP Status Distribution
{table}

## Top User Agents
{ranked list with category classification}

## Uncached Traffic by Install
{ranked list — reseller pods only}

## Anomalies Detected
{description of patterns found}

## Top Requesting IPs
{ranked list with UA cross-reference}
```

---

## Rules

- **ALWAYS filter by date** — Every command MUST include `LC_ALL=C grep -E "$DATE_FILTER_PATTERN"` after reading log lines. Generate `DATE_FILTER_PATTERN` at the start of each SSH session. This prevents ghost install contamination from stale logs left by removed installs.
- **NEVER calculate cache hit rate from current `.access.log` files** — current rotations are partial-day and nginx/apache are not time-aligned. Always use full-day rotated logs (`.log.1` through `.log.5`) aligned by date. Comparing partial rotations produced an 86.5% cache hit rate on a server where the real rate was 20%.
- **Start UA analysis with current logs only** — apachestyle logs are huge, don't run against all `.gz` at once
- **Always cross-reference IPs with user agents** — volume alone doesn't prove malicious intent
- **ALWAYS exclude `-secure` logs** — use `grep -q "\\-secure" && continue` in for loops and `grep -v "\\-secure"` on file lists. The `-secure` suffix is the outer SSL nginx layer; including it double-counts every request.
- **For HA clusters, adjust field positions by +1**
- **Never reference CPU/memory** — utility server metrics
- **Never use `sudo`**
- **Weekend traffic patterns reveal traffic composition** — always calculate weekday vs weekend ratio
