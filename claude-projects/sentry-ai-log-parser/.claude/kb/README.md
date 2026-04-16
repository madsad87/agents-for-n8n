# WP Engine Product Knowledge Base

Internal knowledge base for Sentry AI investigations. Provides structured product capability data so addon recommendations and solution positioning are accurate and evidence-based.

## Purpose

Replace general knowledge with verified product capabilities. Every recommendation in an investigation report should be backed by what the product actually does — not what we think it does.

**Origin:** GES was overclaimed as able to block Facebook meta-externalagent crawlers during a Pod 213877 investigation. It can't — those are legitimate platform crawlers, not the malicious traffic GES is designed to filter. This KB prevents similar overclaims.

## Structure

```
.claude/kb/
├── README.md              ← This file
├── INDEX.md               ← Product index with status and last-verified dates
├── addons/                ← Addon capability files
│   ├── ges.md             ← Global Edge Security
│   ├── apm.md             ← Application Performance Monitoring
│   ├── psb.md             ← Page Speed Boost (NitroPack)
│   ├── ecom.md            ← Ecommerce Performance (Live Cart)
│   └── spm.md             ← Smart Plugin Manager
├── platform/              ← Platform product files
│   ├── server-tiers.md    ← P0-P10, shared vs dedicated vs HA
│   ├── network.md         ← Advanced Network vs Legacy Network
│   ├── headless.md        ← Atlas / Headless WordPress
│   └── ...
└── sources/               ← Drop raw source documents here for processing
```

## How to Add Knowledge

1. Drop source documents (PDFs, docs, URLs, notes) into `sources/`
2. Tag them with which product they cover
3. Claude will extract capabilities, limitations, and trigger conditions into the structured product files

## Schema for Product Files

Each product file follows this structure:

```markdown
---
product: {Product Name}
internal_name: {internal slug}
last_verified: {YYYY-MM-DD}
verified_by: {who confirmed this is accurate}
---

## What It Does
{Specific capabilities — not marketing copy}

## What It Does NOT Do
{Explicit boundaries — prevents overclaiming}

## When to Recommend
{Evidence-based triggers from log analysis}
- Trigger: {condition} → Recommend because: {reason}

## When NOT to Recommend
{Anti-patterns and contraindications}
- Anti-pattern: {condition} → Skip because: {reason}

## How to Position for AMs
{Framing guidance for Zendesk responses}

## Pricing/Tier Notes
{Any tier-specific availability or pricing context}

## Sources
{Links or references used to build this entry}
```

## Integration Points

Once populated, this KB is referenced by:
- **Advisor role** in `/investigate` — addon assessment section
- **Narrator role** — Zendesk addon grid rationale
- **Bot audit skill** — GES value assessment
- **Any skill** that makes product recommendations

## Status

| Product | File | Status |
|---------|------|--------|
| GES | `addons/ges.md` | **Done** — verified 2026-04-06 |
| APM | `addons/apm.md` | **Done** — verified 2026-04-06 |
| PSB | `addons/psb.md` | Pending |
| Ecom | `addons/ecom.md` | Pending |
| SPM | `addons/spm.md` | Pending |
| Server Tiers | `platform/server-tiers.md` | **Done** — verified 2026-04-06 |
| Network | `platform/network.md` | **Done** — verified 2026-04-06 |
| DDoS Mitigation | `platform/ddos-mitigation.md` | **Done** — verified 2026-04-06 |
| 504 Queuing | `platform/504-queuing.md` | **Done** — verified 2026-04-06 |
| Headless/Atlas | `platform/headless.md` | Pending |
| Bot Classification | `reference/bot-classification.md` | **Done** — verified 2026-04-07 |
