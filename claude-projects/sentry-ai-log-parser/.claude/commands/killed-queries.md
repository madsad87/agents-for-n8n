# Killed Queries — PHP-FPM Governor Kill Analysis

Use when `/scout` shows killed queries > 0, or when PHP-FPM error logs contain "KILLED QUERY" entries. Killed queries lock PHP workers and often indicate runaway plugins, unindexed meta queries, or infinite retry loops (e.g., Jetpack sync queue). Also use when 504s correlate with high PHP-FPM error volume.

## Required Input

- **Pod number** (e.g., "228209")
- **Install name** (e.g., "testwebsite773")
- **Context from `/scout`** if available (killed query counts, source files)

## Phase 1: Gather Killed Query Data

Run these SSH commands (batch into 2 parallel calls):

### Batch 1: Counts & Sources
```bash
# Today's killed query count
grep -c 'KILLED QUERY' /nas/log/fpm/{install}.error.log

# Yesterday's killed query count
grep -c 'KILLED QUERY' /nas/log/fpm/{install}.error.log.1

# Source files generating killed queries (today)
grep 'KILLED QUERY' /nas/log/fpm/{install}.error.log | grep -oP 'generated in \K.*?\.php:\d+' | sort | uniq -c | sort -rn

# Source files generating killed queries (yesterday)
grep 'KILLED QUERY' /nas/log/fpm/{install}.error.log.1 | grep -oP 'generated in \K.*?\.php:\d+' | sort | uniq -c | sort -rn
```

### Batch 2: Query Details & Patterns
```bash
# Sample killed queries (first 10 today)
grep 'KILLED QUERY' /nas/log/fpm/{install}.error.log | head -10

# Tables being queried (extract from SQL)
grep 'KILLED QUERY' /nas/log/fpm/{install}.error.log | grep -oP 'FROM \K\w+' | sort | uniq -c | sort -rn

# Query sizes (byte length of killed queries)
grep 'KILLED QUERY' /nas/log/fpm/{install}.error.log | awk '{print length}' | sort -rn | head -10

# Hourly distribution (when are kills happening)
grep 'KILLED QUERY' /nas/log/fpm/{install}.error.log | grep -oP '\d{2}:\d{2}:\d{2}' | awk -F: '{print $1":00"}' | sort | uniq -c | sort -rn
```

## Phase 2: Classify Kill Sources

### Known Patterns

| Source | Plugin/Feature | Root Cause | Fix |
|--------|---------------|------------|-----|
| `jetpack_sync_queue` | Jetpack | Sync queue backup → large SELECT → kill → retry loop | Disconnect/reconnect Jetpack, or `wp jetpack sync reset` |
| `class-search-filter-query.php` | Search Filter Pro | Unindexed meta queries on wp_posts | Add database indexes, check filter configuration |
| `wc-ajax=get_refreshed_fragments` | WooCommerce | Cart fragment refresh on every page load | Ecom Performance addon (Live Cart) |
| `scholar-directory` / `meta_query` | Custom CPT | Unindexed postmeta orderby queries | Add compound index on wp_postmeta |
| `wp-all-import` | WP All Import | Large batch imports exceeding governor | Run imports in smaller batches, off-peak |
| `action-scheduler` | Action Scheduler | Queue runner processing too many actions | Reduce `AS_QUEUE_SIZE`, check pending actions |
| `tribe/views/v2/html` | The Events Calendar | Calendar search/filter queries | TEC query optimization, result caching |

### Infinite Retry Detection

Flag if you see this pattern:
1. Same query source appearing repeatedly (>50/day)
2. Query involves a queue table (e.g., `jetpack_sync_queue`, `actionscheduler_actions`)
3. Query size is large (>10KB)

This indicates an **infinite retry loop**: queue backs up → large query → governor kills → queue stays backed up → immediate retry. The queue never drains.

```
⚠ INFINITE RETRY LOOP DETECTED
Source: {plugin} querying {table}
Pattern: {count} kills/day, query size {size}KB
Impact: Each kill locks 1 PHP worker for governor timeout duration
Fix: {specific fix for this plugin/table}
```

## Phase 3: Impact Assessment

Calculate PHP worker impact:
```
Workers locked per kill = 1 (for governor timeout duration, typically 30-60s)
Concurrent kills at peak hour = Peak hourly kills / (3600 / governor_timeout)
Effective worker reduction = Concurrent kills
```

Example: 200 kills/hour with 30s governor timeout = ~1.7 workers permanently locked

## Output Format

```markdown
## Killed Query Analysis: {install} on Pod {pod-id}

### Summary

| Metric | Today | Yesterday |
|--------|-------|-----------|
| Total killed queries | X | X |
| Unique sources | X | X |
| Peak hour | HH:00 (X kills) | HH:00 (X kills) |
| Largest query | X KB | X KB |

### Kill Sources (Ranked by Volume)

| # | Source File | Plugin | Count (Today) | Count (Yesterday) | Table | Classification |
|---|-----------|--------|---------------|-------------------|-------|---------------|
| 1 | file.php:line | Plugin Name | X | X | table_name | Infinite Retry / Unindexed / Batch Job |

{⚠ Infinite retry loop warning if detected}

### PHP Worker Impact

Workers effectively locked: X of Y available
Peak hour concurrent kills: X
Impact: {Severe — more than 30% of workers / Moderate — 10-30% / Low — under 10%}

### Recommended Actions

1. **{Priority 1}** — {specific fix with command or code}
2. **{Priority 2}** — {specific fix}

### Verification Commands

```bash
# Verify kill count
grep -c 'KILLED QUERY' /nas/log/fpm/{install}.error.log

# Verify specific source
grep 'KILLED QUERY' /nas/log/fpm/{install}.error.log | grep -c '{source_pattern}'

# Check queue table size (if applicable)
wp db query "SELECT COUNT(*) FROM {queue_table}" --path=/nas/content/live/{install}
```
```

## Rules

- **ALWAYS check both today and yesterday** — patterns may be intermittent
- **ALWAYS extract the source file:line** — this identifies the responsible plugin
- **ALWAYS check for infinite retry loops** — these are the most impactful pattern
- **NEVER assume killed queries are harmless** — each one locks a PHP worker
- **Cross-reference with `/scout` slow request data** — killed queries and slow requests often share the same source
- **Large query sizes (>10KB) suggest queue/batch operations** — not individual page loads
