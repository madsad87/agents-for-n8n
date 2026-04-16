---
product: Bot Classification Reference
internal_name: bot-classification
last_verified: 2026-04-07
verified_by: Madison Sadler (SE)
---

## Purpose

Quick-reference for classifying bots encountered during WP Engine log investigations. Organized by **SE action** — what to tell the customer — not just what the bot is.

For detailed agent profiles (UA strings, robots.txt rules, blocking stats, verification methods), see: **https://knownagents.com/agents**

Individual agent details: `https://knownagents.com/agents/{agent-slug}`

---

## Classification: SE Action Categories

### Block-Worthy (Recommend blocking or GES mitigation)

These bots scrape content for AI training, offer no return traffic to the site, and respect robots.txt — blocking them has no business downside.

| Bot | Operator | UA Pattern | Detail |
|-----|----------|------------|--------|
| ClaudeBot | Anthropic | `ClaudeBot` | [Profile](https://knownagents.com/agents/claudebot) |
| GPTBot | OpenAI | `GPTBot` | [Profile](https://knownagents.com/agents/gptbot) |
| Google-Extended | Google | `Google-Extended` | [Profile](https://knownagents.com/agents/google-extended) |
| CCBot | Common Crawl | `CCBot` | [Profile](https://knownagents.com/agents/ccbot) |
| Bytespider | ByteDance/TikTok | `Bytespider` | [Profile](https://knownagents.com/agents/bytespider) |
| Amazonbot | Amazon | `Amazonbot` | [Profile](https://knownagents.com/agents/amazonbot) |
| FacebookBot | Meta | `FacebookBot` | [Profile](https://knownagents.com/agents/facebookbot) |
| Diffbot | Diffbot | `Diffbot` | [Profile](https://knownagents.com/agents/diffbot) |
| Applebot-Extended | Apple | `Applebot-Extended` | [Profile](https://knownagents.com/agents/applebot-extended) |
| cohere-ai | Cohere | `cohere-ai` | [Profile](https://knownagents.com/agents/cohere-ai) |
| YisouSpider | Shenma/Yisou | `YisouSpider` | [Profile](https://knownagents.com/agents/yisouspider) — Chinese search engine, zero SEO value for English sites |

**SE recommendation:** robots.txt block for all, or GES Bot Management for automated mitigation. These all respect robots.txt.

### Conditional (Evaluate before recommending action)

These bots serve a purpose that may benefit the customer. Blocking them has trade-offs.

| Bot | Operator | UA Pattern | Trade-off | Detail |
|-----|----------|------------|-----------|--------|
| PerplexityBot | Perplexity | `PerplexityBot` | Drives AI search citations → potential traffic | [Profile](https://knownagents.com/agents/perplexitybot) |
| OAI-SearchBot | OpenAI | `OAI-SearchBot` | ChatGPT search citations | [Profile](https://knownagents.com/agents/oai-searchbot) |
| Claude-SearchBot | Anthropic | `Claude-SearchBot` | Claude search citations | [Profile](https://knownagents.com/agents/claude-searchbot) |
| ChatGPT-User | OpenAI | `ChatGPT-User` | Real-time content for ChatGPT answers | [Profile](https://knownagents.com/agents/chatgpt-user) |
| Claude-User | Anthropic | `Claude-User` | Real-time content for Claude answers | [Profile](https://knownagents.com/agents/claude-user) |
| SemrushBot | Semrush | `SemrushBot` | SEO tooling — customer may use Semrush | [Profile](https://knownagents.com/agents/semrushbot) |
| AhrefsBot | Ahrefs | `AhrefsBot` | SEO tooling — customer may use Ahrefs | [Profile](https://knownagents.com/agents/ahrefsbot) |
| MJ12bot | Majestic | `MJ12bot` | SEO backlink analysis | [Profile](https://knownagents.com/agents/mj12bot) |
| DotBot | Moz | `DotBot` | Moz SEO crawler | [Profile](https://knownagents.com/agents/dotbot) |
| BrightEdge | BrightEdge | `BrightEdgeOnCrawl` | Enterprise SEO platform — customer likely pays for it | — |
| PetalBot | Huawei | `PetalBot` | Huawei search — relevant for sites with Asian audience | [Profile](https://knownagents.com/agents/petalbot) |

**SE recommendation:** Ask the customer before blocking. "Do you use Semrush/Ahrefs? Do you want your content cited in AI search results?" If volume is excessive, recommend robots.txt `Crawl-delay` or rate limiting rather than outright blocking.

### Leave Alone (Legitimate, high-value crawlers)

Blocking these hurts the customer's search visibility, uptime monitoring, or platform functionality.

| Bot | Operator | UA Pattern | Why Not Block | Detail |
|-----|----------|------------|---------------|--------|
| Googlebot | Google | `Googlebot` | Search indexing — blocking kills SEO | [Profile](https://knownagents.com/agents/googlebot) |
| Bingbot | Microsoft | `bingbot` | Bing search indexing | [Profile](https://knownagents.com/agents/bingbot) |
| Applebot | Apple | `Applebot` | Siri/Spotlight search | [Profile](https://knownagents.com/agents/applebot) |
| meta-externalagent | Meta | `meta-externalagent` | Facebook/Instagram link previews — blocking breaks social sharing | — |
| Twitterbot | X/Twitter | `Twitterbot` | Twitter card previews | — |
| LinkedInBot | LinkedIn | `LinkedInBot` | LinkedIn link previews | — |
| Slackbot | Slack | `Slackbot` | Slack link unfurling | — |
| Pingdom | SolarWinds | `Pingdom` | Uptime monitoring | [Profile](https://knownagents.com/agents/pingdom) |
| UptimeRobot | UptimeRobot | `UptimeRobot` | Uptime monitoring | [Profile](https://knownagents.com/agents/uptimerobot) |
| GTmetrix | GTmetrix | `GTmetrix` | Performance testing | [Profile](https://knownagents.com/agents/gtmetrix) |
| Chrome-Lighthouse | Google | `Chrome-Lighthouse` | PageSpeed/Core Web Vitals | — |
| archive.org_bot | Internet Archive | `archive.org_bot` | Wayback Machine archival | [Profile](https://knownagents.com/agents/archive-org-bot) |

**SE recommendation:** Never recommend blocking these. If their volume is a concern, the issue is site performance, not the crawler. Exception: `meta-externalagent` can be rate-limited if it's generating excessive volume (see GES KB — it cannot be blocked by GES).

### Customer-Owned (Internal monitoring tools)

These are the customer's own tools. Flagging them as "bot traffic" is incorrect. Commonly seen on enterprise accounts.

| Bot | Operator | UA Pattern | Notes |
|-----|----------|------------|-------|
| SolarWindsTransactionBot | SolarWinds | `SolarWindsTransactionBot` | Synthetic transaction monitoring |
| Zabbix | Zabbix | `Zabbix` | Infrastructure monitoring |
| Datadog | Datadog | `Datadog` | APM/monitoring agent |
| New Relic | New Relic | `NewRelicPinger` | Synthetics monitoring |
| StatusCake | StatusCake | `StatusCake` | Uptime monitoring |
| Cypress | Various | `Cypress` | Test automation |
| ObservePoint | ObservePoint | `ObservePoint` | Analytics/tag auditing |

**SE recommendation:** Never recommend blocking. If volume is excessive, advise the customer to review their monitoring frequency or consolidate tools. In reports, classify as "internal monitoring traffic" not "bot traffic."

---

## Quick Classification Workflow

When you see an unknown UA in logs:

1. **Check this table first** — covers ~90% of what we see on WP Engine
2. **If not listed**, look up: `https://knownagents.com/agents/{name-lowercase-hyphenated}`
3. **If not on knownagents.com**, evaluate based on:
   - Does it identify itself? (legitimate bots usually do)
   - Does it respect robots.txt? (check response to disallowed paths)
   - Is the request pattern uniform? (same UA, distributed IPs, even timing = bot)
   - Is the Chrome version outdated? (e.g., Chrome/121 when current is 146 = likely bot)

## Outdated Browser UA Heuristic

Bots that impersonate browsers typically hardcode a UA string and never update it. When you see traffic from a Chrome version that's 10+ versions behind current, combined with:
- Multiple IPs sending the exact same UA
- VPN/proxy IP ranges (146.70.x Mullvad, 185.x/194.x European proxies)
- Uniform request distribution per IP
- Fabricated or non-existent URL paths

...it's almost certainly a scraper or botnet, even though no bot name appears in the UA.

**Current Chrome version (as of April 2026): 146.** Anything below ~130 is suspicious if seen at volume.

---

## Integration with GES Recommendations

| Bot Category | GES Helps? | Why |
|-------------|-----------|-----|
| AI Data Scrapers | [?] Conditional | robots.txt blocks them for free — GES adds automated enforcement but may not be necessary |
| Credential Stuffing (fake UAs) | [O] Strong | WAF + Bot Management identifies distributed attacks regardless of UA |
| SEO Crawlers (excessive) | [?] Conditional | Rate limiting via GES Security tier, but robots.txt `Crawl-delay` is free |
| Customer's Own Tools | [X] No | These are legitimate — don't position GES as blocking the customer's own monitoring |
| Unknown Scrapers (outdated Chrome) | [O] Strong | Bot Management detects behavioral patterns even without known UA signatures |

---

## Sources

- https://knownagents.com/agents — Comprehensive agent database with 200+ profiles
- Field experience: Pod 95308 (SolarWindsTransactionBot, YisouSpider, Chrome/121 botnet)
- Field experience: Pod 213877 (meta-externalagent, GES overclaim correction)
- `.claude/kb/addons/ges.md` — GES capability boundaries for bot mitigation
