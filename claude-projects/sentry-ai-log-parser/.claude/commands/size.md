# Size — P-Tier Sizing Calculator

Use when the investigation involves server sizing, tier recommendation, or upgrade justification. Takes PHP demand metrics from `/scout`, `/cache-audit`, and `/bot-audit` and models four scenarios (current, post-GES, post-cache-fix, post-optimization + surge) to recommend the right P-tier. Also use standalone when an AM asks "what tier should this site be on?"

## Required Input

From `/scout` data or direct observation:
- **Daily PHP requests** (Apache access log count / days)
- **Peak hourly PHP requests** (highest hour from Apache logs)
- **Cache hit rate** (nginx vs apache from full-day .log.1)
- **Bot traffic percentage** (from `/bot-audit` or user agent analysis)
- **Expected traffic multiplier** (e.g., "2-3x for upcoming events")
- **Long-running queries detected?** (max execution time in seconds)
- **WooCommerce?** (yes/no — affects uncacheable traffic estimate)

## P-Tier Reference (from constants.py)

| Tier | PHP Workers | Use Case |
|------|-------------|----------|
| P0 | 8 | Low-traffic, brochure sites, small blogs |
| P1 | 10 | Light WooCommerce, moderate blogs |
| P1.5 | 12 | Growing WooCommerce, active blogs |
| P2 | 15 | Active WooCommerce, media sites |
| P3 | 20 | High-traffic WooCommerce, enterprise |
| P4 | 40 | Large enterprise, high-concurrency |
| P5 | 60 | Very large enterprise |
| P6-P10 | 80-180 | Extreme scale |

## Calculation Method

### Step 1: Current Load Profile
```
Daily PHP requests = Apache 7-day total / 7
Peak hourly PHP = Max hourly from Apache logs
Requests per second at peak = Peak hourly / 3600
```

### Step 2: Estimate Workers Needed at Peak
```
Workers needed = Requests per second × Average execution time (seconds)
```

Conservative assumptions:
- Average execution time: 2-3 seconds for typical WordPress
- Average execution time: 5-8 seconds for WooCommerce
- Add 1 worker per long-running query source (>30s) that runs concurrently

### Step 3: Scenario Modeling

Calculate four scenarios:

1. **Current (no changes)**
   - Use observed daily PHP and peak hourly as-is

2. **After GES (bot removal)**
   - Reduce total by bot traffic percentage
   - `Post-GES daily = Current daily × (1 - bot%)`

3. **After GES + Cache Fix**
   - Project improved cache rate (target 60% for WordPress, 50% for WooCommerce)
   - `Post-cache daily = Post-GES daily × (current_cache_miss% / target_cache_miss%)`
   - Example: 14% cache → 60% cache = 86% miss → 40% miss = 0.47x reduction

4. **After optimization + traffic surge**
   - Apply expected traffic multiplier to the optimized baseline
   - `Surge daily = Post-optimization daily × traffic_multiplier`

### Step 4: Map to Tier

For each scenario, determine the tier:
- Workers needed at peak should be ≤ 60-70% of tier workers (headroom)
- Never recommend a tier where peak demand exceeds 80% of workers

### Step 5: Long-Running Query Warning

If any requests exceed 30 seconds:
```
⚠ Long-running queries detected ({max}s).
Each locks 1 PHP worker for {max/60} minutes.
With {N} concurrent sources, {N} workers are permanently occupied.
Factor this into worker count — these workers are unavailable for normal traffic.
```

## Output Format

```markdown
## P-Tier Sizing: {install} ({domain})

### Current Load Profile

| Metric | Value |
|--------|-------|
| Daily PHP requests | X |
| Peak hourly PHP | X |
| Cache hit rate | X% |
| Bot traffic | X% |
| Max execution time | Xs |
| WooCommerce | Yes/No |

### Scenario Analysis

| Scenario | Daily PHP | Peak Hourly | Workers Needed | Recommended Tier |
|----------|-----------|-------------|----------------|-----------------|
| Current (no changes) | X | X | X | PX |
| After GES (-X% bots) | X | X | X | PX |
| After GES + cache fix (X%) | X | X | X | PX |
| After optimization + Xx surge | X | X | X | PX |

{⚠ Long-running query warning if applicable}

### Recommendation

**Primary: PX + GES** {with optimization}
{1-2 sentence rationale}

**Fallback: PX** {without optimization}
{1-2 sentence rationale}

**Why not PX-1:** {why the lower tier is too tight}
**Why not PX+1:** {why the higher tier is overkill}
```

## Rules

- **NEVER include worker counts in customer-facing reports** — use tier names only (P0, P1, etc.)
- **Worker counts are for internal sizing calculations only**
- **Always model with headroom** — never recommend a tier at >70% peak utilization
- **Always call out long-running queries** — they make worker counts misleading
- **Cache rate improvement is the highest-leverage optimization** — always model it
- **GES bot removal is the second highest leverage** — always model it if bot% > 20%
- **Read constants.py for exact worker counts** — never estimate or use ranges
