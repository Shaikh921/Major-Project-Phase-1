# ========================================================================
# CloudOps Intel Sensor - Update Server IP Address
# ========================================================================

[CmdletBinding()]
param (
    [Parameter(Mandatory = $false, HelpMessage = "New Server IP address (e.g. 10.1.250.105)")]
    [string]$NewServerIP = ""
)

if (-not $NewServerIP) {
    $NewServerIP = Read-Host "Enter the New Server IP address (e.g. 10.1.250.105)"
}

$NewServerIP = $NewServerIP.Trim()
if (-not $NewServerIP) {
    Write-Host "[-] Error: Server IP cannot be empty." -ForegroundColor Red
    exit 1
}

$cfgPath = "C:\ProgramData\CloudOpsIntel\Sensor\sensor_config.json"
if (-not (Test-Path $cfgPath)) {
    Write-Host "[-] Error: Sensor config file not found at $cfgPath" -ForegroundColor Red
    Write-Host "    Make sure the sensor agent was installed on this PC first." -ForegroundColor Yellow
    exit 1
}

# 1. Update server_url in sensor_config.json
try {
    $content = Get-Content $cfgPath -Raw
    $newUrl = "https://$($NewServerIP):8443/api/v1/metrics"
    $updated = $content -replace '"server_url":\s*"https://[^/:]+:8443/api/v1/metrics"', "`"server_url`": `"$newUrl`""
    $updated | Set-Content $cfgPath -Encoding UTF8
    Write-Host "[+] Updated sensor_config.json with new Server URL: $newUrl" -ForegroundColor Green
} catch {
    Write-Host "[-] Failed to update config file: $_" -ForegroundColor Red
    exit 1
}

# 2. Restart running python processes
Write-Host "[*] Restarting background sensor process..." -ForegroundColor Cyan
Stop-Process -Name python -Force -ErrorAction SilentlyContinue

# 3. Trigger scheduled task or start process
$task = Get-ScheduledTask -TaskName "CloudOpsSensorAgent" -ErrorAction SilentlyContinue
if ($task) {
    Start-ScheduledTask -TaskName "CloudOpsSensorAgent" -ErrorAction SilentlyContinue
    Write-Host "[+] Started CloudOpsSensorAgent scheduled task." -ForegroundColor Green
} else {
    $InstallDir = "C:\ProgramData\CloudOpsIntel\Sensor"
    $agentScript = Join-Path $InstallDir "monitoring_agent\agent.py"
    $spoolDb = Join-Path $InstallDir "sensor_spool.db"
    Start-Process -FilePath "python.exe" `
        -ArgumentList "`"$agentScript`" --config `"$cfgPath`" --spool-db `"$spoolDb`"" `
        -WorkingDirectory $InstallDir `
        -WindowStyle Hidden
    Write-Host "[+] Started sensor agent process in background." -ForegroundColor Green
}

# 4. Connectivity test
Write-Host "[*] Testing connection to https://${NewServerIP}:8443 ..." -ForegroundColor Cyan
$test = Test-NetConnection -ComputerName $NewServerIP -Port 8443 -WarningAction SilentlyContinue
if ($test.TcpTestSucceeded) {
    Write-Host "[+] Connection to server on port 8443 SUCCEEDED!" -ForegroundColor Green
    Write-Host "[+] Sensor is now actively streaming telemetry to new server." -ForegroundColor Green
} else {
    Write-Host "[!] Warning: Port 8443 on $NewServerIP is not reachable yet." -ForegroundColor Yellow
    Write-Host "    Check network cable / Wi-Fi and make sure server is running." -ForegroundColor Yellow
}

