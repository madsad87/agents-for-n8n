# Bot Audit — Traffic Classification & GES Value Assessment

Use when you need a quick bot-vs-human traffic breakdown and GES value assessment. Run on every investigation — bot traffic percentage directly feeds `/size` scenario modeling and GES addon recommendations. Also use standalone when an AM asks "would GES help this site?"

## Required Input

- **Pod number** (e.g., "405371")
- **Install name** (e.g., "sffilm2026")
- **Context from `/scout`** if available (user agent data, traffic volumes)

## Phase 1: Collect User Agent Data

```bash
# Top 40 user agents (from apachestyle logs — has full User-Agent string)
for f in /var/log/nginx/{install}.apachestyle.log*; do zcat -f "$f" 2>/dev/null; done | awk -F'"' '{print $(NF-1)}' | sort | uniq -c | sort -rn | head -40

# Total request count for percentage calculation
for f in /var/log/nginx/{install}.apachestyle.log*; do zcat -f "$f" 2>/dev/null; done | wc -l
```

**For HA clusters**, use `/var/log/synced/nginx/` path.

## Phase 2: Classify Traffic

Sort every user agent into one of these buckets:

### 1. AI Crawlers (GES blocks)
```
meta-externalagent, facebookexternalhit    — Facebook/Meta
OAI-SearchBot, GPTBot, ChatGPT-User       — OpenAI
ClaudeBot                                   — Anthropic
bingbot (AI-related), Copilot              — Microsoft
PerplexityBot                               — Perplexity
YouBot                                      — You.com
```

### 2. SEO / Marketing Bots (GES manages)
```
AhrefsBot, SemrushBot, MJ12bot            — SEO tools
DotBot, BLEXBot, MegaIndex                — SEO tools
AwarioBot, BuzzSumo                        — Social monitoring
```

### 3. Search Engine Crawlers (legitimate, keep)
```
Googlebot, Googlebot-Image                 — Google
bingbot (standard search)                  — Microsoft
Applebot                                   — Apple
DuckDuckBot                                — DuckDuck Go
```

### 4. Monitoring / Synthetic (not real users)
```
Site24x7, Pingdom, UptimeRobot             — Monitoring services
CloudWatch Synthetics (Chrome/124 Linux)    — AWS canaries
NewRelicPinger, DatadogSynthetics          — APM
```

### 5. Vulnerability Scanners (noise)
```
Nuclei, WPScan, sqlmap, Nmap              — Security scanners
python-requests, Go-http-client            — Script traffic
curl/, wget/                               — CLI tools
```

### 6. Social Media Previews (low volume, legitimate)
```
Twitterbot, LinkedInBot, Slackbot          — Link preview generators
WhatsApp, TelegramBot                      — Messaging previews
```

### 7. Human Traffic (real users)
```
Mozilla/5.0 ... Chrome/... Safari/...      — Desktop browsers
Mozilla/5.0 ... Mobile ... Safari/...      — Mobile browsers
Mozilla/5.0 ... Firefox/...                — Firefox
```

## Phase 3: GES Value Assessment

### Calculate Impact
```
Total bot requests (categories 1+2+4+5) = X
GES-blockable requests (categories 1+2) = X
Bot percentage = Bot requests / Total requests × 100
GES reduction = GES-blockable / Total requests × 100
```

### GES Recommendation Thresholds

| Bot % | GES Value | Recommendation |
|-------|-----------|---------------|
| >40% | Very High | Strong recommend — immediate PHP demand reduction |
| 25-40% | High | Recommend — meaningful reduction, especially with low cache rate |
| 15-25% | Moderate | Recommend if combined with other factors (low cache, WooCommerce) |
| <15% | Low | GES adds security value but won't significantly change PHP demand |

### Revenue Impact (if applicable)
If Facebook meta-externalagent is high AND the site runs paid ads:
```
⚠ Facebook's meta-externalagent is generating {X} requests ({Y%} of traffic).
These are Facebook crawling pages shared in ads/posts — NOT ad-click traffic.
GES can rate-limit this crawler without affecting Facebook ad performance.
The actual ad clicks come through with normal browser user agents.
```

## Output Format

```markdown
## Bot Audit: {install} on Pod {pod-id}

### Traffic Classification (7-Day)

| Category | Requests | % of Total |
|----------|----------|------------|
| Human traffic | X | X% |
| AI crawlers | X | X% |
| SEO/Marketing bots | X | X% |
| Search engines | X | X% |
| Monitoring/Synthetic | X | X% |
| Vulnerability scanners | X | X% |
| Social previews | X | X% |
| **Total** | **X** | **100%** |

### Top 10 Bot User Agents

| Agent | Requests | Category |
|-------|----------|----------|
| {agent} | X | {category} |

### GES Value Assessment

**Bot traffic:** {X%} of all requests
**GES-blockable:** {X%} (AI crawlers + SEO bots)
**Estimated PHP reduction with GES:** {X%}

**GES Recommendation: {Very High / High / Moderate / Low}**
{1-2 sentence rationale}

{⚠ Facebook/ad revenue note if applicable}
```

## Rules

- **ALWAYS use apachestyle logs for user agents** — pipe-delimited logs don't include User-Agent
- **NEVER classify Googlebot as "bad" traffic** — it's a search engine, not a nuisance bot
- **Facebook meta-externalagent is NOT ad click traffic** — it's Facebook's crawler pre-fetching shared links
- **CloudWatch Synthetics uses real Chrome user agents** — detect by correlating with AWS IP ranges or consistent exact-version patterns
- **GES blocks AI crawlers and manages SEO bots** — it does NOT block search engine crawlers
- **Always note if bot traffic is hitting PHP** — bots hitting cached pages are low-impact; bots hitting PHP (visible in Apache logs) are the problem
- **Feed bot% to `/size` for P-tier modeling** — GES bot removal is the second highest-leverage scenario input
