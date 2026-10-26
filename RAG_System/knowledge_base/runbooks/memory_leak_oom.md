# SRE Runbook: Memory Leak & Out-of-Memory (OOM) Degradation

**ID:** `RUNBOOK-MEM-002`  
**Domain:** Performance & Reliability  
**Applies To:** Backend Application Nodes, Worker Pods, Python/Node/Java Runtimes  
**Severity:** Critical  

## 1. Symptom Profile
- Monotonically increasing memory usage (RAM / Swap) over time without recovery after request completion.
- Kernel OOM Killer events logged (`dmesg` or system event log) terminating processes unexpectedly.
- Sudden container crash restarts (Exit Code 137).
- Persistent memory alerts triggered in CloudOps Intel dashboard (`memory_percent > 85%`).

## 2. Root Cause Classification
- **Application Cache Accumulation:** In-memory LRU caches or dictionaries growing unbounded without TTL or size eviction.
- **Unclosed Connections / File Descriptors:** Database cursor leaks, unclosed HTTP client sessions, or dangling WebSocket connections.
- **Circular References / Object Retention:** Long-lived event listeners or module-level lists retaining garbage-collected objects.
- **Buffer Bloat:** Large in-memory file buffering during telemetry batch imports or export report generations.

## 3. Immediate Diagnostic Commands
```bash
# Check memory breakdown and swap status
free -m
vmstat 1 5

# Inspect top memory-consuming processes
ps aux --sort=-%mem | head -n 6

# Check system logs for kernel OOM killer triggers
dmesg -T | grep -i "killed process"

# On Windows:
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 5 -Property Id, ProcessName, WorkingSet64
```

## 4. Remediation Steps
1. **Graceful Service Restart:**
   - Drain active requests and cycle the worker processes to release heap memory:
     `systemctl restart cloudops-backend` or `Restart-Service CloudOpsBackend`.
2. **Increase Swap Headroom (Temporary Buffer):**
   - Ensure swap is active to prevent immediate kernel OOM while investigating heap dumps.
3. **Inspect Application Heap Profile:**
   - Capture memory allocations using `tracemalloc` (Python) or heap snapshot tools to locate leaking data structures.
4. **Tune Worker Recycling:**
   - Configure process manager max-requests lifecycle (e.g. Uvicorn `--limit-max-requests 5000`) to periodically refresh worker memory footprint.
