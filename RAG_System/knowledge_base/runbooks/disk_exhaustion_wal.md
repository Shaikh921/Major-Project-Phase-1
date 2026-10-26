# SRE Runbook: Storage Exhaustion & Database WAL Log Accumulation

**ID:** `RUNBOOK-DISK-003`  
**Domain:** Storage & Database Reliability  
**Applies To:** SQLite Databases, Log Partitions, System Root Drives  
**Severity:** Critical  

## 1. Symptom Profile
- Available disk space on partition drops below 10% or triggers `disk_percent > 90%` alert.
- Database write operations fail with `sqlite3.OperationalError: database or disk is full` or `I/O error`.
- SQLite Write-Ahead Log (`cloud_intelligence.db-wal`) grows into hundreds of megabytes or gigabytes without checkpointing.
- Log rotation failures causing `/var/log` or application log directory bloating.

## 2. Root Cause Classification
- **Uncheckpointed WAL File:** Long-running read transactions holding open database locks, preventing SQLite WAL autocheckpoint.
- **Runaway Log Files:** Verbose `DEBUG` logging active in production without log rotation / retention limits.
- **Orphaned Temporary / Export Files:** Uncleaned scratch files, failed bulk import artifacts, or temporary crash dumps.
- **Log Archival Failure:** Backups or log shippers stalling and causing local queues to back up onto primary volumes.

## 3. Immediate Diagnostic Commands
```bash
# Check filesystem free space and inode exhaustion
df -h
df -i

# Find top 10 largest directories in application path
du -ah /path/to/app | sort -rh | head -n 10

# On Windows PowerShell:
Get-PSDrive -PSProvider FileSystem | Select-Object Name, Used, Free, @{Name="PercentFree";Expression={[math]::Round($_.Free/($_.Used+$_.Free)*100,2)}}
Get-ChildItem -Path C:\CLoudProject -Recurse -File -ErrorAction SilentlyContinue | Sort-Object Length -Descending | Select-Object -First 10 -Property FullName, Length
```

## 4. Remediation Steps
1. **Force SQLite WAL Checkpoint:**
   - Execute an explicit passive or truncate checkpoint against the database:
     `PRAGMA wal_checkpoint(TRUNCATE);`
2. **Purge Rotated & Expired Logs:**
   - Compress or remove `.log.1`, `.log.2`, or logs older than retention policy (e.g., > 14 days).
3. **Verify Open Database File Handles:**
   - Ensure background tasks and connection pools close cursor transactions promptly.
4. **Provision Emergency Volume Expansion:**
   - If disk growth is legitimate due to telemetry ingestion rates, expand disk volume or configure metric downsampling.
