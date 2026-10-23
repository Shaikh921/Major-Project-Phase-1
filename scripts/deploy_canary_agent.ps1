<#
.SYNOPSIS
    Stage 1 Canary Agent Deployment Script for PC-Room1-01.

.DESCRIPTION
    Installs, configures, and launches the CloudOps Intel Monitoring Agent
    on PC-Room1-01 in Room 1 for Stage 1 of the Lab PC Monitoring Pilot.
    Enforces required environment parameters, randomized startup jitter (1-10s),
    and validates initial telemetry ingestion against the backend.

.PARAMETER ServerUrl
    The base URL of the CloudOps Intel backend server (e.g., https://10.227.136.246:8443).

.PARAMETER ApiKey
    The dedicated REAL_AGENT API key provisioned for PC-Room1-01.

.PARAMETER ForceHostname
    Override hostname verification if running in a staging/validation environment.
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory = $true)]
    [string]$ServerUrl,

    [Parameter(Mandatory = $true)]
    [string]$ApiKey,

    [Parameter(Mandatory = $false)]
    [switch]$ForceHostname,

    [Parameter(Mandatory = $false)]
    [string]$CaBundle = ""
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  CloudOps Intel — Stage 1 Canary Agent Deployment" -ForegroundColor Cyan
Write-Host "  Target Machine: PC-Room1-01 | Room: Room 1" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Hostname Verification
$CurrentHostname = [System.Net.Dns]::GetHostName()
Write-Host "[*] Checking local hostname: $CurrentHostname" -ForegroundColor Yellow

if ($CurrentHostname -ne "PC-Room1-01" -and -not $ForceHostname) {
    Write-Error "Deployment rejected: Current hostname '$CurrentHostname' does not match target 'PC-Room1-01'. Use -ForceHostname if intentionally running staging simulation."
    exit 1
}

# 2. Network Reachability Test
# Enforce transport security: remote targets must use HTTPS
if ($ServerUrl -match "^http://") {
    try {
        $Uri = [System.Uri]$ServerUrl
        if ($Uri.Host -ne "localhost" -and $Uri.Host -ne "127.0.0.1") {
            Write-Error "Deployment rejected: Remote ServerUrl must use HTTPS ($ServerUrl). Cleartext HTTP over the network is forbidden."
            exit 1
        }
    } catch {
        Write-Error "Invalid ServerUrl format: $ServerUrl"
        exit 1
    }
}

Write-Host "[*] Verifying backend network reachability at $ServerUrl..." -ForegroundColor Yellow
$HealthUrl = "$ServerUrl/health"
try {
    $HealthResponse = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 5
    if ($HealthResponse.status -ne "healthy") {
        Write-Warning "Backend health check returned unexpected status: $($HealthResponse.status)"
    } else {
        Write-Host "[+] Backend is online and healthy." -ForegroundColor Green
    }
} catch {
    Write-Error "Failed to reach CloudOps Intel server at $HealthUrl. Error: $_"
    exit 1
}

# 3. Python Runtime & Dependency Verification
Write-Host "[*] Verifying Python runtime and dependencies..." -ForegroundColor Yellow
try {
    $PyVersion = python --version 2>&1
    Write-Host "[+] Detected $PyVersion" -ForegroundColor Green
} catch {
    Write-Error "Python is not installed or not in system PATH."
    exit 1
}

$DepCheck = python -c "import psutil, requests; print('OK')" 2>&1
if ($DepCheck -ne "OK") {
    Write-Host "[*] Installing required dependencies (psutil, requests)..." -ForegroundColor Yellow
    pip install psutil requests
} else {
    Write-Host "[+] Dependencies psutil and requests are present." -ForegroundColor Green
}

# 4. Machine-Level Environment Configuration
Write-Host "[*] Configuring environment variables for monitoring agent..." -ForegroundColor Yellow
$IngestUrl = "$ServerUrl/api/v1/metrics"

[System.Environment]::SetEnvironmentVariable("INGEST_URL", $IngestUrl, "Process")
[System.Environment]::SetEnvironmentVariable("AGENT_API_KEY", $ApiKey, "Process")
[System.Environment]::SetEnvironmentVariable("APP_ENV", "lab", "Process")
[System.Environment]::SetEnvironmentVariable("CLOUD_REGION", "Room 1", "Process")
[System.Environment]::SetEnvironmentVariable("POLL_INTERVAL", "15", "Process")

# 5. Randomized Startup Jitter (1 to 10 seconds)
$JitterSeconds = Get-Random -Minimum 1 -Maximum 10
Write-Host "[*] Applying randomized startup jitter: waiting $JitterSeconds seconds before launch..." -ForegroundColor Yellow
Start-Sleep -Seconds $JitterSeconds

# 6. Launch Monitoring Agent Process
$LogDir = Join-Path $PSScriptRoot "..\logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}
$LogPath = Join-Path $LogDir "agent_canary.log"

Write-Host "[*] Starting agent process (logging to $LogPath)..." -ForegroundColor Yellow

$AgentScript = Join-Path $PSScriptRoot "..\monitoring_agent\agent.py"
$ProcessInfo = New-Object System.Diagnostics.ProcessStartInfo
$ProcessInfo.FileName = "python"
$AgentArgs = "-u `"$AgentScript`" --url `"$IngestUrl`" --interval 15 --env lab --region `"Room 1`" --api-key `"$ApiKey`""
if ($CaBundle) {
    $AgentArgs += " --ca-bundle `"$CaBundle`""
}
$ProcessInfo.Arguments = $AgentArgs
$ProcessInfo.RedirectStandardOutput = $true
$ProcessInfo.RedirectStandardError = $true
$ProcessInfo.UseShellExecute = $false
$ProcessInfo.CreateNoWindow = $true

$Process = New-Object System.Diagnostics.Process
$Process.StartInfo = $ProcessInfo

$null = Register-ObjectEvent -InputObject $Process -EventName OutputDataReceived -Action {
    if ($EventArgs.Data) {
        Add-Content -Path $using:LogPath -Value "[STDOUT] $Date: $($EventArgs.Data)"
    }
}
$null = Register-ObjectEvent -InputObject $Process -EventName ErrorDataReceived -Action {
    if ($EventArgs.Data) {
        Add-Content -Path $using:LogPath -Value "[STDERR] $Date: $($EventArgs.Data)"
    }
}

$Process.Start() | Out-Null
$Process.BeginOutputReadLine()
$Process.BeginErrorReadLine()

Write-Host "[+] Canary Agent started successfully (PID: $($Process.Id))." -ForegroundColor Green

# Save PID for management and rollback
$PidFile = Join-Path $PSScriptRoot "canary_agent.pid"
Set-Content -Path $PidFile -Value $Process.Id

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Canary Agent Deployed: PID $($Process.Id)" -ForegroundColor Green
Write-Host "  Monitoring Log: $LogPath" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
