# SRE Runbook: High CPU Saturation & Process Starvation

**ID:** `RUNBOOK-CPU-001`  
**Domain:** Performance & Capacity  
**Applies To:** Linux/Windows Hosts, API Gateways, Microservices, Lab PCs  
**Severity:** High to Critical  

## 1. Symptom Profile
- Host CPU utilization sustained above 85% for more than 5 minutes.
- Elevated system load average exceeding the number of physical CPU cores.
- Thread starvation causing request timeouts, HTTP 504 Gateway Timeouts, or sluggish agent telemetry check-ins.

## 2. Root Cause Classification
- **Thread Loop / Uncontrolled Recursion:** Application bug executing tight spin-locks or unoptimized nested iterations.
- **Garbage Collection / JIT Thrashing:** High memory churn triggering perpetual stop-the-world or heavy background GC.
- **Crypto-Mining / Rogue Worker Process:** Unauthorized execution or orphaned background jobs consuming 100% of single/multi cores.
- **Sudden Traffic Spike:** Legitimate surge in inbound API requests without horizontal autoscaling triggers.

## 3. Immediate Diagnostic Commands
```bash
# Identify top 5 CPU-consuming processes on Linux
ps aux --sort=-%cpu | head -n 6

# Check per-core CPU utilization breakdown (user, system, iowait)
mpstat -P ALL 1 3

# On Windows PowerShell:
Get-Process | Sort-Object CPU -Descending | Select-Object -First 5 -Property Id, ProcessName, CPU, WorkingSet
```

## 4. Remediation Steps
1. **Targeted Process Intervention:**
   - If a rogue or non-critical process is identified, gracefully signal or terminate:
     `kill -15 <PID>` (or `Stop-Process -Id <PID> -Force` on Windows).
2. **Workload Throttle / Rate Limiting:**
   - Activate API rate limits or shed load at the Caddy proxy level using header rate limiting.
3. **Horizontal or Vertical Autoscaling:**
   - Provision additional worker replicas or upgrade the instance type if steady-state demand exceeds capacity.
4. **Agent Telemetry Verification:**
   - Confirm agent CPU returns to baseline below 65% in the CloudOps Intel Telemetry stream.
