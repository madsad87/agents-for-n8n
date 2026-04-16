---
product: WP Engine DDoS Detection and Mitigation
internal_name: ddos-mitigation
last_verified: 2026-04-06
verified_by: Madison Sadler (SE) — sourced from internal SYS-WP Engine DDoS Detection and Mitigation doc
---

## Overview

WP Engine has layered DDoS protections depending on the customer's network configuration (Legacy/Direct DNS, Advanced Network, or GES). The primary defense strategy is to route traffic through Cloudflare (AN or GES), which mitigates most network and transport layer attacks at the edge before they reach WPE infrastructure.

## Attack Types and Mitigation Matrix

### Network/Transport Layer Attacks

These target network infrastructure — server's ability to process connections. Targeted at domain A/CNAME records or IP addresses.

| Attack | Description | Detection | AN/GES Mitigation | Direct DNS Mitigation |
|--------|------------|-----------|-------------------|----------------------|
| **SYN Flood** | Incomplete TCP handshakes overwhelm conntrack table | Kapacitor conntrack monitoring (`prodeng_farm_conntrack_table_full_alert.tick`) | Fully mitigated | TCP Syn Cookies enabled by default (rarely an issue now) |
| **UDP Flood** | Mass UDP packets to random ports | Manual — `netstat -apun \| grep -i "udp"` | Fully mitigated | No documented mitigation for direct DNS |
| **ICMP Attacks** | Mass ping requests exhaust bandwidth | Manual — `netstat -s \| grep -i icmp` | Fully mitigated | Experimental iptables rules only |
| **Amplification** | NTP/DNS/SMURF protocol amplification | Check network graphs, netstat | Fully mitigated | No documented mitigation; large attacks require Google to black-hole IPs |
| **TCP Connection Floods** | Keep connections open to exhaust capacity | Check netstat for TCPTW (Time Wait) status | Fully mitigated | No documented mitigation |

**Key takeaway:** ALL network/transport layer attacks are fully mitigated by AN or GES. Direct DNS customers have limited or no protection.

### Application Layer Attacks

These target the application — overwhelm or exploit web server request processing.

| Attack | Description | Detection | Mitigation |
|--------|------------|-----------|------------|
| **HTTP Request Floods** | Deluge of HTTP requests | Redshell tools: `alog`, `nlog`, `apachewatch`, `fpmwatch`, `calc-bsph` | AN/GES: Enable UAM (Under Attack Mode) or Managed Challenge via OverDrive. Direct DNS: Block IPs/UAs via nginx rewrites, disable site (`touch _wpeprivate/disable-site`), migrate to quarantine pod |
| **Cache Busting** | Requests with random query strings bypass caching (e.g., `/?ljfasldfjssldfjal`, `/?s=123456`) | Same tools — look for large numbers of unique URLs | Strip query strings via nginx rewrite rules. Can remove specific args (utm=, s=) or all query strings as last resort |
| **Slow and Low** (Slowloris, R-U-Dead-Yet) | Open connections and keep them alive | Check established connections: `netstat -an \| grep ESTABLISHED \| wc -l`, `conntrack -C` | AN/GES handles this. Classic/AWS: Apache LPK (Long Process Killer) kills processes >60s. Apache `mod_reqtimeout` limits request length |
| **XML-RPC Attacks** | Exploit WordPress xmlrpc.php vulnerabilities | High volume of requests to `xmlrpc.php` in logs | `mod_security` rules on EVLV block non-whitelisted UAs. Classic: `BadBoyz` scanner blocks bad actors. WordPress auto-patches for known vulns |

## Mitigation Escalation Path

### For AN/GES Customers
1. **Enable UAM** (Under Attack Mode) or Managed Challenge in Cloudflare dashboard
   - Accessible to CX via OverDrive dashboard config → Domain page
   - Can also be triggered via StackStorm automation

### For Direct DNS (Legacy) Customers
Escalation order:
1. **Block offending IPs or User Agents** with nginx rewrites in OverDrive
   - Unreliable for large attacks, may block legitimate traffic
2. **Disable the site** — `touch _wpeprivate/disable-site` → returns 503
   - Only for non-production sites or customer-approved downtime
3. **Migrate to quarantine pod** and work with customer to update DNS to AN/GES
   - Quarantine clusters: `overdrive.wpengine.io/report/quarantined_clusters/`
4. **GCP-level firewall rules** — block ALL traffic except allowed sources (Cloudflare, Akamai, WPE internal IPs, phpMyAdmin, Atlas, SFTP/SSH Gateway)
   - Classic: `/opt/olympus/scripts/gce_firewall_manager.sh`
   - EVLV: `evolvectl`
   - AN/GES customers still reachable; direct DNS customers go offline
5. If attack targets IP directly (not domain), migration won't help — need GCP black-holing

## Cache Busting Mitigation Details

### Strip specific query arguments
```nginx
# Remove "removeme" query argument
if ( $args ~* ^(.*(?:&|^))(?:removeme)(?:&|$|=[^&]*&?))(.*)  ) {
  set $q1 $1; set $q2 $2;
  rewrite .* "${uri}?${q1}${q2}?" permanent ;
}
```

### Nuclear option — remove ALL query strings
```nginx
# Last resort — breaks plugins that use query strings
if ( $request ~ "GET /.*\?" ) {
  rewrite (.*) $1? permanent ;
}
```

## Platform Protections (Always Active)

| Protection | Platform | Notes |
|-----------|----------|-------|
| TCP Syn Cookies | Classic + EVLV | `net.ipv4.tcp_syncookies=1` enabled by default |
| Apache LPK | Classic + EVLV | Kills processes >60 seconds. Can be disabled via feature flags (premium pods only) |
| Apache `mod_reqtimeout` | Classic/AWS | `RequestReadTimeout header=20-40,minrate=500` / `body=10,minrate=500` |
| Apache KeepAlive | Classic/AWS | `KeepAlive Off`, `MaxKeepAliveRequests 1000`, `KeepAliveTimeout 20` |
| `mod_security` xmlrpc rules | EVLV | Blocks non-whitelisted UAs hitting xmlrpc.php |
| BadBoyz scanner | Classic | `/etc/wpengine/bin/block-bad-actor-ips.sh` blocks known bad actors |
| Nginx rate limiting | All | `/etc/wpengine/nginx/zone-limits.conf` — `rate=30r/s` but set too high for effective DDoS mitigation |
| GKE LB alerts | EVLV | Alerts when ingress >50 MB/s per backend service. PagerDuty: "EVLV - Load Balancer DoS" |

## Known Risks

### `-wpe-cdncheck-` Endpoint Exposure
- `/-wpe-cdncheck-` URI is accessible even through CDN — allows checking if install is hosted on WPE
- Attacker can read `X-WPE-Cluster` header → get cluster ID → resolve `pod-${CID}.wpengine.com` DNS → find origin IP
- **Exposes pod ingress IP even when all customers point through Cloudflare**

### AWS DDoS Rules Limitation
- Cannot enable the "nuclear option" (block all except CF/internal IPs) on AWS clusters
- Makes DDoS mitigation harder on AWS HA clusters vs GCP

### LPK Disabling Risk
- Customers on premium pods can request LPK disable for long-running processes
- This removes protection against slow-and-low attacks
- Recommendation: use `wp-cli` via SSH Gateway or `wp-cron` for long processes instead of disabling LPK entirely

## Automation

| System | Trigger | Action |
|--------|---------|--------|
| StackStorm | SQS DDoS event (`aws.sqs_new_message`) | Enable UAM on affected domains |
| StackStorm | Conntrack table maxed | Enable Google Firewall Tags + PagerDuty alert |
| StackStorm | Cloudflare notification (site still unhealthy post-mitigation) | Post to #production-status |
| OverDrive | Manual CX action | Enable/disable UAM via config → Domain dropdown |

## SE Investigation Relevance

When investigating a pod and finding DDoS-like patterns:

1. **Check network type first** — Legacy/Direct DNS customers are significantly more vulnerable
2. **AN/GES mitigates network-layer attacks automatically** — don't recommend GES solely for attacks that AN already handles
3. **Application-layer attacks (HTTP floods, cache busting, xmlrpc)** are where GES's WAF and Bot Management add value over AN
4. **Cache busting via query strings** is common and often mistaken for organic traffic — check for random `?s=` or `?utm=` patterns
5. **xmlrpc.php attacks** are platform-managed (mod_security + BadBoyz) — recommend keeping WordPress updated rather than GES for this specific vector

## Sources

- Internal document: "SYS-WP Engine DDoS Detection and Mitigation" (PDF, 12 pages)
