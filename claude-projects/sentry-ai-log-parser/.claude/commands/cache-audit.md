# Cache Audit — Cache Hit Rate Analysis & Optimization

Use when you need to measure how much traffic is bypassing Varnish and hitting PHP. Run on every investigation — cache rate is the single highest-leverage optimization insight. Also use standalone when an AM asks "why is the site slow?" or "why are we seeing so many PHP requests?" Feeds directly into `/size` scenario modeling.

## Required Input

- **Pod number** (e.g., "405371")
- **Install name** (e.g., "sffilm2026")
- **WooCommerce installed?** (yes/no — changes target expectations)
- **Context from `/scout`** if available (nginx/apache counts, cache rate)

## Phase 1: Measure Cache Rate

**CRITICAL: Always use `.log.1` (yesterday's full-day rotation) for cache rate calculations.** Never use `.log` (partial day) — it skews the ratio.

```bash
# Yesterday's full-day nginx (ALL traffic including cached)
zcat -f /var/log/nginx/{install}.access.log.1 | wc -l

# Yesterday's full-day apache (ONLY dynamic/PHP — cache misses)
zcat -f /var/log/apache2/{install}.access.log.1 | wc -l
```

**For HA clusters:**
```bash
zcat -f /var/log/synced/nginx/{install}.access.log.1 | wc -l
zcat -f /var/log/apache2/{install}.access.log.1 | wc -l
```

### Calculate
```
Cache hits = Nginx count - Apache count
Cache hit rate = Cache hits / Nginx count × 100
Cache miss rate = Apache count / Nginx count × 100
```

## Phase 2: Identify Cache Bypass Sources

Run in parallel:

### Batch 1: Uncacheable Traffic Patterns
```bash
# Query strings (bypass cache by default)
zcat -f /var/log/apache2/{install}.access.log.1 | awk -F'|' '{print $10}' | grep '?' | awk '{print $2}' | sed 's/\?.*//' | sort | uniq -c | sort -rn | head -20

# POST requests (always uncacheable)
zcat -f /var/log/apache2/{install}.access.log.1 | awk -F'|' '$10 ~ /^POST/' | awk -F'|' '{print $10}' | awk '{print $2}' | sort | uniq -c | sort -rn | head -15

# Logged-in user traffic (has wordpress_logged_in cookie → bypasses cache)
zcat -f /var/log/apache2/{install}.access.log.1 | awk -F'|' '$10 ~ /wp-admin/' | wc -l
```

### Batch 2: Top Uncached URLs
```bash
# Top URLs hitting PHP (these are all cache misses)
zcat -f /var/log/apache2/{install}.access.log.1 | awk -F'|' '{print $10}' | awk '{print $1, $2}' | sort | uniq -c | sort -rn | head -30

# WooCommerce uncacheable endpoints
zcat -f /var/log/apache2/{install}.access.log.1 | awk -F'|' '$10 ~ /wc-ajax|cart|checkout|my-account/' | wc -l

# REST API requests (typically uncached)
zcat -f /var/log/apache2/{install}.access.log.1 | awk -F'|' '$10 ~ /wp-json/' | wc -l

# wp-cron requests
zcat -f /var/log/apache2/{install}.access.log.1 | awk -F'|' '$10 ~ /wp-cron/' | wc -l
```

## Phase 3: Assess & Rate

### Cache Rate Grading

| Rate | Grade | Assessment |
|------|-------|------------|
| 70%+ | Good | Healthy caching. Focus on other optimizations. |
| 50-69% | Moderate | Room for improvement. Check for unnecessary cache bypasses. |
| 30-49% | Poor | Significant PHP overhead. Likely causes: high bot traffic, query strings, logged-in users, or WooCommerce. |
| <30% | Critical | Most traffic hits PHP. Immediate investigation needed — this is usually the #1 performance problem. |

### WooCommerce Adjustment

WooCommerce sites have inherently lower cache rates because cart, checkout, and my-account pages are uncacheable. Adjusted targets:

| Site Type | Target Cache Rate | Realistic Range |
|-----------|------------------|-----------------|
| Brochure / Blog | 60-80% | Most pages cacheable |
| WooCommerce (light) | 50-65% | Cart fragments add uncacheable load |
| WooCommerce (heavy) | 40-55% | High checkout volume is inherently uncacheable |
| Membership / LMS | 30-50% | Logged-in users bypass cache entirely |

## Phase 4: Optimization Recommendations

Based on the cache bypass analysis, recommend from this menu:

### High Impact
1. **GES (Global Edge Security)** — Blocks bot traffic before it reaches PHP. If bot% > 20%, this alone can dramatically improve effective cache rate.
2. **Page cache configuration** — Ensure WP Engine page cache is not being bypassed by plugins setting no-cache headers.
3. **Query string cleanup** — UTM parameters and tracking query strings bypass Varnish. Plugins like "Remove Query Strings" or server-level rules can strip these.

### Medium Impact
4. **REST API caching** — If heavy REST API traffic (e.g., Tribe Events), check if responses can be cached or rate-limited.
5. **Cart fragment optimization** — For WooCommerce, the Ecom Performance addon (Live Cart) reduces `wc-ajax=get_refreshed_fragments` calls.
6. **Object cache** — Redis or Memcached for database query results (reduces PHP execution time even on cache misses).

### Lower Impact
7. **Browser caching headers** — Ensure static assets have proper cache-control headers.
8. **CDN for static assets** — Offload images, CSS, JS to CDN.

## Output Format

```markdown
## Cache Audit: {install} on Pod {pod-id}

### Cache Hit Rate (Yesterday — Full Day)

| Metric | Count |
|--------|-------|
| Nginx (all traffic) | X |
| Apache (PHP/dynamic) | X |
| Cache hits | X |
| **Cache hit rate** | **X%** |

**Grade: {Good/Moderate/Poor/Critical}**
{1-sentence assessment}

### Cache Bypass Breakdown

| Source | PHP Requests | % of Uncached | Cacheable? |
|--------|-------------|---------------|------------|
| Content pages (no query string) | X | X% | YES — should be cached |
| Query string URLs | X | X% | Partially — strip tracking params |
| WooCommerce endpoints | X | X% | NO — inherently uncacheable |
| REST API | X | X% | Partially — depends on endpoint |
| wp-admin | X | X% | NO — logged-in traffic |
| wp-cron | X | X% | NO — background processing |
| POST requests | X | X% | NO — form submissions |

### Optimization Impact Estimate

| Action | Estimated Cache Rate After | PHP Reduction |
|--------|---------------------------|---------------|
| Current (no changes) | X% | baseline |
| + GES (remove X% bots) | X% | -X% PHP |
| + Query string cleanup | X% | -X% PHP |
| + {other applicable} | X% | -X% PHP |

### Recommendations

1. **{Highest impact action}** — {rationale}
2. **{Second action}** — {rationale}
3. **{Third action}** — {rationale}
```

## Rules

- **ALWAYS use `.log.1` for cache rate** — never partial-day `.log`
- **ALWAYS use the same day for nginx and apache** — mismatched days produce meaningless ratios
- **Cache rate = (nginx - apache) / nginx** — NOT apache / nginx (that's the miss rate)
- **WooCommerce sites have inherently lower rates** — don't grade a WooCommerce site against brochure targets
- **Bot traffic inflates the miss rate** — if bots are hitting PHP (low cache rate), GES is the fix, not cache tuning
- **Never recommend Redis/object cache as a cache rate fix** — object cache reduces query time, not cache hit rate
- **Feed data to `/size` for P-tier modeling** — cache improvement is the highest-leverage scenario input
