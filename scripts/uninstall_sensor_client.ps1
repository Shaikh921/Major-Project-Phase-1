# PowerShell Windows Agent Uninstaller for CloudOps Intel Lab PC Monitoring
# Safely unregisters daemon, notifies backend, and removes local binaries

[CmdletBinding()]
param (
    [Parameter(Mandatory = $false)]
    [string]$InstallDir = "C:\ProgramData\CloudOpsIntel\Sensor",

    [Parameter(Mandatory = $false)]
    [string]$PythonExe = "",

    [Parameter(Mandatory = $false)]
    [switch]$KeepLogs
)

$ErrorActionPreference = "Continue"

Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host " CloudOps Intel - Lab PC Sensor Uninstaller               " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Yellow

$TaskName = "CloudOpsSensorAgent"

# 1. Stop and remove scheduled task
Write-Host "[*] Stopping and unregistering Windows Scheduled Task: $TaskName..." -ForegroundColor Gray
schtasks.exe /End /TN $TaskName 2>$null
schtasks.exe /Delete /TN $TaskName /F 2>$null
Write-Host "[+] Scheduled task removed." -ForegroundColor Green

# 2. Kill any lingering python processes running the agent script from InstallDir
try {
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*$InstallDir*" } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force 2>$null
    }
} catch {
    # Non-fatal
}

# 3. Locate Python executable to send remote uninstall notice
if (-not $PythonExe) {
    $foundPython = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if ($foundPython) {
        $PythonExe = $foundPython.Source
    } elseif (Test-Path "C:\Python313\python.exe") {
        $PythonExe = "C:\Python313\python.exe"
    } elseif (Test-Path "C:\Python312\python.exe") {
        $PythonExe = "C:\Python312\python.exe"
    }
}

$configFile = Join-Path $InstallDir "sensor_config.json"
$agentScript = Join-Path $InstallDir "monitoring_agent\agent.py"
$remoteRevocationConfirmed = $false

if ((Test-Path $configFile) -and (Test-Path $agentScript) -and $PythonExe) {
    Write-Host "[*] Attempting to notify CloudOps Intel server of local uninstallation..." -ForegroundColor Cyan
    & $PythonExe "$agentScript" --notify-uninstall --config "$configFile"
    if ($LASTEXITCODE -eq 0) {
        $remoteRevocationConfirmed = $true
        Write-Host "[+] Server confirmed device retirement notice." -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Warning "=========================================================================="
        Write-Warning "[!] WARNING: REMOTE REVOCATION NOT CONFIRMED!"
        Write-Warning "    The CloudOps Intel server could not be reached to confirm credential"
        Write-Warning "    revocation at this time."
        Write-Warning "    Super Admin MUST confirm device retirement in the CloudOps Intel Web UI"
        Write-Warning "    (Device Management) to permanently revoke this device credential."
        Write-Warning "=========================================================================="
        Write-Host ""
    }
}

# 4. Remove local installation directory
if (Test-Path $InstallDir) {
    if ($KeepLogs) {
        Write-Host "[*] Preserving spool and log files in $InstallDir as requested." -ForegroundColor Gray
        Remove-Item (Join-Path $InstallDir "monitoring_agent") -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item (Join-Path $InstallDir "sensor_config.json") -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "[*] Removing installation files from $InstallDir..." -ForegroundColor Gray
        Remove-Item -Path $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "[+] Removed $InstallDir" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Local Sensor Agent Uninstalled Successfully.             " -ForegroundColor Green
if (-not $remoteRevocationConfirmed) {
    Write-Host " Note: Remote server status remains PENDING RETIREMENT.    " -ForegroundColor Yellow
}
Write-Host "==========================================================" -ForegroundColor Green
