---
product: Application Performance Monitoring (APM)
internal_name: apm
last_verified: 2026-04-06
verified_by: Madison Sadler (SE) — sourced from Embrace KB (application-performance)
---

## What It Does

WP Engine's Application Performance solution powered by **New Relic APM Pro**. Provides code-level visibility into WordPress application performance.

### Key Capabilities
- **Real-time and historical application state** — throughput metrics, error rates, end-user response time
- **Code-level visibility** — drill down to see where time is spent in the application (specific PHP functions, database queries, external calls)
- **Error analysis** — visualize errors by frequency, host, or transaction; group, sort, and analyze errors in WordPress application context
- **Deployment tracking** — mark deployments on charts to understand impact of changes; compare before-and-after performance data

### Included Additional Tools
- **New Relic Browser Insights (Lite)** — browser pageviews and page load times
- **New Relic Synthetics (Lite)** — uptime monitoring; supports up to **50 free ping monitors**

## What It Does NOT Do

- **Not a fix** — APM identifies problems, it doesn't fix them. It's a diagnostic tool, not a remediation tool
- **Not a replacement for log analysis** — APM shows application-layer performance; server-level patterns (bot traffic, cache rates, worker saturation) still require log analysis
- **Not real-time alerting** — while it has real-time dashboards, it's not a replacement for uptime monitoring or incident response tooling
- **Does not cover infrastructure metrics** — CPU, memory, disk I/O at the server level are not exposed (WP Engine is PaaS)
- **Does not persist across environment changes** — deployment markers and baselines reset when the application changes significantly

## When to Recommend

| Log Evidence | Recommendation | Why |
|-------------|---------------|-----|
| Slow execution times (>2s average) with no obvious plugin/query cause | **[O] Strong recommend** | APM pinpoints exactly which PHP functions/queries are slow |
| Intermittent performance issues that don't reproduce consistently | **[O] Strong recommend** | APM captures historical data — no need to catch it live |
| Customer has frequent deployments and performance regressions | **[O] Strong recommend** | Deployment tracking shows exactly when regressions started |
| Killed queries or slow queries from unknown source | **[O] Recommend** | APM traces queries to the originating PHP code path |
| Customer asking "is it the code or the server?" | **[O] Recommend** | APM definitively answers this question |
| Simple 504s caused by obvious bot traffic or low cache rate | **[?] Conditional** | Fix the root cause first; APM adds value only if code performance is also a factor |

## When NOT to Recommend

| Situation | Why Not |
|-----------|---------|
| 504s are purely from bot traffic / credential stuffing | Problem is traffic volume, not application performance — GES is the answer |
| Customer has no development resources | APM data is only useful if someone can act on it |
| Performance issue is entirely cache-related | Fix cache configuration first; APM won't help with cache misses |
| Customer already has their own New Relic / Datadog / equivalent | Duplicate monitoring adds cost without value |
| Small brochure site with no dynamic content | No meaningful application performance to monitor |

## How to Position for AMs

### Strong positioning (investigation-led):
*"We found execution times averaging [X]s on [endpoint], but the root cause isn't visible from logs alone. APM would give [customer] code-level visibility — they'd see exactly which plugin function or database query is causing the bottleneck, and could track whether their fixes actually improve performance."*

### Moderate positioning (proactive):
*"For a site with this many plugins and this level of traffic, APM gives the development team a permanent diagnostic dashboard. They can catch performance regressions immediately after deployments instead of waiting for customer complaints."*

### Weak positioning (avoid):
- Don't claim APM will "speed up the site" — it identifies problems, it doesn't fix them
- Don't recommend APM as a substitute for an upgrade when the issue is capacity
- Don't position it for non-technical site owners who won't use the dashboard

## Pricing Notes

- Paid add-on
- Most valuable for customers with active development teams or agencies managing the site
- Lower value for "set and forget" brochure sites
- SPM is always [O] regardless — but APM should only be recommended when there's evidence of application-level performance issues

## Sources

- Embrace KB: "Application Performance" (verified 2026-03-27, confidence: high)
- Guru card ID: f5c66448-fd1b-4b79-81f6-6609f5f2016f
