# SSH Usage Guide for Claude Instances

This guide documents SSH patterns and commands used for WP Engine pod investigations. It complements the comprehensive investigation methodology in `CLAUDE.md` by providing a focused command reference.

---

## Table of Contents

1. [SSH Connection Patterns](#ssh-connection-patterns)
2. [Log File Locations](#log-file-locations)
3. [Common Analysis Commands](#common-analysis-commands)
4. [WP Engine-Specific Commands](#wp-engine-specific-commands)
5. [Troubleshooting](#troubleshooting)

---

## SSH Connection Patterns

### Connection Architecture

WP Engine pods use SSH connections to **utility servers** (not production web/database servers):
- Utility servers handle maintenance, logs, and administrative tasks
- Production servers handle live web traffic and database queries
- **IMPORTANT:** System resource metrics (CPU, memory, disk I/O) from utility servers are NOT relevant to production performance

### Connection Types

**1. Standard Pods (with SSH config + bastion proxy):**
```bash
# Connection format
ssh username_@pod-123456.wpengine.com

# Example
ssh jdoe_@pod-210345.wpengine.com

# Requires:
# - SSH config file (~/.ssh/config) with bastion proxy settings
# - VPN connection to WP Engine network
# - SSH key authentication
```

**2. Direct Kubernetes Utility Pods (no SSH config needed):**
```bash
# Connection format
ssh username_@pod-123456-utility-79d59564f-nt7n2

# Example
ssh jdoe_@pod-210345-utility-79d59564f-nt7n2

# Requires:
# - VPN connection to WP Engine network
# - SSH key authentication
# - No SSH config file needed
```

### Testing Connection

```bash
# Test basic connection
ssh username_@pod-123456.wpengine.com 'echo "Connection successful"'

# Test with command execution
ssh username_@pod-123456.wpengine.com 'hostname && uptime'

# Verify log access
ssh username_@pod-123456.wpengine.com 'ls -la /var/log/nginx/ | head -5'
```

---

## Log File Locations

### Nginx Access Logs

**Location:** `/var/log/nginx/{install}.access.log`

**Format:** Pipe-delimited WP Engine custom format
- Field 9: Request execution time (seconds)
- Field 4: Request URI
- Field 5: HTTP status code

**Rotation Pattern:**
- `.access.log` = Today (current)
- `.access.log.1` = Yesterday
- `.access.log.2.gz` = 2 days ago (compressed)
- `.access.log.3.gz` through `.access.log.7.gz` = 3-7 days ago

**Apache-Style Logs (with User-Agent):**
```bash
/var/log/nginx/{install}.apachestyle.log
/var/log/nginx/{install}.apachestyle.log.1
/var/log/nginx/{install}.apachestyle.log.2.gz
# ... through .apachestyle.log.7.gz
```

### PHP-FPM Error Logs

**Location:** `/nas/log/fpm/{install}.error.log`

**Content:**
- PHP errors, warnings, notices
- Fatal errors with stack traces
- Database connection errors
- MySQL query errors

**Rotation Pattern:**
- `.error.log` = Today
- `.error.log.1` = Yesterday
- `.error.log.2.gz` through `.error.log.7.gz` = 2-7 days ago

**❌ WRONG LOCATIONS (do not exist on WP Engine):**
- `/var/log/fpm/` (does not exist)
- `/var/log/php-fpm/` (does not exist)

### MySQL Slow Query Logs

**Location:** `/var/log/mysql/mysql-slow.log*`

**Content:**
- Queries exceeding slow query threshold
- Query execution time, lock time, rows examined
- Database and user information

**CRITICAL:** Always check MySQL slow query logs - never skip this step in performance investigations.

**Check if logs exist:**
```bash
# Count slow query log entries (current week)
zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -c "# Time:"

# If result is 0: No slow queries logged
# If result is >0: Slow queries exist and MUST be analyzed
```

**Log Entry Format:**
```
# Time: 2026-01-16T14:23:45.123456Z
# User@Host: wp_123456[wp_123456] @ localhost []
# Query_time: 5.480935  Lock_time: 0.000036  Rows_sent: 30  Rows_examined: 1318172
SET timestamp=1737035025;
SELECT * FROM wp_postmeta WHERE meta_key = 'some_key';
```

---

## Common Analysis Commands

### Default Analysis Timeframe

**ALWAYS analyze the most recent 7 days (current week) unless explicitly instructed otherwise.**

**Why 7 days:**
- Focus on current state and recent patterns
- Older logs may reflect different configurations or code versions
- Reduces analysis time and improves accuracy

### Nginx Access Log Analysis

**1. Count Total Requests (Current Week):**
```bash
# All rotated logs for current week
cat /var/log/nginx/install.access.log \
    /var/log/nginx/install.access.log.1 \
    /var/log/nginx/install.access.log.2.gz \
    /var/log/nginx/install.access.log.3.gz \
    /var/log/nginx/install.access.log.4.gz \
    /var/log/nginx/install.access.log.5.gz \
    /var/log/nginx/install.access.log.6.gz \
    /var/log/nginx/install.access.log.7.gz | wc -l
```

**2. Count 504 Gateway Timeout Errors:**
```bash
# Pipe-delimited format — MUST use awk field matching (field 5 = status code)
# NEVER use grep " 504 " on pipe-delimited logs — it will return 0 results
zcat -f $(find /var/log/nginx/ -name "install.access.log*" -mtime -7) 2>/dev/null | awk -F'|' '$5 == 504' | wc -l
```

**3. Count 502 Bad Gateway Errors:**
```bash
# Pipe-delimited format — MUST use awk field matching (field 5 = status code)
zcat -f $(find /var/log/nginx/ -name "install.access.log*" -mtime -7) 2>/dev/null | awk -F'|' '$5 == 502' | wc -l
```

**4. Find Slowest Requests (Execution Time > 30 seconds):**
```bash
# Field 9 = execution time in seconds
awk -F'|' '$9 > 30 {print $9, $4}' /var/log/nginx/install.access.log | sort -rn | head -20
```

**5. Top Requested URLs:**
```bash
# Field 4 = request URI
zcat -f /var/log/nginx/install.access.log* | \
  awk -F'|' '{print $4}' | sort | uniq -c | sort -rn | head -20
```

**6. Error Rate by Hour:**
```bash
# Errors (4xx and 5xx) by hour
zcat -f /var/log/nginx/install.access.log* | \
  awk -F'|' '$5 >= 400 {print $1}' | cut -d: -f1-2 | uniq -c
```

### User-Agent Analysis (Bot Detection)

**CRITICAL:** User-Agent data is in apache-style logs, NOT pipe-delimited logs.

**1. Extract and Count All User Agents (Current Week):**
```bash
# Apache-style logs have User-Agent in field 6 (quoted)
zgrep -h "" $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | \
  awk -F'"' '{print $6}' | sort | uniq -c | sort -rn > /tmp/user_agents.txt

# View results
head -50 /tmp/user_agents.txt
```

**2. Find Malicious Tool User-Agents (excluding internal IPs):**
```bash
zgrep -iE 'curl|wget|python-requests|scrapy|nikto|sqlmap|nmap' \
  $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | \
  grep -v "^10\." | awk '{print $1}' | sort | uniq -c | sort -rn | head -20
```

**3. Googlebot Traffic Volume:**
```bash
zgrep -i "googlebot" $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | wc -l
```

**4. Identify WordPress Vulnerability Scanners:**
```bash
zgrep -iE 'wp-login\.php|xmlrpc\.php|wp-admin' \
  $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | \
  awk -F'"' '{print $6}' | grep -iE 'curl|wget|python' | sort | uniq -c | sort -rn
```

**5. Extract IPs Using Specific User-Agent:**
```bash
# Example: Find all IPs using curl
zgrep -i "curl" $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | \
  awk '{print $1}' | sort | uniq -c | sort -rn
```

### PHP-FPM Error Log Analysis

**1. Count Total PHP Errors (Current Week):**
```bash
zcat -f /nas/log/fpm/install.error.log* | wc -l
```

**2. Count Fatal Errors:**
```bash
zgrep -i "fatal error" /nas/log/fpm/install.error.log* | wc -l
```

**3. Find Database Connection Errors:**
```bash
zgrep -iE 'database|mysql|connection|too many connections' /nas/log/fpm/install.error.log* | head -20
```

**4. Extract Unique Error Messages:**
```bash
# Get unique error types (excluding stack traces and file paths)
zcat -f /nas/log/fpm/install.error.log* | \
  grep -oP 'PHP (Fatal error|Warning|Notice): \K.*' | \
  sort | uniq -c | sort -rn | head -20
```

**5. Errors by File Path:**
```bash
# Find which files are generating the most errors
zcat -f /nas/log/fpm/install.error.log* | \
  grep -oP ' in /nas/content/live/\K[^:]+' | \
  sort | uniq -c | sort -rn | head -20
```

### MySQL Slow Query Log Analysis

**MODERN APPROACH: Use dbsummary RedShell Command**

```bash
# Navigate to install directory
cd /nas/content/live/install_name

# Run dbsummary to analyze slow query logs
dbsummary -s

# This provides:
# - Total slow queries
# - Top slow query patterns
# - Most expensive queries
# - Query execution time analysis
```

**MANUAL APPROACH: Direct Log Parsing**

**1. Count Total Slow Queries (Current Week):**
```bash
zcat -f /var/log/mysql/mysql-slow.log* | grep -c "# Time:"
```

**2. Extract Top 20 Slowest Queries:**
```bash
# Parse Query_time and sort by execution time
zcat -f /var/log/mysql/mysql-slow.log* | \
  grep "Query_time:" | \
  awk '{print $3}' | \
  sort -rn | \
  head -20
```

**3. Find Files Generating Most Slow Queries:**
```bash
# Extract file paths from slow query log context
sudo zcat -f /var/log/mysql/mysql-slow.log* | \
  grep -oP '(?<=in \[)\S*(?=\])' | \
  sort | uniq -c | sort -nr | head -20
```

**4. Identify Specific Slow Query Patterns:**
```bash
# Find queries examining excessive rows
zcat -f /var/log/mysql/mysql-slow.log* | \
  grep -A5 "Rows_examined: [0-9]\{7,\}" | \
  head -50
```

**5. Common Problem Query: wp_postmeta**
```bash
# Count slow queries against wp_postmeta table
zcat -f /var/log/mysql/mysql-slow.log* | \
  grep -i "wp_postmeta" | wc -l
```

### Traffic Pattern Analysis

**1. Requests Per Minute During Peak Period:**
```bash
# Count requests per minute for specific hour
zcat -f /var/log/nginx/install.access.log* | \
  awk -F'|' '$1 ~ /2026-01-16 14:/ {print substr($1,1,16)}' | \
  uniq -c | sort -rn
```

**2. Concurrent Request Estimation:**
```bash
# Requests with execution time > 1 second, grouped by minute
awk -F'|' '$9 > 1 {print substr($1,1,16), $9}' /var/log/nginx/install.access.log | \
  awk '{sum[$1]++; time[$1]+=$2} END {for(i in sum) print i, sum[i], time[i]}' | \
  sort -rn -k2
```

**3. Error Correlation with Traffic Spikes:**
```bash
# Show request volume and error rate by 5-minute intervals
zcat -f /var/log/nginx/install.access.log* | \
  awk -F'|' '{
    time = substr($1,1,15);
    total[time]++;
    if ($5 >= 400) errors[time]++;
  }
  END {
    for (t in total) {
      error_rate = (errors[t] / total[t]) * 100;
      printf "%s  Total: %d  Errors: %d  Rate: %.2f%%\n", t, total[t], errors[t], error_rate;
    }
  }' | sort
```

---

## WP Engine-Specific Commands

### Server Tier Verification (CRITICAL)

**ALWAYS verify server tier BEFORE making capacity assumptions.**

```bash
# Get current and historical server plan
wpeapi server-meta <pod-id> sales_offering historical=True

# Example
wpeapi server-meta 228552 sales_offering historical=True

# Output shows:
# - Current plan tier (P3, P6, etc.)
# - Historical upgrade dates
# - Plan change timeline
```

**Why This Matters:**
- Prevents human error when user provides incorrect plan information
- Shows complete upgrade history (crucial for timeline correlation)
- Determines accurate capacity thresholds

**❌ NEVER:**
- Trust user-provided server tier without verification
- Estimate or guess plan specifications
- Skip this step when investigating capacity issues

### PHP Worker Pool Configuration

**ALWAYS reference Sentry tool or constants.py for accurate worker counts.**

**Common WP Engine Plans (PHP-FPM Workers):**
- P1.5: 12 workers
- P3: 20 workers
- P6: 80 workers
- P8: 120 workers
- P12: 180 workers

**❌ NEVER estimate worker counts** - always verify from official source.

### Install Discovery

**1. List All Installs on Pod:**
```bash
# Find all install directories
ls -la /nas/content/live/

# Count total installs
ls /nas/content/live/ | wc -l
```

**2. Find Primary Install (Usually Largest):**
```bash
# Show installs by size
du -sh /nas/content/live/* | sort -rh | head -10
```

**3. Find Install Generating Most Traffic:**
```bash
# Count log file sizes
ls -lh /var/log/nginx/*.access.log | sort -k5 -rh | head -10
```

### WP Engine Environment Information

**1. Check PHP Version:**
```bash
php -v
```

**2. Check Available Disk Space:**
```bash
df -h /nas/content
```

**3. Check Current Server Time (for log timestamp correlation):**
```bash
date
# Note: WP Engine servers use UTC
```

---

## Troubleshooting

### SSH Connection Issues

**Problem: "Permission denied (publickey)"**

**Solution:**
```bash
# Verify SSH key exists
ls -la ~/.ssh/id_rsa

# Check key permissions (must be 600)
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub

# Verify SSH agent has key loaded
ssh-add -l

# Add key if not loaded
ssh-add ~/.ssh/id_rsa

# Test connection with verbose output
ssh -v username_@pod-123456.wpengine.com
```

**Problem: "Connection timed out"**

**Solution:**
- Verify VPN connection to WP Engine network
- Check if pod hostname is correct
- Try alternative connection method (utility pod vs standard pod)

**Problem: "Host key verification failed"**

**Solution:**
```bash
# Remove old host key
ssh-keygen -R pod-123456.wpengine.com

# Or remove old utility pod key
ssh-keygen -R pod-123456-utility-79d59564f-nt7n2

# Reconnect (will prompt to accept new host key)
ssh username_@pod-123456.wpengine.com
```

### Log Access Issues

**Problem: "No such file or directory" when accessing logs**

**Solution:**
```bash
# Verify install name is correct
ls /nas/content/live/

# Check if log files exist for this install
ls -la /var/log/nginx/ | grep install_name
ls -la /nas/log/fpm/ | grep install_name

# Common mistake: Using wrong install name (case-sensitive)
```

**Problem: "Permission denied" when reading logs**

**Solution:**
- Nginx access logs: Should be readable by all users
- PHP-FPM error logs: May require sudo (usually not on WP Engine)
- MySQL slow query logs: Often require sudo

```bash
# Try with sudo for MySQL logs
sudo zcat -f /var/log/mysql/mysql-slow.log* | head
```

**Problem: Compressed log files not decompressing**

**Solution:**
```bash
# Use zcat instead of cat for .gz files
zcat /var/log/nginx/install.access.log.2.gz | head

# Or use zgrep for pattern matching
zgrep "504" /var/log/nginx/install.access.log.2.gz

# For multiple files (compressed and uncompressed)
zcat -f /var/log/nginx/install.access.log* | grep "504"
```

### Command Execution Issues

**Problem: Awk command returns no results**

**Solution:**
```bash
# Verify field delimiter is correct
# Pipe-delimited format uses '|'
awk -F'|' '{print $1}' /var/log/nginx/install.access.log | head

# Apache-style format uses quotes for fields
awk -F'"' '{print $6}' /var/log/nginx/install.apachestyle.log | head

# Test field extraction with sample line
head -1 /var/log/nginx/install.access.log | awk -F'|' '{for(i=1;i<=NF;i++) print i": "$i}'
```

**Problem: Grep pattern not matching expected results**

**Solution:**
```bash
# Use case-insensitive search
grep -i "pattern" file.log

# Use extended regex
grep -E "pattern1|pattern2" file.log

# Show line numbers for debugging
grep -n "pattern" file.log

# Show context around match
grep -A5 -B5 "pattern" file.log
```

**Problem: Command times out on large log files**

**Solution:**
```bash
# Limit to recent logs only (current week)
zcat -f /var/log/nginx/install.access.log.{1..7}.gz | grep "pattern"

# Use head to limit output
zcat -f /var/log/nginx/install.access.log* | head -10000 | grep "pattern"

# Process in smaller chunks
for i in {1..7}; do
  echo "Processing log $i..."
  zgrep "pattern" /var/log/nginx/install.access.log.$i.gz | wc -l
done
```

### Data Verification

**Problem: Unexpected results from log analysis**

**Solution:**
```bash
# Verify log format by inspecting sample lines
head -5 /var/log/nginx/install.access.log
head -5 /var/log/nginx/install.apachestyle.log

# Check date range in logs
head -1 /var/log/nginx/install.access.log  # Oldest entry
tail -1 /var/log/nginx/install.access.log  # Newest entry

# Verify field positions
head -1 /var/log/nginx/install.access.log | awk -F'|' '{for(i=1;i<=NF;i++) print "Field "i": "$i}'

# Count 504s — ONLY use awk field matching on pipe-delimited logs
# NEVER use grep " 504 " — it matches space-delimited text, not pipe-delimited fields
awk -F'|' '$5 == 504' /var/log/nginx/install.access.log | wc -l
```

---

## Best Practices Summary

### Investigation Workflow

1. **ALWAYS verify server tier first** using `wpeapi server-meta <pod-id> sales_offering historical=True`
2. **ALWAYS check MySQL slow query logs** - never skip this step
3. **ALWAYS analyze User-Agent data** from apache-style logs for traffic classification
4. **ALWAYS use 7-day analysis window** unless explicitly instructed otherwise
5. **ALWAYS verify PHP worker counts** from Sentry tool or constants.py (never estimate)
6. **ALWAYS document commands used** in investigation reports for reproducibility

### What to Avoid

- ❌ Trusting user-provided server tier without verification
- ❌ Skipping MySQL slow query log analysis in performance investigations
- ❌ Analyzing utility server system metrics (CPU, memory, disk I/O) - not relevant to production
- ❌ Using pipe-delimited logs for User-Agent analysis (use apache-style logs)
- ❌ Estimating PHP worker pool sizes (always verify from official source)
- ❌ Including logs older than 7 days without explicit requirement

### Report Attribution

**ALWAYS use this attribution in WP Engine investigation reports:**

```markdown
**Report Prepared By:** Sentry Ai Analysis
**Analysis Date:** [Date]
**Data Source:** Server-side log analysis (pod-XXXXXX.wpengine.com)
**Log Period:** [Date range]
**Total Requests Analyzed:** [Count] requests
```

---

## Quick Reference Card

### Essential Commands

```bash
# Verify server tier (CRITICAL - always first)
wpeapi server-meta <pod-id> sales_offering historical=True

# Count 504 errors (current week — pipe-delimited, MUST use awk field matching)
zcat -f $(find /var/log/nginx/ -name "install.access.log*" -mtime -7) 2>/dev/null | awk -F'|' '$5 == 504' | wc -l

# Check MySQL slow queries (CRITICAL - never skip)
zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -c "# Time:"

# Extract User-Agent data (current week)
zgrep -h "" $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | \
  awk -F'"' '{print $6}' | sort | uniq -c | sort -rn > /tmp/user_agents.txt

# Find slow requests (>30 seconds)
awk -F'|' '$9 > 30 {print $9, $4}' /var/log/nginx/install.access.log | sort -rn | head -20

# Count PHP errors (current week)
zcat -f /nas/log/fpm/install.error.log* | grep -i "fatal error" | wc -l

# Run MySQL slow query analysis (preferred method)
cd /nas/content/live/install_name && dbsummary -s
```

### Log File Quick Reference

```
Nginx Access (pipe-delimited):  /var/log/nginx/{install}.access.log
Nginx Access (apache-style):    /var/log/nginx/{install}.apachestyle.log
PHP-FPM Errors:                 /nas/log/fpm/{install}.error.log
MySQL Slow Queries:             /var/log/mysql/mysql-slow.log*

Rotation: .log (today), .log.1 (yesterday), .log.2.gz through .log.7.gz (2-7 days ago)
```

---

**For comprehensive WP Engine investigation methodology, see:**
- `CLAUDE.md` - Complete investigation best practices, real failure cases, report guidelines
- `.claude/commands/bot-traffic.md` - Bot traffic investigation workflow
- `.claude/commands/mysql.md` - MySQL performance investigation workflow
- `.claude/commands/502-errors.md` - 502 Bad Gateway troubleshooting
- `.claude/commands/504-errors.md` - 504 Gateway Timeout troubleshooting
