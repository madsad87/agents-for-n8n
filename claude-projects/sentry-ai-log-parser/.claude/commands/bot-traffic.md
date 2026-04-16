# Troubleshoot WP Engine Bot Traffic and Security Issues

Use when investigating bot traffic patterns, security threats, or automated crawler behavior in depth — including bot classification across 9 categories, WordPress-specific attack detection, and detailed user agent analysis. For a quicker bot-vs-human breakdown with GES assessment, use `/bot-audit` instead.

## Pre-Investigation: Gather Required Information

**Before proceeding, ensure you have:**

1. **Pod Number** (e.g., "213668" or "pod-213668")
   - If not provided: Ask user for the pod number

2. **Investigation Scope**
   - If not provided: Ask user:
     - "Should I analyze the entire server (all installs)?"
     - "Or focus on specific install(s)? (provide install name)"

3. **Timeframe** (optional)
   - Default: Last 7 days (current week)
   - Ask only if user mentions specific dates/times

4. **Analysis Focus** (optional)
   - General bot traffic overview
   - Security threat detection (malicious bots)
   - Performance impact analysis
   - WordPress-specific attacks
   - Ask user if they have a specific concern

5. **SSH Configuration**
   - Check `~/.ssh/config` for correct WP Engine username
   - Reference CLAUDE.md for bastion server setup if needed
   - Support both connection types:
     - Standard pods: via SSH config + bastion proxy
     - Direct Kubernetes utility pods: direct connection

**Example Pre-Flight Check:**
```
I'll help investigate bot traffic on WP Engine. Please provide:

1. Pod number: (e.g., 213668)
2. Investigation scope:
   - Entire server (all installs)?
   - Specific install name(s)?
3. [Optional] Timeframe: Default is last 7 days
4. [Optional] Focus area:
   - General bot overview
   - Security threats
   - Performance impact
   - WordPress attacks

I'll then connect via SSH and begin the analysis.
```

## Your Mission

Perform a comprehensive bot traffic investigation by:
1. Connecting to the WP Engine server via SSH (using correct username and bastion configuration)
2. Analyzing user agents and bot patterns from Nginx logs
3. Classifying bots into categories (beneficial, neutral, suspicious)
4. Identifying security threats and malicious activity
5. Analyzing WordPress-specific attack patterns
6. Correlating bot traffic with performance issues (if applicable)
7. Delivering a professional, customer-facing security and optimization report

## Critical Context: Bot Traffic at WP Engine

### Bot Categories and Classification

Sentry's bot intelligence system classifies bots into **9 categories**:

#### 1. Search Engines (Beneficial)
**Purpose**: SEO and discovery
**Examples**: Googlebot, Bingbot, Slurp (Yahoo), DuckDuckBot, Baiduspider, Yandexbot, Sogou, FacebookExternalHit, TwitterBot, LinkedInBot, Applebot, ia_archiver (Internet Archive)

**User Agent Patterns**:
```
googlebot, bingbot, slurp, duckduckbot, baiduspider, yandexbot, sogou,
facebookexternalhit, twitterbot, linkedinbot, applebot, ia_archiver
```

#### 2. Monitoring Tools (Beneficial)
**Purpose**: Uptime and availability checking
**Examples**: UptimeRobot, Pingdom, Site24x7, StatusCake, New Relic, Datadog

**User Agent Patterns**:
```
uptimerobot, pingdom, site24x7, statuscake, newrelic, datadog, monitor,
check_http, nagios, zabbix
```

#### 3. SEO Tools (Neutral)
**Purpose**: SEO analysis and research
**Examples**: Ahrefs, Semrush, Moz (Rogerbot), Majestic, Screaming Frog, DeepCrawl, Botify

**User Agent Patterns**:
```
ahrefs, semrush, rogerbot, moz.com, majestic, screaming frog, deepcrawl,
botify, oncrawl, sistrix, searchmetrics
```

#### 4. Social Media (Beneficial)
**Purpose**: Link preview generation
**Examples**: Facebook, Twitter, LinkedIn, WhatsApp, Telegram, Slack, Discord

**User Agent Patterns**:
```
facebookexternalhit, twitterbot, linkedinbot, whatsapp, telegrambot,
skype, slackbot, discordbot
```

#### 5. Security Scanners (Suspicious)
**Purpose**: Security scanning - may be legitimate or malicious
**Examples**: Nessus, OpenVAS, Qualys, Nikto, SQLMap, Nmap, Nuclei

**User Agent Patterns**:
```
nessus, openvas, qualys, rapid7, tenable, nuclei, nikto, sqlmap,
nmap, masscan, zgrab
```

#### 6. Malicious Tools (Suspicious)
**Purpose**: Often used for scraping or attacks
**Examples**: curl, wget, python-requests, scrapy, BeautifulSoup, PhantomJS, Selenium

**User Agent Patterns**:
```
curl/7., wget, python-requests, python-urllib, libwww-perl, mechanize,
scrapy, beautifulsoup, phantomjs, headlesschrome, selenium
```

#### 7. AI Crawlers (Neutral)
**Purpose**: AI training and research
**Examples**: GPTBot, Google-Extended, ClaudeBot, ChatGPT-User, CCBot (Common Crawl)

**User Agent Patterns**:
```
gptbot, google-extended, claudebot, anthropic, openai, chatgpt, claude,
ccbot, omgili, diffbot
```

#### 8. Content Scrapers (Neutral)
**Purpose**: Content crawling and archiving
**Examples**: Archive.org, Wayback Machine, Heritrix, generic crawlers

**User Agent Patterns**:
```
archive.org, wayback, heritrix, crawler, spider, scraper, harvester,
extractor, bot.*crawler, fetch
```

#### 9. WordPress-Specific (Neutral)
**Purpose**: WordPress automated requests
**Examples**: WordPress.com crawlers, Jetpack, Automattic, Pingback, Trackback, XMLRPC

**User Agent Patterns**:
```
wordpress, wp-, jetpack, automattic, pingback, trackback, xmlrpc
```

### Critical Exclusion: WP Engine Alternate Cron

**DO NOT classify as bot traffic:**
- **IP Pattern**: 10.x.x.x (internal WP Engine network)
- **User Agent**: curl/7.81.0 (exactly)
- **Paths**: /wp-cron.php?doing_wp_cron OR /?wp-cmd=cron
- **Purpose**: Legitimate internal WordPress scheduling service

**This is infrastructure, not bot traffic!**

### WordPress Attack Patterns

**Suspicious paths to watch for**:
- `/wp-admin` - Admin area access attempts
- `/wp-login.php` - Login page attacks
- `/wp-config.php` - Config file exposure attempts
- `/xmlrpc.php` - XMLRPC exploitation
- `/wp-json` - REST API abuse
- `/wp-content/uploads` - File upload exploitation

**Additional suspicious indicators**:
- `.env` files
- `.git` directories
- `phpmyadmin` access
- `backup` files
- `config` exposure

### WP Engine Container Constraints

WP Engine uses containers with limited SSH access on utility servers. You cannot:
- Modify Nginx configuration
- Block IPs or user agents yourself
- Install security software
- Make any infrastructure changes

**Your role is INVESTIGATIVE ONLY**: Analyze logs, identify threats, and report findings with recommendations.

## Investigation Methodology

### Phase 1: Connect and Verify

1. **SSH Connection**
   - Use username from `~/.ssh/config`
   - Connect as: `ssh [username]@pod-[number].wpengine.com`
   - Or direct Kubernetes pod: `ssh [username]@pod-[number]-utility-[hash]`
   - Reference CLAUDE.md for bastion server configuration if needed

2. **Verify Log Access**
   - Check Nginx access logs exist and are recent
   - Verify user agent data is available
   - Identify timeframe of issues

**Verification Commands**:
```bash
# Check if logs exist
ls -lht /var/log/nginx/INSTALL.access.log*
ls -lht /var/log/nginx/INSTALL.apachestyle.log*

# Sample user agents to verify data
tail -100 /var/log/nginx/INSTALL.apachestyle.log | awk -F'"' '{print $6}' | head -20
```

### Phase 2: Discover and Filter Logs

**Default Timeframe**: Analyze only logs from the **last 7 days** (current week)

**Discover Available Logs**:
```bash
# Find all nginx logs modified in last 7 days
find /var/log/nginx/ -name "INSTALL.access.log*" -mtime -7 -exec ls -lht {} \;
find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7 -exec ls -lht {} \;

# Check modification dates to ensure logs are recent
ls -lht /var/log/nginx/INSTALL.access.log*
```

**IMPORTANT**:
- Always check file modification dates (`ls -lt`)
- Only analyze logs modified within 7 days
- Ignore old/stale logs (e.g., 1 month or 1 year old)
- Log rotation may go beyond .log.7.gz (could be .log.9.gz or more)
- Use `-mtime -7` to find files modified in last 7 days

**You Have Full Autonomy**: Use ANY analysis approach you deem effective:
- Standard commands (grep, awk, sed, cut, sort, uniq)
- Python scripts for complex parsing
- Custom one-liners optimized for the specific pattern
- Multi-stage analysis pipelines
- Real-time monitoring

### Phase 3: Bot Detection and Classification

**Extract and Classify User Agents**:

```bash
# Get all user agents from last 7 days
zgrep -h "" $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk -F'"' '{print $6}' | sort | uniq -c | sort -rn > /tmp/user_agents.txt

# Count total requests
TOTAL_REQUESTS=$(wc -l < /tmp/user_agents.txt)
```

**Classify by Category** (use grep with case-insensitive matching):

#### 1. Search Engines (Beneficial)
```bash
# Count search engine bots
grep -iE 'googlebot|bingbot|slurp|duckduckbot|baiduspider|yandexbot|sogou|facebookexternalhit|twitterbot|linkedinbot|applebot|ia_archiver' /tmp/user_agents.txt | awk '{sum+=$1} END {print "Search Engines:", sum}'

# Top search engine crawlers
grep -iE 'googlebot|bingbot|slurp|duckduckbot|baiduspider|yandexbot' /tmp/user_agents.txt | head -10
```

#### 2. Monitoring Tools (Beneficial)
```bash
# Count monitoring tools
grep -iE 'uptimerobot|pingdom|site24x7|statuscake|newrelic|datadog|monitor|check_http|nagios|zabbix' /tmp/user_agents.txt | awk '{sum+=$1} END {print "Monitoring Tools:", sum}'
```

#### 3. SEO Tools (Neutral)
```bash
# Count SEO tools
grep -iE 'ahrefs|semrush|rogerbot|moz\.com|majestic|screaming frog|deepcrawl|botify|oncrawl|sistrix|searchmetrics' /tmp/user_agents.txt | awk '{sum+=$1} END {print "SEO Tools:", sum}'

# Top SEO crawlers (often heavy)
grep -iE 'ahrefs|semrush|majestic' /tmp/user_agents.txt | head -10
```

#### 4. Social Media (Beneficial)
```bash
# Count social media bots
grep -iE 'facebookexternalhit|twitterbot|linkedinbot|whatsapp|telegrambot|slackbot|discordbot' /tmp/user_agents.txt | awk '{sum+=$1} END {print "Social Media:", sum}'
```

#### 5. Security Scanners (Suspicious - HIGH PRIORITY)
```bash
# Count security scanners
grep -iE 'nessus|openvas|qualys|rapid7|tenable|nuclei|nikto|sqlmap|nmap|masscan|zgrab' /tmp/user_agents.txt | awk '{sum+=$1} END {print "Security Scanners:", sum}'

# List all security scanner activity
grep -iE 'nessus|openvas|qualys|nikto|sqlmap|nmap' /tmp/user_agents.txt
```

#### 6. Malicious Tools (Suspicious - HIGH PRIORITY)
```bash
# Count malicious tools (excluding WP Engine Alternate Cron)
grep -iE 'curl/7\.|wget|python-requests|python-urllib|libwww-perl|mechanize|scrapy|beautifulsoup|phantomjs|headlesschrome|selenium' /tmp/user_agents.txt | grep -v "10\." | awk '{sum+=$1} END {print "Malicious Tools:", sum}'

# Top malicious tool activity
grep -iE 'curl|wget|python-requests|scrapy' /tmp/user_agents.txt | head -20
```

#### 7. AI Crawlers (Neutral)
```bash
# Count AI crawlers
grep -iE 'gptbot|google-extended|claudebot|anthropic|openai|chatgpt|claude|ccbot|omgili|diffbot' /tmp/user_agents.txt | awk '{sum+=$1} END {print "AI Crawlers:", sum}'

# List AI crawlers
grep -iE 'gptbot|google-extended|claudebot|chatgpt|ccbot' /tmp/user_agents.txt
```

#### 8. Content Scrapers (Neutral)
```bash
# Count content scrapers
grep -iE 'archive\.org|wayback|heritrix|crawler|spider|scraper|harvester|extractor|fetch' /tmp/user_agents.txt | awk '{sum+=$1} END {print "Content Scrapers:", sum}'
```

#### 9. WordPress-Specific (Neutral)
```bash
# Count WordPress bots
grep -iE 'wordpress|wp-|jetpack|automattic|pingback|trackback|xmlrpc' /tmp/user_agents.txt | awk '{sum+=$1} END {print "WordPress Bots:", sum}'
```

**Exclude WP Engine Alternate Cron**:
```bash
# Identify and exclude Alternate Cron (10.x.x.x + curl/7.81.0 + wp-cron paths)
zgrep -h "" $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | \
grep "^10\." | \
grep "curl/7.81.0" | \
grep -E "wp-cron\.php\?doing_wp_cron|/\?wp-cmd=cron" | \
wc -l

# Note: This is legitimate infrastructure, not bot traffic
```

### Phase 4: Security Threat Analysis

**Identify Malicious Bot Activity**:

```bash
# Find security scanner IPs
zgrep -iE 'nessus|openvas|nikto|sqlmap|nmap' $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk '{print $1}' | sort | uniq -c | sort -rn

# Find malicious tool IPs (excluding internal 10.x.x.x)
zgrep -iE 'curl|wget|python-requests|scrapy' $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | grep -v "^10\." | awk '{print $1}' | sort | uniq -c | sort -rn | head -20
```

**Analyze WordPress Attack Patterns**:

```bash
# wp-admin access attempts by bots
zgrep "/wp-admin" $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk -F'"' '{print $6}' | grep -iE 'bot|crawl|spider|curl|wget|python' | sort | uniq -c | sort -rn

# wp-login attacks
zgrep "/wp-login" $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk -F'"' '{print $6}' | grep -iE 'bot|crawl|curl|wget|python' | sort | uniq -c | sort -rn

# xmlrpc.php exploitation attempts
zgrep "xmlrpc.php" $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk '{print $1, $7}' | sort | uniq -c | sort -rn

# Suspicious path access
zgrep -E '\.env|\.git|phpmyadmin|backup|config' $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk '{print $1, $7}' | sort | uniq -c | sort -rn
```

**Threat Level Assessment**:
- **High**: 10+ malicious bot requests OR security scanner activity
- **Medium**: 5-10 suspicious bot requests OR WordPress admin attacks
- **Low**: <5 suspicious requests, mostly beneficial bots

### Phase 5: Bot Behavior Analysis

**Request Frequency Patterns**:

```bash
# Requests per hour by bot category
# Example for Ahrefs (often aggressive)
zgrep -i "ahrefs" $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk '{print $4}' | cut -d: -f2 | sort | uniq -c | sort -rn

# Identify aggressive bots (>100 requests/hour)
for bot in ahrefs semrush majestic screaming; do
  count=$(zgrep -i "$bot" $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | wc -l)
  if [ $count -gt 100 ]; then
    echo "$bot: $count requests (aggressive)"
  fi
done
```

**Path Access Patterns**:

```bash
# Most accessed paths by bots
zgrep -iE 'bot|crawl|spider' $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk '{print $7}' | cut -d? -f1 | sort | uniq -c | sort -rn | head -20

# Bots accessing sitemap.xml (compliance check)
zgrep "sitemap" $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk -F'"' '{print $6}' | grep -iE 'bot|crawl' | sort | uniq -c

# Bots accessing robots.txt (compliance check)
zgrep "robots.txt" $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk -F'"' '{print $6}' | grep -iE 'bot|crawl' | sort | uniq -c
```

**Status Code Analysis**:

```bash
# Bot requests resulting in 404 errors
zgrep " 404 " $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk -F'"' '{print $6}' | grep -iE 'bot|crawl|spider' | sort | uniq -c | sort -rn

# Bot requests resulting in 403 errors (blocked)
zgrep " 403 " $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk -F'"' '{print $6}' | grep -iE 'bot|crawl|spider' | sort | uniq -c | sort -rn

# Bot requests resulting in 502/504 errors
zgrep -E " 502 | 504 " $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk -F'"' '{print $6}' | grep -iE 'bot|crawl|spider' | sort | uniq -c | sort -rn
```

### Phase 6: Performance Correlation

**Correlate bot traffic with server issues**:

```bash
# Check if bot traffic correlates with 502/504 errors
# Get timestamps of 502/504 errors (pipe-delimited logs — MUST use awk field matching)
zcat -f $(find /var/log/nginx/ -name "INSTALL.access.log*" -mtime -7) 2>/dev/null | awk -F'|' '$5 == 502 || $5 == 504 {print $1}' | cut -d: -f1-2 | sort | uniq -c > /tmp/error_times.txt

# Get timestamps of heavy bot traffic
zgrep -iE 'bot|crawl|spider|ahrefs|semrush' $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk '{print $4}' | cut -d: -f1-3 | tr -d '[]' | cut -d: -f1-2 | sort | uniq -c | sort -rn > /tmp/bot_times.txt

# Compare timestamps to find correlation
# Look for matching hours in both files
```

**Heavy bot traffic periods**:

```bash
# Identify peak bot traffic hours
zgrep -iE 'bot|crawl|spider' $(find /var/log/nginx/ -name "INSTALL.apachestyle.log*" -mtime -7) | awk '{print $4}' | cut -d: -f2 | sort | uniq -c | sort -rn | head -10
```

### Phase 7: Customer-Facing Report

Include the original user request/prompt that initiated this investigation as the first section of the evidence file, under an "Original Request" heading with the verbatim text in a blockquote.

**Generate a professional Markdown report** with:

#### Required Sections:

1. **Executive Summary**
   - Brief overview of bot traffic analysis
   - Total bot requests vs human requests
   - Bot traffic percentage
   - Threat level assessment
   - Key findings summary

2. **Investigation Timeline**
   - Analysis period covered (e.g., "Last 7 days: Jan 8-15, 2026")
   - Total requests analyzed
   - Peak bot activity periods

3. **Bot Traffic Breakdown**
   - Requests by bot category (9 categories)
   - Beneficial bots: count and percentage
   - Neutral bots: count and percentage
   - Suspicious bots: count and percentage
   - Top 10 most active bots (by user agent)
   - Unique bot IPs identified

4. **Security Analysis**
   - Threat level: Low/Medium/High
   - Malicious bot count and IPs
   - Security scanner activity
   - WordPress attack patterns detected:
     - wp-admin access attempts
     - wp-login brute force attempts
     - xmlrpc.php exploitation
     - Suspicious path access (.env, .git, etc.)
   - Recommended IPs to block (if applicable)

5. **Behavior Analysis**
   - Aggressive bots (>100 requests/hour)
   - Compliance check:
     - Bots checking robots.txt
     - Bots accessing sitemap.xml
   - Path access patterns
   - Status code distribution (404s, 403s, 502s from bots)

6. **Performance Impact**
   - Correlation with 502/504 errors (if applicable)
   - Peak bot traffic hours
   - Estimated bot traffic percentage of total load
   - Heavy crawlers identified (SEO tools)

7. **Recommendations**
   - Immediate actions (if high threat level):
     - Block malicious IPs
     - Implement rate limiting
     - Enable WordPress login protection
   - Long-term strategies:
     - robots.txt optimization
     - Sitemap configuration
     - Bot management (beneficial vs harmful)
     - CDN/WAF recommendations
     - WP Engine Advanced Network features

8. **Technical Details** (Appendix)
   - Commands used for verification
   - Full analysis methodology
   - Sample log entries (sanitized)
   - Bot classification criteria
   - WP Engine Alternate Cron exclusions (if any)

#### Report Formatting:

- Use professional, customer-friendly language
- Avoid jargon; explain bot categories clearly
- Include specific counts and percentages
- Use markdown formatting for readability
- Always attribute to "Sentry Ai Analysis"
- Save report to: `~/Documents/pod-[number]_bot_analysis_[date].md`

#### Restrictions (from CLAUDE.md)

**DO NOT**:
- Block IPs or user agents yourself (WP Engine manages infrastructure)
- Recommend server configuration changes
- Modify Nginx or Apache configs
- Install security software
- Make any infrastructure changes

**DO**:
- Focus on application-level security
- Recommend WP Engine security features (Advanced Network, Login Protection)
- Suggest robots.txt optimization
- Recommend WordPress security plugins (Wordfence, etc.)
- Provide bot management best practices
- Suggest CDN/WAF solutions (Cloudflare, etc.)
- Identify beneficial bots to allow (Googlebot, etc.)
- Recommend rate limiting strategies (customer to implement)

## Example Commands Reference

**These are examples only** - use your judgment to create better analysis:

```bash
# Discover recent logs (last 7 days)
find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7 -exec ls -lht {} \;

# Extract all user agents
zgrep -h "" $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | awk -F'"' '{print $6}' | sort | uniq -c | sort -rn > /tmp/user_agents.txt

# Count bot categories
grep -iE 'googlebot|bingbot|slurp' /tmp/user_agents.txt | awk '{sum+=$1} END {print sum}'
grep -iE 'ahrefs|semrush|majestic' /tmp/user_agents.txt | awk '{sum+=$1} END {print sum}'
grep -iE 'curl|wget|python-requests' /tmp/user_agents.txt | grep -v "10\." | awk '{sum+=$1} END {print sum}'

# Find malicious bot IPs
zgrep -iE 'sqlmap|nikto|nmap' $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | awk '{print $1}' | sort | uniq -c | sort -rn

# WordPress attack detection
zgrep "/wp-admin" $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | grep -iE 'curl|wget|python' | wc -l
zgrep "/wp-login" $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | grep -iE 'curl|wget|python' | wc -l
zgrep "xmlrpc.php" $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | awk '{print $1}' | sort | uniq -c | sort -rn

# Aggressive bot detection (requests per hour)
zgrep -i "ahrefs" $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | awk '{print $4}' | cut -d: -f2 | sort | uniq -c | sort -rn

# Compliance check
zgrep "robots.txt" $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | grep -iE 'bot|crawl' | wc -l
zgrep "sitemap" $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | grep -iE 'bot|crawl' | wc -l

# Status code analysis
zgrep " 404 " $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | grep -iE 'bot|crawl' | wc -l
zgrep " 502 " $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | grep -iE 'bot|crawl' | wc -l

# Exclude WP Engine Alternate Cron
zgrep "^10\." $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | grep "curl/7.81.0" | grep -E "wp-cron|wp-cmd=cron" | wc -l

# Peak bot traffic hours
zgrep -iE 'bot|crawl|spider' $(find /var/log/nginx/ -name "install.apachestyle.log*" -mtime -7) | awk '{print $4}' | cut -d: -f2 | sort | uniq -c | sort -rn
```

## Bot Classification Quick Reference

**Beneficial (Allow)**:
- Search Engines: googlebot, bingbot, slurp, yandexbot, applebot
- Monitoring: uptimerobot, pingdom, statusc ake, newrelic
- Social Media: facebookexternalhit, twitterbot, linkedinbot

**Neutral (Monitor)**:
- SEO Tools: ahrefs, semrush, majestic (can be aggressive)
- AI Crawlers: gptbot, claudebot, google-extended, ccbot
- Content Scrapers: archive.org, wayback
- WordPress: jetpack, automattic

**Suspicious (Investigate/Block)**:
- Security Scanners: nessus, nikto, sqlmap, nmap
- Malicious Tools: curl (non-internal), wget, python-requests, scrapy

**Exclude from Analysis**:
- WP Engine Alternate Cron: 10.x.x.x + curl/7.81.0 + wp-cron paths

## Success Criteria

Your investigation is complete when you have:

✅ Gathered all required information (pod number, scope, timeframe, focus)
✅ Connected via SSH using correct username and bastion configuration
✅ Verified log access and user agent data availability
✅ Analyzed logs from the appropriate timeframe (last 7 days, verified by modification dates)
✅ Classified bot traffic into 9 categories
✅ Excluded WP Engine Alternate Cron from bot counts
✅ Identified security threats and malicious activity
✅ Analyzed WordPress attack patterns
✅ Assessed bot behavior (frequency, paths, compliance)
✅ Correlated bot traffic with performance issues (if applicable)
✅ Generated a professional, customer-facing Markdown report
✅ Provided actionable security and optimization recommendations
✅ Documented all analysis steps for verification

## Attribution

All reports must be attributed to:
**"Sentry Ai Analysis"**

---

**Remember**:
- You have full autonomy in your investigation approach
- Use the examples as guidance, but adapt to specific patterns you discover
- Leverage Sentry's 70+ bot patterns for comprehensive classification
- Your goal is to find the truth, not to follow a script
- You are INVESTIGATIVE ONLY - never block IPs or change configurations
- WP Engine uses containers with limited SSH access - work within those constraints
- Always exclude WP Engine Alternate Cron (10.x.x.x + curl/7.81.0 + wp-cron)
- Security threats should be prioritized in recommendations
- Beneficial bots (search engines) should be preserved and optimized
