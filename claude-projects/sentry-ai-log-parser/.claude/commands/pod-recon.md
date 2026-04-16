# Pod Reconnaissance — Server Discovery & Log Enumeration

Use when connecting to a pod for the first time — discovers server type, install count, log formats, HA cluster detection, and WordPress versions. This is the foundation skill that other analysis skills depend on. For a combined recon + full data collection in one pass, use `/scout` instead.

## Required Input

**Pod number** — provided by the user (e.g., "213646", "96143", "217862")

If the user does not provide a pod number, ask for it. No other input is needed.

## Output

Create the directory and save structured metadata:
```bash
mkdir -p ~/Documents/"Sentry Reports"/{pod-id}/
```

Save results to `~/Documents/Sentry Reports/{pod-id}/pod-metadata.json` AND print a human-readable summary to the conversation.

---

## Phase 1: SSH Connection

### Connection Strategy

Try connections in this order until one succeeds:

1. **Standard pod (bastion proxy):**
   ```bash
   ssh pod-{pod-id}.wpengine.com "hostname && echo CONNECTION_OK"
   ```

2. **Kubernetes utility pod (if standard fails):**
   ```bash
   # Discover the utility hostname
   kubectl get pods -l app=utility,pod-id={pod-id} -o name 2>/dev/null
   ```

3. **Direct utility hostname (if user provides it):**
   ```bash
   ssh -o StrictHostKeyChecking=accept-new {utility-hostname} "hostname && echo CONNECTION_OK"
   ```

If all connection methods fail, report the failure and ask the user for the correct hostname. Do NOT proceed without a working SSH connection.

---

## Phase 2: Server Type Detection

Detect whether this is a **standard pod** or an **HA (High Availability) cluster**.

```bash
# Check for HA cluster synced log path
ssh {host} 'if [ -d /var/log/synced/nginx ]; then echo "HA_CLUSTER"; else echo "STANDARD_POD"; fi'
```

Set the log base path:
- **Standard:** `/var/log/nginx/`
- **HA Cluster:** `/var/log/synced/nginx/`

### HA Cluster: Detect Web Nodes

If HA cluster, identify web node IDs from log filenames:
```bash
ssh {host} 'ls /var/log/synced/nginx/*.access.log 2>/dev/null | head -5'
```

HA logs include a web-node-ID field that shifts all pipe-delimited field positions by +1. Record this for downstream skills.

---

## Phase 3: Install Discovery & Ghost Install Detection

Enumerate all installs by extracting unique install names from access log filenames.

```bash
# Standard pod
ssh {host} 'ls /var/log/nginx/*.access.log 2>/dev/null | sed "s|.*/||;s|\.access\.log||" | grep -v "\\-secure$" | sort -u'

# HA cluster
ssh {host} 'ls /var/log/synced/nginx/*.access.log 2>/dev/null | sed "s|.*/||;s|\.access\.log||" | grep -v "\\-secure$" | sort -u'
```

**Important:** Filter out `-secure` suffixed logs — these are the outer SSL nginx layer duplicates. The non-secure logs are the inner proxy layer and are the primary analysis target.

Count total installs:
```bash
ssh {host} 'ls {log_base}/*.access.log 2>/dev/null | sed "s|.*/||;s|\.access\.log||" | grep -v "\\-secure$" | sort -u | wc -l'
```

### Ghost Install Detection (CRITICAL)

**WP Engine does not clean up log files when installs are removed or migrated off a pod.** Stale log files from removed installs can persist for months or years with rotated logs (.log.1, .log.2.gz, etc.) still present. Including these in analysis contaminates results with data from a completely different time period.

Validate every install by checking if its current `.access.log` has recent data:

```bash
ssh {host} 'TODAY=$(date +"%d/%b/%Y"); YESTERDAY=$(date -d "1 day ago" +"%d/%b/%Y"); for f in {log_base}*.access.log; do name=$(basename "$f" .access.log); echo "$f" | grep -q "\\-secure" && continue; if [ ! -s "$f" ]; then echo "GHOST $name (empty current log)"; elif ! head -1 "$f" | grep -qE "$TODAY|$YESTERDAY"; then latest=$(tail -1 "$f" 2>/dev/null | cut -d"|" -f1 | grep -oP "\d+/\w+/\d+" 2>/dev/null); echo "GHOST $name (latest: $latest)"; else echo "ACTIVE $name"; fi; done'
```

Also check for log files that have NO current `.access.log` but DO have rotated logs:

```bash
ssh {host} 'for f in {log_base}*.access.log.1; do name=$(basename "$f" .access.log.1); echo "$f" | grep -q "\\-secure" && continue; [ ! -f "{log_base}${name}.access.log" ] && echo "ORPHAN $name (rotated logs only, no current log)"; done'
```

Record ghost and orphan installs separately in metadata. **Downstream skills must NEVER include ghost/orphan install logs in analysis.**

---

## Phase 4: Log Coverage Enumeration

For each log type, check available rotations:

### Nginx Access Logs
```bash
# Current + rotated (7 days typical)
ssh {host} 'for f in {log_base}/{first_install}.access.log{,.1,.2.gz,.3.gz,.4.gz,.5.gz,.6.gz,.7.gz}; do [ -f "$f" ] && echo "EXISTS: $f" || echo "MISSING: $f"; done'
```

### Nginx Apachestyle Logs (User-Agent data)
```bash
ssh {host} 'ls {log_base}/{first_install}.apachestyle.log* 2>/dev/null | head -10'
```

### PHP-FPM Error Logs
```bash
ssh {host} 'ls /nas/log/fpm/*.error.log 2>/dev/null | head -10'
```

### Apache Access Logs (Dynamic/PHP Requests Only)
```bash
ssh {host} 'ls /var/log/apache2/*.access.log* 2>/dev/null | head -10'
```

Apache logs capture ONLY requests that passed through Varnish cache misses to Apache for PHP generation. The line count in apache logs = exact dynamic request volume. This is the key metric for capacity assessment.

### MySQL Slow Query Logs
```bash
ssh {host} 'ls /var/log/mysql/mysql-slow.log* 2>/dev/null'
```

### MySQL Killed-by-WPE Logs (Governor kills)
```bash
ssh {host} 'ls /var/log/mysql/killed-by-wpe.log* 2>/dev/null'
```

---

## Phase 5: Log Format Verification

Read the first line of a pipe-delimited access log to confirm field positions:

```bash
ssh {host} 'head -1 {log_base}/{first_install}.access.log'
```

**Standard pod fields (pipe-delimited):**
```
timestamp|v1|IP|domain|STATUS|bytes|upstream|time1|exec_time|REQUEST|cached|gzip|trace_id
Field:  1    2  3  4       5     6      7       8      9        10      11    12    13
```

**HA cluster fields (pipe-delimited — extra web-node-ID field):**
```
timestamp|v1|web-node-ID|IP|domain|STATUS|bytes|upstream|time1|exec_time|REQUEST|cached|gzip|trace_id
Field:  1    2      3       4   5      6     7      8       9      10       11      12    13    14
```

Record the field offset (0 for standard, +1 for HA) — all downstream skills need this.

---

## Phase 6: Network Type Detection

Determine whether each install is on the **Advanced Network**, **Legacy Network**, or **Global Edge Security (GES)** by resolving the primary domain's DNS.

```bash
# Get the primary domain for each active install via wp-cli
ssh {host} 'for install in {active_installs}; do
  domain=$(cd /nas/wp/www/sites/$install 2>/dev/null && wp option get siteurl 2>/dev/null | sed "s|https\?://||;s|/.*||")
  if [ -n "$domain" ]; then
    echo "$install: $domain"
  fi
done'
```

Then resolve DNS for each domain to classify the network:

```bash
# Check DNS records for network classification
for domain in {domains}; do
  cname=$(dig +short CNAME "$domain" 2>/dev/null)
  a_records=$(dig +short A "$domain" 2>/dev/null)
  echo "$domain|CNAME:$cname|A:$a_records"
done
```

**Classification logic:**

| DNS Result | Network Type |
|------------|-------------|
| A records `141.193.213.10` and `141.193.213.11` | Advanced Network |
| CNAME to `wp.wpenginepowered.com` | Advanced Network |
| CNAME to `*.wpeproxy.com` | Global Edge Security |
| A record or CNAME to `{install}.wpengine.com` | **Legacy Network** (flag for upgrade) |

**If Legacy Network is detected**, flag it prominently in the recon summary and metadata. Include in all downstream reports as a recommendation:

> **Network Alert:** {install} is on the Legacy Network, which is being retired. Recommend upgrading to the Advanced Network (free) for Cloudflare CDN, HTTP/3, tiered caching, automatic image optimization, and enhanced DDoS protection. Upgrade via User Portal → Domains → Switch Network.

Record the network type per-install in `pod-metadata.json` under a `"network"` key:

```json
{
  "network": {
    "oiaglobal": "advanced",
    "oiaglobaldev": "legacy"
  },
  "legacy_network_installs": ["oiaglobaldev"]
}
```

---

## Phase 7: Quick Traffic Snapshot

Get a fast overview of current traffic volume:

```bash
# Total lines in current access log (one representative install, or all installs for reseller)
ssh {host} 'wc -l {log_base}/*.access.log 2>/dev/null | tail -1'

# Date range covered by current logs
ssh {host} 'head -1 {log_base}/{first_install}.access.log | cut -d"|" -f1'
ssh {host} 'tail -1 {log_base}/{first_install}.access.log | cut -d"|" -f1'
```

For reseller pods (many installs), also get a quick request count per install:
```bash
ssh {host} 'wc -l {log_base}/*.access.log 2>/dev/null | grep -v "\\-secure" | grep -v "total" | sort -rn | head -20'
```

---

## Output Format

### JSON Metadata (`pod-metadata.json`)

```json
{
  "pod_id": "213646",
  "server_type": "standard|ha_cluster",
  "ssh_host": "pod-213646.wpengine.com",
  "log_base_path": "/var/log/nginx/",
  "field_offset": 0,
  "status_field": 5,
  "exec_time_field": 9,
  "request_field": 10,
  "install_count": 95,
  "installs": ["install1", "install2", "..."],
  "ghost_installs": ["removed_install1", "removed_install2"],
  "orphan_installs": ["orphan1"],
  "log_coverage": {
    "access_log_rotations": 8,
    "apachestyle_available": true,
    "apache_access_available": true,
    "fpm_error_available": true,
    "mysql_slow_available": true,
    "mysql_killed_available": false
  },
  "date_range": {
    "start": "23/Mar/2026",
    "end": "30/Mar/2026"
  },
  "analysis_date": "2026-03-30",
  "date_filter_pattern": "30/Mar/2026|29/Mar/2026|28/Mar/2026|27/Mar/2026|26/Mar/2026|25/Mar/2026|24/Mar/2026",
  "network": {
    "install1": "advanced",
    "install2": "legacy"
  },
  "legacy_network_installs": ["install2"],
  "recon_timestamp": "2026-03-30T14:22:00Z"
}
```

**`install_count`** = active installs only (excludes ghost/orphan).
**`ghost_installs`** = installs with empty or stale current `.access.log` (removed/migrated).
**`orphan_installs`** = installs with rotated logs but no current `.access.log` at all.
**`date_filter_pattern`** = pipe-separated date strings for the 7-day analysis window. All downstream skills MUST use this to filter log lines.

Generate the date filter pattern during recon:
```bash
DATE_FILTER_PATTERN=$(for I in $(seq 0 6); do date -d "$I days ago" +"%d/%b/%Y"; done | tr "\n" "|" | sed "s/|$//")
```

### Conversation Summary

Print a clean summary like:

```
## Pod {pod-id} Reconnaissance Complete

| Property | Value |
|----------|-------|
| Server Type | Standard Pod |
| SSH Host | pod-213646.wpengine.com |
| Log Path | /var/log/nginx/ |
| Active Installs | 95 |
| Ghost/Orphan Installs | 5 (excluded from analysis) |
| Log Coverage | 8 rotations (7 days) |
| Date Range | Mar 23–30, 2026 |
| Apachestyle Logs | ✓ Available |
| Apache Access Logs | ✓ Available |
| PHP-FPM Logs | ✓ Available |
| MySQL Slow Logs | ✓ Available |
| Network Type | ✓ Advanced Network (or ⚠️ Legacy — upgrade recommended) |

**Ready for analysis.** Run `/error-analysis`, `/traffic-profile`, `/mysql-analysis`, or `/wp-endpoints` next.
```

---

## Rules

- **Never reference CPU, memory, or disk I/O** — utility server metrics, not production
- **Never use `sudo`** — it fails silently on WP Engine
- **Always filter out `-secure` log suffixes** when counting installs (dual-layer nginx)
- **Always detect ghost installs** — WP Engine does not clean up log files when installs are removed. Stale logs from months/years ago will contaminate every downstream analysis. This is a CRITICAL validation step.
- **Always generate and store `date_filter_pattern`** — downstream skills depend on this to filter log lines to the 7-day analysis window
- **Only count active installs in `install_count`** — ghost and orphan installs are tracked separately
- **Store metadata for downstream skills** — other skills will read `pod-metadata.json` to avoid re-discovering the environment
- **Always check network type** — Legacy Network sites must be flagged for upgrade to Advanced Network (free). This is a quick win that adds CDN, HTTP/3, tiered caching, image optimization, and enhanced DDoS protection at no cost.
- **If SSH fails**, do not proceed with assumptions. Report the failure clearly.
