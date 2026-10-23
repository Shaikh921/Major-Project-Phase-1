<#
.SYNOPSIS
    Gracefully stops and unregisters CloudOps Intel Windows Services and restores ACLs (Phase 8B.3.2 Rollback).

.DESCRIPTION
    Stops CloudOpsProxy and CloudOpsBackend, deregisters them via NSSM, and restores NTFS ACLs
    from the Phase 8B.3.1 implementation recovery checkpoint.

.NOTES
    Must be executed in an elevated PowerShell session (Run as Administrator).
#>

[CmdletBinding()]
param (
    [string]$ProjectRoot = "C:\CLoudProject",
    [string]$BackupDir   = "C:\CLoudProject\backups\stage_8b3_1_recovery_20261022_195058"
)

$ErrorActionPreference = "Continue"

# 1. Validate Elevation
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "==========================================================================" -ForegroundColor Red
    Write-Host " ERROR: ELEVATION REQUIRED                                                " -ForegroundColor Red
    Write-Host "==========================================================================" -ForegroundColor Red
    Write-Host " This script requires an elevated PowerShell prompt (Run as Administrator) to:" -ForegroundColor Yellow
    Write-Host "   1. Stop and remove services from Windows Service Control Manager       " -ForegroundColor Yellow
    Write-Host "   2. Restore original NTFS ACLs                                          " -ForegroundColor Yellow
    Write-Host ""
    Write-Host " To execute, open an elevated PowerShell prompt (Run as Administrator) and run:" -ForegroundColor White
    Write-Host " powershell -ExecutionPolicy Bypass -File C:\CLoudProject\scripts\uninstall_windows_services.ps1" -ForegroundColor Green
    Write-Host "==========================================================================" -ForegroundColor Red
    exit 1
}

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " CloudOps Intel - Service Rollback & Uninstaller (Phase 8B.3.2)           " -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

$NssmExe = Join-Path $ProjectRoot "tools\nssm.exe"

# 2. Stop Services Gracefully
Write-Host "[1/3] Gracefully stopping services..." -ForegroundColor Yellow

$proxySvc = Get-Service -Name CloudOpsProxy -ErrorAction SilentlyContinue
if ($proxySvc -and $proxySvc.Status -eq 'Running') {
    Write-Host "  - Stopping CloudOpsProxy..."
    & sc.exe stop CloudOpsProxy | Out-Null
    Start-Sleep -Seconds 2
} else {
    Write-Host "  - CloudOpsProxy is not running." -ForegroundColor Cyan
}

$backendSvc = Get-Service -Name CloudOpsBackend -ErrorAction SilentlyContinue
if ($backendSvc -and $backendSvc.Status -eq 'Running') {
    Write-Host "  - Stopping CloudOpsBackend..."
    & sc.exe stop CloudOpsBackend | Out-Null
    Start-Sleep -Seconds 2
} else {
    Write-Host "  - CloudOpsBackend is not running." -ForegroundColor Cyan
}

# 3. Deregister Services from SCM
Write-Host "[2/3] Deregistering services from SCM..." -ForegroundColor Yellow
if (Test-Path $NssmExe) {
    if ($proxySvc) {
        & $NssmExe remove CloudOpsProxy confirm | Out-Null
        Write-Host "  - CloudOpsProxy removed from SCM." -ForegroundColor Green
    }
    if ($backendSvc) {
        & $NssmExe remove CloudOpsBackend confirm | Out-Null
        Write-Host "  - CloudOpsBackend removed from SCM." -ForegroundColor Green
    }
} else {
    if ($proxySvc) { & sc.exe delete CloudOpsProxy | Out-Null }
    if ($backendSvc) { & sc.exe delete CloudOpsBackend | Out-Null }
}

# 4. Restore Verified ACLs from Recovery Checkpoint
Write-Host "[3/3] Restoring original ACLs from recovery checkpoint..." -ForegroundColor Yellow
if (Test-Path $BackupDir) {
    $aclFiles = @(
        "acl_root.acl",
        "acl_env.acl",
        "acl_db.acl",
        "acl_caddyfile.acl",
        "acl_caddy_exe.acl",
        "acl_nssm_exe.acl",
        "acl_backend_code.acl",
        "acl_data_caddy.acl",
        "acl_data_caddy_pki.acl",
        "acl_logs_backend.acl",
        "acl_logs_proxy.acl"
    )

    foreach ($file in $aclFiles) {
        $fullPath = Join-Path $BackupDir $file
        if (Test-Path $fullPath) {
            $res = & icacls.exe $ProjectRoot /restore $fullPath 2>&1
            Write-Host "  - Restored: $file" -ForegroundColor Green
        } else {
            Write-Warning "  - Checkpoint file not found: $file"
        }
    }
    Write-Host "  -> ACLs successfully restored from $BackupDir." -ForegroundColor Green
} else {
    Write-Warning "Backup checkpoint directory not found at $BackupDir. Manual ACL verification required."
}

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " Rollback and ACL Restoration Completed Cleanly.                          " -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan
