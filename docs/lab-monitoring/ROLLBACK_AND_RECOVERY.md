# CloudOps Intel — Rollback & Disaster Recovery Procedures
**Document Version:** 1.0.0  
**Target Environment:** Windows Server / Windows Developer Laptop  
**Backup Baseline:** `backups/pre_phase8b/cloud_intelligence_pre_phase8b_20261023_125836.db`  

---

## 1. Verified Backup Baseline

Prior to applying any schema modifications or migrations, an online, transactionally consistent SQLite backup was created and cryptographically verified:

- **Source File:** `C:\CLoudProject\cloud_intelligence.db`
- **Backup File:** `C:\CLoudProject\backups\pre_phase8b\cloud_intelligence_pre_phase8b_20261023_125836.db`
- **Backup Size:** 1,228,800 bytes
- **SHA-256 Checksum:** `1c5acd13c570b994faba139260a20f97e87492bda9d4e1dd9e63c2c80d4204f8`
- **Data Preserved:** 46 Users, 13 Hosts, 5,381 Metrics, 278 Alerts, Threshold Rules, Pricing Catalog, and Audit Logs.

---

## 2. Database Disaster Recovery Procedure

If the live database experiences corruption, an administrative error, or an unrecoverable failure, follow these exact steps to restore the verified pre-implementation baseline:

### Step 1: Stop Application Services
Open an **Elevated Administrator PowerShell Prompt** on the server:
```powershell
# Stop CloudOps Intel backend and proxy services
Stop-Service -Name "CloudOpsBackend" -Force -ErrorAction SilentlyContinue
Stop-Service -Name "CloudOpsProxy" -Force -ErrorAction SilentlyContinue

# Ensure no lingering python processes hold database locks
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*backend.app.main*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

### Step 2: Archive Damaged Database & WAL Files
```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
New-Item -ItemType Directory -Path "C:\CLoudProject\backups\emergency_archive_$timestamp" -Force | Out-Null

Copy-Item "C:\CLoudProject\cloud_intelligence.db*" "C:\CLoudProject\backups\emergency_archive_$timestamp\" -Force
Remove-Item "C:\CLoudProject\cloud_intelligence.db*" -Force
```

### Step 3: Restore Verified Backup Baseline
```powershell
$backupPath = "C:\CLoudProject\backups\pre_phase8b\cloud_intelligence_pre_phase8b_20261023_125836.db"
Copy-Item $backupPath "C:\CLoudProject\cloud_intelligence.db" -Force

# Verify file integrity
python -c "
import sqlite3
conn = sqlite3.connect('C:/CLoudProject/cloud_intelligence.db')
cursor = conn.cursor()
cursor.execute('PRAGMA integrity_check;')
print('Integrity Check:', cursor.fetchall())
cursor.execute('PRAGMA journal_mode=WAL;')
print('Journal Mode:', cursor.fetchall())
conn.close()
"
```
Expected output:
```
Integrity Check: [('ok',)]
Journal Mode: [('wal',)]
```

### Step 4: Restart Services
```powershell
Start-Service -Name "CloudOpsBackend"
Start-Service -Name "CloudOpsProxy"
```

---

## 3. Code Rollback Procedure

If code changes must be reverted to the baseline commit:

```powershell
cd C:\CLoudProject

# Verify git working tree status
git status

# Revert working tree files to baseline commit (e5a4124)
git checkout e5a4124 -- backend/app/
git checkout e5a4124 -- frontend/
git checkout e5a4124 -- monitoring_agent/
git checkout e5a4124 -- tests/

# Re-run test suite to confirm baseline green state
pytest tests/ -q
```

---

## 4. Workstation Sensor Rollback

To roll back a test workstation to a clean pre-sensor state:

```powershell
# Run the clean uninstaller
powershell -ExecutionPolicy Bypass -File C:\ProgramData\CloudOpsIntel\Sensor\uninstall_sensor_client.ps1

# Verify scheduled task is removed
schtasks /Query /TN "CloudOpsSensorAgent" 2>$null
```
The workstation is now completely cleansed, and all server-side historical metrics remain preserved.
