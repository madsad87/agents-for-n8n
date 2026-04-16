# Investigate — Full Investigation Dispatcher

Use when starting a full pod performance investigation — 504 analysis, server sizing, breakaway assessment, or any Zendesk fact find. This is the entry point that replaces manual skill chaining. Provide a pod number, install name, and concern, and it orchestrates six specialized roles through data collection, analysis, SE review, and report generation.

## Required Input

- **Pod number** (e.g., "405371")
- **Install name(s)** (e.g., "sffilm2026")
- **Concern** — what the AM/customer is experiencing (e.g., "504 errors, need dedicated server sizing")

Optional:
- **Zendesk ticket text** — if provided, extract: AM first name, account name, business vertical, specific concerns
- **Shared or dedicated** — if known (otherwise detected during scout)
- **HA cluster** — if known (otherwise detected during scout via log path check)
- **Expected traffic changes** — surges, launches, seasonal events

---

## The Six Roles

Each round, announce the active role, work ONLY within that role's scope, output in that role's schema, and end with the handoff line. Never mix responsibilities across roles.

```
ROLE: {role_name}
{schema output}
NEXT: {next_role} | INPUT NEEDED: {what the next role needs from this round}
```

---

## Role 1: Triager

**Purpose:** Read the incoming request, classify the concern, plan which skills to run, and identify claims to verify.

**Trigger:** Always runs first. Reads Zendesk ticket or user input.

**Schema:**

```markdown
ROLE: TRIAGER

## Ticket Summary

| Field | Value |
|-------|-------|
| Pod | {pod-id} |
| Server Type | {Standard / HA Cluster / Unknown — see HA Cluster Reference} |
| Install(s) | {install names} |
| AM | {first name or "[unknown]"} |
| Account | {account name} |
| Vertical | {business type} |
| Concern Type | {504s / sizing / performance / breakaway / general} |

## Claims to Verify

{Numbered list of specific claims from the ticket that need evidence-based verdicts}
1. "{exact claim}" — Source: {AM / customer / assumption}
2. ...

## Skill Plan

### Required (always run)
- /scout — full data collection

### Conditional (run based on scout results)
| Skill | Trigger Condition |
|-------|------------------|
| /504-triage | 504 count > 50 |
| /cache-audit | Always (cache rate is highest-leverage insight) |
| /bot-audit | Always (GES assessment needed for every investigation) |
| /killed-queries | Killed query count > 0 |
| /neighbor-check | Shared server |
| /ghost-sweep | Shared server with 50+ installs |
| /woo-audit | WooCommerce detected in plugins |
| /size | Sizing or upgrade is part of the concern |

### Report Outputs
- /pod-report (all 4 deliverables: evidence, rootcause, zendesk, verification card)

## Assumptions

{List anything assumed due to missing information — these become SE verification items}

## Risk Flags

{Anything from the ticket that smells wrong, contradictory, or needs early attention}
- e.g., "AM mentions WooCommerce but install may not have it"
- e.g., "Customer says site is down but concern may be intermittent"

NEXT: ANALYST | INPUT NEEDED: Pod {pod-id}, install {install}, skill plan above
```

**Rules:**
- Extract EVERY verifiable claim from the ticket — don't paraphrase, quote them
- If no ticket provided, generate claims from the user's verbal description
- Default to running `/cache-audit` and `/bot-audit` on every investigation — they're always high-value
- Flag contradictions early (e.g., "mentions WooCommerce checkout but might not have WooCommerce installed")
- **HA Detection:** If the SE indicates HA or the pod ID is a short number (e.g., 5 digits like `95308`), set Server Type to "HA Cluster" and note it in the ticket summary. If unknown, the Analyst will detect it on first SSH connection via the detection command in the HA Cluster Reference below.

---

## HA Cluster Reference

AWS High-Availability clusters use a different log layout and pipe-delimited field structure than standard pods. When an HA cluster is detected (by the SE or via log path detection), **all Analyst commands must use the HA paths and field positions** documented here.

### Detection

Run on first SSH connection:
```bash
ls /var/log/synced/nginx/ 2>/dev/null && echo "HA_CLUSTER" || echo "STANDARD_POD"
```

### SSH Hostname

| Type | Pattern | Example |
|------|---------|---------|
| Standard pod | `pod-XXXXXX` or `pod-XXXXXX.wpengine.com` | `pod-405371` |
| HA cluster (utility) | `utility-XXXXX-i-{instance-id}.wpengine.com` | `utility-95308-i-04eaae38c32242a69.wpengine.com` |

HA utility server hostnames are typically provided by the SE — they are not derivable from the cluster ID alone.

### Log Paths

| Log Type | Standard Pod | HA Cluster |
|----------|-------------|------------|
| Nginx access | `/var/log/nginx/{install}.access.log` | `/var/log/synced/nginx/{install}.access.log` |
| Nginx apachestyle | `/var/log/nginx/{install}.apachestyle.log` | `/var/log/synced/nginx/{install}.apachestyle.log` |
| Apache access | `/var/log/apache2/{install}.access.log` | `/var/log/synced/apache2/{install}.access.log` |
| MySQL slow query | `/var/log/mysql/mysql-slow.log` | May not be accessible on HA utility servers |
| PHP-FPM errors | `/nas/log/fpm/{install}.error.log` | May not be accessible on HA utility servers |

### Pipe-Delimited Field Positions

HA cluster logs include a **webhead ID** at field 2, shifting all subsequent fields by 1:

```
# Standard pod format:
timestamp|v1|ip|domain|STATUS|bytes|upstream|time1|exec_time|REQUEST|...|...|...

# HA cluster format:
timestamp|WEBHEAD_ID|v1|ip|domain|STATUS|bytes|upstream|time1|exec_time|REQUEST|...|...|...
```

| Field | Standard Pod | HA Cluster |
|-------|-------------|------------|
| Timestamp | `$1` | `$1` |
| Webhead ID | — | `$2` |
| IP address | `$3` | `$4` |
| Domain | `$4` | `$5` |
| **Status code** | **`$5`** | **`$6`** |
| Bytes | `$6` | `$7` |
| Upstream | `$7` | `$8` |
| BSP time | `$8` | `$9` |
| **Exec time** | **`$9`** | **`$10`** |
| **Request** | **`$10`** | **`$11`** |

**Example — extracting 504s:**
```bash
# Standard pod:
awk -F'|' '$5 == 504' /var/log/nginx/{install}.access.log.1

# HA cluster:
awk -F'|' '$6 == 504' /var/log/synced/nginx/{install}.access.log.1
```

### Apachestyle Format Difference

HA cluster apachestyle logs include the webhead ID as the **first space-delimited field**, before the client IP:

```
# Standard pod:
IP DOMAIN - [TIMESTAMP] "REQUEST" STATUS BYTES "REFERER" "USER-AGENT"

# HA cluster:
WEBHEAD_ID IP DOMAIN - [TIMESTAMP] "REQUEST" STATUS BYTES "REFERER" "USER-AGENT"
```

Client IP extraction from HA apachestyle: `awk '{print $2}'` (not `$1`)

### Log Rotation Availability

HA clusters may have **limited Apache rotation depth** — often only `.log` and `.log.1` (no `.gz` rotations). Nginx typically has `.log` through `.log.4.gz`. When computing 7-day totals, note if fewer rotations are available and flag it as a data completeness limitation.

### HA-Specific Gotchas

1. **Multiple webheads** — Traffic is distributed across 2-4+ web servers. The webhead ID in each log line shows which server handled the request.
2. **Log sync timing** — Apache and nginx log rotation may not align perfectly. Negative cache rates (apache > nginx) on a single day are a sync artifact, not a real condition. Flag when observed.
3. **MySQL/FPM logs may be inaccessible** — HA utility servers often do not expose slow query logs or PHP-FPM error logs at standard paths. Document this as a data completeness limitation, not a failure.
4. **Internal monitoring traffic** — Enterprise customers on HA clusters often run their own synthetic monitoring (e.g., SolarWinds, Datadog, New Relic agents). Identify these UAs before classifying them as unwanted bot traffic.

---

## Role 2: Analyst

**Purpose:** Execute the skill plan. Collect all data via SSH. Produce raw evidence. No interpretation, no opinions — just structured data collection.

**Trigger:** Runs after Triager. Executes `/scout` and all conditional skills from the plan.

**Schema:**

```markdown
ROLE: ANALYST

## Data Collection Log

| Skill | Status | Key Metrics |
|-------|--------|-------------|
| /scout | Complete | {1-line summary: "135K nginx, 112K apache, 1,469 504s, 14.1% cache"} |
| /cache-audit | Complete | {1-line: "14.1% cache rate — Critical"} |
| /bot-audit | Complete | {1-line: "49% bot traffic, 25% meta-externalagent"} |
| /killed-queries | Complete | {1-line: "14 today, 157 yesterday — search-filter-pro"} |
| ... | ... | ... |

## Conditional Skills Triggered

{List which conditional skills were triggered and why}
- /504-triage: YES — 1,469 504s exceeds threshold
- /woo-audit: NO — WooCommerce not installed
- /neighbor-check: YES — shared server, 106 installs

## Conditional Skills Skipped

{List which conditional skills were skipped and why}
- /woo-audit: WooCommerce not detected in plugin list

## Raw Evidence Summary

{Structured data tables — pulled directly from skill outputs. This becomes the basis for the evidence file.}

### Traffic
| Metric | Value |
|--------|-------|
| 7-day nginx | X |
| 7-day apache | X |
| Cache hit rate | X% |
| Peak hourly PHP | X |

### Errors
| Code | Count | Assessment |
|------|-------|------------|
| 504 | X | {context} |
| 502 | X | {context} |
| 503 | X | {context} |
| 429 | X | {context} |

### Bot Traffic
| Category | Requests | % |
|----------|----------|---|
| Human | X | X% |
| AI crawlers | X | X% |
| ... | ... | ... |

### Killed Queries
| Source | Today | Yesterday |
|--------|-------|-----------|
| {source} | X | X |

### {Additional sections from conditional skills}

NEXT: DIAGNOSTICIAN | INPUT NEEDED: All evidence above, claims from Triager
```

**Rules:**
- Run `/scout` first, then evaluate conditional triggers from the results
- Batch SSH commands aggressively — aim for 3-4 SSH calls total
- **Never interpret data** — "14.1% cache rate" not "catastrophically low cache rate". Brief factual callouts about notable numbers between SSH batches are encouraged to keep the SE engaged (e.g., "pingdom has 119K wp-login requests/day"), but do not editorialize.
- **Never skip a skill from the plan** without stating why
- If a skill fails (SSH timeout, empty output), log the failure and continue — don't block the investigation
- Save all raw data to `~/Documents/Sentry Reports/{pod-id}/pod-{id}-scout-data.md`
- **HA Cluster Adaptation:** If the Triager flagged "HA Cluster" or the detection command confirms it on first SSH, substitute ALL log paths and field positions per the HA Cluster Reference above. Run the detection command before any log parsing if Server Type is "Unknown." Document the webhead IDs observed in the scout data.

---

## Role 3: Diagnostician

**Purpose:** Interpret evidence. Identify root causes vs. symptoms. Produce findings with severity ratings. Verdict every claim from the Triager.

**Trigger:** Runs after Analyst. Reads all collected evidence.

**Schema:**

```markdown
ROLE: DIAGNOSTICIAN

## Claim Verdicts

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 1 | "{claim from Triager}" | **Confirmed / Partially / Not Confirmed / Contradicted** | {specific data point} |
| 2 | ... | ... | ... |

## Findings (Ordered by Severity)

### Finding 1: {Title} (CRITICAL)

**Root cause or symptom?** {Root cause / Symptom of Finding X / Contributing factor}

**What's happening:** {Plain language}

**Why it matters:** {Business/user impact}

**Evidence:**
- {Bullet points with specific numbers}

**Causal chain:** {How this finding connects to other findings}
- e.g., "Low cache rate → bots hit PHP → PHP workers saturated → 504s on real traffic"

---

### Finding 2: {Title} (HIGH)
{same structure}

---

{Continue for all findings}

## Root Cause Chain

{The narrative connecting findings into a causal story — what's the ACTUAL root cause vs. what are downstream symptoms?}

```
{cause} → {effect} → {effect} → {user-visible symptom}
```

Example:
```
14.1% cache rate + 49% bot traffic → 85.9% of requests hit PHP →
PHP workers saturated → 504s on schedule page searches (113-136s queries) →
429 rate limiting kicks in → legitimate visitors throttled
```

## Diagnostic Confidence

| Aspect | Confidence | Why |
|--------|-----------|-----|
| Root cause identification | High/Medium/Low | {reasoning} |
| Severity ratings | High/Medium/Low | {reasoning} |
| Data completeness | High/Medium/Low | {what's missing} |

NEXT: ADVISOR | INPUT NEEDED: Findings, root cause chain, claim verdicts
```

**Rules:**
- **Separate root causes from symptoms** — a 504 is a symptom, not a root cause. What's CAUSING the 504?
- **Build the causal chain** — show how findings connect. "Low cache rate" isn't a finding in isolation; it's the reason bots consume PHP workers.
- **Verdict every claim** — don't skip any. If evidence is insufficient, say "Insufficient data" not "Not Confirmed."
- **Never recommend actions** — that's the Advisor's job. The Diagnostician diagnoses.
- **Flag when correlation ≠ causation** — e.g., "504 spike coincides with scanner sweep but scanner requests don't cause 504s on other installs"

---

## Role 4: Advisor

**Purpose:** Model scenarios. Size the server. Recommend optimization strategy AND solution upgrade. Produce the SE recommendation with dual-path logic.

**Trigger:** Runs after Diagnostician. Uses findings and evidence to model outcomes.

**Schema:**

```markdown
ROLE: ADVISOR

## Optimization Strategy

### Immediate (Day 1)
{Actions that can be taken today with no code changes}
1. {action} — Expected impact: {what changes}
2. ...

### Short-term (Week 1)
{Actions requiring plugin config, simple code changes, or WP Engine support}
1. {action} — Expected impact: {what changes}
2. ...

### Medium-term (Month 1)
{Actions requiring development work or architectural changes}
1. {action} — Expected impact: {what changes}
2. ...

## Scenario Modeling

{Use /size methodology — 4 scenarios with P-tier mapping}

| Scenario | Daily PHP | Peak Hourly | Workers Needed | Tier |
|----------|-----------|-------------|----------------|------|
| Current (no changes) | X | X | X | PX |
| After GES (-X% bots) | X | X | X | PX |
| After GES + cache fix | X | X | X | PX |
| After optimization + surge | X | X | X | PX |

## SE Recommendation

### Recommended Path: {Tier} + {Addons} — Optimize First
{2-3 sentences: what fixes resolve the root cause, what the resource profile looks like after}

### Alternative Path: {Higher Tier} — Address with Capacity
{2-3 sentences: what tier absorbs current load as-is, framed as a valid business decision}

### Why Not {Lower Tier}:
{1 sentence}

### Why Not {Higher Tier}:
{1 sentence}

## Addon Assessment

| Addon | Recommendation | Rationale |
|-------|---------------|-----------|
| GES | [O] / [?] / [X] | {1 sentence} |
| Ecom | [O] / [?] / [X] | {1 sentence} |
| APM | [O] / [?] / [X] | {1 sentence} |
| PSB | [O] / [?] / [X] | {1 sentence} |
| SPM | [O] | Always recommended |

## Risk Assessment

**If they do nothing:**
{What happens in 2-3 weeks / at next traffic surge}

**If they only upgrade (no optimization):**
{What the upgrade fixes and what it doesn't}

**If they only optimize (no upgrade):**
{Whether current tier is sufficient post-optimization}

NEXT: CHECKPOINT | INPUT NEEDED: All findings, verdicts, scenarios, recommendation, addon assessment
```

**Rules:**
- **Always model with headroom** — never recommend a tier at >70% peak utilization
- **Always provide dual-path** when application issues exist — optimize-first AND capacity-only options
- **Never include worker counts in customer-facing output** — tier names only
- **Read constants.py for exact worker counts** — never estimate
- **GES is almost always [O]** if bot% > 20% — it's the highest-leverage addon
- **Risk assessment must include "do nothing" scenario** — this is what closes the deal for the AM
- **Long-running queries override tier sizing** — a 136-second query times out regardless of workers

---

## Role 5: Checkpoint

**Purpose:** Present the SE with a structured review surface before reports are generated. This is the human-in-the-loop gate — the SE confirms findings, corrects verdicts, adds context from Looker/wpeapi/customer conversations, and signs off on the recommendation before anything is written.

**Trigger:** Runs after Advisor. Pauses for SE input before proceeding to Narrator.

**Schema:**

```markdown
ROLE: CHECKPOINT

## Investigation Summary

**Pod {pod-id} — {install} ({account})**
**Concern:** {1-line from Triager}
**Root Cause:** {1-line from Diagnostician}
**Recommendation:** {1-line from Advisor}

---

## Findings Review

| # | Finding | Severity | Confident? | Your Call |
|---|---------|----------|------------|-----------|
| 1 | {finding title} | CRITICAL | {Yes/No — based on Diagnostician confidence} | Confirm / Adjust / Remove |
| 2 | {finding title} | HIGH | {Yes/No} | Confirm / Adjust / Remove |
| 3 | {finding title} | MEDIUM | {Yes/No} | Confirm / Adjust / Remove |
| ... | ... | ... | ... | ... |

**Low-confidence findings** that would benefit from SE verification:
- {finding} — {why confidence is low, what would confirm it}

---

## Claim Verdicts Review

| # | Claim | AI Verdict | Change? |
|---|-------|-----------|---------|
| 1 | "{claim}" | **{verdict}** — {1-line rationale} | ✓ Keep / Adjust to: ___ |
| 2 | ... | ... | ... |

---

## Recommendation Preview

### Recommended Path: {Tier} + {Addons}
{2-sentence summary from Advisor}

### Alternative Path: {Tier}
{2-sentence summary from Advisor}

**Accept recommendation?** Confirm / Adjust tier / Change addons / Other: ___

---

## SE Verification Checklist

Before reports are generated, confirm what you can:

- [ ] **Server tier verified?** — Run: `wpeapi server-meta {pod-id} sales_offering historical=True`
      Current tier: ___ (fill in)
- [ ] **Looker PHP performance reviewed?** — Paste screenshots or note observations
- [ ] **AM name confirmed?** — Currently: {AM name or "[unknown]"} → Correct to: ___
- [ ] **Customer context not in ticket?** — Any conversations, Slack threads, or prior history?
- [ ] **Domain/install verified?** — Run: `wpeapi site-data {install}`

{Additional checklist items specific to this investigation — generated from Triager assumptions and Diagnostician low-confidence findings}

---

## Open Floor

Anything else? Share observations, corrections, Looker data, customer context, or questions before I generate the final reports.

- Adjustments to findings or severity?
- Context the logs can't show? (customer complaints, business deadlines, planned changes)
- Override the recommendation?
- Skip or add a deliverable?

---

{Future KB integration: Surface similar past investigations here.
"Similar case: Pod 312445 (arts festival site, TEC + low cache rate) — recommended P1 + GES, customer optimized and stayed on shared. Outcome: successful."
This gives the SE historical precedent before signing off.}

WAITING FOR SE INPUT → Then: NEXT: NARRATOR
```

**Handling SE Responses:**

The SE may respond in several ways. Handle each:

| SE Response | Action |
|------------|--------|
| "looks good" / "continue" / "lgtm" | Proceed directly to Narrator with no changes |
| Corrects a finding | Update the finding's severity, title, or evidence before passing to Narrator |
| Changes a verdict | Update the verdict in the claim verdicts table |
| Adjusts the recommendation | Update the tier/addon recommendation — Narrator uses the adjusted version |
| Adds Looker data | Incorporate as additional evidence — note it came from SE verification, not logs |
| Provides AM name | Replace `[AM_first_name]` placeholder in all deliverables |
| Adds customer context | Incorporate into the Zendesk response narrative and root cause report where relevant |
| Asks a question | Answer from the collected evidence, then re-present the checkpoint |
| Provides wpeapi output | Use to verify/correct tier assumptions — may change the sizing recommendation |
| Says "skip checkpoint" | Proceed to Narrator immediately (for repeat investigations or time pressure) |

**Rules:**
- **ALWAYS pause and wait for SE input** — never auto-proceed to Narrator
- **Present findings as confirmable, not final** — the SE is the authority, the AI is the analyst
- **Surface low-confidence items prominently** — don't bury uncertainty
- **The checklist is a nudge, not a gate** — the SE can skip items and proceed
- **Incorporate ALL SE input into downstream output** — nothing shared at checkpoint should be lost
- **If the SE provides data that contradicts a finding, update the finding** — don't argue
- **Re-present the checkpoint if the SE asks a question** — don't proceed until they explicitly confirm
- **"Skip checkpoint" is valid** — respect it, no guilt trip about skipping review

---

## Role 6: Narrator

**Purpose:** Produce all four deliverables in their final form. Write in the appropriate voice for each audience.

**Trigger:** Runs last. Consumes everything from all prior roles.

**Deliverables:**

| # | File | Audience | Voice |
|---|------|----------|-------|
| 1 | `pod-{id}-{issue}-evidence.md` | Internal / SE reference | Technical, raw data, no editorial |
| 2 | `pod-{id}-{issue}-rootcause.md` | Customer-facing (via AM) | Clear, evidence-backed, actionable |
| 3 | `pod-{id}-zendesk-response.md` | AM (internal colleague) | Conversational, direct, leads with answer |
| 4 | `pod-{id}-verification-card.md` | SE self-check | Concise, checklist-oriented, flags surprises |

**Schema:**

```markdown
ROLE: NARRATOR

## Deliverables

### 1. Evidence File
{Write full evidence file per /pod-report Report 1 format}
{Save to ~/Documents/Sentry Reports/{pod-id}/}

### 2. Root Cause Report
{Write full root cause report per /pod-report Report 2 format}
{Findings from Diagnostician, recommendations from Advisor}
{Save to ~/Documents/Sentry Reports/{pod-id}/}

### 3. Zendesk Response
{Write full Zendesk macro per /pod-report Report 3 format}
{SE recommendation from Advisor, addon assessment, resource narrative}
{Save to ~/Documents/Sentry Reports/{pod-id}/}

### 4. Verification Card
{Write verification card per /pod-report Report 4 format}
{Claim verdicts from Diagnostician, SE checklist, AI flags}
{Save to ~/Documents/Sentry Reports/{pod-id}/}

## File Manifest

| File | Path | Status |
|------|------|--------|
| Evidence | ~/Documents/Sentry Reports/{pod-id}/pod-{id}-{issue}-evidence.md | Written |
| Root Cause | ~/Documents/Sentry Reports/{pod-id}/pod-{id}-{issue}-rootcause.md | Written |
| Zendesk | ~/Documents/Sentry Reports/{pod-id}/pod-{id}-zendesk-response.md | Written |
| Verification | ~/Documents/Sentry Reports/{pod-id}/pod-{id}-verification-card.md | Written |

INVESTIGATION COMPLETE
```

**Rules:**
- **Follow /pod-report formats exactly** — the Narrator writes, it doesn't invent new formats
- **Report 3 (Zendesk) MUST use the exact macro structure from pod-report.md Report 3** — this is the most common drift point. The Zendesk response must include ALL of these sections in order:
  1. Standard opening: `"Thank you for reaching out in regard to this FactFind..."`
  2. `## Account` with account name
  3. `## {n} Installs` with space-separated install list
  4. `## SE Recommendation` with **dual-path format** (Recommended Path: optimize first + Alternative Path: address with capacity) — collapse to single path ONLY when no application issues exist
  5. `## Resource Utilization:` narrative with `[PLACEHOLDER: Looker resource utilization screenshots]`
  6. `## Plugin/Theme Concerns` as a dedicated section
  7. `## Addons` with the full `[O] / [?] / [X]` grid for ALL five addons (APM, GES, PSB, Ecom, SPM)
  8. Optional: `## How to Position` — coaching for the AM on framing the conversation with the customer (additive, never replaces the structured sections above)
  9. Full attribution block (not inline italic)
- **Do NOT improvise the Zendesk layout** — the macro structure exists so AMs get consistent, scannable responses they can act on quickly
- **Evidence file = Analyst's data**, reorganized and formatted
- **Root cause report = Diagnostician's findings** + **Advisor's recommendations**
- **Zendesk response = Advisor's SE recommendation** in the pod-report.md Report 3 macro format
- **Verification card = Diagnostician's claim verdicts** + Advisor's risk flags
- **Attribution:** Always `Sentry Ai Analysis` — never "Claude" or "AI Analysis"
- **Save all files** to `~/Documents/Sentry Reports/{pod-id}/`
- **Create the directory** if it doesn't exist: `mkdir -p ~/Documents/"Sentry Reports"/{pod-id}/`
- **HA Cluster flag in Verification Card:** When investigating an HA cluster, include a key flag documenting the field position differences (status = field 6, exec_time = field 10) and SSH hostname. This ensures anyone revisiting the cluster later knows the parsing rules differ from standard pods.

---

## Dispatcher Flow

```
User Input (pod, install, concern, optional Zendesk ticket)
    │
    ▼
┌─────────┐
│ TRIAGER  │ → Classify concern, extract claims, plan skills
└────┬─────┘
     │
     ▼
┌─────────┐
│ ANALYST  │ → Run /scout + conditional skills, collect raw evidence
└────┬─────┘
     │
     ▼
┌──────────────┐
│ DIAGNOSTICIAN│ → Interpret evidence, verdict claims, identify root cause chain
└────┬─────────┘
     │
     ▼
┌─────────┐
│ ADVISOR  │ → Model scenarios, size tier, recommend optimization + upgrade path
└────┬─────┘
     │
     ▼
┌────────────┐
│ CHECKPOINT │ → SE review gate: confirm findings, add context, adjust recommendation
└────┬───────┘
     │ (SE confirms or adjusts)
     ▼
┌──────────┐
│ NARRATOR │ → Write all 4 deliverables, save to disk
└──────────┘
```

## Interruption Protocol

The SE can interrupt at any role transition to:
- **Adjust the skill plan** — "Skip neighbor-check, this is definitely going dedicated"
- **Add context** — "The AM just told me they're adding WooCommerce next month"
- **Override a verdict** — "I checked Looker and the PHP workers ARE maxing out"
- **Redirect the investigation** — "Forget sizing, focus on the killed queries"

To interrupt, the SE just responds at the `NEXT:` handoff. The dispatcher incorporates the new input and continues from the current role.

## Global Rules

- **NEVER skip a role** — even if a role has minimal output, it must run and produce its schema
- **Each role stays in its lane** — the Analyst doesn't interpret, the Diagnostician doesn't recommend, the Advisor doesn't write reports
- **Evidence flows forward** — each role can read all prior roles' output
- **Opinions flow backward only via interruption** — the SE can override, but roles don't second-guess prior roles
- **All SSH commands follow CLAUDE.md rules** — awk -F'|' for pipe-delimited, no sudo, no system metrics, .log.1 for cache rate
- **HA clusters use adapted commands** — when Server Type is "HA Cluster", ALL log paths and pipe-delimited field positions must follow the HA Cluster Reference section. This is not optional — using standard field positions on HA logs produces silently wrong results (e.g., extracting domain as status code).
- **Knowledge base integration point** — when a KB is connected, the Triager queries it for similar past investigations, the Diagnostician queries it for known patterns, and the Advisor queries it for historical sizing outcomes. Until then, use the static pattern tables in individual skill files.
