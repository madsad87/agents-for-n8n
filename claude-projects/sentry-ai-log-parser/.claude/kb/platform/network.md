---
product: WP Engine Network Options
internal_name: network
last_verified: 2026-04-06
verified_by: Madison Sadler (SE) — sourced from internal AN/GES network options doc
---

## Overview

There are 3 network tiers a WP Engine site can use. All are powered by Cloudflare (except Legacy which is direct-to-origin).

| Tier | Cost | Cloudflare Zone | Key Differentiator |
|------|------|----------------|-------------------|
| Legacy Network | Free | None — DNS direct to WPE | No performance or security benefits. Being deprecated. |
| Advanced Network (AN) | Free | `wpeenginepowered.com` (SSL for SaaS) | CDN, basic DDoS, SSL/TLS, web optimization |
| Global Edge Security (GES) | Paid | `wpewaf.com` (SSL for SaaS) | Everything in AN + WAF, Argo, Advanced DDoS, Rate Limiting, Bot Management |

## Legacy Network

- Customer points DNS directly to WP Engine origin servers
- **No performance or security benefits**
- Being deprecated — enforcement program started in 2024 cohorts
- New domains cannot choose Legacy Network as of May 16, 2023 (exceptions for 3rd-party CDN incompatibilities)
- **Detection:** DNS resolves to Google Cloud IP (34.75.x.x range) = Legacy Network

### SE Action
Always flag Legacy Network sites in investigations. Recommend free Advanced Network upgrade — it's a no-cost improvement the customer can make immediately.

## Advanced Network (AN)

- DNS points through Cloudflare to WPE
- **Free** — included with all plans
- Strategy: put ALL customers behind Cloudflare (AN or GES)

### AN Features
- CDN
- SSL/TLS certificates
- Basic DDoS protection
- Analytics
- Logs
- Web Optimization
- Page Rules
- Workers
- Full Page Cache
- Accelerated Mobile Pages
- TLS 1.3

## Global Edge Security (GES)

- DNS points through Cloudflare CDN to WPE with **enhanced** performance and security
- **Paid add-on** — ranges from a few hundred to 15% of customer MRR
- Uses Cloudflare zone `wpewaf.com`

### GES Features (everything in AN plus)
- **WAF** (Managed Web Application Firewall)
- **Argo** (Smart Routing — optimizes network path)
- **Advanced DDoS** protection
- **Rate Limiting**
- **Bot Management**
- **Waiting Room**
- TLS 1.3

See `addons/ges.md` for full GES capability matrix and recommendation triggers.

## Architecture: Cloudflare SSL for SaaS

Both AN and GES use Cloudflare's "SSL for SaaS" product. This means:
- All AN customers share the `wpeenginepowered.com` zone
- All GES customers share the `wpewaf.com` zone
- Each customer domain is a "customer hostname" within the zone

### Limitation
Many Cloudflare features operate at the **zone level**, not the hostname level. This means:
- All AN/GES customers share the same network configuration within their zone
- Individual customer requests for specific Cloudflare features may not be possible if the feature is zone-level
- Adding/removing a zone-level feature affects ALL customers on that zone
- For specialized requests (especially from premium customers), WPE can offer a **dedicated Cloudflare zone** — but this requires architecture work

## Feature Comparison Matrix

| Feature | AN Basic | AN Performance | AN Video | GES | GES Security |
|---------|----------|---------------|----------|-----|-------------|
| CDN | x | x | x | x | x |
| SSL/TLS certs | x | x | x | x | x |
| Basic DDoS | x | x | x | x | x |
| Analytics | x | x | x | x | x |
| Logs | x | x | x | x | x |
| Web Optimization | x | x | x | x | x |
| Page Rule | x | x | x | x | x |
| Workers | x | x | x | x | x |
| Full Page Cache | | x | | | |
| Accelerated Mobile Page | | x | | x | x |
| Waiting Room | | | | | x |
| WAF | | | | x | x |
| Argo | | | | x | x |
| Advanced DDoS | | | | x | x |
| Stream | | | x | | |
| Rate Limiting | | | | | x |
| Bot Management | | | | | x |
| TLS version | 1.2 | 1.3 | 1.3 | 1.3 | 1.3 |

*Note: "AN Performance", "AN Video", and "GES Security" were proposed tiers from this internal doc. Verify current product lineup — some may not have launched.*

## Sources

- Internal document: "AN/GES network options" (PDF, undated — references 2023-2024 timelines)
