# WP Engine Report Templates

Reference templates for WP Engine investigation reports. See `CLAUDE.md` for rules on what to include/exclude.

## Customer-Facing Report Template

```markdown
# [Issue Type] Root Cause Analysis - Pod [ID]

**Investigation Date:** [Date]
**Server:** pod-[ID] ([Plan Type])
**Primary Install Affected:** [install name]

---

## Executive Summary
[1-2 paragraph overview with root cause and recommendation]

## Evidence and Findings
[Detailed analysis with quantified data]

## Root Cause Determination
[Clear statement of what caused the issue]

## Recommendations
[Specific, actionable next steps]

## Conclusion
[Summary of findings and next steps]

---

**Report Prepared By:** Sentry Ai Analysis
**Analysis Date:** [Date]
**Data Source:** Server-side log analysis (pod-[ID].wpengine.com)
**Log Period:** [Start Date] - [End Date] ([N] days)
**Total Requests Analyzed:** [Count] requests
**Total 504 Errors Found:** [Count] errors ([%] of all requests)
**Analysis Tools:** SSH server-side log parsing, nginx access logs, nginx apachestyle logs, PHP-FPM error logs, MySQL slow query logs, traffic pattern analysis
```

## Evidence File Template

```markdown
# Evidence File - Pod [ID] [Issue]

## Original Request
> [The exact prompt or request that initiated this investigation]

## SSH Commands Used

### Command 1: [Description]
`[command]`
**Result:** [output summary]

### Command 2: [Description]
`[command]`
**Sample Output:**
[Raw output]

## Log File Excerpts

### PHP-FPM Error Log: /nas/log/fpm/[install].error.log
[Relevant error messages]

### Nginx Access Log: /var/log/nginx/[install].access.log
[Sample log lines]

### MySQL Slow Query Log
[Slow query excerpts if applicable]

---

**Report Prepared By:** Sentry Ai Analysis
**Analysis Date:** [Date]
**Data Source:** Server-side log analysis (pod-[ID].wpengine.com)
**Log Period:** [Start Date] - [End Date] ([N] days)
**Total Requests Analyzed:** [Count] requests
**Analysis Tools:** SSH server-side log parsing, nginx access logs, nginx apachestyle logs, PHP-FPM error logs, MySQL slow query logs, traffic pattern analysis
**Sampling:** None applied; all counts represent complete data from the analysis period
```

## Server Overview Section (Customer-Facing)

Use plan tier name only. Do NOT expose worker counts, CPU cores, memory, or capacity ranges.

```markdown
## Server Overview

**Server:** pod-219945 (Single-Tenant P1 Plan)
**Analysis Period:** January 14-21, 2026 (7 days)
**Primary Install:** milesit
**Total Traffic:** 948,976 requests (135,568/day average)
```

## Upgrade Recommendation Template

Use conditional format. NEVER include pricing or costs.

```markdown
### Consider Server Plan Upgrade (LONG-TERM)

**Issue:** [Plan] capacity being exceeded during peak traffic with [specific cause].

**Upgrade is recommended if:**
1. After plugin updates and optimizations, error rate remains > [threshold]
2. Average response time remains > 0.5 seconds
3. Traffic continues to grow
4. Peak traffic days exceed [threshold] requests
5. Business requirements demand higher availability

**Wait on upgrade if:**
1. Plugin updates reduce error rates
2. Error rate drops below [threshold]
3. Average response time improves to < 0.5 seconds
4. Traffic stabilizes at current levels

**Recommendation:**
Implement code/plugin optimizations first, then monitor for 7-14 days.
- **If performance improves:** Current plan is adequate with optimized code
- **If performance does not improve:** Upgrade to [next tier]

**Implementation:** Contact WP Engine Support to evaluate server plan options.
```

## Report Footer (Full Attribution) — REQUIRED ON ALL REPORTS

Every report (root cause and evidence) MUST end with this structured attribution block. Never use inline italic footnotes or plain-text closings instead.

```markdown
---

**Report Prepared By:** Sentry Ai Analysis
**Analysis Date:** [Date]
**Data Source:** Server-side log analysis (pod-[ID].wpengine.com)
**Log Period:** [Start Date] - [End Date] ([N] days)
**Total Requests Analyzed:** [Count] requests
**Total 504 Errors Found:** [Count] errors ([%] of all requests)
**Total 502 Errors Found:** [Count] errors ([%] of all requests)
**Analysis Tools:** SSH server-side log parsing, nginx access logs, nginx apachestyle logs, PHP-FPM error logs, MySQL slow query logs, traffic pattern analysis
```

- Include/omit error lines as applicable (e.g., skip 502 line if no 502s were found)
- For evidence files, add: `**Sampling:** None applied; all counts represent complete data from the analysis period`
- Adjust **Analysis Tools** to reflect what was actually used in the investigation

## Analysis Period Documentation

Always include in reports:

```markdown
**Log Period:** [Start Date] to [End Date] (7 days)
**Log Files Analyzed:**
- Nginx: access.log through access.log.7.gz
- PHP-FPM: error.log through error.log.7.gz
- MySQL: mysql-slow.log through mysql-slow.log.7.gz
**Total Requests Analyzed:** [Count] requests
```

## File Organization

All reports saved to: `~/Documents/Sentry Reports/{pod-id}/`

```
~/Documents/Sentry Reports/
├── 402850/
│   ├── pod-402850-traffic-influx-root-cause-analysis.md
│   ├── pod-402850-traffic-influx-evidence.md
│   ├── pod-402850-504-errors-root-cause-analysis.md
│   └── pod-402850-504-errors-evidence.md
├── 227383/
│   ├── pod-227383-downtime-report.md
│   └── pod-227383-downtime-evidence.md
└── 225190/
    ├── pod-225190-health-report.md
    └── pod-225190-health-evidence.md
```

Create folders before saving: `mkdir -p ~/Documents/"Sentry Reports"/{pod-id}/`

## Naming Convention

- Customer-facing: `pod-[ID]-[issue]-rootcause.md`
- Evidence file: `pod-[ID]-[issue]-evidence.md` (or `-data.md`)

## Prohibited Content Reminder

**NEVER include in customer-facing reports:**
- Pod specs: worker counts, CPU cores, memory, BSPH, capacity ranges
- System metrics: CPU, memory, disk I/O (utility server data)
- Pricing, costs, ROI, financial analysis
- Managed infrastructure recommendations: rate limiting, Redis, CDN, PHP-FPM config, Nginx config, DB tuning

**Always attribute to:** "Sentry Ai Analysis"
