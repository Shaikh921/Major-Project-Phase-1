# SRE Runbook: Brute Force Authentication & Perimeter Intrusion

**ID:** `RUNBOOK-SEC-004`  
**Domain:** Security & Identity  
**Applies To:** Caddy Reverse Proxy, SSH Bastions, Super Admin Authentication Endpoints  
**Severity:** High to Critical  

## 1. Symptom Profile
- Surging volume of HTTP 401 Unauthorized or 403 Forbidden responses on `/api/v1/auth/login`.
- High rate of repeated failed login attempts against identical or rotating usernames from specific external IP addresses.
- Security event detections: `brute_force_detected`, `ssh_auth_failure`, or `credential_stuffing_wave`.
- Elevated network connection states in `SYN_RECV` or rapid TCP connection recycling.

## 2. Root Cause Classification
- **Automated Credential Stuffing:** Botnet attacking exposed management endpoints with leaked credential lists.
- **Password Spray Attack:** Slow-rate attempts testing common passwords across hundreds of known enterprise usernames to avoid naive rate limits.
- **Port / Vulnerability Scanner:** Automated internet scanners (e.g., Shodan, Censys) probing for open admin dashboards or SSH ports.
- **Misconfigured Automation Script:** Internal agent or cron worker attempting to authenticate with an expired or rotated API key.

## 3. Immediate Diagnostic Commands
```bash
# Identify top IP addresses generating failed login attempts
grep "401" /var/log/caddy/access.log | awk '{print $1}' | sort | uniq -c | sort -nr | head -n 10

# Inspect active TCP connections by remote address
netstat -ntu | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -n

# Query CloudOps Intel Security Event audit log
SELECT ip_address, count(*) as failed_attempts FROM security_events WHERE event_type = 'auth_failure' GROUP BY ip_address ORDER BY failed_attempts DESC LIMIT 10;
```

## 4. Remediation Steps
1. **Immediate IP Perimeter Block:**
   - Drop offending source IPs at firewall or Caddy level:
     `iptables -A INPUT -s <OFFENDING_IP> -j DROP` or add IP ban rule in Caddyfile reverse proxy block.
2. **Account Lockout & Password Invalidation:**
   - Temporarily suspend accounts targeted with > 10 failed attempts and require password reset via email verification.
3. **Enforce Multi-Factor Authentication (MFA):**
   - Ensure all admin and operator accounts require TOTP or security keys for privileged access.
4. **Audit Token Revocation:**
   - Invalidate active JWT refresh tokens if compromised credentials or session hijacking is suspected.
