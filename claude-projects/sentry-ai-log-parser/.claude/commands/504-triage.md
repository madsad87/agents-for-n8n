# 504 Triage — Classify 504 Errors by Source

Use when 504 count is high (>50) and you need to separate real performance issues from noise — scanner probes, bot hits, and admin traffic inflate 504 counts and mislead investigations. Run this after `/scout` to classify 504s before sizing or reporting.

## Required Input

- **504 URL list** — from `/scout` data or direct SSH output
- **Total 504 count** — for percentage calculations

## Classification Buckets

### 1. Scanner/Probe (NOISE)
URLs that don't exist on WordPress sites — automated vulnerability scanners and credential hunters.

**Signatures:**
```
.env, .env.vite, .env.local, .env.production
swagger.json, openapi.json
settings.py, serverless.yml, parameters.yml, config.env
/admin, /billing, /payment, /pricing, /signup, /register, /subscribe, /dashboard
adminfuns.php, sf.php, file.php, as.php, about.php, buy.php, xmrlpc.php, wp.php
/wp-content/themes/admin.php, /wp-includes/index.php, /wp-includes/js/index.php
.git/, .circleci/, .aws/, .config
404.php, debug/default/view
```

### 2. Bot/Crawler (SECONDARY)
Legitimate pages requested by bots — real content but not human visitors.

**Detection:** Cross-reference 504 URLs with user agent data. If the URL is a real page but the requesting agent is a bot (Googlebot, bingbot, meta-externalagent, etc.), classify here.

### 3. WooCommerce (REVENUE IMPACT)
eCommerce transaction pages — each 504 is a potential lost sale.

**Signatures:**
```
wc-ajax=*, checkout, /cart, /my-account, /shop, /product/
wc-ajax=get_refreshed_fragments, wc-ajax=xoo_wsc_refresh_fragments
wc-ajax=update_order_review, wc-ajax=checkout
wc-ajax=add_to_cart, wc-ajax=get_variation
wc-ajax=wcpay_get_woopay_signature
```

### 4. Admin/Backend (INTERNAL)
Admin-side requests — affect site operators, not visitors.

**Signatures:**
```
/wp-admin/admin-ajax.php
/wp-admin/admin.php
/wp-admin/edit.php, /wp-admin/post.php
/wp-admin/plugins.php, /wp-admin/upload.php
/wp-cron.php
action=as_async_request_queue_runner
```

### 5. Events Calendar / Dynamic (APPLICATION)
Calendar, search, and filter pages with heavy database queries.

**Signatures:**
```
/wp-json/tribe/views/v2/html
/schedule/, /event/, /events/
tribe-bar-search=, tribe-bar-sort=
tribe_events_cat=, event-spotlight=
search-filter, ?s=
```

### 6. Facebook/Ad Landing (PAID TRAFFIC)
Paid advertising landing pages — wasted ad spend when they 504.

**Signatures:**
```
meta.json?utm_source=facebook
utm_campaign=FB*, utm_medium=paidsocial
fbclid=
```

### 7. Legitimate Content (USER IMPACT)
Real content pages hit by real users.

**Everything not classified above.**

## Output Format

```markdown
## 504 Triage: {install} — {total} Total

| Bucket | Count | % | Impact |
|--------|-------|---|--------|
| Scanner/Probe | X | X% | Noise — ignore |
| Bot/Crawler | X | X% | Secondary — GES would filter |
| WooCommerce | X | X% | Revenue impact — each is a potential lost sale |
| Admin/Backend | X | X% | Internal — affects operators only |
| Events/Dynamic | X | X% | Application — query optimization needed |
| Facebook/Ad Landing | X | X% | Paid traffic — wasted ad spend |
| Legitimate Content | X | X% | User impact — real visitors affected |

**Real 504 count (excluding scanner/probe):** X ({X%} of total)
**Revenue-impacting 504s (WooCommerce + Ad Landing):** X
**Application-fixable 504s (Events/Dynamic + Admin):** X
```

## Rules

- **Always separate scanner noise from real 504s** — the headline count is often misleading
- **Cross-reference with user agents** when possible to distinguish bot hits on real pages
- **Call out revenue impact explicitly** — checkout and ad landing 504s are direct money lost
- **A URL can only be in one bucket** — use the most specific match (WooCommerce > Legitimate Content)
