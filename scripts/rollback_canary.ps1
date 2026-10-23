<#
.SYNOPSIS
    Stage 1 Canary Rollback Script.

.DESCRIPTION
    Safely terminates the Canary Monitoring Agent on PC-Room1-01,
    revokes the dedicated REAL_AGENT key in the database, and leaves
    historical telemetry and host records intact.
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory = $false)]
    [switch]$RevokeKey
)

$ErrorActionPreference = "Continue"

Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host "  CloudOps Intel — Stage 1 Canary Rollback" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Yellow

# 1. Stop Agent Process via PID
$PidFile = Join-Path $PSScriptRoot "canary_agent.pid"
if (Test-Path $PidFile) {
    $AgentPid = Get-Content -Path $PidFile -ErrorAction SilentlyContinue
    if ($AgentPid) {
        Write-Host "[*] Terminating Canary Agent PID: $AgentPid..." -ForegroundColor Yellow
        Stop-Process -Id $AgentPid -Force -ErrorAction SilentlyContinue
        Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "[+] Process $AgentPid stopped." -ForegroundColor Green
    }
}

# 2. Terminate any residual monitoring_agent processes
$Residual = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*monitoring_agent*agent.py*" }
if ($Residual) {
    foreach ($p in $Residual) {
        Write-Host "[*] Stopping residual agent process (PID: $($p.ProcessId))..." -ForegroundColor Yellow
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "[+] All residual agent processes stopped." -ForegroundColor Green
}

# 3. Optional Key Revocation
if ($RevokeKey) {
    Write-Host "[*] Revoking dedicated Canary key in database..." -ForegroundColor Yellow
    python -c @"
import sys
from pathlib import Path
sys.path.insert(0, str(Path(r'$PSScriptRoot').parent))
from datetime import datetime, timezone
from backend.app.database.session import SessionLocal
from backend.app.models.agent_key import AgentApiKey

db = SessionLocal()
try:
    key = db.query(AgentApiKey).filter(AgentApiKey.name == 'PC-Room1-01-Canary').first()
    if key:
        key.is_active = False
        key.revoked_at = datetime.now(timezone.utc)
        db.commit()
        print(f'[+] Successfully revoked key {key.name} (ID: {key.id})')
    else:
        print('[-] Key PC-Room1-01-Canary not found in database.')
finally:
    db.close()
"@
}

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Rollback Complete: Agent stopped. Historical telemetry preserved." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
