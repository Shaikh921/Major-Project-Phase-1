# SRE Runbook: Lab PC & Edge Hardware Sensor Telemetry Offline

**ID:** `RUNBOOK-LAB-005`  
**Domain:** IoT & Lab Device Management  
**Applies To:** Computer Labs, Edge PCs, Local Hardware Agents, Monitoring Daemons  
**Severity:** Medium to High  

## 1. Symptom Profile
- Lab PC status transitions to `offline` or `unreachable` in the Device Management dashboard.
- Last heartbeat timestamp exceeds tolerance threshold (> 5 minutes without check-in).
- Local sensor metrics (temperature, fan speed, GPU state, power draw) cease updating.
- Room or rack-level environmental telemetry displays gaps or missing telemetry points.

## 2. Root Cause Classification
- **Host Sleep / Power State Transition:** Windows or Linux machine entering unexpected S3 Sleep, Hibernation, or Fast Startup shutdown.
- **Local Network Disconnection:** Physical Ethernet cable unplugged, switch port flapping, or local DHCP lease renewal failure.
- **Daemon Crash / Service Stopped:** CloudOps local hardware agent service terminated due to unhandled OS exception or auto-update reboot.
- **Firewall / Port Egress Block:** Local host firewall (Windows Defender Firewall) blocking outbound HTTP/HTTPS telemetry push to Caddy/FastAPI backend on port 8000/8443.

## 3. Immediate Diagnostic Commands
```powershell
# Check Windows service status of local telemetry agent
Get-Service -Name "CloudOpsAgent*"

# Verify network reachability to CloudOps Intel API
Test-NetConnection -ComputerName 127.0.0.1 -Port 8000
Test-NetConnection -ComputerName 127.0.0.1 -Port 8443

# Check recent Windows Event Log for sudden shutdowns or power events
Get-WinEvent -FilterHashtable @{LogName='System'; Id=41,1074,6008} -MaxEvents 5
```

## 4. Remediation Steps
1. **Restart Local Agent Service:**
   - Restart the telemetry daemon on target Lab PC:
     `Restart-Service -Name "CloudOpsAgent" -Force`
2. **Disable Aggressive Power-Saving:**
   - Configure OS power profile to high performance and disable network adapter sleep on idle:
     `powercfg /change standby-timeout-ac 0`
     `powercfg /change hibernate-timeout-ac 0`
3. **Validate Ingestion Key Credentials:**
   - Ensure `AGENT_INGESTION_KEY` configured in local agent matches backend configuration in `.env`.
4. **Resynchronize Sensor Inventory:**
   - Trigger a manual hardware discovery scan from Device Management dashboard to refresh hardware topology.
