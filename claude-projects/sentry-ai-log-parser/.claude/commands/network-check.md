# WP Engine Network Type Check

Use when you need to identify a site's network type — Legacy, Advanced Network (AN), or Global Edge Security (GES). Run when flagging Legacy Network sites for free upgrade, confirming GES status before recommending it as an addon, or verifying network configuration during `/scout`.

## Pre-Check: Gather Required Information

**Determine what the user provided:**

1. **Install name(s)** (e.g., "mysite", "clientstore")
   - If provided: Use SSH method (dns-check) — requires pod number and SSH access
2. **Domain(s)** (e.g., "example.com", "www.clientsite.com")
   - If provided: Use local curl method — no SSH needed
3. **Both** — use whichever is more convenient, or both for cross-verification

**If install names are provided, also need:**
- **Pod Number** (e.g., "213668" or "pod-213668")
- **SSH Configuration** — check `~/.ssh/config` for correct WP Engine username

**If neither install names nor domains are provided, ask:**
```
I'll help identify the WP Engine network type. Please provide:

1. Install name(s) OR domain(s) to check
2. If using install names: Pod number (e.g., 213668)

I can check via SSH (install names) or locally via curl (domains).
```

## Method 1: SSH — `dns-check` (Install Names)

Use this when you have install names and SSH access to the pod.

### Steps

1. **Connect via SSH:**
   ```bash
   ssh {username}@pod-{id}.wpengine.com
   ```

2. **Run dns-check for each install:**
   ```bash
   dns-check {install_name}
   ```

3. **Interpret the output:**
   - The `dns-check` command returns DNS records and network configuration for the install
   - Look for references to Advanced Network, GES, or legacy DNS patterns
   - Cross-reference with the Network Type Reference table below

## Method 2: Local curl (Domains)

Use this when you have domains and want a quick check without SSH.

### Steps

For each domain, run locally:

```bash
curl -sI "https://{domain}" 2>/dev/null | grep -i "x-wpe-edge"
```

**Interpret the response:**

- **Header present with value `AN`** → Advanced Network
- **Header present with value `GES`** → Global Edge Security
- **Header absent (no `x-wpe-edge`)** → Legacy Network

**Alternative: full header check for more context:**

```bash
curl -sIL "https://{domain}" 2>/dev/null | grep -iE "x-wpe-edge|server|x-cache|cf-ray"
```

- `cf-ray` header present → site is behind Cloudflare (AN or GES)
- No `cf-ray` → likely Legacy

**DNS verification (optional, for confirmation):**

```bash
dig +short {domain}
```

- Resolves to `141.193.213.10` or `141.193.213.11` → Advanced Network
- CNAME to `*.wpenginepowered.com` → Advanced Network
- CNAME to `*.wpeproxy.com` → Global Edge Security (GES)
- A record to a direct server IP → Legacy Network

## Network Type Reference

| Network | `x-wpe-edge` Header | DNS Pattern | Key Features |
|---------|---------------------|-------------|--------------|
| Legacy | (none) | A record to server IP directly | No CDN, no Cloudflare |
| Advanced Network (AN) | `AN` | A: `141.193.213.10/11` or CNAME: `wp.wpenginepowered.com` | Cloudflare CDN, HTTP/3, Polish |
| Global Edge Security (GES) | `GES` | CNAME: `*.wpeproxy.com` | Cloudflare WAF, Argo Smart Routing, Tiered Caching |

## Decision Logic

| Scenario | Recommended Method |
|----------|--------------------|
| Have install name + SSH access | SSH `dns-check` (most detail) |
| Have domain only, no SSH | Local `curl` (fastest) |
| Have both | Use `curl` for quick answer; `dns-check` for full detail |
| Checking multiple domains quickly | Local `curl` in a loop |
| Need DNS record details | Combine `curl` + `dig` locally |

## Multiple Sites

When checking multiple installs or domains, present results in a summary table:

```
| Install / Domain | Network Type | Method Used | Notes |
|------------------|-------------|-------------|-------|
| example.com      | AN          | curl        | x-wpe-edge: AN |
| clientsite.com   | GES         | curl        | x-wpe-edge: GES |
| oldsite.com      | Legacy      | curl        | No x-wpe-edge header |
```

## Success Criteria

Your check is complete when you have:

- Identified the network type for each provided install/domain
- Presented results clearly (table format for multiple sites)
- Noted any anomalies (e.g., domain not resolving, unexpected headers)
