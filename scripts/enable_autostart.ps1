<#
.SYNOPSIS
    Instantly enables Automatic Startup (SERVICE_AUTO_START) on system boot for CloudOps Intel services.
#>

$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[ELEVATION REQUIRED] Requesting Administrator privileges..." -ForegroundColor Yellow
    try {
        $proc = Start-Process powershell -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -NoProfile -File `"$PSCommandPath`"" -PassThru -Wait
        exit $proc.ExitCode
    } catch {
        Write-Host "ERROR: Administrator elevation was denied or cancelled." -ForegroundColor Red
        exit 1
    }
}

$ProjectRoot = "C:\CLoudProject"
$NssmExe = Join-Path $ProjectRoot "tools\nssm.exe"

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " Enabling Automatic Startup on System Boot for CloudOps Intel Services    " -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

# 1. Update CloudOpsBackend
Write-Host "[1/3] Configuring CloudOpsBackend for Auto-Start & Crash Recovery..." -ForegroundColor Yellow
& $NssmExe set CloudOpsBackend Start SERVICE_AUTO_START
& $NssmExe set CloudOpsBackend AppThrottle 1500
& $NssmExe set CloudOpsBackend AppRestartDelay 3000
& $NssmExe set CloudOpsBackend AppExit Default Restart
& sc.exe config CloudOpsBackend start= auto | Out-Null
Write-Host "  -> CloudOpsBackend start mode: AUTOMATIC (Starts on boot before login)." -ForegroundColor Green

# 2. Update CloudOpsProxy
Write-Host "[2/3] Configuring CloudOpsProxy for Auto-Start & Crash Recovery..." -ForegroundColor Yellow
& $NssmExe set CloudOpsProxy Start SERVICE_AUTO_START
& $NssmExe set CloudOpsProxy AppThrottle 1500
& $NssmExe set CloudOpsProxy AppRestartDelay 3000
& $NssmExe set CloudOpsProxy AppExit Default Restart
& sc.exe config CloudOpsProxy start= auto | Out-Null
Write-Host "  -> CloudOpsProxy start mode: AUTOMATIC (Starts on boot before login)." -ForegroundColor Green

# 3. Ensure Services are Running Now
Write-Host "[3/3] Checking current service status..." -ForegroundColor Yellow
Start-Service -Name CloudOpsBackend -ErrorAction SilentlyContinue
Start-Service -Name CloudOpsProxy -ErrorAction SilentlyContinue

$backendStatus = (Get-Service -Name CloudOpsBackend).Status
$proxyStatus = (Get-Service -Name CloudOpsProxy).Status
Write-Host "  Backend Service Status: $backendStatus" -ForegroundColor Green
Write-Host "  Proxy Service Status:   $proxyStatus" -ForegroundColor Green

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " SUCCESS: CloudOps Intel will now start automatically whenever Windows boots!" -ForegroundColor Green
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can close this window now." -ForegroundColor Gray
Read-Host "Press Enter to close"

