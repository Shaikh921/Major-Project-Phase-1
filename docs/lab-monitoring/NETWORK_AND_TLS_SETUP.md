# CloudOps Intel — Network & TLS Configuration Guide
**Document Version:** 1.0.0  
**Transport Protocol:** HTTPS / TLS 1.3 & TLS 1.2  
**Standard Port:** TCP 8443  

---

## 1. Network Architecture & Port Binding

All remote telemetry ingestion, enrollment requests, and administrative API traffic flow through an authenticated, encrypted reverse proxy:

```
[ Lab Workstation ] 
       |
       | TCP Port 8443 (Verified HTTPS)
       v
[ Caddy TLS Proxy ] (Terminates TLS, validates Subject Alternative Names)
       |
       | TCP Port 8000 (Loopback 127.0.0.1 cleartext)
       v
[ FastAPI Core Backend ]
```

### Network Rules & Firewall Configuration:
- **Inbound Rule on Server:** Allow TCP port `8443` from the authorized collegiate laboratory subnet (e.g. `10.227.136.0/24`).
- **Outbound Rule on Client PCs:** Allow TCP port `8443` outbound to the CloudOps Intel Server IP or DNS hostname.
- **Port 8000 Isolation:** TCP port `8000` is bound strictly to `127.0.0.1` and must **never** be exposed externally or opened in the Windows Firewall.

---

## 2. TLS Authority & Certificate Architecture

CloudOps Intel utilizes Caddy's internal Public Key Infrastructure (PKI) with Elliptic Curve Cryptography (`ECDSA P-256` / `2026 ECC Root`).

### Files & Locations:
- **Public Authority Certificate:** `data/caddy/pki/authorities/local/root.crt`
  - *Purpose:* Distributed to client workstations. Used as the trusted root CA to validate the server's certificate.
  - *Sensitivity:* **PUBLIC**. Can be safely packaged into installer zips and shared with network administrators.
- **Private Authority Key:** `data/caddy/pki/authorities/local/root.key`
  - *Purpose:* Used by Caddy on the server to sign leaf certificates.
  - *Sensitivity:* **TOP SECRET**. Strictly locked with Windows NTFS ACLs (`Administrators` and `SYSTEM` only).
  - *CRITICAL RULE:* **NEVER** copy, package, export, or transmit `root.key` to client machines, installers, git repositories, or documentation.

---

## 3. Server Configuration & Subject Alternative Name (SAN) Adaptation

The college server's final static IP or internal DNS name is determined by college IT during final deployment. Caddy must be configured with matching SAN entries so that client TLS verification succeeds without hostname mismatches.

### Current Development Configuration (`Caddyfile`):
```caddy
{
    admin off
    persist_config off
    auto_https disable_redirects
}

https://10.227.136.246:8443, https://localhost:8443 {
    tls internal

    reverse_proxy 127.0.0.1:8000 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto https
    }
}
```

### Adapting for College Production:
When College IT assigns an internal DNS name (e.g. `cloudops.college.internal`) or static IP (e.g. `192.168.50.10`):
1. Update `Caddyfile`:
   ```caddy
   https://cloudops.college.internal:8443, https://192.168.50.10:8443 {
       tls internal
       ...
   }
   ```
2. Reload Caddy:
   ```powershell
   caddy reload --config Caddyfile
   ```
3. Caddy automatically provisions a new leaf certificate signed by `root.crt` containing the new IP and DNS SANs.

---

## 4. Sensor TLS Verification & Zero-Fallback Enforcement

The sensor agent implements strict transport security in `monitoring_agent/buffer.py` and `monitoring_agent/agent.py`:

```python
import ssl
import urllib.request

def create_verified_ssl_context(ca_bundle_path: str) -> ssl.SSLContext:
    if not os.path.exists(ca_bundle_path):
        raise FileNotFoundError(f"Authority certificate not found at {ca_bundle_path}")
    
    # Strictly load only the authority root certificate
    ctx = ssl.create_default_context(cafile=ca_bundle_path)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx
```

### Enforcement Rules:
1. **No Insecure Fallback:** Remote HTTP (`http://...`) is intercepted by `validate_transport_security()` and immediately rejected with `InsecureTransportError` before any credentials, tokens, or telemetry leave the process memory.
2. **Untrusted Certificates:** If the server certificate does not chain to `root.crt`, Python raises `ssl.SSLCertVerificationError`. The agent logs an error, retains all telemetry in its persistent SQLite spool queue, and retries with backoff.
3. **No Insecure Bypass:** The sensor client has no command-line flag or configuration option to disable certificate verification in production environments.
