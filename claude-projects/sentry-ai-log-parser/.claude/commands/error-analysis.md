# Error Analysis — Full-Week 504/502/503/499/429 Analysis

Use when you need a full-week error breakdown across all HTTP error types (504/502/503/499/429) with per-install attribution. Essential for reseller or multi-install pods where you need to identify which install is generating which errors. For single-install 504-only investigations, `/504-errors` or `/504-triage` may be faster.

## Required Input

**Pod number** — provided by the user (e.g., "213646")

Optional: specific error code focus (e.g., "just 504s"), specific install name, or date range.

## Pre-Flight: Load Pod Metadata

Check for existing reconnaissance data:
```bash
cat ~/Documents/"Sentry Reports"/{pod-id}/pod-metadata.json 2>/dev/null
```

If metadata exists, use it for `ssh_host`, `log_base_path`, `field_offset`, `status_field`, `exec_time_field`, `request_field`, and `installs`.

If metadata does NOT exist, run `/pod-recon` first or ask the user to provide the SSH host.

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

**Example:**
```bash
# WRONG — includes stale data from ghost installs
for f in *.access.log{,.1}; do cat "$f"; done | awk -F"|" '$5 == 502'

# CORRECT — filtered to 7-day window
for f in *.access.log{,.1}; do cat "$f"; done | LC_ALL=C grep -E "$DATE_FILTER_PATTERN" | awk -F"|" '$5 == 502'
```

### Exclude Ghost Installs

If `pod-metadata.json` lists `ghost_installs` or `orphan_installs`, skip those install log files entirely. When iterating by filename, check against the ghost list.

---

## Phase 1: Error Volume — Full Week

Count every error type across ALL rotated logs (`.log` through `.log.7.gz`).

### Total Error Counts

```bash
# Standard pod (field_offset=0, status=field 5)
# IMPORTANT: Always exclude -secure logs AND filter by date to avoid ghost install contamination
ssh {host} 'DATE_FILTER_PATTERN=$(for I in $(seq 0 6); do date -d "$I days ago" +"%d/%b/%Y"; done | tr "\n" "|" | sed "s/|$//") && for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | LC_ALL=C grep -E "$DATE_FILTER_PATTERN" | awk -F"|" "\$5 ~ /^(499|500|502|503|504|429)$/ {print \$5}" | sort | uniq -c | sort -rn'

# Include gzipped rotations (exclude -secure via grep -v on filenames)
ssh {host} 'DATE_FILTER_PATTERN=$(for I in $(seq 0 6); do date -d "$I days ago" +"%d/%b/%Y"; done | tr "\n" "|" | sed "s/|$//") && for f in $(ls {log_base}*.access.log.{2,3,4,5,6,7}.gz 2>/dev/null | grep -v "\\-secure"); do zcat "$f" 2>/dev/null; done | LC_ALL=C grep -E "$DATE_FILTER_PATTERN" | awk -F"|" "\$5 ~ /^(499|500|502|503|504|429)$/ {print \$5}" | sort | uniq -c | sort -rn'
```

**HA Cluster adjustment:** If `field_offset=1`, status is field 6:
```bash
awk -F"|" '$6 ~ /^(499|500|502|503|504|429)$/'
```

### Errors by Day

```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$5 == 504 {split(\$1,d,\"/\"); print d[1]\"/\"d[2]\"/\"d[3]}" | sort | uniq -c | sort -k2'
```

Repeat for each error code (502, 503, 499, 429).

For gzipped files:
```bash
ssh {host} 'for f in $(ls {log_base}*.access.log.{2,3,4,5,6,7}.gz 2>/dev/null | grep -v "\\-secure"); do zcat "$f" 2>/dev/null; done | awk -F"|" "\$5 == 504 {split(\$1,d,\"/\"); print d[1]\"/\"d[2]\"/\"d[3]}" | sort | uniq -c | sort -k2'
```

---

## Phase 2: Per-Install Attribution

**This is the critical differentiator for reseller pods.** Attribute errors to specific installs.

### 502 Errors by Install
```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$5 == 502 {print FILENAME}" | sed "s|.*/||;s|\.access\.log.*||" | sort | uniq -c | sort -rn | head -20'
```

**Better approach for rotated logs (domain field instead of filename):**
```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$5 == 502 {print \$4}" | sort | uniq -c | sort -rn | head -20'

ssh {host} 'for f in $(ls {log_base}*.access.log.{2,3,4,5,6,7}.gz 2>/dev/null | grep -v "\\-secure"); do zcat "$f" 2>/dev/null; done | awk -F"|" "\$5 == 502 {print \$4}" | sort | uniq -c | sort -rn | head -20'
```

Repeat for 504, 503, 499.

### Hourly Distribution for Spikes

When a single day shows a large error spike, drill into hourly distribution:
```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$5 == 502 && /24\\/Mar\\/2026/ {split(\$1,t,\":\"); print t[2]\":00\"}" | sort | uniq -c | sort -rn | head -10'
```

---

## Phase 3: Error URLs

Identify what endpoints are failing.

### Top 502 URLs
```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$5 == 502 {print \$10}" | sed "s/ HTTP.*//" | sort | uniq -c | sort -rn | head -20'
```

### Top 504 URLs
```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$5 == 504 {print \$10}" | sed "s/ HTTP.*//" | sort | uniq -c | sort -rn | head -20'
```

### Top 503 URLs
```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$5 == 503 {print \$10}" | sed "s/ HTTP.*//" | sort | uniq -c | sort -rn | head -20'
```

---

## Phase 4: Error Source IPs

For 503 errors (often vulnerability scanners) and 502 errors, identify source IPs:

### 503 Source IPs
```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$5 == 503 {print \$3}" | sort | uniq -c | sort -rn | head -15'
```

### 504 Source IPs (for single-install pods)
```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$5 == 504 {print \$3}" | sort | uniq -c | sort -rn | head -15'
```

### Cross-reference scanner IPs with User-Agent (apachestyle logs)
```bash
ssh {host} 'grep "93.123.109.246" {log_base}*.apachestyle.log 2>/dev/null | awk -F"\"" "{print \$(NF-1)}" | sort | uniq -c | sort -rn'
```

---

## Phase 5: Execution Time Analysis

### Slowest Requests (full week)
```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$9+0 > 30 {printf \"%.3fs %s %s\\n\", \$9, \$4, \$10}" | sort -rn | head -20'

ssh {host} 'zcat -f {log_base}*.access.log.{2,3,4,5,6,7}.gz 2>/dev/null | awk -F"|" "\$9+0 > 30 {printf \"%.3fs %s %s\\n\", \$9, \$4, \$10}" | sort -rn | head -20'
```

### Requests over 5 seconds (count)
```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$9+0 > 5" | wc -l'
```

### Requests over 10 seconds by install
```bash
ssh {host} 'for f in {log_base}*.access.log{,.1}; do echo "$f" | grep -q "\\-secure" && continue; cat "$f" 2>/dev/null; done | awk -F"|" "\$9+0 > 10 {print \$4}" | sort | uniq -c | sort -rn | head -15'
```

---

## Phase 6: PHP-FPM Error Summary

```bash
# Fatal errors
ssh {host} 'grep -c "PHP Fatal error" /nas/log/fpm/*.error.log 2>/dev/null'

# Warnings
ssh {host} 'grep -c "PHP Warning" /nas/log/fpm/*.error.log 2>/dev/null'

# Fatal errors by install
ssh {host} 'grep "PHP Fatal error" /nas/log/fpm/*.error.log 2>/dev/null | sed "s|.*/||;s|\.error\.log.*||" | sort | uniq -c | sort -rn | head -10'
```

---

## Error Code Reference

| Code | WP Engine Origin | Root Cause |
|------|-----------------|------------|
| **502** | PHP-FPM crash/unavailable | NGINX cannot reach PHP-FPM — process crashed (SIGSEGV, SIGTERM, SIGKILL), mod-sec killed it, Governor killed it, or memory limit exceeded |
| **503** | Queuing layer capacity | Platform protection — request queue is full, server at capacity |
| **504** | PHP execution timeout | PHP script exceeded 60-second limit (or 30s on some plans) |
| **499** | Client abandoned | Client closed connection before server responded — often email clients or impatient bots |
| **429** | Rate limiting | WP Engine platform rate limiting applied |

**CRITICAL:** Do NOT conflate 503 and 504. They have completely different root causes. 503 = capacity/queuing, 504 = code timeout.

---

## Output Format

Save evidence to `~/Documents/Sentry Reports/{pod-id}/pod-{pod-id}-error-evidence.md`.

Structure the output as:

```markdown
# Error Evidence: Pod {pod-id}

**Analysis Period:** {date range}

## Error Totals (Full Week)
| Code | Count | Description |
|------|-------|-------------|
| 502  | X     | PHP-FPM crash |
| 503  | X     | Queue capacity |
| 504  | X     | Gateway timeout |
| 499  | X     | Client abandoned |
| 429  | X     | Rate limited |

## Errors by Day
{table}

## Per-Install Attribution
### 502 Errors by Install
{ranked list}

### 504 Errors by Install
{ranked list}

## Error URLs
### Top 502 URLs
{ranked list}

### Top 504 URLs
{ranked list}

## Execution Times
### Slowest Requests
{ranked list}

### Requests >10s by Install
{ranked list}

## PHP-FPM Error Summary
{fatal + warning counts, by install}
```

---

## Rules

- **ALWAYS filter by date** — Every command MUST include `LC_ALL=C grep -E "$DATE_FILTER_PATTERN"` after reading log lines. Generate `DATE_FILTER_PATTERN` at the start of each SSH session. This prevents ghost install contamination from stale logs left by removed installs.
- **ALWAYS exclude `-secure` logs** — use `grep -q "\\-secure" && continue` in for loops and `grep -v "\\-secure"` on file lists. The `-secure` suffix is the outer SSL nginx layer; including it double-counts every request.
- **Always use full-week data** — include rotated `.gz` logs via `zcat -f`
- **Always attribute to installs** — use domain field ($4 standard, $5 HA) not filename
- **Combine current + rotated log results** — present unified totals
- **Never reference CPU/memory** — utility server metrics
- **Never use `sudo`** — fails silently
- **Never use `grep " 504 "` on pipe-delimited logs** — use `awk -F"|"` field matching
- **HA clusters shift field positions by +1** — check `pod-metadata.json` for `field_offset`
