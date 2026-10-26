# CloudOps Intel — Windows Agent Installer & Uninstaller Guide
**Document Version:** 1.0.0  
**Target Operating Systems:** Windows 10 (x64), Windows 11 (x64), Windows Server 2019/2022  
**Service Type:** Windows Scheduled Task (Non-interactive / `SYSTEM` / Boot Trigger)  

---

## 1. Packaging the Sensor Client

A reproducible packaging utility is provided at `scripts/package_sensor_agent.py`. It inspects the project files, verifies security constraints, and outputs a self-contained archive:

```bash
python scripts/package_sensor_agent.py
```

### Packaging Outputs:
- **Zip Package:** `dist/cloudops-sensor-package.zip` (Approx. 16.3 KB)
- **Checksum File:** `dist/cloudops-sensor-package.zip.sha256`

### Package Contents:
```
cloudops-sensor-package.zip
├── install_sensor_client.ps1     # PowerShell unattended/interactive installer
├── uninstall_sensor_client.ps1   # Clean uninstaller with server notification
├── requirements.txt              # Minimal dependencies (psutil>=5.9.0)
├── root.crt                      # Public Caddy Root CA authority certificate
├── README.md                     # Workstation technician deployment instructions
└── monitoring_agent/
    ├── __init__.py
    ├── agent.py                  # Sensor daemon and lifecycle manager
    ├── buffer.py                 # Persistent SQLite spool queue
    └── collector.py              # psutil hardware metric collector
```

### Security Audit Guarantee:
The packager automatically scans staged files prior to compression and aborts if `root.key`, `.env`, `cloud_intelligence.db`, `.git`, or credential files are present.

---

## 2. Windows Installation Procedure

### Step 1: Verify Package Checksum (Trusted Channel)
Obtain the SHA-256 checksum from the Super Admin via an out-of-band channel and verify it on the target workstation:
```powershell
Get-FileHash .\cloudops-sensor-package.zip -Algorithm SHA256
```
Compare the output against `cloudops-sensor-package.zip.sha256`.

### Step 2: Extract Package
Extract the zip package to a temporary administrative folder:
```powershell
Expand-Archive .\cloudops-sensor-package.zip -DestinationPath C:\Temp\CloudOpsSensor
cd C:\Temp\CloudOpsSensor
```

### Step 3: Run the PowerShell Installer
Open an **Elevated Administrator PowerShell Prompt** and execute:
```powershell
powershell -ExecutionPolicy Bypass -File .\install_sensor_client.ps1 `
    -ServerUrl "https://<SERVER_IP_OR_DNS>:8443" `
    -EnrollmentCode "<SUPER_ADMIN_ENROLLMENT_CODE>"
```

### What the Installer Performs Automatically:
1. **Administrative Privilege Verification:** Asserts that the script is running with elevated permissions.
2. **Runtime Detection:** Locates `python.exe` on PATH or standard directories (`C:\Python313\python.exe`).
3. **Directory Creation & NTFS Security Hardening:**
   - Creates `C:\ProgramData\CloudOpsIntel\Sensor`.
   - Restricts NTFS ACLs using `icacls`:
     ```powershell
     icacls "C:\ProgramData\CloudOpsIntel\Sensor" /inheritance:r /grant:r "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F"
     ```
   - Standard non-privileged users cannot read or modify the sensor configuration, API keys, or queued telemetry.
4. **Binary & CA Deployment:** Copies `monitoring_agent`, `root.crt`, and dependencies into the install folder.
5. **Dependency Check:** Verifies or installs `psutil`.
6. **Enrollment Handshake:** Executes `python agent.py --enroll ...` to submit reported hostname and hardware UUID to the server.
7. **Scheduled Task Registration:**
   - Task Name: `CloudOpsSensorAgent`
   - Principal: `NT AUTHORITY\SYSTEM` (or current user if non-elevated)
   - Trigger: `<BootTrigger>` (starts automatically upon system startup without user logon)
   - Settings: Restart on failure (3 retries at 1m interval), run whether user is logged on or not.
8. **Service Startup:** Immediately launches the background task via `schtasks /Run /TN CloudOpsSensorAgent`.

---

## 3. Verifying Installation & Operational Health

Verify the scheduled task status:
```powershell
schtasks /Query /TN "CloudOpsSensorAgent" /V /FO LIST
```

Verify local spool database and configuration:
```powershell
Get-ChildItem "C:\ProgramData\CloudOpsIntel\Sensor"
```
Expected files:
- `sensor_config.json`: Contains device UUID, server URL, and provisioned `ak_lab_...` key.
- `sensor_spool.db`: SQLite database for persistent telemetry queuing.
- `root.crt`: Trusted CA certificate.

---

## 4. Uninstallation Procedure

To cleanly remove the sensor from a workstation:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_sensor_client.ps1
```

### Uninstallation Sequence:
1. **Stop & Unregister Service:** Stops running agent processes and unregisters the `CloudOpsSensorAgent` scheduled task.
2. **Server Notification:**
   - Sensor calls `POST /api/v1/devices/uninstall-notice` using its stored credential.
   - Server records device status as `RETIREMENT_REQUESTED` in the audit log.
3. **Offline Fallback & Prominent Warning:**
   - If the server cannot be reached, the uninstaller displays:
     ```
     ==========================================================================
     [!] WARNING: REMOTE REVOCATION NOT CONFIRMED!
         The CloudOps Intel server could not be reached to confirm credential
         revocation at this time.
         Super Admin MUST confirm device retirement in the CloudOps Intel Web UI
         (Device Management) to permanently revoke this device credential.
     ==========================================================================
     ```
   - The uninstaller does **not** falsely claim remote credential revocation occurred.
4. **Clean File Removal:** Deletes `C:\ProgramData\CloudOpsIntel\Sensor` and all cached credentials.
