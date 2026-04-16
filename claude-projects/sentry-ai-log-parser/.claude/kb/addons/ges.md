---
product: Global Edge Security (GES)
internal_name: ges
last_verified: 2026-04-06
verified_by: Madison Sadler (SE) — sourced from internal AN/GES doc + field experience
---

## What It Does

GES is WP Engine's paid security and performance add-on powered by Cloudflare. It routes customer traffic through Cloudflare's `wpewaf.com` zone with enhanced protections beyond the free Advanced Network.

### Security Capabilities
- **WAF (Managed Web Application Firewall)** — blocks common attack patterns (SQL injection, XSS, known vulnerability exploits)
- **Advanced DDoS Protection** — layer 3/4/7 DDoS mitigation at the edge
- **Rate Limiting** — throttle excessive requests from individual sources (GES Security tier only)
- **Bot Management** — identify and challenge automated traffic (GES Security tier only)

### Performance Capabilities
- **Cloudflare CDN** — edge caching of static assets globally
- **Argo Smart Routing** — optimizes network path between visitor and origin, reducing latency
- **Polish** — lossless image optimization at the edge
- **TLS 1.3** — faster handshakes than TLS 1.2

### Infrastructure
- Uses Cloudflare SSL for SaaS zone: `wpewaf.com`
- All GES customers share this zone — zone-level features affect all GES customers
- Dedicated Cloudflare zone available for premium/specialized requests

## GES vs AN: What GES Adds Over Free Advanced Network

Both AN and GES mitigate all network/transport layer DDoS attacks (SYN flood, UDP flood, ICMP, amplification, TCP connection floods). The following are GES-only capabilities:

| Capability | AN | GES | SE Implication |
|-----------|----|----|---------------|
| WAF (Web Application Firewall) | No | Yes | GES blocks SQL injection, XSS, known exploits at the edge |
| Advanced DDoS (Layer 7) | Basic only | Yes | GES handles sophisticated application-layer DDoS |
| Rate Limiting | No | Yes (GES Security) | GES can throttle per-source request rates |
| Bot Management | No | Yes (GES Security) | GES identifies/challenges automated traffic patterns |
| Argo Smart Routing | No | Yes | GES optimizes network path — TTFB improvement |
| Waiting Room | No | Yes (GES Security) | Queue visitors during traffic surges |
| UAM (Under Attack Mode) | Yes | Yes | Both can enable via OverDrive dashboard |

**Key distinction for investigations:** If the attack is purely network-layer (SYN flood, UDP, ICMP), AN already mitigates it — don't upsell GES for something the free tier handles. GES's value-add is application-layer: WAF, bot management, rate limiting.

## What It Does NOT Do

### Crawler / Bot Limitations
- **Cannot block legitimate platform crawlers** — Facebook meta-externalagent, Googlebot, Bingbot, and similar legitimate crawlers are NOT blocked by GES. These require app-level solutions (robots.txt, Google Search Console crawl rate limits, server-level UA blocking)
- **Bot Management detects, it doesn't block everything** — it identifies bot traffic patterns but legitimate crawlers with valid purposes pass through by design
- **Cannot selectively block by user-agent at the customer level** — zone-level configuration means UA-based rules affect all GES customers unless a dedicated zone is provisioned

### Architecture Limitations
- **Zone-level configuration** — individual customer feature requests may not be possible if the Cloudflare feature operates at the zone level (affects all GES customers)
- **Not a replacement for application-level security** — weak passwords, vulnerable plugins, and misconfigured WordPress are not mitigated by edge security
- **Does not reduce PHP worker consumption from cached-bypassing traffic** — wp-cron, wp-admin, logged-in user traffic, and POST requests still reach PHP regardless of GES

### What It Won't Fix
- Slow database queries
- PHP code performance issues
- Plugin conflicts
- Cache configuration problems on origin
- High traffic from the customer's own tools (synthetic monitoring, internal bots)

## When to Recommend

| Log Evidence | Recommendation | Why |
|-------------|---------------|-----|
| Credential-stuffing / brute-force on wp-login (rotated UAs, distributed IPs) | **[O] Strong recommend** | WAF blocks common brute-force patterns at the edge before they reach PHP |
| Malicious vulnerability scanning (probes for backdoor filenames) | **[O] Strong recommend** | WAF blocks known exploit patterns |
| Application-layer DDoS (HTTP floods, cache busting) | **[O] Strong recommend** | WAF + Bot Management + Rate Limiting mitigate at edge |
| Network-layer DDoS on Legacy/Direct DNS customer | **[O] Recommend AN first** | AN already mitigates network-layer DDoS for free; GES adds application-layer protection |
| Cache busting attacks (random query strings like `/?s=123456`) | **[O] Strong recommend** | WAF can identify and challenge cache-busting patterns |
| xmlrpc.php volumetric attacks | **[?] Conditional** | Platform already has mod_security + BadBoyz protections; GES adds edge-level blocking but may not be necessary |
| High SEO crawler traffic (AhrefsBot, SemrushBot, etc.) | **[?] Conditional** | Bot Management can help, but robots.txt is the primary tool |
| General bot % > 20% (mixed sources) | **[?] Conditional** | Evaluate what types of bots — GES helps with malicious, not legitimate |
| Customer on Legacy Network | **[O] Recommend AN first** | Free AN upgrade is step 1; GES is step 2 if security concerns exist |

## When NOT to Recommend

| Situation | Why Not |
|-----------|---------|
| Traffic is primarily from legitimate platform crawlers (Facebook, Google, Apple, etc.) | GES does not block these — recommend robots.txt and crawl rate management instead |
| Enterprise customer with existing WAF/CDN (Cloudflare Enterprise, Akamai, AWS CloudFront) | Duplicate edge layer creates complexity; verify they don't already have equivalent protection |
| Performance issues caused by slow queries or PHP code | GES is edge security, not application optimization — fix the code first |
| Customer's own internal monitoring bots are the "bot traffic" | Blocking the customer's own tools is not the solution |
| Bot traffic is high but entirely served from Varnish cache (high cache rate) | If bots aren't consuming PHP workers, GES provides less value — they're already being served cheaply |

## How to Position for AMs

### Strong positioning (security-led):
*"We're seeing [X]K credential-stuffing attempts per day on wp-login — that's [X]% of this site's PHP traffic being consumed by a botnet trying to brute-force passwords. GES's WAF would block these patterns at the edge before they reach the server, which both reduces PHP load and eliminates the security risk."*

### Moderate positioning (performance-led):
*"GES includes Argo Smart Routing which optimizes the network path for every request, plus Cloudflare's CDN for global edge caching. For a site with international visitors, this typically improves TTFB by 20-40%."*

### Weak positioning (avoid):
- Don't claim GES will block specific legitimate crawlers (Facebook, Google, etc.)
- Don't claim specific percentage reductions in bot traffic without knowing the bot composition
- Don't position GES as a fix for application-level performance problems

## Pricing Notes

- Paid add-on — ranges from a few hundred dollars to ~15% of customer MRR
- Price sensitivity varies — agencies and SMBs may push back; enterprise and ecommerce customers often see immediate value
- Free AN upgrade should always be recommended first for Legacy Network customers

## DDoS Context

For full DDoS detection, mitigation, and escalation details, see `platform/ddos-mitigation.md`.

Key points for SE investigations:
- **Legacy/Direct DNS customers** have minimal DDoS protection — strongest GES recommendation
- **AN customers** already have network-layer DDoS protection — GES adds WAF/bot management for application-layer attacks
- **UAM (Under Attack Mode)** can be enabled on both AN and GES via OverDrive dashboard
- **Cache busting patterns** (random query strings in logs) are a strong GES trigger — WAF can challenge these at the edge
- **`-wpe-cdncheck-` endpoint** exposes pod origin IP even through Cloudflare — known risk, not fixable by GES

## Sources

- Internal document: "AN/GES network options" (PDF)
- Internal document: "SYS-WP Engine DDoS Detection and Mitigation" (PDF, 12 pages)
- Field experience: Pod 213877 investigation (GES overclaim on Facebook crawlers — corrected)
- CLAUDE.md investigation guidelines
