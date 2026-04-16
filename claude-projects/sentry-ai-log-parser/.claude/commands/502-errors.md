# Troubleshoot WP Engine 502 Bad Gateway Errors

Use when a site is returning 502 Bad Gateway errors — indicates PHP-FPM container crashes, process unavailability, or upstream connection failures. Also use when 502s appear alongside 504s to distinguish timeout issues from process-level failures.

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
I'll help investigate 502 errors on WP Engine. Please provide:

1. Pod number: (e.g., 213668)
2. Investigation scope:
   - Entire server (all installs)?
   - Specific install name(s)?
3. [Optional] Timeframe: Default is last 7 days

I'll then connect via SSH and begin the analysis.
```

## Your Mission

Perform a comprehensive 502 error investigation by:
1. Connecting to the WP Engine server via SSH (using correct username and bastion configuration)
2. Analyzing server logs and error patterns intelligently
3. Identifying root causes with supporting evidence
4. Determining if LPK/Governor are enabled and their role
5. Delivering a professional, customer-facing root cause analysis report

## Critical Context: 502 Errors at WP Engine

### What is a 502 Error?

A **502 Bad Gateway** means the server acting as a gateway or proxy received an invalid response from the upstream server. At WP Engine, this typically refers to the NGINX → Apache/PHP-FPM proxy relationship.

**When NGINX doesn't receive a response from Apache/PHP-FPM, it returns a 502 error.**

### Two Main Causes (99% of the time)

1. **Request killed by Apache-Long-Process-Killer (LPK)**
   - Logged in: `/var/log/apache-killed-by-wpe.log`
   - Kills processes running longer than 60 seconds
   - Can be disabled in `wp-config.php`

2. **Apache/PHP-FPM not responding to NGINX**
   - Logged in: `/var/log/apache2/error.log`
   - SIGTERMs, graceful restarts, segmentation faults
   - Caused by high load, timeouts, bad code

### Important: Limited Access on WP Engine

⚠️ **WP Engine uses containers** - SSH access happens on utility servers with **limited access**. You cannot modify server configurations, enable/disable LPK or Governor, or make infrastructure changes.

**Your role is INVESTIGATIVE ONLY**: Parse logs, identify root cause, and report findings.

## Investigation Methodology

### Phase 1: Connect and Verify

1. **SSH Connection**
   - Use username from `~/.ssh/config`
   - Connect as: `ssh [username]@pod-[number].wpengine.com`
   - Or direct Kubernetes pod: `ssh [username]@pod-[number]-utility-[hash]`
   - Reference CLAUDE.md for bastion server configuration if needed

2. **Verify 502 Errors Exist**
   - Check for recent 502 errors in logs
   - Identify affected install(s)
   - Verify timeframe of issues

**Confirmation Commands:**
```bash
# Find 502 errors for specific install (pipe-delimited logs — MUST use awk field matching)
zcat -f /var/log/nginx/INSTALL.access.log* 2>/dev/null | awk -F'|' '$5 == 502'

# Use RedShell alias (if available)
get50x
get50x INSTALL

# Count 502 errors in last 7 days (pipe-delimited logs — MUST use awk field matching)
zcat -f $(find /var/log/nginx/ -name "INSTALL.access.log*" -mtime -7) 2>/dev/null | awk -F'|' '$5 == 502' | wc -l
```

### Phase 2: Determine 502 Timing Characteristics

**CRITICAL QUESTION: Is the 502 immediate or after ~60 seconds?**

This tells you the likely cause:
- **Immediate 502**: Login protection, segmentation faults, plugin/theme issues
- **After 60 seconds**: LPK timeout, server load, killed processes

### Phase 3: Intelligent Log Analysis

**Default Timeframe**: Analyze only logs from the **last 7 days** (current week)

**Discover Available Logs**:
```bash
# Find all relevant logs modified in last 7 days
find /var/log/nginx/ -name "INSTALL.access.log*" -mtime -7 -exec ls -lht {} \;
find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7 -exec ls -lht {} \;
find /var/log/apache2/ -name "INSTALL.access.log*" -mtime -7 -exec ls -lht {} \;

# Check modification dates to ensure logs are recent
ls -lht /var/log/nginx/INSTALL.access.log*
ls -lht /var/log/apache2/error.log*
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
- RedShell aliases (if available)

### Phase 4: Root Cause Investigation

Investigate these common 502 causes systematically:

#### 1. Long Process Killer (LPK)

**Check if LPK is the cause:**

```bash
# Use RedShell alias (from install directory)
killed

# Manual check (from install directory)
grep INSTALL /var/log/apache-killed-by-wpe.log | cut -d' ' -f8 | sort | uniq -c | sort -rn | head -20

# Server-wide check (from /nas/content/live/)
tail -500 /var/log/apache-killed-by-wpe.log | cut -d' ' -f6 | sed -r 's/domain=(.*):[0-9]+;/\1/' | sort | uniq -c | sort -rn | head -20
```

**Check if LPK is enabled:**
- Look for `define( 'WPE_GOVERNOR', false );` in `wp-config.php`
- If LPK is disabled, it's NOT the cause

**What to look for:**
- Which URLs are being killed most?
- Patterns in killed processes (admin-ajax, specific pages)
- Correlation with 502 timestamps

#### 2. WPE Governor (Long Query Killer)

**The WPE Governor kills queries with too many CHARACTERS (not slow queries).**

```bash
# Check for Governor-killed queries in error logs
grep "KILLED QUERY" /var/log/apache2/error.log
grep "KILLED QUERY" /var/log/fpm/error.log

# Example format:
# KILLED QUERY (24497 characters long generated in /path/to/file.php:73): SELECT ...
```

**Check if Governor is enabled:**
- Look for `define( 'WPE_GOVERNOR', false );` in `wp-config.php`
- If disabled, Governor is NOT the cause

**Important Distinction:**
- **Long queries** = Many characters (Governor kills these)
- **Slow queries** = Long execution time (LPK kills these if >60s)
- They are NOT the same!

#### 3. Apache/PHP-FPM Restarts (SIGTERMs)

**Check for service restarts:**

```bash
# Use RedShell alias
restarts

# Manual check
grep Segmentation /var/log/apache2/error.log | wc -l
grep SIGTERM /var/log/apache2/error.log | wc -l
grep restart /var/log/apache2/error.log | wc -l

# Get timestamps
grep "SIGTERM" /var/log/apache2/error.log
```

**Correlate with 502 errors:**
```bash
# If SIGTERM at 13:21:32, check for 502s at same time
grep "13:21:32" /var/log/nginx/INSTALL.apachestyle.log | grep " 502 "
```

#### 4. Segmentation Faults

**Check for segfaults:**

```bash
# Classic servers
grep Segmentation /var/log/apache2/error.log | wc -l

# EVLV servers (use SIGSEGV instead)
grep -c SIGSEGV /var/log/apache2/error.log

# Check upstream proxy failures
grep "upstream" /var/log/nginx/error.log | grep "INSTALLNAME"

# Find which domains cause segfaults
grep "upstream" /var/log/nginx/error.log | cut -d'"' -f5 | sort | uniq -c | sort -rn
```

**Known Issue**: Thesis theme version <1.8.6 causes segmentation faults. Check theme version if segfaults detected.

**Real-time monitoring:**
```bash
# Replicate 502 and watch for segfaults
tail -f /var/log/apache2/error.log | grep "Segmentation"
# EVLV: tail -f /var/log/apache2/error.log | grep "SIGSEGV"
```

**Port Analysis** (from upstream errors):
- Port 80/443: Nginx (HTTP/HTTPS)
- Port 9002: Varnish
- Port 6788: Apache read/write
- Port 6789: Apache read-only
- Port 6778/6779: PHP 7.4 containers

#### 5. SIGKILL Errors (EVLV Only)

**Resource overuse causing kills:**

```bash
# Count SIGKILL errors (high memory consumption)
grep -c 'SIGKILL' /var/log/fpm/error.log

# View recent SIGKILL errors
grep 'SIGKILL' /var/log/fpm/error.log | tail -20
```

**What it means:**
- PHP child process unable to obtain necessary resources
- Process terminated due to memory limits
- Directly results in 502 errors
- May indicate need for PHP variant on dedicated servers

#### 6. Mod-Sec Rate Limiting (444s interpreted as 502s)

**Intermittent 502s that DON'T show in logs:**

```bash
# Check if client IP is being rate-limited
grep '{IP_ADDRESS}' /var/log/nginx/error.log

# Example usage
grep '137.83.201.115' /var/log/nginx/error.log
```

**What to look for:**
```
ModSecurity: Access denied with code 444 (phase 1)
[msg "Attack rate-limit block applied"]
```

**Important**: Browsers and CloudFlare interpret 444 responses as 502 errors.

**Resolution** (customer-facing recommendation only):
- Recommend customer IP be allowlisted in mod-sec
- Reference: "Bulk Allow IPs in Modsec" documentation

#### 7. Apache Offenders (Uncached Requests)

**Too many uncached requests hitting Apache:**

```bash
# Use RedShell alias
apacheoff INSTALL

# Manual command
zcat -f /var/log/apache2/INSTALL.access.log /var/log/apache2/INSTALL.access.log.1* | cut -d' ' -f7 | sort | uniq -c | sort -rn | head -20
```

**Common finding**: `/wp-admin/admin-ajax.php` appears frequently
- Indicates heavy AJAX usage
- Recommend admin-ajax monitoring/optimization
- Check for plugins causing excessive AJAX calls

#### 8. Proxy Failures

**DNS pointed elsewhere or reverse proxy issues:**

```bash
# Check for upstream connection failures
grep "upstream" /var/log/nginx/error.log

# Check for specific domain
grep "example.com" /var/log/nginx/error.log | grep "upstream"
```

**Questions to answer:**
- Was server receiving traffic during the issue?
- What HTTP status codes were received?
- Was this reported by monitoring service?
- Did requests make it to WP Engine server?

**Common scenarios:**
- Site migrated but DNS not updated (proxying from old server)
- CloudFlare/CloudProxy/Incapsula/Akamai proxy failures
- 444 (empty) or 499 (incomplete) interpreted as 502 by external services

#### 9. Autoload Data Issues

**Object caching "fix" indicates deeper problem:**

```bash
# Check autoloaded data size
dbautoload

# Look for threshold
# If >800K, object caching may fail and cause loop
```

**What happens:**
- WordPress tries to autoload too much data
- Object caching stores all autoloaded data as one object
- If data exceeds object size limit, caching rejects it
- WordPress retries in infinite loop
- Results in 502 error

**Recommendation** (customer-facing):
- Investigate large autoloaded rows
- Consider setting non-critical rows to `autoload = 'no'`
- This is an application issue, not infrastructure

#### 10. Slow Database Queries

**Not the same as long queries:**

```bash
# Check slow query threshold
wp db query "show variables like 'long_query_time'"
# Default: 5.000000 seconds

# View slow query log
tail -100 /var/log/mysql/mysql-slow.log

# Count slow queries today
grep "Query_time" /var/log/mysql/mysql-slow.log | wc -l
```

**Important**: Slow queries (>5s) are watched and logged, but only killed if they exceed 60 seconds (LPK).

### Phase 5: Pattern Analysis

**Analyze 502 patterns intelligently:**

**Timing Analysis:**
```bash
# 502s per hour timeline (pipe-delimited logs — MUST use awk field matching)
zcat -f $(find /var/log/nginx/ -name "INSTALL.access.log*" -mtime -7) 2>/dev/null | awk -F'|' '$5 == 502 {print $1}' | cut -d: -f1-2 | sort | uniq -c

# Peak times (pipe-delimited logs — field 1 = timestamp)
zcat -f $(find /var/log/nginx/ -name "INSTALL.access.log*" -mtime -7) 2>/dev/null | awk -F'|' '$5 == 502 {split($1, t, ":"); print t[2]}' | sort | uniq -c | sort -rn
```

**IP Analysis:**
```bash
# Top IPs receiving 502s
zgrep -h " 502 " $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk '{print $1}' | sort | uniq -c | sort -rn | head -20

# IP geolocation
curl -s ipinfo.io/[IP-ADDRESS]
```

**User Agent Analysis:**
```bash
# Top user agents with 502s
zgrep -h " 502 " $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk -F'"' '{print $6}' | sort | uniq -c | sort -rn | head -20
```

**URL Analysis:**
```bash
# Top URLs generating 502s
zgrep -h " 502 " $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk -F'"' '{print $2}' | sort | uniq -c | sort -rn | head -20
```

**Server Load (if accessible):**
```bash
# EVLV servers - use Grafana metrics (preferred)
# Classic servers
sar -q
htop
```

### Phase 6: Customer-Facing Report

Include the original user request/prompt that initiated this investigation as the first section of the evidence file, under an "Original Request" heading with the verbatim text in a blockquote.

**Generate a professional Markdown report** with:

#### Required Sections:

1. **Executive Summary**
   - Brief overview of issue
   - Root cause in 1-2 sentences
   - Recommendation summary

2. **Investigation Timeline**
   - When 502 errors occurred
   - How many 502 errors observed
   - Analysis period covered (e.g., "Last 7 days: Jan 8-15, 2026")
   - 502 timing characteristic (immediate vs after 60s)

3. **Root Cause Analysis**
   - Primary cause with evidence
   - Contributing factors
   - Technical explanation (customer-appropriate language)
   - Whether LPK/Governor are enabled and their role

4. **Evidence & Metrics**
   - Specific log excerpts (sanitized)
   - Killed process counts (if applicable)
   - SIGTERM/segfault counts (if applicable)
   - Traffic patterns (IPs, user agents, URLs)
   - Correlation between events and 502s

5. **Recommendations**
   - Immediate actions (if any)
   - Long-term solutions
   - Application-level optimizations
   - Plugin/theme recommendations
   - When to escalate to WP Engine support

6. **Technical Details** (Appendix)
   - Commands used for verification
   - Full analysis methodology
   - Citations to specific log files and timestamps
   - Configuration checks (LPK/Governor status)

#### Report Formatting:

- Use professional, customer-friendly language
- Avoid jargon; explain technical terms when necessary
- Include specific timestamps and metrics
- Use markdown formatting for readability
- Always attribute to "Sentry Ai Analysis"
- Save report to: `~/Documents/pod-[number]_502_analysis_[date].md`

#### Restrictions (from CLAUDE.md)

**DO NOT**:
- Recommend enabling/disabling LPK or Governor (customers can self-serve)
- Recommend server configuration changes (WP Engine manages infrastructure)
- Quote CPU/Memory metrics from utility pods (unreliable)
- Make any configuration changes yourself (INVESTIGATION ONLY)

**DO**:
- Focus on application-level optimizations
- Recommend WP Engine features (Advanced Network, CDN, etc.)
- Suggest code/plugin improvements
- Provide autoload data optimization guidance
- Recommend mod-sec allowlisting (if rate-limiting detected)
- Suggest theme updates (e.g., Thesis <1.8.6 segfault issue)

## Example Commands Reference

**These are examples only** - use your judgment to create better analysis:

```bash
# Discover recent logs (last 7 days) with modification dates
find /var/log/nginx/ -name "install.access.log*" -mtime -7 -exec ls -lht {} \;
find /var/log/apache2/ -name "error.log*" -mtime -7 -exec ls -lht {} \;

# Confirm 502 errors exist (pipe-delimited logs — MUST use awk field matching)
zcat -f /var/log/nginx/install.access.log* 2>/dev/null | awk -F'|' '$5 == 502'
get50x install

# Check LPK kills
killed
grep install /var/log/apache-killed-by-wpe.log | tail -50

# Check Apache/PHP-FPM restarts
restarts
grep SIGTERM /var/log/apache2/error.log

# Check segmentation faults
grep -c SIGSEGV /var/log/apache2/error.log  # EVLV
grep Segmentation /var/log/apache2/error.log | wc -l  # Classic

# Check SIGKILL (EVLV)
grep -c 'SIGKILL' /var/log/fpm/error.log

# Check mod-sec rate limiting
grep '192.168.1.1' /var/log/nginx/error.log | grep "444"

# Check upstream failures
grep "upstream" /var/log/nginx/error.log | grep "install"

# Check Apache offenders
apacheoff install

# Check autoload data
dbautoload

# Check slow queries
wp db query "show variables like 'long_query_time'"
tail -100 /var/log/mysql/mysql-slow.log

# 502 timeline (pipe-delimited logs — MUST use awk field matching)
zcat -f /var/log/nginx/install.access.log* 2>/dev/null | awk -F'|' '$5 == 502 {print $1}' | cut -d: -f1-2 | sort | uniq -c

# Top IPs with 502s
zgrep -h " 502 " /var/log/nginx/install.apachestyle.log* | awk '{print $1}' | sort | uniq -c | sort -rn | head -20

# Top URLs with 502s
zgrep -h " 502 " /var/log/nginx/install.apachestyle.log* | awk -F'"' '{print $2}' | sort | uniq -c | sort -rn | head -20
```

## Success Criteria

Your investigation is complete when you have:

✅ Gathered all required information (pod number, scope, timeframe)
✅ Connected via SSH using correct username and bastion configuration
✅ Confirmed 502 errors exist and determined timing characteristic (immediate vs 60s)
✅ Identified the root cause with supporting evidence
✅ Analyzed logs from the appropriate timeframe (last 7 days, verified by modification dates)
✅ Checked LPK and Governor status (enabled/disabled)
✅ Investigated all relevant root causes systematically
✅ Generated a professional, customer-facing Markdown report
✅ Provided actionable recommendations with clear next steps
✅ Documented all analysis steps for verification

## Attribution

All reports must be attributed to:
**"Sentry Ai Analysis"**

---

**Remember**:
- You have full autonomy in your investigation approach
- Use the examples as guidance, but adapt to specific patterns you discover
- Your goal is to find the truth, not to follow a script
- You are INVESTIGATIVE ONLY - never enable/disable functions or change configurations
- WP Engine uses containers with limited SSH access - work within those constraints
- Long queries ≠ Slow queries - understand the difference
