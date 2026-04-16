# Troubleshoot WP Engine MySQL Performance Issues

Use when investigating MySQL performance in depth — slow query analysis, query optimization recommendations, index suggestions, and database contention patterns. This is the comprehensive standalone MySQL skill. For killed-query-specific analysis within an `/investigate` workflow, use `/killed-queries` instead. For quick slow query counts within `/scout`, use `/mysql-analysis`.

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
I'll help investigate MySQL performance issues on WP Engine. Please provide:

1. Pod number: (e.g., 213668)
2. Investigation scope:
   - Entire server (all installs)?
   - Specific install name(s)?
3. [Optional] Timeframe: Default is last 7 days

I'll then connect via SSH and begin the analysis.
```

## Your Mission

Perform a comprehensive MySQL performance investigation by:
1. Connecting to the WP Engine server via SSH (using correct username and bastion configuration)
2. Analyzing MySQL slow query logs for SLOW queries (execution time >5s)
3. Analyzing PHP-FPM error logs for Governor-killed LONG queries (character count)
4. Identifying problematic queries, tables, and files from BOTH data sources
5. Correlating slow and killed queries with site performance issues
6. Delivering a professional, customer-facing optimization report

## Critical Context: MySQL at WP Engine

### Two Separate Query Kill Systems (CRITICAL DISTINCTION)

WP Engine has **two independent systems** that terminate database queries for different reasons. Conflating them produces incorrect diagnoses.

#### 1. WPE Governor — Kills LONG Queries (Character Count)

**What it does:** Monitors query **string length** (character count) and kills queries that are too long, regardless of how fast they would execute.

**Trigger:** Query contains too many characters (e.g., a `SELECT ... WHERE id IN (1,2,3,...thousands)` with thousands of IDs).

**Log location:** PHP-FPM error logs at `/nas/log/fpm/{install}.error.log`

**Log format:**
```
KILLED QUERY (24497 characters long generated in /nas/content/live/install/wp-content/plugins/plugin-name/file.php:73): SELECT term_id, meta_key, meta_value FROM wp_termmeta WHERE term_id IN (5240,3240,2817,...)
```

**Key facts:**
- A LONG query is NOT necessarily SLOW — it may execute in milliseconds if properly indexed
- The Governor kills based on **character count**, not execution time
- Common causes: large `IN()` clauses, taxonomy queries with many term IDs, sitemap generation, bulk operations
- **Customer fix:** Add `define( 'WPE_GOVERNOR', false );` to `wp-config.php` — this allows long queries to run, but they remain subject to the 60-second LPK timeout
- TSE1 and TSE2 can also disable the Governor for customers

**Investigation commands:**
```bash
# Count Governor-killed queries per install
for f in /nas/log/fpm/*.error.log; do
  install=$(basename "$f" .error.log)
  count=$(zcat -f /nas/log/fpm/${install}.error.log* 2>/dev/null | grep -c "KILLED QUERY")
  [ "$count" -gt 0 ] && echo "$count $install"
done | sort -rn

# View killed query details (character count + source file)
zcat -f /nas/log/fpm/{install}.error.log* 2>/dev/null | grep "KILLED QUERY" | head -5

# Extract source files generating killed queries
zcat -f /nas/log/fpm/{install}.error.log* 2>/dev/null | grep -oP 'generated in \K[^)]+' | sort | uniq -c | sort -rn

# Extract tables targeted by killed queries
zcat -f /nas/log/fpm/{install}.error.log* 2>/dev/null | grep "KILLED QUERY" | grep -oP 'FROM \K\w+' | sort | uniq -c | sort -rn

# Daily distribution of killed queries
zcat -f /nas/log/fpm/{install}.error.log* 2>/dev/null | grep "KILLED QUERY" | grep -oP '\d{4}/\d{2}/\d{2}' | sort | uniq -c | sort -rn
```

#### 2. LPK (Long Process Killer) — Kills SLOW Queries (Execution Time)

**What it does:** Terminates queries (and their parent PHP processes) that exceed **60 seconds** of execution time.

**Trigger:** Query execution time exceeds 60 seconds.

**Log locations:**
- MySQL slow query log: `/var/log/mysql/mysql-slow.log` — the `Killed:` field shows non-zero if MySQL itself terminated the query
- Apache killed log: `/var/log/apache-killed-by-wpe.log` — shows processes killed by WP Engine's LPK system
- PHP-FPM error log: may also show related PHP fatal errors when the parent process is killed

**Key facts:**
- A SLOW query is NOT necessarily LONG (character count) — a short `SELECT * FROM huge_table` can run for minutes
- Queries >5 seconds are **logged** in the MySQL slow query log
- Queries >60 seconds are **killed** by LPK
- Even with Governor disabled, LPK still enforces the 60-second limit

**IMPORTANT:** Not all killed long queries are slow, and not all killed slow queries are long. These are independent dimensions.

### MySQL Slow Query Log

**Location**: `/var/log/mysql/mysql-slow.log`

**Access Requirements**:
- Requires root user permissions
- Use `sudo` for read-only access (if you have intermediate shell access)
- Log rotation: `mysql-slow.log*` files available

**Threshold**: Queries running over **5 seconds** are logged

**IMPORTANT**:
- ⚠️ **DO NOT change the 5-second threshold** - this is a WP Engine standard
- ⚠️ **NEVER run sudo commands that make changes** - investigation only
- ⚠️ **Read-only access only** - analyze, don't modify

### WP Engine Container Constraints

WP Engine uses containers with limited SSH access on utility servers. You cannot:
- Modify MySQL configuration
- Change slow query thresholds
- Restart MySQL services
- Make any infrastructure changes

**Your role is INVESTIGATIVE ONLY**: Parse logs, identify problematic queries, and report findings.

## Investigation Methodology

### Phase 1: Connect and Verify

1. **SSH Connection**
   - Use username from `~/.ssh/config`
   - Connect as: `ssh [username]@pod-[number].wpengine.com`
   - Or direct Kubernetes pod: `ssh [username]@pod-[number]-utility-[hash]`
   - Reference CLAUDE.md for bastion server configuration if needed

2. **Verify MySQL Slow Log Access**
   - Check if log exists and is accessible
   - Verify log contains recent entries
   - Identify timeframe of issues

**Verification Commands:**
```bash
# Check if slow log exists
ls -lht /var/log/mysql/mysql-slow.log*

# Check recent entries (requires sudo)
sudo tail -50 /var/log/mysql/mysql-slow.log

# Check slow query threshold
wp db query "show variables like 'long_query_time'"
# Expected: 5.000000 seconds
```

### Phase 2: Intelligent Slow Query Analysis

**Default Timeframe**: Analyze only logs from the **last 7 days** (current week)

**Discover Available Logs**:
```bash
# Find all MySQL slow logs modified in last 7 days
find /var/log/mysql/ -name "mysql-slow.log*" -mtime -7 -exec ls -lht {} \;

# Check modification dates to ensure logs are recent
ls -lht /var/log/mysql/mysql-slow.log*
```

**IMPORTANT**:
- Always check file modification dates (`ls -lt`)
- Only analyze logs modified within 7 days
- Ignore old/stale logs (e.g., 1 month or 1 year old)
- Log rotation may produce multiple compressed files (.gz)
- Use `-mtime -7` to find files modified in last 7 days

**You Have Full Autonomy**: Use ANY analysis approach you deem effective:
- RedShell commands (dbsummary, etc.)
- Standard commands (grep, awk, sed, cut, sort, uniq)
- Python scripts for complex parsing
- Custom one-liners optimized for the specific pattern
- Multi-stage analysis pipelines

### Phase 3: Using dbsummary RedShell Command

**The Modern Approach** (replaces old `mysqloff` command):

```bash
# Analyze slow queries for specific install
cd /nas/content/live/INSTALL
dbsummary -s
# OR
dbsummary --slow

# Server-wide analysis (from /nas/content/live/)
cd /nas/content/live
dbsummary -s
```

**What dbsummary Shows**:
- **Distillate**: Query type (SELECT, UPDATE, INSERT, DELETE) + tables targeted
- Query patterns and frequency
- Source files generating slow queries
- Performance metrics per install

**Example Output Interpretation**:
```
Distillate: SELECT wp_comments
```
This means: `SELECT` queries targeting the `wp_comments` table are slow.

### Phase 4: Reading MySQL Slow Log Entries

**Log Entry Format**:
```
# Time: 150821 22:51:33
# User@Host: <install>[<install>] @ web-101-4 [172.16.0.5]
# Thread_id: 5544135  Schema: wp_install  Last_errno: 0  Killed: 0
# Query_time: 5.480935  Lock_time: 0.000036  Rows_sent: 30  Rows_examined: 1318172  Rows_affected: 0  Rows_read: 1318172
# Bytes_sent: 532
SET timestamp=1440197493;
SELECT meta_key
        FROM wp_1_postmeta
        GROUP BY meta_key
        HAVING meta_key NOT LIKE '\\_%'
        ORDER BY meta_key
        LIMIT 30 /* From [www.domain.com/wp-admin/post.php?post=651669&action=edit&message=10] in [N/A] */;
```

**Field Explanations**:

1. **Time**: Date and time the query ran (format: YYMMDD HH:MM:SS)

2. **User@Host**:
   - MySQL user (install name) that ran the query
   - Server it came from (different only if cluster)

3. **Thread_id**: Database the query was run on

4. **Schema**: Database name (usually wp_installname)

5. **Query_time**: How long the query took to execute (in seconds)
   - **This is the key metric!**
   - Higher values = more problematic queries

6. **Lock_time**: Time spent waiting for table locks (in seconds)
   - High values indicate table locking contention

7. **Rows_sent**: Number of records returned that meet query parameters
   - Small number is good

8. **Rows_examined**: Number of rows searched to return Rows_sent
   - **High values indicate inefficiency**
   - Example: Examining 1,318,172 rows to return 30 = bad!

9. **Rows_affected**: Number of rows updated (UPDATE/INSERT/DELETE queries)

10. **Rows_read**: Should match Rows_examined (relevant to UPDATE/INSERT)

11. **Bytes_sent**: Amount of data in the query result

12. **Query Source**:
    - Shows the actual SQL query
    - Source file/URL that generated it
    - Example: `/* From [www.domain.com/wp-admin/post.php] in [plugin-file.php] */`

### Phase 5: Troubleshooting Analysis

**Use these commands to identify patterns:**

#### 1. Analyze Slow Queries by Date

```bash
# Find all slow queries from specific date
sudo grep "Time: 150821" -A 20 /var/log/mysql/mysql-slow.log

# Count slow queries per day (last 7 days)
sudo zgrep -h "# Time:" $(find /var/log/mysql/ -name "mysql-slow.log*" -mtime -7) | cut -d' ' -f3 | cut -c1-6 | sort | uniq -c
```

#### 2. Analyze Slow Queries by File/URL

```bash
# Find slow queries from specific file
sudo grep "www.domain.com/wp-admin/post.php" -B 20 /var/log/mysql/mysql-slow.log

# Top files generating slow queries for specific install
sudo zgrep "INSTALL" /var/log/mysql/mysql-slow.log | grep -oP '(?<=in \[)\S*(?=\])' | sort | uniq -c | sort -nr | head

# Top files generating slow queries (all sites, current week)
sudo zcat -f /var/log/mysql/mysql-slow.log* | grep -oP '(?<=in \[)\S*(?=\])' | sort | uniq -c | sort -nr | head
```

#### 3. Analyze Query Performance Metrics

```bash
# Find queries with highest Query_time
sudo grep "Query_time:" /var/log/mysql/mysql-slow.log | sort -t: -k2 -nr | head -20

# Find queries examining the most rows
sudo grep "Rows_examined:" /var/log/mysql/mysql-slow.log | sort -t: -k7 -nr | head -20

# Find queries with highest Lock_time
sudo grep "Lock_time:" /var/log/mysql/mysql-slow.log | awk '{print $4}' | sort -nr | head -20
```

#### 4. Analyze by Install

```bash
# Count slow queries per install
sudo zcat -f /var/log/mysql/mysql-slow.log* | grep "User@Host:" | awk '{print $3}' | sort | uniq -c | sort -rn | head -20

# Slow queries for specific install
sudo grep "User@Host: install\[install\]" /var/log/mysql/mysql-slow.log | wc -l
```

#### 5. Analyze by Table

```bash
# Find which tables are being queried slowly
sudo zcat -f /var/log/mysql/mysql-slow.log* | grep -oP "FROM \K\w+" | sort | uniq -c | sort -rn | head -20

# Check for specific table (e.g., wp_postmeta)
sudo grep "wp_postmeta" /var/log/mysql/mysql-slow.log | wc -l
```

#### 6. Analyze Query Types

```bash
# Count by query type (SELECT, UPDATE, INSERT, DELETE)
sudo zcat -f /var/log/mysql/mysql-slow.log* | grep -E "^(SELECT|UPDATE|INSERT|DELETE)" | cut -d' ' -f1 | sort | uniq -c | sort -rn
```

### Phase 6: Common MySQL Performance Issues

Investigate these patterns systematically:

#### 1. Inefficient Queries (High Rows_examined)

**Symptom**: Rows_examined >> Rows_sent

**Example**: Examining 1,318,172 rows to return 30 rows

**Causes**:
- Missing indexes on queried columns
- Full table scans
- Queries without WHERE clauses
- Complex JOIN operations without proper indexing

**Recommendation**:
- Suggest adding indexes to frequently queried columns
- Recommend query optimization
- Check if caching can reduce query frequency

#### 2. Table Locking Contention (High Lock_time)

**Symptom**: Lock_time close to or approaching Query_time

**Causes**:
- Multiple queries waiting for table locks
- Long-running UPDATE/INSERT/DELETE queries
- MyISAM tables (table-level locking)

**Recommendation**:
- Check if tables are InnoDB (row-level locking preferred)
- Recommend batch operations during low-traffic periods
- Suggest optimization of write-heavy operations

#### 3. Slow wp_postmeta / wp_options Queries

**Common Issue**: WordPress meta tables grow very large

**Symptoms**:
- Frequent slow queries on `wp_postmeta`, `wp_options`
- High Rows_examined on these tables

**Recommendation**:
- Check autoload data size: `dbautoload`
- Recommend cleaning up orphaned postmeta
- Suggest object caching to reduce query frequency
- Consider transients cleanup

#### 4. Plugin/Theme Generated Queries

**Symptom**: Slow queries with source file pointing to specific plugin/theme

**Example**: `in [wp-content/plugins/bad-plugin/file.php]`

**Recommendation**:
- Identify problematic plugin/theme
- Recommend disabling/replacing inefficient plugins
- Suggest contacting plugin developer
- Check for plugin updates

#### 5. Admin-Ajax Heavy Queries

**Symptom**: Slow queries from `/wp-admin/admin-ajax.php`

**Causes**:
- AJAX requests triggering expensive database queries
- Real-time updates, notifications, widgets
- Live search functionality

**Recommendation**:
- Identify which plugin/theme triggers admin-ajax
- Recommend caching AJAX responses
- Suggest reducing real-time update frequency
- Consider disabling problematic AJAX features

#### 6. WooCommerce / eCommerce Query Issues

**Common Tables**: `wp_woocommerce_*`, `wp_posts`, `wp_postmeta`

**Symptoms**:
- Slow product queries
- Complex pricing calculations
- Order lookup queries

**Recommendation**:
- WooCommerce-specific optimizations
- Product query caching
- Indexed meta keys for filtering
- Consider WooCommerce performance plugins

#### 7. Governor-Killed Queries (Long Character Count)

**Symptom**: `KILLED QUERY (XXXXX characters long generated in ...)` entries in FPM error logs

**NOT the same as slow queries** — these are killed for query string length, not execution time.

**Common Causes**:
- Taxonomy queries with large `IN()` clauses (hundreds/thousands of term IDs)
- SEO plugins generating sitemap queries across all terms (e.g., Yoast `class-taxonomy-sitemap-provider.php`)
- Link checker plugins querying term metadata in bulk
- Bulk import/export operations building large query strings
- Themes querying all taxonomy terms for navigation/headers

**Example** (from real investigation):
```
KILLED QUERY (24497 characters long generated in
/nas/content/live/install/wp-content/plugins/wordpress-seo-premium/inc/sitemaps/class-taxonomy-sitemap-provider.php:73):
SELECT term_id, meta_key, meta_value FROM wp_termmeta WHERE term_id IN (5240,3240,2817,...thousands more...)
```

**Recommendation**:
- Identify the source plugin/theme generating oversized queries
- For taxonomy-heavy sites: evaluate adding `define( 'WPE_GOVERNOR', false );` to `wp-config.php`
- With Governor disabled, queries can run but are still subject to the 60-second LPK execution limit
- Consider whether the plugin can be configured to batch its queries (smaller `IN()` clauses)
- Check if a plugin update addresses the query size issue
- For theme-generated queries: refactor to use paginated/batched taxonomy lookups

### Phase 7: Governor-Killed Query Analysis (FPM Error Logs)

**ALWAYS check FPM error logs for Governor-killed queries in addition to MySQL slow query logs.** These are two separate data sources that reveal different problems.

```bash
# Count KILLED QUERY entries per install
for f in /nas/log/fpm/*.error.log; do
  install=$(basename "$f" .error.log)
  count=$(zcat -f /nas/log/fpm/${install}.error.log* 2>/dev/null | grep -c "KILLED QUERY")
  [ "$count" -gt 0 ] && echo "$count $install"
done | sort -rn

# For installs with killed queries — get details
zcat -f /nas/log/fpm/{install}.error.log* 2>/dev/null | grep "KILLED QUERY" | head -10

# Character count distribution
zcat -f /nas/log/fpm/{install}.error.log* 2>/dev/null | grep -oP 'KILLED QUERY \(\K\d+' | sort -n | uniq -c

# Source files responsible
zcat -f /nas/log/fpm/{install}.error.log* 2>/dev/null | grep -oP 'generated in \K[^)]+' | sort | uniq -c | sort -rn
```

**When reporting Governor-killed queries:**
- Clearly state they were killed for **character length**, not execution time
- Include the character count from the log entry
- Identify the source plugin/theme file generating oversized queries
- Recommend: evaluate whether `define('WPE_GOVERNOR', false);` is appropriate, understanding that LPK still enforces the 60-second execution limit
- Common culprits: SEO plugins (Yoast sitemaps), link checkers, taxonomy-heavy themes, bulk import tools

### Phase 8: Correlation with Other Issues

**Cross-reference MySQL slow queries with:**

1. **502/504 Errors**:
   - **LPK-killed queries** (>60s execution): These kill the parent PHP process, causing 502 errors
   - **Governor-killed queries** (long character count): These terminate the query but the PHP process may survive — the page may return incomplete data or a PHP error rather than a 502
   - Correlation: Check if slow query timestamps match 502/504 timestamps
   - `/var/log/apache-killed-by-wpe.log` may show LPK-killed processes

2. **High Server Load**:
   - Multiple slow queries can cause server load spikes
   - Governor-killed queries may actually reduce load by preventing large queries from running
   - Check `sar -q` or Grafana metrics during slow query times

3. **PHP Worker Saturation**:
   - Slow queries block PHP workers (LPK issue)
   - Governor-killed queries release workers quickly but may cause repeated retries
   - Check `fpmwatch` or `apachewatch` for long-running processes

4. **Cache Miss Patterns**:
   - High slow query count may indicate poor cache hit rate
   - Correlate with Nginx access logs for uncached requests

### Phase 9: Customer-Facing Report

Include the original user request/prompt that initiated this investigation as the first section of the evidence file, under an "Original Request" heading with the verbatim text in a blockquote.

**Generate a professional Markdown report** with:

#### Required Sections:

1. **Executive Summary**
   - Brief overview of MySQL performance issue
   - Root cause in 1-2 sentences
   - Recommendation summary

2. **Investigation Timeline**
   - When slow queries occurred
   - How many slow queries observed
   - How many Governor-killed queries found (if any)
   - Analysis period covered (e.g., "Last 7 days: Jan 8-15, 2026")
   - Slow query threshold noted (5 seconds)

3. **Slow Query Analysis** (MySQL slow query log)
   - Total slow query count
   - Queries per install (if multiple installs)
   - Peak times for slow queries
   - Query types breakdown (SELECT, UPDATE, INSERT, DELETE)

4. **Governor-Killed Query Analysis** (FPM error logs — include if found)
   - Total killed query count per install
   - Clarify these were killed for **query string length (character count)**, not execution time
   - Character counts from log entries
   - Source plugin/theme files generating the oversized queries
   - Tables targeted by killed queries
   - Daily distribution and spike patterns
   - **Note:** A long query is not necessarily slow — the Governor prevents potentially resource-intensive queries from running based on query size

5. **Root Cause Analysis**
   - Primary cause with evidence
   - Contributing factors
   - Clearly distinguish between slow query issues (execution time) and Governor-killed query issues (character length) if both are present
   - Technical explanation (customer-appropriate language)
   - Source files/plugins identified

6. **Evidence & Metrics**
   - Specific slow query examples (sanitized)
   - Query_time metrics (average, maximum)
   - Rows_examined vs Rows_sent ratios
   - Problematic tables identified
   - Files/URLs generating slow queries
   - Governor-killed query samples showing character count and source

7. **Performance Impact**
   - Correlation with 502/504 errors (if applicable)
   - Server load correlation (if applicable)
   - User-facing impact assessment
   - For Governor kills: pages may return incomplete data or PHP errors rather than gateway errors

8. **Recommendations**
   - Immediate actions (if any)
   - Query optimization opportunities
   - Indexing recommendations (if applicable)
   - Plugin/theme changes suggested
   - For Governor kills: evaluate `define( 'WPE_GOVERNOR', false );` in wp-config.php — this allows long queries to run but they remain subject to the 60-second LPK timeout
   - Caching strategies
   - Long-term database maintenance

9. **Technical Details** (Appendix)
   - Commands used for verification
   - Full analysis methodology
   - Citations to specific log files and timestamps
   - Sample slow queries (full text)
   - Sample Governor-killed query entries (full text with character count)

#### Report Formatting:

- Use professional, customer-friendly language
- Avoid jargon; explain technical terms when necessary
- Include specific timestamps and metrics
- Use markdown formatting for readability
- Always attribute to "Sentry Ai Analysis"
- Save report to: `~/Documents/pod-[number]_mysql_analysis_[date].md`

#### Restrictions (from CLAUDE.md)

**DO NOT**:
- Change MySQL slow query threshold (fixed at 5 seconds)
- Recommend server configuration changes (WP Engine manages infrastructure)
- Run sudo commands that modify MySQL settings
- Create, modify, or delete indexes yourself
- Make any database changes
- Restart MySQL services

**DO**:
- Focus on application-level optimizations
- Recommend query optimization strategies
- Suggest plugin/theme improvements
- Provide indexing recommendations (customer to implement or request)
- Recommend WP Engine features (object caching, CDN, etc.)
- Suggest database cleanup strategies (customer to implement)
- Correlate with other performance issues (502/504, server load)

## Example Commands Reference

**These are examples only** - use your judgment to create better analysis:

```bash
# Verify slow log access and threshold
ls -lht /var/log/mysql/mysql-slow.log*
wp db query "show variables like 'long_query_time'"

# Use dbsummary (modern approach)
cd /nas/content/live/INSTALL
dbsummary -s

# Find recent slow logs
find /var/log/mysql/ -name "mysql-slow.log*" -mtime -7 -exec ls -lht {} \;

# View recent slow queries
sudo tail -100 /var/log/mysql/mysql-slow.log

# Slow queries by date
sudo grep "Time: 260115" -A 20 /var/log/mysql/mysql-slow.log

# Top files generating slow queries (specific install)
sudo zgrep "installname" /var/log/mysql/mysql-slow.log | grep -oP '(?<=in \[)\S*(?=\])' | sort | uniq -c | sort -nr | head

# Top files generating slow queries (all sites, current week)
sudo zcat -f /var/log/mysql/mysql-slow.log* | grep -oP '(?<=in \[)\S*(?=\])' | sort | uniq -c | sort -nr | head

# Count slow queries per install
sudo zcat -f /var/log/mysql/mysql-slow.log* | grep "User@Host:" | awk '{print $3}' | sort | uniq -c | sort -rn | head -20

# Queries with highest Query_time
sudo grep "Query_time:" /var/log/mysql/mysql-slow.log | sort -t: -k2 -nr | head -20

# Queries examining most rows
sudo grep "Rows_examined:" /var/log/mysql/mysql-slow.log | sort -t: -k7 -nr | head -20

# Find queries on specific table
sudo grep "wp_postmeta" /var/log/mysql/mysql-slow.log | wc -l

# Query type breakdown
sudo zcat -f /var/log/mysql/mysql-slow.log* | grep -E "^(SELECT|UPDATE|INSERT|DELETE)" | cut -d' ' -f1 | sort | uniq -c | sort -rn

# Slow queries per day
sudo zgrep -h "# Time:" /var/log/mysql/mysql-slow.log* | cut -d' ' -f3 | cut -c1-6 | sort | uniq -c

# Check autoload data (often correlates with slow queries)
dbautoload

# --- Governor-Killed Query Analysis (FPM Error Logs) ---

# Count KILLED QUERY entries per install
for f in /nas/log/fpm/*.error.log; do
  install=$(basename "$f" .error.log)
  count=$(zcat -f /nas/log/fpm/${install}.error.log* 2>/dev/null | grep -c "KILLED QUERY")
  [ "$count" -gt 0 ] && echo "$count $install"
done | sort -rn

# View killed query details (shows character count + source file + query)
zcat -f /nas/log/fpm/{install}.error.log* 2>/dev/null | grep "KILLED QUERY" | head -5

# Source files generating killed queries
zcat -f /nas/log/fpm/{install}.error.log* 2>/dev/null | grep -oP 'generated in \K[^)]+' | sort | uniq -c | sort -rn

# Tables targeted by killed queries
zcat -f /nas/log/fpm/{install}.error.log* 2>/dev/null | grep "KILLED QUERY" | grep -oP 'FROM \K\w+' | sort | uniq -c | sort -rn

# Daily distribution of killed queries
zcat -f /nas/log/fpm/{install}.error.log* 2>/dev/null | grep "KILLED QUERY" | grep -oP '\d{4}/\d{2}/\d{2}' | sort | uniq -c | sort -rn

# Check if Governor is currently disabled
grep -r "WPE_GOVERNOR" /nas/content/live/{install}/wp-config.php
```

## Success Criteria

Your investigation is complete when you have:

✅ Gathered all required information (pod number, scope, timeframe)
✅ Connected via SSH using correct username and bastion configuration
✅ Verified slow query log access and threshold (5 seconds)
✅ Identified slow queries with supporting metrics
✅ Checked FPM error logs for Governor-killed queries (`grep "KILLED QUERY" /nas/log/fpm/*.error.log`)
✅ Clearly distinguished between SLOW queries (execution time, MySQL slow log) and LONG queries (character count, Governor kills in FPM logs)
✅ Analyzed logs from the appropriate timeframe (last 7 days, verified by modification dates)
✅ Identified problematic queries, tables, files, and plugins/themes from BOTH data sources
✅ Correlated slow/killed queries with other performance issues (if applicable)
✅ Generated a professional, customer-facing Markdown report
✅ Provided actionable optimization recommendations (including `WPE_GOVERNOR` disable option where appropriate)
✅ Documented all analysis steps for verification

## Attribution

All reports must be attributed to:
**"Sentry Ai Analysis"**

---

**Remember**:
- You have full autonomy in your investigation approach
- Use the examples as guidance, but adapt to specific patterns you discover
- Your goal is to find the truth, not to follow a script
- You are INVESTIGATIVE ONLY - never change MySQL settings or run sudo commands that modify anything
- WP Engine uses containers with limited SSH access - work within those constraints
- The 5-second slow query threshold should NEVER be changed
- Focus on application-level optimizations, not infrastructure changes
