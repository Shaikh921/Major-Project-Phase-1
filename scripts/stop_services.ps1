<#
.SYNOPSIS
    Stops CloudOps Intel Windows Services cleanly.
#>

$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[ELEVATION REQUIRED] Requesting Administrator privileges to stop services..." -ForegroundColor Yellow
    try {
        $proc = Start-Process powershell -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -NoProfile -File `"$PSCommandPath`"" -PassThru -Wait
        exit $proc.ExitCode
    } catch {
        Write-Host "ERROR: Administrator elevation was denied or cancelled." -ForegroundColor Red
        exit 1
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Stopping CloudOps Intel Windows Services" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

Write-Host "[1/2] Stopping CloudOpsProxy..." -ForegroundColor Yellow
Stop-Service -Name "CloudOpsProxy" -Force -ErrorAction SilentlyContinue

Write-Host "[2/2] Stopping CloudOpsBackend..." -ForegroundColor Yellow
Stop-Service -Name "CloudOpsBackend" -Force -ErrorAction SilentlyContinue

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " CloudOps Intel Services have been stopped." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

