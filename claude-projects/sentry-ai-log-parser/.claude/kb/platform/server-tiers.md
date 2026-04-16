---
product: WP Engine Server Tiers & PHP Workers
internal_name: server-tiers
last_verified: 2026-04-06
verified_by: Madison Sadler (SE) — sourced from Embrace KB (php-workers-nginx-queue-size)
---

## Overview

WP Engine runs on three infrastructure types — GCP, AWS, and Evolve (EVLV). Each has its own plan naming and worker/queue allocations. The plan name tells you what infrastructure you're on: P-tiers = GCP or EVLV, C-tiers = AWS.

**Resolved:** Embrace KB listed P9=140/P10=160 but those values are outdated. The authoritative source is `constants.py` (P9=160, P10=180). Tables below use the correct values.

---

## GCP Infrastructure (P-Tiers)

| Plan | PHP Workers | NGINX Queue Size |
|------|-------------|------------------|
| P0b | 8 | 8 |
| P1 | 10 | 10 |
| P1.5 | 12 | 12 |
| P2 | 15 | 15 |
| P3 | 20 | 20 |
| P4 | 40 | 40 |
| P5 | 60 | 60 |
| P6 | 80 | 80 |
| P7 | 100 | 100 |
| P8 | 120 | 120 |
| P9 | 160 | 160 |
| P10 | 180 | 180 |

**GCP note:** Workers = Queue size. When all workers are busy, requests queue up to the queue size limit. When the queue is also full, nginx returns a 504.

---

## AWS Infrastructure (C-Tiers)

| Plan | PHP Workers | NGINX Queue Size |
|------|-------------|------------------|
| C1 | 20 | 40 |
| C2 | 20 | 40 |
| C3 | 40 | 80 |
| C4 | 40 | 80 |
| C5 | 60 | 120 |
| C6 | 80 | 160 |
| C7 | 100 | 200 |
| C8 | 120 | 240 |

**AWS notes:**
- Queue size is **2x workers** (unlike GCP where they're equal)
- This larger queue means AWS plans absorb more burst traffic before 504s
- C-tiers are HA (High Availability) clusters with multiple webheads
- **Custom webheads with 8+ vCPUs double workers** — e.g., 20 workers becomes 40. Rare; known example: wyzecam

---

## Evolve (EVLV) Infrastructure

| Plan | PHP Workers | NGINX Queue Size |
|------|-------------|------------------|
| P0b | 8 | 40 |
| P1 | 10 | 50 |
| P1.5 | 12 | 60 |
| P2 | 15 | 75 |
| P3 | 20 | 100 |
| P4 | 40 | 150 |
| P5 | 60 | 300 |
| P6 | 80 | 400 |
| P7 | 100 | 500 |
| P8 | 120 | 600 |
| P9 | 160 | 800 |
| P10 | 180 | 900 |

**EVLV notes:**
- Queue size is **5x workers** — dramatically larger burst absorption than GCP or AWS
- Same P-tier naming as GCP but very different queue behavior
- A P0b on EVLV has 8 workers but a 40-request queue (vs 8/8 on GCP)
- This means EVLV plans tolerate traffic spikes much better but may also mask underlying performance issues (requests queue instead of 504ing)

---

## SE Investigation Implications

### Identifying Infrastructure Type
- **P-tier plan name** → Could be GCP or EVLV. Check `wpeapi server-meta` output for infrastructure type
- **C-tier plan name** → Always AWS
- **HA cluster** (multiple webheads, synced logs) → Typically AWS C-tier

### Queue Size Matters for 504 Analysis
- **GCP (1:1 ratio):** 504s appear quickly under load — workers full = queue full = 504
- **AWS (2:1 ratio):** More burst headroom — can absorb double the workers in queue before 504
- **EVLV (5:1 ratio):** Substantial burst absorption — 504s mean the problem is severe or sustained

When investigating 504s, **the infrastructure type changes what the 504 count means:**
- 100 daily 504s on GCP P0b (8/8) = moderate concern
- 100 daily 504s on EVLV P0b (8/40) = significant concern (took a lot to exhaust that queue)

### Sizing Recommendations
- Always use the exact worker count from these tables — never estimate or use ranges
- When recommending an upgrade, show the worker jump (e.g., "P2 → P3 doubles workers from 15 to 20")
- For AWS customers, note the queue advantage when comparing to GCP tiers

---

## Sources

- Embrace KB: "PHP Workers and NGINX Queue Size" (verified 2026-03-27, confidence: high)
- Guru card ID: 3a02513c-1ba4-464a-83ec-4c8ace7d60be
