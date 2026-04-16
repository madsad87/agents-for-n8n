# Woo Audit — WooCommerce Performance & Revenue Impact Analysis

Use when WooCommerce is detected in the install's plugin list and you need to assess ecommerce-specific performance — cart fragment refresh volume, checkout 504s (lost sales), Facebook ad landing failures (wasted spend), and Ecom Performance addon fit. Skip if WooCommerce is not installed.

## Required Input

- **Pod number** (e.g., "228209")
- **Install name** (e.g., "testwebsite773")
- **Context from `/scout`** if available (plugin list, slow requests, 504 URLs)

**Prerequisite:** Confirm WooCommerce is installed before running this skill. If not installed, note this and skip.

```bash
ls /nas/content/live/{install}/wp-content/plugins/ | grep -i woo
```

## Phase 1: WooCommerce Traffic Volume

Run in parallel:

### Batch 1: Endpoint Traffic
```bash
# Cart fragment refreshes (the #1 WooCommerce performance issue)
for f in /var/log/nginx/{install}.access.log*; do zcat -f "$f" 2>/dev/null; done | awk -F'|' '$10 ~ /wc-ajax=get_refreshed_fragments/' | wc -l

# All wc-ajax requests by action
for f in /var/log/nginx/{install}.access.log*; do zcat -f "$f" 2>/dev/null; done | awk -F'|' '$10 ~ /wc-ajax/' | grep -oP 'wc-ajax=\K[^& ]+' | sort | uniq -c | sort -rn

# Checkout page requests
for f in /var/log/nginx/{install}.access.log*; do zcat -f "$f" 2>/dev/null; done | awk -F'|' '$10 ~ /checkout/' | wc -l

# Cart page requests
for f in /var/log/nginx/{install}.access.log*; do zcat -f "$f" 2>/dev/null; done | awk -F'|' '$10 ~ /\/cart/' | wc -l

# My-account requests
for f in /var/log/nginx/{install}.access.log*; do zcat -f "$f" 2>/dev/null; done | awk -F'|' '$10 ~ /my-account/' | wc -l
```

### Batch 2: WooCommerce Errors & Slow Requests
```bash
# 504s on WooCommerce endpoints
for f in /var/log/nginx/{install}.access.log*; do zcat -f "$f" 2>/dev/null; done | awk -F'|' '$5 == 504 && ($10 ~ /wc-ajax/ || $10 ~ /checkout/ || $10 ~ /cart/ || $10 ~ /my-account/)' | awk -F'|' '{print $10}' | awk '{print $1, $2}' | sort | uniq -c | sort -rn

# Slow WooCommerce requests (>5s)
for f in /var/log/nginx/{install}.access.log*; do zcat -f "$f" 2>/dev/null; done | awk -F'|' '$9+0 > 5 && ($10 ~ /wc-ajax/ || $10 ~ /checkout/ || $10 ~ /cart/)' | wc -l

# Cart fragment execution times
for f in /var/log/nginx/{install}.access.log*; do zcat -f "$f" 2>/dev/null; done | awk -F'|' '$10 ~ /wc-ajax=get_refreshed_fragments/ {printf "%.1fs\n", $9}' | sort -rn | head -20
```

## Phase 2: Cart Fragment Analysis

Cart fragment refreshes (`wc-ajax=get_refreshed_fragments`) are the single most common WooCommerce performance problem. By default, WooCommerce refreshes the cart on **every page load** for **every visitor**, even those with empty carts.

### Impact Calculation
```
Daily cart fragment requests = 7-day total / 7
Cart fragment % of PHP traffic = Cart fragment requests / Total Apache requests × 100
Average execution time = Sum of execution times / Count
Workers consumed = (Requests per second) × (Average execution time)
```

### Ecom Performance Addon Assessment

The **Ecom Performance addon (Live Cart)** replaces the default cart fragment AJAX with a lightweight JavaScript-based cart that only refreshes when the cart actually changes.

| Cart Fragment Volume | Avg Exec Time | Ecom Addon Value |
|---------------------|---------------|-----------------|
| >5,000/day | Any | Very High — immediate PHP reduction |
| 2,000-5,000/day | >3s | High — significant worker savings |
| 1,000-2,000/day | >5s | Moderate — worth it for slow execution |
| <1,000/day | <3s | Low — minimal impact |

## Phase 3: Checkout & Revenue Impact

### 504s on Revenue Paths
```
Checkout 504s = direct lost sales
Cart 504s = abandoned carts (user may retry)
My-account 504s = post-purchase friction (order tracking, downloads)
```

### Facebook Ad Landing Impact
```bash
# WooCommerce product pages from Facebook ads
for f in /var/log/nginx/{install}.apachestyle.log*; do zcat -f "$f" 2>/dev/null; done | grep 'fbclid=' | grep -c '/product/'

# 504s on pages with fbclid (wasted ad spend)
for f in /var/log/nginx/{install}.access.log*; do zcat -f "$f" 2>/dev/null; done | awk -F'|' '$5 == 504 && $10 ~ /fbclid/' | wc -l
```

## Phase 4: WooCommerce Plugin Stack

```bash
# WooCommerce-related plugins
ls /nas/content/live/{install}/wp-content/plugins/ | grep -iE 'woo|wc-|payment|stripe|paypal|cart|checkout|subscription|membership'

# Check for known heavy plugins
ls /nas/content/live/{install}/wp-content/plugins/ | grep -iE 'woocommerce-product-bundles|woocommerce-subscriptions|woocommerce-memberships|woocommerce-bookings|wc-dynamic-pricing'
```

### Known Heavy WooCommerce Plugins

| Plugin | Impact | Why |
|--------|--------|-----|
| Product Bundles | High | Complex price calculations on cart/checkout |
| Subscriptions | Medium-High | Renewal processing, status checks |
| Dynamic Pricing | High | Price recalculation on every cart update |
| Bookings | Medium | Availability checks against calendar |
| Memberships | Medium | Access control checks on every page |
| YITH plugins (many) | Variable | Often add admin-ajax calls per page |

## Output Format

```markdown
## WooCommerce Audit: {install} on Pod {pod-id}

### WooCommerce Traffic (7-Day)

| Endpoint | Requests | % of PHP Traffic | Avg Exec Time |
|----------|----------|-----------------|---------------|
| Cart fragment refresh | X | X% | Xs |
| Checkout | X | X% | — |
| Cart page | X | X% | — |
| My-account | X | X% | — |
| Other wc-ajax | X | X% | — |
| **Total WooCommerce** | **X** | **X%** | — |

### Revenue-Impact Errors (7-Day)

| Error Type | Endpoint | Count | Impact |
|-----------|----------|-------|--------|
| 504 | Checkout | X | Lost sales |
| 504 | Cart | X | Abandoned carts |
| 504 | Product pages (fbclid) | X | Wasted ad spend |
| Slow >5s | Cart fragments | X | Degraded experience |

### Cart Fragment Assessment

**Daily cart fragment requests:** X
**Average execution time:** Xs
**PHP workers consumed by fragments:** X

**Ecom Performance Addon Recommendation: {Very High / High / Moderate / Low}**
{Rationale — e.g., "4,200 daily cart fragment requests at 3.2s average = 0.16 workers permanently occupied. Ecom addon would eliminate these entirely."}

### WooCommerce Plugin Stack

| Plugin | Concern Level |
|--------|--------------|
| {plugin} | {None / Monitor / Investigate} |

### Recommendations

1. **{Priority 1}** — {specific action}
2. **{Priority 2}** — {specific action}
```

## Rules

- **Confirm WooCommerce is installed before running** — don't waste SSH commands on non-WooCommerce sites
- **Every checkout 504 is a potential lost sale** — always quantify revenue impact
- **Cart fragment refresh is THE #1 WooCommerce performance issue** — always check it first
- **Ecom Performance addon is the fix for cart fragments** — position it when volume justifies
- **WooCommerce traffic is inherently uncacheable** — don't compare cache rates against non-WooCommerce targets
- **Facebook ad landing 504s = wasted ad spend** — always check fbclid + 504 correlation
- **Feed WooCommerce data to `/size`** — WooCommerce changes the execution time assumptions (5-8s vs 2-3s)
