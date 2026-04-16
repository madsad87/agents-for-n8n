# Scout — Full Data Collection for a Pod Investigation

Use when starting any pod investigation — this is the first data collection pass that combines `/pod-recon` environment discovery with all standard log parsing (traffic, errors, bots, slow requests, killed queries, cache rate). Output feeds downstream skills: `/504-triage`, `/bot-audit`, `/cache-audit`, `/killed-queries`, `/size`, `/pod-report`.

## Required Input

- **Pod number** (e.g., "228209")
- **Install name(s)** to focus on (e.g., "testwebsite773" or "sffilm2026")
- **Shared or dedicated** — determines whether `/neighbor-check` runs automatically

If the user provides a Zendesk ticket, extract: AM first name, account name, install names, business vertical, and stated concerns.

## Output

Save all raw data to `~/Documents/Sentry Reports/{pod-id}/pod-{id}-scout-data.md` and print a summary to the conversation.

---

## Phase 1: SSH Connection & Environment

Run in a single SSH session:

```bash
ssh -o StrictHostKeyChecking=accept-new pod-{pod-id}.wpengine.com "
  echo '=== HOSTNAME ===' && hostname &&
  echo '=== SERVER TYPE ===' && ([ -d /var/log/synced/nginx ] && echo 'HA_CLUSTER' || echo 'STANDARD_POD') &&
  echo '=== INSTALL COUNT ===' && ls /var/log/nginx/*.access.log 2>/dev/null | sed 's|.*/||;s|\.access\.log||' | grep -v secure | wc -l &&
  echo '=== WP VERSION ===' && cat /nas/content/live/{install}/wp-includes/version.php 2>/dev/null | grep 'wp_version ' &&
  echo '=== DNS ===' && host {domain} 2>/dev/null | head -3
"
```

## Phase 2: Parallel Data Collection

Run ALL of the following SSH commands in parallel (batch into 3-4 parallel calls max to avoid SSH connection limits):

### Batch 1: Traffic & Errors
```bash
# 7-day traffic volume
for f in /var/log/nginx/{install}.access.log*; do zcat -f "$f" 2>/dev/null; done | wc -l

# 7-day Apache (PHP) volume
for f in /var/log/apache2/{install}.access.log*; do zcat -f "$f" 2>/dev/null; done | wc -l

# Error counts (504, 502, 503, 429)
for f in /var/log/nginx/{install}.access.log*; do zcat -f "$f" 2>/dev/null; done | awk -F'|' '$5 == 504' | wc -l
# (repeat for 502, 503, 429)
```

### Batch 2: 504 URLs, Slow Requests, Worst Exec Times
```bash
# 504 by URL (top 30)
awk -F'|' '$5 == 504 {print $10}' | awk '{print $1, $2}' | sort | uniq -c | sort -rn | head -30

# Slow requests >10s by URL (top 25)
awk -F'|' '$9+0 > 10 {print $10}' | awk '{print $1, $2}' | sort | uniq -c | sort -rn | head -25

# Total slow count
awk -F'|' '$9+0 > 10' | wc -l

# Worst execution times (>30s, top 20)
awk -F'|' '$9+0 > 30 {printf "%.1fs  %s\n", $9, $10}' | sort -rn | head -20
```

### Batch 3: User Agents, WP Endpoints, Cache Rate
```bash
# User agents (top 25, from apachestyle logs)
awk -F'"' '{print $(NF-1)}' | sort | uniq -c | sort -rn | head -25

# WP endpoints
awk -F'|' '{print $10}' | grep -oE '(admin-ajax|wp-cron|wp-login|xmlrpc)' | sort | uniq -c | sort -rn

# Cache rate (yesterday, full day — .log.1)
echo 'Nginx:' && zcat -f /var/log/nginx/{install}.access.log.1 | wc -l
echo 'Apache:' && zcat -f /var/log/apache2/{install}.access.log.1 | wc -l

# Peak hourly PHP (Apache)
awk -F'[' '{print $2}' | awk -F':' '{print $1" "$2":00"}' | sort | uniq -c | sort -rn | head -10
```

### Batch 4: PHP-FPM, MySQL, Plugins
```bash
# Killed queries (today + yesterday)
grep -c 'KILLED QUERY' /nas/log/fpm/{install}.error.log
grep -c 'KILLED QUERY' /nas/log/fpm/{install}.error.log.1

# Killed query sources
grep 'KILLED QUERY' /nas/log/fpm/{install}.error.log | grep -oP 'generated in \K.*?\.php:\d+' | sort | uniq -c | sort -rn

# PHP Fatal + Warning counts
grep -c 'Fatal' /nas/log/fpm/{install}.error.log
grep -c 'Warning' /nas/log/fpm/{install}.error.log

# MySQL slow queries (total + by schema)
zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -c '# Time:'
zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep '^use ' | sort | uniq -c | sort -rn | head -20

# Plugin list
ls /nas/content/live/{install}/wp-content/plugins/

# Theme list
ls /nas/content/live/{install}/wp-content/themes/
```

## Phase 3: Conditional Checks

Based on what Phase 2 reveals, run these if triggered:

- **If shared server:** Run `/neighbor-check` commands (504s across all installs)
- **If WooCommerce detected in plugins:** Run `/woo-audit` commands (cart fragments, checkout traffic)
- **If killed queries > 0:** Run `/killed-queries` detail commands (source files, tables, query samples)
- **If 504 count > 100:** Run `/504-triage` classification

## Phase 4: Save & Summarize

Save all raw output to the scout data file. Print a conversation summary:

```
## Scout Complete: Pod {pod-id} — {install} ({domain})

| Metric | Value | Assessment |
|--------|-------|------------|
| 7-day nginx requests | X | |
| 7-day PHP requests | X | |
| Cache hit rate | X% | {Critical/Poor/Moderate/Good} |
| 504 errors | X | |
| 502 errors | X | |
| 503 errors | X | |
| 429 errors | X | |
| Killed queries (today) | X | |
| Slow requests (>10s) | X | |
| Active plugins | X | |
| Peak hourly PHP | X | |

**Bot traffic:** ~X% ({top bot} at X requests)
**Top 504 driver:** {URL or "scanner probes"}
**Killed query source:** {plugin/file or "none"}

Ready for: /504-triage, /bot-audit, /cache-audit, /size, /report-gen
```

## Critical Rules

- **ALWAYS use `awk -F'|'` for pipe-delimited logs** — never `grep " 504 "`
- **ALWAYS exclude `-secure` log variants** when counting installs
- **ALWAYS use `.log.1` (full day) for cache rate** — never partial-day `.log`
- **NEVER reference CPU/memory** — utility server metrics
- **NEVER use `sudo`** — fails silently on WP Engine
- **Batch SSH commands** to minimize round-trips — aim for 3-4 SSH calls total
- **Save raw output** — downstream skills read this file instead of re-running SSH
