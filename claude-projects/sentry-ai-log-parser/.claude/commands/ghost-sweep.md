# Ghost Sweep — Stale Install Detection & Database Impact

Use when analyzing a shared server with 50+ installs, or when neighbor analysis results look suspicious (phantom 504s from installs that shouldn't exist). Ghost installs — removed sites with lingering logs — inflate install counts, skew neighbor analysis, and contaminate error totals. Run early in investigations to correct metrics before other skills consume them.

## Required Input

- **Pod number** (e.g., "405371")
- **Context from `/scout`** if available (install count, neighbor check data)

## Phase 1: Identify Active vs Ghost Installs

### Step 1: List All Log-Producing Installs
```bash
# All installs with nginx access logs (exclude -secure variants)
ls /var/log/nginx/*.access.log 2>/dev/null | sed 's|.*/||;s|\.access\.log||' | grep -v secure | sort > /tmp/log_installs.txt
cat /tmp/log_installs.txt | wc -l
```

### Step 2: List All Installs with Live Filesystems
```bash
# All installs with content directories
ls -d /nas/content/live/*/ 2>/dev/null | sed 's|.*/live/||;s|/||' | sort > /tmp/live_installs.txt
cat /tmp/live_installs.txt | wc -l
```

### Step 3: Find Ghosts
```bash
# Installs with logs but NO filesystem = definite ghosts
comm -23 /tmp/log_installs.txt /tmp/live_installs.txt

# Installs with filesystem but NO recent logs = possibly decommissioned
comm -13 /tmp/log_installs.txt /tmp/live_installs.txt
```

## Phase 2: Assess Ghost Impact

For each ghost install found:

### Traffic Volume (Are ghosts generating load?)
```bash
# Ghost install traffic volume (today)
for ghost in $(comm -23 /tmp/log_installs.txt /tmp/live_installs.txt); do
  count=$(wc -l < /var/log/nginx/${ghost}.access.log 2>/dev/null)
  [ "$count" -gt 0 ] && echo "$count $ghost"
done | sort -rn

# Ghost install 504s (today)
for ghost in $(comm -23 /tmp/log_installs.txt /tmp/live_installs.txt); do
  count=$(awk -F'|' '$5 == 504' /var/log/nginx/${ghost}.access.log 2>/dev/null | wc -l)
  [ "$count" -gt 0 ] && echo "$count $ghost"
done | sort -rn
```

### Date Filtering Check
```bash
# Last log entry date for each ghost (when did traffic last arrive?)
for ghost in $(comm -23 /tmp/log_installs.txt /tmp/live_installs.txt); do
  last=$(tail -1 /var/log/nginx/${ghost}.access.log 2>/dev/null | awk -F'|' '{print $1}')
  echo "$ghost: $last"
done
```

## Phase 3: Database Schema Check

```bash
# List all database schemas on the MySQL server
zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep '^use ' | sort -u

# Check if ghost installs have database schemas producing slow queries
for ghost in $(comm -23 /tmp/log_installs.txt /tmp/live_installs.txt); do
  count=$(zcat -f /var/log/mysql/mysql-slow.log* 2>/dev/null | grep "^use wp_${ghost}" | wc -l)
  [ "$count" -gt 0 ] && echo "$count slow queries: wp_${ghost}"
done | sort -rn
```

## Phase 4: Impact Assessment

### Ghost Installs Matter When:
1. **They inflate neighbor analysis** — A ghost with 504s in its logs makes the shared server look worse than it is
2. **They consume database resources** — Orphaned schemas with cron jobs, action scheduler, or wp-cron still running
3. **They skew install counts** — "106 installs on the server" may include 20 ghosts
4. **They produce misleading 504 counts** — Server-wide 504 totals include ghost traffic

### Ghost Installs Are Harmless When:
1. **No recent traffic** — Last log entry is days/weeks old
2. **No database activity** — No slow queries from the ghost's schema
3. **Low volume** — A few requests from cached DNS or bookmarks

## Output Format

```markdown
## Ghost Sweep: Pod {pod-id}

### Install Inventory

| Category | Count |
|----------|-------|
| Active installs (logs + filesystem) | X |
| Ghost installs (logs only, no filesystem) | X |
| Dormant installs (filesystem only, no recent logs) | X |
| **Reported install count** | **X** |
| **Actual active count** | **X** |

### Ghost Installs Detected

| Install | Today's Traffic | Today's 504s | Last Activity | DB Schema? | Impact |
|---------|----------------|-------------|---------------|------------|--------|
| {ghost} | X | X | {date} | Yes/No | {High/Low/None} |

### Impact on Current Analysis

**Install count correction:** {X} reported → {Y} actual active installs
**504 count correction:** {X} server-wide → {Y} from active installs only
**Neighbor analysis affected:** {Yes/No} — {explanation}

### Recommendations

{If high-impact ghosts found:}
- Flag ghost installs to WP Engine platform team for log cleanup
- Exclude ghost installs from neighbor analysis in current report
- Note corrected install count in evidence file

{If no significant ghosts:}
- No ghost install impact detected. Install count is accurate.
```

## Rules

- **ALWAYS date-filter log commands** — Ghost install logs may contain stale data from weeks ago
- **NEVER include ghost install traffic in the target install's analysis** — they are separate installs
- **ALWAYS note corrected install counts** — "106 installs" means nothing if 20 are ghosts
- **Ghost 504s should NOT be counted in server-wide totals** — they inflate the problem
- **Check database schemas** — orphaned databases may still have active cron jobs or scheduled events
- **This is a diagnostic aid, not a cleanup tool** — we cannot remove ghost installs, only flag them and correct our analysis
- **Run this early in the investigation** — ghost contamination affects `/neighbor-check`, `/scout`, and `/size` calculations
