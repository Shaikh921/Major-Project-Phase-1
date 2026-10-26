<#
.SYNOPSIS
    Restarts CloudOps Intel Windows Services (Backend & Reverse Proxy) cleanly with health verification.
.DESCRIPTION
    Must be executed in PowerShell with Administrator privileges ("Run as Administrator").
#>

# Validate Elevation; if non-elevated, re-launch with RunAs UAC prompt
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "[ELEVATION REQUIRED] Requesting Administrator privileges to restart Windows Services..." -ForegroundColor Yellow
    try {
        $proc = Start-Process powershell -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -NoProfile -File `"$PSCommandPath`"" -PassThru -Wait
        exit $proc.ExitCode
    } catch {
        Write-Host "==========================================================" -ForegroundColor Red
        Write-Host " ERROR: Administrator elevation was denied or cancelled." -ForegroundColor Red
        Write-Host " Please open PowerShell as Administrator and run:" -ForegroundColor Yellow
        Write-Host " powershell -ExecutionPolicy Bypass -File C:\CLoudProject\scripts\restart_services.ps1" -ForegroundColor Green
        Write-Host "==========================================================" -ForegroundColor Red
        exit 1
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Restarting CloudOps Intel Services (Backend & Proxy)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

Write-Host "[1/3] Stopping CloudOpsBackend and dependent services..." -ForegroundColor Yellow
Restart-Service -Name "CloudOpsBackend" -Force

Write-Host "[2/3] Polling for backend readiness on http://127.0.0.1:8000/health..." -ForegroundColor Yellow
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction Stop
        if ($resp.status -eq "healthy") {
            $ready = $true
            break
        }
    } catch {
        # Waiting for uvicorn to bind
    }
}

if ($ready) {
    Write-Host "[3/3] Backend is UP and HEALTHY on port 8000!" -ForegroundColor Green
    Start-Service -Name "CloudOpsProxy" -ErrorAction SilentlyContinue
    $proxyStatus = (Get-Service -Name "CloudOpsProxy").Status
    Write-Host "CloudOpsProxy (Caddy HTTPS :8443) Status: $proxyStatus" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host " Services restarted successfully. Dashboard is ready!" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Cyan
} else {
    Write-Host "ERROR: Timed out waiting for CloudOpsBackend to become healthy." -ForegroundColor Red
}
