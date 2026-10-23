<#
.SYNOPSIS
    Installs, configures, and hardens CloudOps Intel Windows Services (Phase 8B.3.2 Hotfix).

.DESCRIPTION
    Registers CloudOpsBackend and CloudOpsProxy under isolated Virtual Service Accounts
    (NT SERVICE\CloudOpsBackend and NT SERVICE\CloudOpsProxy) via NSSM.
    Implements least-privilege NTFS ACL isolation using verified native icacls permission syntax.
    Enforces cross-service isolation and grants CloudOpsBackend targeted sidecar rights (WD,AD,DC)
    and CREATOR OWNER Modify without granting broad repository Modify.

.NOTES
    Must be executed in an elevated PowerShell session (Run as Administrator).
#>

[CmdletBinding()]
param (
    [string]$ProjectRoot = "C:\CLoudProject",
    [string]$PythonExe   = "C:\Python313\python.exe",
    [switch]$StartAfterInstall
)

$ErrorActionPreference = "Stop"

# 1. Validate Elevation
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "==========================================================================" -ForegroundColor Red
    Write-Host " ERROR: ELEVATION REQUIRED                                                " -ForegroundColor Red
    Write-Host "==========================================================================" -ForegroundColor Red
    Write-Host " This script requires an elevated PowerShell prompt (Run as Administrator) to:" -ForegroundColor Yellow
    Write-Host "   1. Register services in Windows Service Control Manager (SCM)          " -ForegroundColor Yellow
    Write-Host "   2. Resolve Virtual Service Account SIDs for isolated ACL grants        " -ForegroundColor Yellow
    Write-Host ""
    Write-Host " To execute, open an elevated PowerShell prompt (Run as Administrator) and run:" -ForegroundColor White
    Write-Host " powershell -ExecutionPolicy Bypass -File C:\CLoudProject\scripts\install_windows_services.ps1 -StartAfterInstall" -ForegroundColor Green
    Write-Host "==========================================================================" -ForegroundColor Red
    exit 1
}

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " CloudOps Intel - Hardened Windows Services Installer (Phase 8B.3.2)      " -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

$NssmExe = Join-Path $ProjectRoot "tools\nssm.exe"
$CaddyExe = Join-Path $ProjectRoot "tools\caddy.exe"
$CaddyFile = Join-Path $ProjectRoot "Caddyfile"
$EnvFile = Join-Path $ProjectRoot ".env"
$DbFile = Join-Path $ProjectRoot "cloud_intelligence.db"
$BackendDir = Join-Path $ProjectRoot "backend"
$CaddyData = Join-Path $ProjectRoot "data\caddy"
$CaddyPki = Join-Path $ProjectRoot "data\caddy\pki"
$BackendLogs = Join-Path $ProjectRoot "logs\backend"
$ProxyLogs = Join-Path $ProjectRoot "logs\proxy"

# 2. Precondition Checks
Write-Host "[1/6] Validating prerequisites and files..." -ForegroundColor Yellow
if (-not (Test-Path $NssmExe)) { throw "NSSM binary not found at $NssmExe" }
if (-not (Test-Path $CaddyExe)) { throw "Caddy binary not found at $CaddyExe" }
if (-not (Test-Path $PythonExe)) { throw "Python binary not found at $PythonExe" }
if (-not (Test-Path $DbFile)) { throw "Database not found at $DbFile" }
if (-not (Test-Path $EnvFile)) { throw "Environment file not found at $EnvFile" }
if (-not (Test-Path $BackendDir)) { throw "Backend directory not found at $BackendDir" }

# Ensure required directories exist
New-Item -ItemType Directory -Path $BackendLogs -Force | Out-Null
New-Item -ItemType Directory -Path $ProxyLogs -Force | Out-Null
New-Item -ItemType Directory -Path $CaddyData -Force | Out-Null

# Helper function to execute icacls with strict error handling
function Invoke-AclCommand {
    param (
        [string]$Target,
        [string[]]$ArgumentList
    )
    $output = & icacls.exe $Target @ArgumentList 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ERROR: icacls command failed on target '$Target': icacls.exe $Target $($ArgumentList -join ' ')`nOutput: $output"
        exit 1
    }
}

# 3. Register CloudOpsBackend Service (Idempotent)
Write-Host "[2/6] Configuring CloudOpsBackend service..." -ForegroundColor Yellow
$backendQuery = & sc.exe query CloudOpsBackend 2>&1
if ($backendQuery -match "FAILED 1060") {
    Write-Host "  - Installing CloudOpsBackend via NSSM..."
    & $NssmExe install CloudOpsBackend $PythonExe "-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"
} else {
    Write-Host "  - Service CloudOpsBackend exists in SCM. Updating configuration parameters..."
    & $NssmExe set CloudOpsBackend Application $PythonExe
    & $NssmExe set CloudOpsBackend AppParameters "-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"
}
& $NssmExe set CloudOpsBackend AppDirectory $ProjectRoot
& $NssmExe set CloudOpsBackend ObjectName "NT SERVICE\CloudOpsBackend"
& $NssmExe set CloudOpsBackend Start SERVICE_DEMAND_START
& $NssmExe set CloudOpsBackend AppStdout (Join-Path $BackendLogs "backend_stdout.log")
& $NssmExe set CloudOpsBackend AppStderr (Join-Path $BackendLogs "backend_stderr.log")
& $NssmExe set CloudOpsBackend AppRotateFiles 1
& $NssmExe set CloudOpsBackend AppRotateBytes 10485760
& $NssmExe set CloudOpsBackend AppEnvironmentExtra "PYTHONUNBUFFERED=1"
Write-Host "  -> CloudOpsBackend configured (NT SERVICE\CloudOpsBackend, Manual startup, 10MB logs)." -ForegroundColor Green

# 4. Register CloudOpsProxy Service (Idempotent)
Write-Host "[3/6] Configuring CloudOpsProxy service..." -ForegroundColor Yellow
$proxyQuery = & sc.exe query CloudOpsProxy 2>&1
if ($proxyQuery -match "FAILED 1060") {
    Write-Host "  - Installing CloudOpsProxy via NSSM..."
    & $NssmExe install CloudOpsProxy $CaddyExe "run --config Caddyfile"
} else {
    Write-Host "  - Service CloudOpsProxy exists in SCM. Updating configuration parameters..."
    & $NssmExe set CloudOpsProxy Application $CaddyExe
    & $NssmExe set CloudOpsProxy AppParameters "run --config Caddyfile"
}
& $NssmExe set CloudOpsProxy AppDirectory $ProjectRoot
& $NssmExe set CloudOpsProxy ObjectName "NT SERVICE\CloudOpsProxy"
& $NssmExe set CloudOpsProxy Start SERVICE_DEMAND_START
& $NssmExe set CloudOpsProxy AppStdout (Join-Path $ProxyLogs "proxy_stdout.log")
& $NssmExe set CloudOpsProxy AppStderr (Join-Path $ProxyLogs "proxy_stderr.log")
& $NssmExe set CloudOpsProxy AppRotateFiles 1
& $NssmExe set CloudOpsProxy AppRotateBytes 10485760
& $NssmExe set CloudOpsProxy DependOnService CloudOpsBackend
Write-Host "  -> CloudOpsProxy configured (NT SERVICE\CloudOpsProxy, DependOnService=CloudOpsBackend)." -ForegroundColor Green

# 5. Apply Hardened NTFS Isolation (Resolving Inherited Authenticated Users Modify)
Write-Host "[4/6] Applying Hardened ACL Isolation..." -ForegroundColor Yellow

$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name

# Helper function to harden a target: sever inheritance, remove Authenticated Users, ensure Admins/SYSTEM/User retain F
function Harden-TargetBase {
    param (
        [string]$Path
    )
    if (Test-Path $Path) {
        Invoke-AclCommand -Target $Path -ArgumentList @('/inheritance:d')
        & icacls.exe $Path /remove "NT AUTHORITY\Authenticated Users" 2>&1 | Out-Null
        Invoke-AclCommand -Target $Path -ArgumentList @('/grant:r', 'BUILTIN\Administrators:(OI)(CI)(F)')
        Invoke-AclCommand -Target $Path -ArgumentList @('/grant', 'NT AUTHORITY\SYSTEM:(OI)(CI)(F)')
        if ($currentUser) {
            Invoke-AclCommand -Target $Path -ArgumentList @('/grant', "${currentUser}:(OI)(CI)(F)")
        }
    }
}

# 5.1 Project Root Folder: Sever inheritance from C:\, strip Authenticated Users Modify
Write-Host "  - Hardening C:\CLoudProject root directory..."
Harden-TargetBase -Path $ProjectRoot
# Grant Backend Read/Execute across project
Invoke-AclCommand -Target $ProjectRoot -ArgumentList @('/grant', 'NT SERVICE\CloudOpsBackend:(OI)(CI)(RX)')
# Grant Backend specific sidecar creation/deletion rights using valid icacls permission syntax: (WD,AD,DC)
Invoke-AclCommand -Target $ProjectRoot -ArgumentList @('/grant', 'NT SERVICE\CloudOpsBackend:(WD,AD,DC)')
# Ensure creator has Modify rights on dynamic WAL/SHM sidecars created
Invoke-AclCommand -Target $ProjectRoot -ArgumentList @('/grant', 'CREATOR OWNER:(OI)(CI)(IO)(M)')
# Grant Proxy Read only on root (non-inheriting, allowing Caddyfile reading, NO create/write/delete)
Invoke-AclCommand -Target $ProjectRoot -ArgumentList @('/grant', 'NT SERVICE\CloudOpsProxy:(R)')

# 5.2 Backend Secrets: .env
Write-Host "  - Hardening .env (Backend Read, Proxy NO ACCESS)..."
Harden-TargetBase -Path $EnvFile
& icacls.exe $EnvFile /remove "NT SERVICE\CloudOpsProxy" 2>&1 | Out-Null
Invoke-AclCommand -Target $EnvFile -ArgumentList @('/grant:r', 'NT SERVICE\CloudOpsBackend:(R)')

# 5.3 Active SQLite Database: cloud_intelligence.db
Write-Host "  - Hardening cloud_intelligence.db (Backend Modify, Proxy NO ACCESS)..."
Harden-TargetBase -Path $DbFile
& icacls.exe $DbFile /remove "NT SERVICE\CloudOpsProxy" 2>&1 | Out-Null
Invoke-AclCommand -Target $DbFile -ArgumentList @('/grant:r', 'NT SERVICE\CloudOpsBackend:(M)')

# 5.4 Backend Source Code: backend directory
Write-Host "  - Hardening backend source code (Backend Read/Execute, Proxy NO ACCESS)..."
Harden-TargetBase -Path $BackendDir
& icacls.exe $BackendDir /remove "NT SERVICE\CloudOpsProxy" 2>&1 | Out-Null
Invoke-AclCommand -Target $BackendDir -ArgumentList @('/grant:r', 'NT SERVICE\CloudOpsBackend:(OI)(CI)(RX)')

# 5.5 Caddy Configuration and Executable (Read/Execute only, NO service modification)
Write-Host "  - Hardening Caddyfile & caddy.exe (Read-only to services)..."
Harden-TargetBase -Path $CaddyFile
Invoke-AclCommand -Target $CaddyFile -ArgumentList @('/grant:r', 'NT SERVICE\CloudOpsProxy:(R)')
Invoke-AclCommand -Target $CaddyFile -ArgumentList @('/grant', 'NT SERVICE\CloudOpsBackend:(R)')

Harden-TargetBase -Path $CaddyExe
Invoke-AclCommand -Target $CaddyExe -ArgumentList @('/grant:r', 'NT SERVICE\CloudOpsProxy:(RX)')

# 5.6 NSSM Executable: tools\nssm.exe (No service modification)
Harden-TargetBase -Path $NssmExe

# 5.7 Caddy Storage & PKI CA Private Keys: data\caddy
Write-Host "  - Hardening data\caddy & PKI keys (Proxy Modify, Backend NO ACCESS)..."
Harden-TargetBase -Path $CaddyData
& icacls.exe $CaddyData /remove "NT SERVICE\CloudOpsBackend" 2>&1 | Out-Null
Invoke-AclCommand -Target $CaddyData -ArgumentList @('/grant:r', 'NT SERVICE\CloudOpsProxy:(OI)(CI)(M)')

# 5.8 Service Logs Isolation
Write-Host "  - Hardening backend and proxy log directories..."
Harden-TargetBase -Path $BackendLogs
& icacls.exe $BackendLogs /remove "NT SERVICE\CloudOpsProxy" 2>&1 | Out-Null
Invoke-AclCommand -Target $BackendLogs -ArgumentList @('/grant:r', 'NT SERVICE\CloudOpsBackend:(OI)(CI)(M)')

Harden-TargetBase -Path $ProxyLogs
& icacls.exe $ProxyLogs /remove "NT SERVICE\CloudOpsBackend" 2>&1 | Out-Null
Invoke-AclCommand -Target $ProxyLogs -ArgumentList @('/grant:r', 'NT SERVICE\CloudOpsProxy:(OI)(CI)(M)')

Write-Host "  -> Hardened ACLs applied successfully. Cross-service boundaries strictly isolated." -ForegroundColor Green

# 6. Service Startup and Live Health Verification
if ($StartAfterInstall) {
    Write-Host "[5/6] Starting services with bounded health polling..." -ForegroundColor Yellow
    
    # 6.1 Start Backend First
    $backendSvc = Get-Service -Name CloudOpsBackend -ErrorAction SilentlyContinue
    if ($backendSvc -and $backendSvc.Status -eq 'Running') {
        Write-Host "  - CloudOpsBackend service is already running." -ForegroundColor Cyan
    } else {
        Write-Host "  - Starting CloudOpsBackend service..."
        & sc.exe start CloudOpsBackend 2>&1 | Out-Null
    }
    
    $backendHealthy = $false
    $retries = 30
    Write-Host "  - Polling http://127.0.0.1:8000/health..." -NoNewline
    while ($retries -gt 0 -and -not $backendHealthy) {
        try {
            $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
            if ($resp.status -eq "healthy") {
                $backendHealthy = $true
                Write-Host " [OK (HTTP 200)]" -ForegroundColor Green
                break
            }
        } catch {
            Write-Host "." -NoNewline
            Start-Sleep -Seconds 1
            $retries--
        }
    }
    
    if (-not $backendHealthy) {
        Write-Error "`nERROR: CloudOpsBackend failed to reach healthy status within 30 seconds. Check logs\backend\backend_stderr.log."
        exit 1
    }
    
    # 6.2 Start Proxy Only After Backend Is Confirmed Healthy
    $proxySvc = Get-Service -Name CloudOpsProxy -ErrorAction SilentlyContinue
    if ($proxySvc -and $proxySvc.Status -eq 'Running') {
        Write-Host "  - CloudOpsProxy service is already running." -ForegroundColor Cyan
    } else {
        Write-Host "  - Starting CloudOpsProxy service..."
        & sc.exe start CloudOpsProxy 2>&1 | Out-Null
    }
    Start-Sleep -Seconds 2
    
    $proxyHealthy = $false
    $retries = 15
    Write-Host "  - Polling https://localhost:8443/health..." -NoNewline
    while ($retries -gt 0 -and -not $proxyHealthy) {
        try {
            $resp = Invoke-RestMethod -Uri "https://localhost:8443/health" -Method Get -TimeoutSec 2 -SkipCertificateCheck -ErrorAction Stop
            if ($resp.status -eq "healthy") {
                $proxyHealthy = $true
                Write-Host " [OK (HTTP 200)]" -ForegroundColor Green
                break
            }
        } catch {
            Write-Host "." -NoNewline
            Start-Sleep -Seconds 1
            $retries--
        }
    }
    
    if (-not $proxyHealthy) {
        Write-Warning "`nWARNING: CloudOpsProxy did not respond on 8443 immediately. Check logs\proxy\proxy_stderr.log."
    }
} else {
    Write-Host "[5/6] Services registered in Manual startup mode (not started)." -ForegroundColor Yellow
}

# 7. Verification and Diagnostics
Write-Host "[6/6] Service Status and Verification:" -ForegroundColor Yellow
& sc.exe query CloudOpsBackend | Select-String "STATE" | ForEach-Object { Write-Host "  Backend: $_" -ForegroundColor White }
& sc.exe query CloudOpsProxy | Select-String "STATE" | ForEach-Object { Write-Host "  Proxy:   $_" -ForegroundColor White }

$conns = Get-NetTCPConnection -LocalPort 8000, 8443 -ErrorAction SilentlyContinue | Select-Object LocalAddress, LocalPort, State, OwningProcess
Write-Host "  Active Port Listeners:" -ForegroundColor Yellow
$conns | Format-Table -AutoSize | Out-String | Write-Host

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " Phase 8B.3.2 Service Registration and ACL Hardening Complete!             " -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan
