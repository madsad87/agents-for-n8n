# MySQL Analysis — Slow Queries, Governor Kills & Database Health

Use when you need slow query counts, governor kill totals, and per-schema database health as part of a broader investigation. This is the composable MySQL skill used within `/scout` and `/investigate`. For deep MySQL optimization with query-level analysis and index recommendations, use `/mysql` instead.

## Required Input

**Pod number** — provided by the user (e.g., "213646")

## Pre-Flight: Load Pod Metadata

```bash
cat ~/Documents/"Sentry Reports"/{pod-id}/pod-metadata.json 2>/dev/null
```

---

## Phase 1: Slow Query Volume

### Count Total Slow Queries (Full Week)

```bash
ssh {host} 'zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -c "# Time:"'
```

**CRITICAL:** Never use `sudo`. It fails silently on WP Engine and returns 0.

### Slow Queries by Day

```bash
ssh {host} 'zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep "# Time:" | awk "{print \$3}" | cut -c1-10 | sort | uniq -c | sort -k2'
```

---

## Phase 2: Slow Query Analysis

### Extract Full Slow Query Details

```bash
ssh {host} 'zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | awk "/# Time:/{time=\$3\" \"\$4} /# User/{user=\$0} /# Query_time:/{qt=\$0} /^(SELECT|INSERT|UPDATE|DELETE|REPLACE)/{print time\"|\"user\"|\"qt\"|\"\$0}" | head -100'
```

### Top Queries by Execution Time

```bash
ssh {host} 'zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep "# Query_time:" | awk "{print \$3}" | sed "s/Query_time: //" | sort -rn | head -20'
```

### Slow Queries by Schema (Install Attribution)

```bash
ssh {host} 'zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep "^use " | sort | uniq -c | sort -rn'
```

This maps schemas to installs. WP Engine schema naming: `wp_{install_name}`.

### Slow Queries by Table

```bash
ssh {host} 'zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -E "^(SELECT|INSERT|UPDATE|DELETE)" | grep -oP "FROM \K\S+" | sort | uniq -c | sort -rn | head -20'
```

### Rows Examined

```bash
ssh {host} 'zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep "Rows_examined:" | awk "{print \$NF}" | sort -rn | head -20'
```

Flag any query examining >100K rows — these are the database contention drivers.

---

## Phase 3: Known Problem Plugins

Check for queries from known problematic plugins:

### WordPress Popular Posts
```bash
ssh {host} 'zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -i "popularpostssummary"'
```
**Pattern:** `SELECT * FROM wp_popularpostssummary` dumping millions of rows (3.7M+ seen on real pods).

### Gravity Forms
```bash
ssh {host} 'zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -i "gf_entry_meta\|rg_lead_detail"'
```
**Pattern:** Full table scans on entry metadata tables with 100K-900K rows.

### Rank Math Analytics
```bash
ssh {host} 'zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -i "rank_math_analytics"'
```
**Pattern:** `SELECT * FROM wp_rank_math_analytics_gsc` scanning 400K+ rows.

### WP Statistics
```bash
ssh {host} 'zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -i "statistics_visitor\|statistics_visit"'
```

### FVM (Fast Velocity Minify)
```bash
ssh {host} 'zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -i "fvm_cache"'
```

### WooCommerce
```bash
ssh {host} 'zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -i "wc_orders\|postmeta.*_sku\|woocommerce_sessions"'
```

### Custom/Unknown Tables
```bash
# Find any non-WordPress-core table generating slow queries
ssh {host} 'zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -E "^SELECT|^INSERT|^UPDATE|^DELETE" | grep -oP "(?:FROM|INTO|UPDATE) \K\S+" | sort | uniq -c | sort -rn | head -20'
```

---

## Phase 4: Governor Killed Queries

WP Engine's Governor kills queries that exceed character-count thresholds (NOT execution time — that's LPK).

### Check for Killed-by-WPE Log

```bash
ssh {host} 'ls -la /var/log/mysql/killed-by-wpe.log* 2>/dev/null'
```

### Count Governor Kills

```bash
ssh {host} 'zcat -f /var/log/mysql/killed-by-wpe.log* 2>/dev/null | grep -c "killed by" 2>/dev/null || echo "0"'
```

### Governor Kills by Install

```bash
ssh {host} 'zcat -f /var/log/mysql/killed-by-wpe.log* 2>/dev/null | grep -oP "db=\K\S+" | sort | uniq -c | sort -rn'
```

### PHP-FPM Error Log: Governor-Killed Queries

The PHP-FPM error log captures the actual query text when Governor kills a query. This is often more useful than the MySQL killed log.

```bash
ssh {host} 'grep -i "killed" /nas/log/fpm/*.error.log 2>/dev/null | head -20'
```

### Historical Kill Patterns

```bash
ssh {host} 'zcat -f /var/log/mysql/killed-by-wpe.log* 2>/dev/null | grep "# Time:" | awk "{print \$3}" | cut -c1-10 | sort | uniq -c | sort -k2'
```

---

## Phase 5: LPK (Long Process Kill) — MySQL Killed Queries

LPK kills queries exceeding execution time thresholds. These show up in the MySQL slow log as killed queries.

```bash
# Find killed queries in slow log
ssh {host} 'zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep -B5 "# Killed" | head -50'
```

### Killed Queries by Source (Plugin/Theme)

Cross-reference killed queries with PHP-FPM error log to identify the code source:

```bash
ssh {host} 'grep -A2 "WordPress database error.*killed" /nas/log/fpm/*.error.log 2>/dev/null | head -30'
```

---

## Phase 6: Database Size Context (dbsummary)

If `dbsummary` is available, get a quick overview of database sizes:

```bash
ssh {host} 'which dbsummary 2>/dev/null && dbsummary 2>/dev/null | head -40'
```

If not available, query table sizes directly:

```bash
ssh {host} 'mysql -e "SELECT table_schema, ROUND(SUM(data_length + index_length) / 1024 / 1024, 1) AS size_mb, SUM(table_rows) AS total_rows FROM information_schema.tables WHERE table_schema LIKE \"wp_%\" GROUP BY table_schema ORDER BY size_mb DESC LIMIT 20;" 2>/dev/null'
```

---

## Distinguishing Governor vs LPK

| Kill Type | Trigger | Where Logged | What to Look For |
|-----------|---------|-------------|------------------|
| **Governor** | Query character count too long | `killed-by-wpe.log`, FPM error log | Complex JOINs, enormous IN() clauses, auto-generated queries from page builders |
| **LPK** | Query execution time too long | `mysql-slow.log` (# Killed), FPM error log | Full table scans, missing indexes, large `Rows_examined` counts |

---

## Output Format

Save to `~/Documents/Sentry Reports/{pod-id}/pod-{pod-id}-mysql-evidence.md`.

```markdown
# MySQL Evidence: Pod {pod-id}

**Analysis Period:** {date range}

## Slow Query Summary
| Metric | Value |
|--------|-------|
| Total slow queries | X |
| Slowest query | X.XXs |
| Most affected schema | wp_{install} |

## Slow Queries by Schema (Install)
{ranked list}

## Slow Queries by Table
{ranked list with rows examined}

## Known Plugin Issues
{for each plugin found: plugin name, table, row count, query time}

## Governor Killed Queries
{count, by install, sample queries}

## LPK Killed Queries
{count, sources, sample queries}
```

---

## Rules

- **Governor kills are character-count based, NOT execution time** — never confuse them with LPK
- **Schema names map to installs** — `wp_{install_name}` (strip `wp_` prefix)
- **Full table scans (`SELECT * FROM`) on 100K+ rows = finding** — always flag these
- **Never use `sudo`** — fails silently, returns 0 counts
- **Always use `zcat -f`** to handle both plain and gzipped log files
- **Gravity Forms has two table naming conventions** — `wp_gf_entry_meta` (new) and `wp_rg_lead_detail` (old/legacy)
- **WooCommerce slow queries may indicate need for HPOS migration** — note if `postmeta` queries dominate
