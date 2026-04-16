# Pod Report — Evidence File & Root Cause Report Generation

Use when all analysis skills have run and you're ready to generate final deliverables — evidence file, root cause report, Zendesk response, and verification card. Also use standalone when you have raw data and need to format it into the standard report set. This is the Narrator's output skill within `/investigate`.

## Required Input

**Pod number** — provided by the user (e.g., "213646")

Optional:
- **Customer context** — what the customer is experiencing or asking about (e.g., "site is slow", "need to justify a third server", "502 errors during peak hours")
- **Zendesk ticket text** — the original AM request from Zendesk. If provided, extract: AM first name, account name, business vertical, specific concerns, and questions to answer. This drives the Zendesk response (Report 3).
- **Pod type** — single-install vs reseller/multi-install
- **Combined pods** — if analyzing multiple pods together (e.g., "213646 and 212147")

## Pre-Flight: Gather Evidence

Check for existing evidence files in `~/Documents/Sentry Reports/{pod-id}/`:

```bash
ls ~/Documents/"Sentry Reports"/{pod-id}/
```

Look for:
- `pod-{id}-error-evidence.md` — from `/error-analysis`
- `pod-{id}-traffic-evidence.md` — from `/traffic-profile`
- `pod-{id}-mysql-evidence.md` — from `/mysql-analysis`
- `pod-{id}-endpoints-evidence.md` — from `/wp-endpoints`
- `pod-metadata.json` — from `/pod-recon`

Read all available evidence files. If none exist, tell the user to run the analysis skills first:
> No evidence files found for pod {id}. Run `/pod-recon` first, then `/error-analysis`, `/traffic-profile`, `/mysql-analysis`, and `/wp-endpoints` to gather data.

---

## Report 1: Evidence File

**Filename:** `pod-{id}-performance-evidence.md`

The evidence file is the raw data backing for every claim in the root cause report. It is NOT customer-facing — it's for internal reference and auditability.

### Structure

```markdown
# Evidence File: Pod {pod-id} — {domain or "Reseller Server"} Performance Analysis

**Analysis Date:** {today's date}
**Analysis Period:** {date range from logs}

---

## Data Sources

| Source | Path | Coverage |
|--------|------|----------|
| Nginx access log (pipe-delimited) | {log_base_path} | {X} days |
| Nginx apachestyle log | {log_base_path} | {X} days |
| PHP-FPM error log | /nas/log/fpm/ | Current rotation |
| MySQL slow query log | /var/log/mysql/mysql-slow.log | {X} days |

**Log format:** Pipe-delimited (`|`), field {status_field} = status code, field {exec_time_field} = execution time, field {request_field} = request.
**Utility server:** {ssh_host}
**Install count:** {count}

---

## Evidence: {Section Title}

{Raw data: counts, tables, command output, ranked lists}
{Each section corresponds to a finding in the root cause report}

---

**Report Prepared By:** Sentry Ai Analysis
**Analysis Date:** {today's date}
```

### Evidence Sections to Include

Pull from evidence files and organize by topic:
1. **Daily Traffic Volume** — total requests, by-day breakdown, weekday vs weekend
2. **BSP (Billable Server Processing)** — total BSP (seconds), BSPH (hours), BSP breakdown by request type, BSP by install (reseller pods)
3. **Dynamic vs Total Traffic** — apache access log counts vs nginx counts, cache hit rate
4. **HTTP Status Code Distribution** — full week
5. **Error Details** — 502/503/504/499/429 by day, by install, by URL, by IP
6. **WordPress Endpoints** — wp-login, xmlrpc, wp-cron, admin-ajax, wp-json volumes AND BSP per endpoint
7. **Slow Execution Times** — slowest requests, >5s count, >10s by install
8. **User Agents** — top 20 agents with request counts
9. **MySQL Slow Queries** — by schema, by table, query details
10. **PHP-FPM Errors** — fatal + warning counts, by install
11. **Uncached Traffic** — by install (reseller pods)
12. **Any additional evidence** — scanner IPs, email signature patterns, etc.

---

## Report 2: Root Cause Report

**Filename:** `pod-{id}-performance-rootcause.md`

This is the customer-facing report. It must be clear, evidence-backed, and actionable.

### Structure

```markdown
# Root Cause Analysis: Pod {pod-id} — {domain or description}

**Analysis Date:** {today's date}
**Analysis Period:** {date range}
**Total Requests Analyzed:** {total}

---

## Executive Summary

{2-4 sentences identifying the primary root cause and its impact. Lead with the single most important finding. Be direct — "The root cause is X" not "After analysis we found that..."}

---

## Finding 1: {Title} (CRITICAL|HIGH|MEDIUM|LOW|INFORMATIONAL)

**What's happening:** {Plain language — what a site owner would understand}

**Impact:** {Business/user impact — why this matters}

**Evidence:**
{Bullet points with specific numbers, log excerpts, data points}

**Recommended action:**
{Concrete steps — not vague suggestions}

---

{Repeat for each finding, ordered by severity}

---

## WordPress Endpoint Health

| Endpoint | Weekly Requests | Assessment |
|----------|----------------|------------|
| admin-ajax.php | X | {Healthy/Elevated/Critical} |
| xmlrpc.php | X | {Healthy/Abuse detected} |
| wp-cron.php | X | {Healthy/Elevated/Excessive} |
| wp-login.php | X | {Healthy/Brute force} |
| wp-json | X | {Healthy/Enumeration} |

---

## PHP-FPM Error Summary

```
X PHP Fatal errors
X PHP Warnings
```

---

## Capacity Assessment and Recommendation

### {Assessment Title}

{Analysis of whether the server's issues are capacity-related or application-level}

| Metric | Value |
|--------|-------|
| {key metrics} | {values} |

### Server Upgrade Recommendation

{Clear YES or NO with justification}

{If YES — what upgrade addresses and what application fixes are still needed}
{If NO — what application-level changes will resolve the issues}

---

**Report Prepared By:** Sentry Ai Analysis
**Analysis Date:** {today's date}
**Analysis Period:** {date range}

**Error Totals:**
- {code}: {count} ({description})
{repeat for each error code}

**Analysis Tools:** Server-side log parsing (nginx access/apachestyle, PHP-FPM error, MySQL slow query)
**Data Sources:** {log paths}
```

---

## Finding Severity Guidelines

| Severity | Criteria |
|----------|----------|
| **CRITICAL** | Causing active downtime, data loss risk, or >50% of traffic is problematic |
| **HIGH** | Significant performance degradation, PHP worker saturation, cascading failures |
| **MEDIUM** | Notable resource consumption but not causing outages; security scanning, elevated cron |
| **LOW** | Minor issues; small error counts, informational security findings |
| **INFORMATIONAL** | Historical events, observations, no current action needed |

---

## Report Content Rules

### DO Include
- Plan tier name (e.g., "P2 plan") — tier only, never worker counts
- HTTP request counts, error rates, execution times, traffic patterns
- PHP-FPM and database query errors from logs
- Per-install attribution (reseller pods)
- Specific plugin/theme names causing issues
- WP Engine documentation links for relevant topics
- Actionable recommendations: plugin updates, code optimization, CDN for static assets

### DO NOT Include
- System resource metrics (CPU, memory, disk I/O) — these are utility server data
- Pod configuration details (worker counts, CPU cores, memory allocations, BSPH, capacity ranges)
- Pricing, costs, ROI calculations
- Recommendations for WP Engine managed infrastructure (rate limiting config, Redis, object cache config, PHP-FPM config, Nginx config, database tuning)
- Internal WP Engine tooling details

### WP Engine Documentation Links

Use these when relevant:
- Two-Factor Authentication: `https://wpengine.com/support/two-factor-authentication/`
- Web Rules Engine: `https://wpengine.com/support/web-rules-engine/`
- Platform Settings: `https://wpengine.com/support/platform-settings/`
- 504 Errors: `https://wpengine.com/support/resolving-504-gateway-timeout-errors/`
- 502 Errors: `https://wpengine.com/support/troubleshooting-502-error/`

---

## Server Upgrade Assessment Criteria

### BSP/BSPH Capacity Assessment

Use BSP data from `/traffic-profile` and `/wp-endpoints` to quantify capacity utilization:

1. **Calculate weekly BSPH:** Total BSP (seconds) / 3600 = BSPH for the week
2. **Calculate daily BSPH:** Weekly BSPH / 7 = average BSPH per day
3. **Compare against tier BSPH range** from `constants.py` (`bsph_min` to `bsph_max`)
4. **Calculate utilization:** Daily BSPH / tier `bsph_max` = capacity utilization percentage

Include in the Capacity Assessment table:

```markdown
| Metric | Value |
|--------|-------|
| Total weekly BSP | {X} seconds |
| Weekly BSPH | {X / 3600} hours |
| Daily avg BSPH | {weekly / 7} hours |
| Tier BSPH range | {min}–{max} |
| Capacity utilization | {%} |
| Top BSP consumer | {endpoint or install} ({%} of total) |
```

### BSP Waste Analysis

Break down BSP into legitimate vs waste processing:

- **Legitimate BSP:** Frontend page loads, WooCommerce transactions, REST API for app functionality, normal admin usage
- **Waste BSP:** Brute-force wp-login processing, XMLRPC abuse, runaway wp-cron, backup plugin polling, bot-generated PHP processing

If waste BSP is significant, calculate what BSPH would look like after remediation. This determines whether an upgrade is needed or if application fixes alone would bring the pod within its tier capacity.

### Upgrade Decision Criteria

**A server upgrade is justified when ALL of these are present:**
1. Evidence of PHP worker pool exhaustion (502/503 errors at scale)
2. Gateway timeout errors (504) correlating with traffic spikes
3. Request execution times showing queue backup
4. BSP/BSPH consistently exceeding tier capacity even after accounting for waste traffic
5. No single code-level issue causing the degradation

**A server upgrade is NOT recommended when:**
- A single application issue (email signature images, runaway plugin, SQL injection) is the root cause
- Fixing the application issue would reduce BSP/BSPH to within tier capacity
- Waste BSP accounts for >30% of total — remediate first, then reassess

**For reseller/multi-install pods:**
- Calculate BSP per install to identify disproportionate consumers
- Consider install density vs capacity
- Consider whether redistributing installs would help more than adding capacity
- Recommend both: capacity increase + application fixes (the most honest answer)

---

## Report 3: Zendesk Fact Find Response

**Filename:** `pod-{id}-zendesk-response.md`

This is the internal response to an Account Manager's Zendesk fact find ticket. It follows Madison's macro template exactly. The tone is colleague-to-colleague — conversational, direct, leads with the answer. NOT customer-facing.

### Optional Input: Zendesk Ticket Context

If the user provides the original AM request (ticket text, business context, specific questions), incorporate that context into the response. Reference the AM's specific concerns and answer their questions directly.

If no ticket context is provided, generate a standalone fact find response based purely on the log analysis findings.

### Structure

```markdown
Hey {AM_first_name},

Thank you for reaching out in regard to this FactFind. Below is the results and recommendation of my findings:



## Account

{account_name or primary install domain}

## {install_count} Installs

{space-separated list of all install names from pod-metadata.json}



## SE Recommendation

Based on the information provided as well as any available resource usage we can track this is the recommended solution for this customer:

**{Vertical}**

**Recommended Path: {recommended_tier} — Optimize First**
{1-3 sentences explaining what application-level fixes would resolve the issues and what the expected resource profile looks like after remediation. This is the "right" answer — fix the root cause.}

**Alternative Path: {higher_tier} — Address with Capacity**
{1-3 sentences explaining what tier would absorb the current load AS-IS, without any application fixes. Frame this as: "If the agency/customer is unable or unwilling to make the recommended application changes, a move to {tier} would provide enough headroom to absorb the current resource consumption including the waste traffic." This keeps the sale on the table.}

{If the data clearly shows ONLY a capacity problem (no waste BSP, no application issues), collapse both paths into a single upgrade recommendation. The dual-path is only needed when there are application-level issues that COULD be fixed but might not be.}



## Resource Utilization:

{Narrative description of observations from log analysis. Write this conversationally, as if explaining to a colleague. Include:
- Traffic volume and trends (daily avg, weekday vs weekend patterns)
- BSP/BSPH utilization and what's consuming it
- Error patterns (502/504/503 counts and what's causing them)
- Any notable spikes or anomalies
- Per-install attribution for the top consumers

Reference specific numbers but frame them as observations, not raw data dumps.

If bot traffic or brute force is detected, describe the pattern and its impact on resources.

If a single install is the noisy neighbor, call it out explicitly with the evidence.}

[PLACEHOLDER: Looker resource utilization screenshots — paste from WP Engine portal]



## Plugin/Theme Concerns

{Description of any application-level issues found:
- Slow MySQL queries (table names, query times, affected installs)
- Excessive wp-cron activity (which installs, what thresholds exceeded)
- PHP fatal errors or warnings (counts, affected installs)
- Backup plugin conflicts
- Known problematic plugins detected in logs

If no concerns found, state: "No significant plugin or theme concerns identified in the current log analysis."}



## Addons

X = No thank you
? = Questionable
O = Send it

[?] **APM** - Probably not a great fit here, unless they have a developer or other highly technical team member interested in wordpress backend performance observability. This tool can help the customer diagnose bottlenecks and optimize site performance.

[{ges_recommendation}] **GES** - {ges_explanation}
- **Security benefits** - DDOS protection, Managed Web Application Firewall (WAF)
- **Performance benefits** - Cloudflare CDN, Polish lossless image optimization & Argo smartrouting

[?] **PSB** - {psb_explanation or "N/A"}

[{ecom_recommendation}] **Ecom** - {ecom_explanation}

[O] **SPM** - Always a great option to help reduce the volume of hands on site management needed for the sites.
```

### Addon Decision Logic

**GES recommendation:**
- `[O]` (Send it) — if significant bot traffic, brute force attacks, or scanner probes detected. Explain: "Based on the volume of bot/malicious traffic observed ({X} requests from credential-stuffing botnets, {Y} scanner probes), GES would provide immediate value through its WAF and DDoS protection."
- `[?]` (Questionable) — if moderate bot traffic or the customer already has Cloudflare. Default to "N/A" with the standard security/performance benefits listed.
- `[X]` (No) — rare, only if traffic is extremely clean and low-volume.

**Ecom recommendation:**
- `[O]` — if WooCommerce endpoints detected in logs (`/cart`, `/shop`, `/product`, `wc-ajax`, `wc-api`)
- `[X]` — "Not an ecom site, no need for this addon's tools." (default if no WooCommerce traffic detected)

**APM recommendation:**
- Default `[?]` with standard boilerplate unless the AM's ticket indicates a highly technical customer team.

**PSB recommendation:**
- Default `[?]` with "N/A" unless specific page performance concerns are raised in the ticket.

**SPM recommendation:**
- Always `[O]` — this is a universal recommendation.

### Tier Recommendation Logic

Use BSP/BSPH data from the analysis to determine the recommended tier:

1. Calculate daily BSPH from total BSP
2. Find the tier where daily BSPH falls within the `bsph_min`–`bsph_max` range in `constants.py`
3. Consider growth headroom — recommend the tier that gives room to grow, not the minimum viable tier
4. Factor in waste BSP — if remediation would significantly reduce BSPH, recommend based on post-remediation estimates

**Dual-path recommendation (default when waste BSP is present):**

Always provide two paths when application-level issues exist:

1. **Recommended Path (Optimize First):** Calculate post-remediation BSPH by subtracting identifiable waste BSP (brute force, excessive cron, bad queries). Find the tier that fits the post-remediation daily BSPH with growth headroom. This is the "right" answer.

2. **Alternative Path (Address with Capacity):** Calculate the tier needed to absorb CURRENT daily BSPH as-is, without any fixes. This is the "pay your way out" option. Frame it neutrally — don't discourage it, just present the trade-off: more cost but no application work required.

**Single-path recommendation (when no waste BSP):**
If the analysis shows clean traffic with no significant waste, just recommend the appropriate tier directly. No need for dual paths.

**Framing guidance:**
- Lead with the recommended path (optimize) — it's the better technical answer
- Present the alternative path as a valid business decision, not a failure
- Never include pricing — the AM has that. Just name the tier.
- For reseller/agency pods, factor in install density and whether specific installs could be redistributed

### Optional: How to Position (AM Coaching)

When the findings are complex, counterintuitive, or likely to disappoint the AM's expectations (e.g., the data doesn't support an upgrade they were hoping for, or a security issue overshadows the original concern), add a `## How to Position` section after the Addon grid.

This section coaches the AM on how to frame the conversation with their customer. It should:
- Suggest an opening line or framing for the customer conversation
- Anticipate objections ("the customer came in expecting an upgrade...")
- Clarify what an upgrade would and wouldn't fix
- Help the AM deliver tough news constructively (e.g., malware, code issues)

```markdown
## How to Position

{Coaching paragraph — how to frame the findings for the customer.
Example: "The customer came in expecting an upgrade recommendation. The data shows their server is handling the load fine — the problems are in their theme code and bot traffic. Lead with the good news: they can fix this without spending more on infrastructure. Then position GES as the protection layer and the theme fix as something their dev team needs to address."}
```

**This section is additive** — it must never replace the structured sections above (Account, Installs, SE Recommendation, Resource Utilization, Plugin/Theme Concerns, Addons). Include it after Addons when it adds value; omit it when the findings are straightforward.

### Tone and Style Rules

- **Address the AM by first name** — "Hey Kelly," "Hey Justin,"
- **Conversational but professional** — write like you're talking to a colleague at your desk
- **Lead with the answer** — recommendation first, evidence second
- **Be honest** — if the data doesn't support an upgrade, say so. If the AM's concerns don't match the evidence, ask clarifying questions.
- **Ask follow-up questions** when data is ambiguous — e.g., "Could you expound further on the 'outages' mentioned previously?"
- **Don't pad** — if GES/PSB/APM aren't clearly relevant, mark them "N/A" rather than fabricating justification
- **Never include**: worker counts, BSPH ranges, internal capacity metrics, or pricing. The AM has access to those through their own tools.

---

## Combined Pod Reports

When analyzing multiple pods for the same customer:
- Use a single root cause report covering both pods
- **Filename:** `pods-{id1}-{id2}-performance-rootcause.md`
- Compare metrics side-by-side in tables
- Identify shared attack patterns (same botnet IPs on both pods)
- Include separate evidence files per pod

---

## Report 4: Verification Card

**Filename:** `pod-{id}-verification-card.md`

The verification card is a quality gate between the AI analysis and the SE's final review. It lists every key claim made in the root cause report, a verdict on whether the data supports it, and a checklist of items only a human SE can verify (Looker screenshots, wpeapi calls, AM name, customer conversations).

### Structure

```markdown
# Verification Card: Pod {pod-id} — {install} ({account_name})
**Ticket Type:** {brief description of what was analyzed}
**AM:** [AM_first_name] | **Account:** {account_name} ({vertical})

---

## Key Claims to Verify

| # | Claim | Verdict | Where to Look |
|---|-------|---------|---------------|
| 1 | {claim from ticket or report} | **{Confirmed/Partially/Not Confirmed/Contradicted}** — {1-2 sentence explanation with data} | [Finding X](pod-{id}-rootcause.md#finding-x), [Evidence: Section](pod-{id}-evidence.md#section) |
| 2 | ... | ... | ... |

---

## SE Should Verify

- [ ] **Server tier** — `wpeapi server-meta {pod-id} sales_offering historical=True`
- [ ] **Looker resource utilization** — Paste PHP Performance screenshots
- [ ] **AM name** — Replace `[AM_first_name]` placeholder in Zendesk response
- [ ] {additional items specific to this investigation}

---

## AI Flags

- **{Flag title}** — {Explanation of something surprising, counterintuitive, or high-risk that the SE should be aware of before sending the report. These are the "watch out for this" notes.}
- ...
```

### Claim Verdicts

| Verdict | When to Use |
|---------|-------------|
| **Confirmed** | Data fully supports the claim |
| **Partially** | Data partially supports but with caveats (e.g., "504s exist but 82% are scanner noise") |
| **Not Confirmed** | No evidence found to support the claim (e.g., "WooCommerce mentioned but not installed") |
| **Contradicted** | Data actively contradicts the claim (e.g., "customer says site is down but only 11 504s today") |

### AI Flags Guidelines

AI flags should capture insights that are:
- **Surprising** — "82% of 504s were a vulnerability scanner, not real traffic"
- **Counterintuitive** — "The install IS the noisy neighbor, not a victim"
- **High-risk if missed** — "WooCommerce is NOT installed despite AM mentioning it"
- **Context the SE needs** — "P1 + GES only works IF they optimize the calendar queries"
- **Reframing** — "Don't lead with the 504 count — lead with the 14.1% cache rate"

Aim for 5-10 flags per investigation. Each should be actionable — the SE should be able to read it and know what to do differently.

---

## Attribution

**Always use:** `**Report Prepared By:** Sentry Ai Analysis`

**Never use:** "Claude", "Claude Code", "AI Analysis", or any generic attribution.

The full attribution block at the end of the report (Error Totals, Analysis Tools, Data Sources) is required — never replace it with an inline italic footnote.
