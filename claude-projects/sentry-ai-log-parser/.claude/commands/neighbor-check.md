# Neighbor Check — Shared Server Noisy Neighbor Analysis

Use when the target install is on a shared server and you need to determine if it's a noisy-neighbor victim, IS the noisy neighbor, or has an application-level issue independent of neighbors. Skip this skill entirely for dedicated servers. Run after `/scout` provides install count and initial 504 data.

## Required Input

- **Pod number** (e.g., "405371")
- **Target install name** (e.g., "sffilm2026")
- **Context from `/scout`** if available (install count, 504 counts)

**Skip this skill if the server is dedicated (single install).** This is only relevant for shared pods.

## Phase 1: Server-Wide 504 Distribution

```bash
# 504s by install across ALL installs on the pod (today)
for f in /var/log/nginx/*.access.log; do
  install=$(basename "$f" .access.log)
  count=$(awk -F'|' '$5 == 504' "$f" | wc -l)
  [ "$count" -gt 0 ] && echo "$count $install"
done | sort -rn | head -20

# 504s by install (yesterday — full day for better comparison)
for f in /var/log/nginx/*.access.log.1; do
  install=$(basename "$f" .access.log.1)
  count=$(zcat -f "$f" | awk -F'|' '$5 == 504' | wc -l)
  [ "$count" -gt 0 ] && echo "$count $install"
done | sort -rn | head -20
```

**Exclude `-secure` log variants** to avoid double-counting.

## Phase 2: Server-Wide Slow Request Distribution

```bash
# Slow requests (>10s) by install (today)
for f in /var/log/nginx/*.access.log; do
  install=$(basename "$f" .access.log)
  count=$(awk -F'|' '$9+0 > 10' "$f" | wc -l)
  [ "$count" -gt 0 ] && echo "$count $install"
done | sort -rn | head -20
```

## Phase 3: PHP Worker Demand by Install

```bash
# Apache (PHP) traffic by install (yesterday — full day)
for f in /var/log/apache2/*.access.log.1; do
  install=$(basename "$f" .access.log.1)
  count=$(zcat -f "$f" | wc -l)
  [ "$count" -gt 0 ] && echo "$count $install"
done | sort -rn | head -20
```

## Phase 4: Classify the Situation

### Decision Matrix

| Target Install Rank (504s) | Target Install Rank (PHP Traffic) | Classification |
|---------------------------|----------------------------------|----------------|
| #1 in 504s | #1 in PHP traffic | **TARGET IS THE PROBLEM** — it's consuming the most resources AND generating the most errors |
| Top 5 in 504s | Top 5 in PHP traffic | **MUTUAL CONTENTION** — target is part of the problem, not just a victim |
| Low in 504s | Low in PHP traffic | **VICTIM** — other installs are consuming resources; dedicated server would help |
| Low in 504s | #1 in PHP traffic | **LATENT RISK** — target is the heaviest consumer but not erroring yet; will be first to break under load |
| #1 in 504s | Low in PHP traffic | **APPLICATION ISSUE** — target has slow code, not traffic volume problems; dedicated server won't fix this |

### Key Questions to Answer

1. **Is the target install the top 504 generator?** If yes, moving it to a dedicated server moves the problem, not fixes it.
2. **What percentage of server-wide 504s does the target account for?** If >50%, the target IS the noisy neighbor.
3. **Are other installs generating significant PHP traffic?** If yes, there's real contention for workers.
4. **Would removing the target fix the shared server?** If the target is #1, yes — but the target still needs code fixes.

## Output Format

```markdown
## Neighbor Check: Pod {pod-id} — {install_count} Installs

### 504 Distribution (Today)

| Rank | Install | 504 Count | % of Server Total |
|------|---------|-----------|-------------------|
| 1 | {install} | X | X% |
| 2 | {install} | X | X% |
| ... | ... | ... | ... |
| ? | **{target}** | **X** | **X%** |

**Server total 504s today:** X
**Target's share:** X% ({ranking} of {install_count} installs)

### PHP Worker Demand (Yesterday)

| Rank | Install | PHP Requests | % of Server Total |
|------|---------|-------------|-------------------|
| 1 | {install} | X | X% |
| ... | ... | ... | ... |
| ? | **{target}** | **X** | **X%** |

### Classification: {TARGET IS THE PROBLEM / MUTUAL CONTENTION / VICTIM / LATENT RISK / APPLICATION ISSUE}

{2-3 sentence explanation of why this classification applies}

### Dedicated Server Justification

**Would a dedicated server help {target}?** {Yes/No/Partially}
{Rationale — e.g., "Yes, eliminates contention with guildservice (59 504s) and cityfilmguide (39 504s), but won't fix the 113-136s calendar queries that timeout regardless of server capacity."}
```

## Rules

- **ALWAYS exclude `-secure` log variants** — they double-count the same requests
- **ALWAYS show where the target install ranks** — not just the top N
- **If the target IS the noisiest install, say so clearly** — don't frame dedicated server as "escaping" neighbors when the target is the problem
- **A dedicated server eliminates contention but doesn't fix slow code** — always pair with application-level findings
- **429 rate limiting on the target suggests platform-level throttling** — this IS helped by a dedicated server
- **Run this ONLY on shared servers** — skip for dedicated pods
- **Ghost installs may appear in log listings** — cross-reference with `/ghost-sweep` if stale install logs appear
