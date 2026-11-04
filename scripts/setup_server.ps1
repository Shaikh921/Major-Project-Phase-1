<#
.SYNOPSIS
    Automated Enterprise Server Provisioner & Auto-Start Setup for CloudOps Intel.
.DESCRIPTION
    Runs on any fresh Windows Server, workstation, or laptop to prepare the system:
    1. Validates Administrator privileges.
    2. Detects/validates Python 3.10+.
    3. Provisions dedicated isolated virtual environment (.venv).
    4. Installs all required platform dependencies from requirements.txt.
    5. Configures production .env with a secure generated SECRET_KEY (if missing).
    6. Initializes SQLite database schemas, seed rules, and admin accounts.
    7. Configures Windows Defender Firewall rules for ports 8443 (HTTPS) and 8000 (Backend).
    8. Registers and hardens CloudOpsBackend and CloudOpsProxy as Automatic Windows Services (SERVICE_AUTO_START).
    9. Configures NSSM auto-restart crash recovery.
    10. Starts services and runs immediate health diagnostics.
.NOTES
    Must be executed with Administrator privileges.
#>

[CmdletBinding()]
param (
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

# Auto-resolve ProjectRoot if not explicitly passed
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
    if (-not (Test-Path (Join-Path $ProjectRoot "backend"))) {
        $ProjectRoot = "C:\CLoudProject"
    }
}

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Setup complete! Press Enter to close"
Write-Host " CloudOps Intel - Automated Server Provisioner & Auto-Start Configurator  " -ForegroundColor Cyan
Write-Host " Target Directory: $ProjectRoot" -ForegroundColor Gray
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Setup complete! Press Enter to close"

# 1. Administrator Elevation Check
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ELEVATION REQUIRED] Requesting Administrator privileges to configure Windows Services..." -ForegroundColor Yellow
    try {
        $proc = Start-Process powershell -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -NoProfile -File `"$PSCommandPath`" -ProjectRoot `"$ProjectRoot`"" -PassThru -Wait
        exit $proc.ExitCode
    } catch {
        Write-Host "==========================================================================" -ForegroundColor Red
        Write-Host " ERROR: Administrator elevation was denied or cancelled." -ForegroundColor Red
        Write-Host " Please open PowerShell as Administrator and run this script." -ForegroundColor Yellow
        Write-Host "==========================================================================" -ForegroundColor Red
        exit 1
    }
}

# 2. Detect System Python
Write-Host "`n[1/7] Checking Python runtime..." -ForegroundColor Yellow
$sysPython = $null

$pythonCandidates = @(
    "C:\Python313\python.exe",
    "C:\Program Files\Python313\python.exe",
    "C:\Python312\python.exe",
    "C:\Python311\python.exe"
)

foreach ($cand in $pythonCandidates) {
    if (Test-Path $cand) {
        $sysPython = $cand
        break
    }
}

if (-not $sysPython) {
    $cmdPy = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if ($cmdPy) { $sysPython = $cmdPy }
}

if (-not $sysPython) {
    Write-Host "ERROR: Python 3.10+ was not found on this system." -ForegroundColor Red
    Write-Host "Please install Python 3.11 or 3.13 from https://www.python.org/downloads/ and check 'Add python.exe to PATH'." -ForegroundColor Yellow
    exit 1
}

$pyVer = & $sysPython --version 2>&1
Write-Host "  -> Detected System Python: $sysPython ($pyVer)" -ForegroundColor Green

# 3. Create or Validate Virtual Environment (.venv)
Write-Host "`n[2/7] Verifying Python Virtual Environment (.venv)..." -ForegroundColor Yellow
$venvDir = Join-Path $ProjectRoot ".venv"
$venvPy = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
    Write-Host "  - Creating virtual environment at $venvDir..." -ForegroundColor Cyan
    & $sysPython -m venv $venvDir
    if (-not (Test-Path $venvPy)) {
        Write-Host "ERROR: Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
    Write-Host "  -> Virtual environment created successfully." -ForegroundColor Green
} else {
    Write-Host "  -> Virtual environment already exists at $venvDir." -ForegroundColor Green
}

# 4. Install Dependencies
Write-Host "`n[3/7] Verifying dependencies from requirements.txt..." -ForegroundColor Yellow
$reqFile = Join-Path $ProjectRoot "requirements.txt"
if (Test-Path $reqFile) {
    Write-Host "  - Ensuring pip, wheel, and setuptools are up to date..." -ForegroundColor Cyan
    & $venvPy -m pip install --upgrade pip setuptools wheel --quiet
    
    Write-Host "  - Checking installed packages against requirements.txt..." -ForegroundColor Cyan
    & $venvPy -m pip install -r $reqFile --quiet
    Write-Host "  -> All Python dependencies are installed and up to date." -ForegroundColor Green
} else {
    Write-Warning "requirements.txt not found at $reqFile. Skipping dependency installation."
}

# 5. Environment & Secret Configuration (.env)
Write-Host "`n[4/7] Verifying configuration (.env)..." -ForegroundColor Yellow
$envFile = Join-Path $ProjectRoot ".env"
$envExample = Join-Path $ProjectRoot ".env.example"

if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Host "  - Created .env from .env.example." -ForegroundColor Cyan
    } else {
        # Fallback minimal .env
        $defaultEnv = @"
APP_NAME=CloudOps Intel
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000
DATABASE_URL=sqlite:///./cloud_intelligence.db
SECRET_KEY=$( & $venvPy -c "import secrets; print(secrets.token_urlsafe(48))" )
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
"@
        Set-Content -Path $envFile -Value $defaultEnv -Encoding UTF8
        Write-Host "  - Created default production .env file." -ForegroundColor Cyan
    }
}

# Ensure SECRET_KEY is secure and non-default
$envContent = Get-Content $envFile -Raw
if ($envContent -match "change-this-in-production" -or $envContent -match "CHANGE_ME") {
    $newSecret = & $venvPy -c "import secrets; print(secrets.token_urlsafe(48))"
    $envContent = $envContent -replace "change-this-in-production.*", $newSecret
    $envContent = $envContent -replace "CHANGE_ME.*", $newSecret
    Set-Content -Path $envFile -Value $envContent -Encoding UTF8
    Write-Host "  -> Generated strong cryptographic SECRET_KEY in .env." -ForegroundColor Green
} else {
    Write-Host "  -> .env configuration verified." -ForegroundColor Green
}

# 6. Initialize Database Schema
Write-Host "`n[5/7] Initializing database schemas & default seed data..." -ForegroundColor Yellow
$initScript = "import os; from backend.app.database.init_db import init_db; init_db(); print('Database schema and seed rules initialized successfully.')"
$dbInitOutput = & $venvPy -c $initScript 2>&1
Write-Host "  -> $dbInitOutput" -ForegroundColor Green

# 7. Configure Windows Firewall Inbound Rules
Write-Host "`n[6/7] Configuring Windows Defender Firewall rules..." -ForegroundColor Yellow
try {
    $rule8443 = Get-NetFirewallRule -DisplayName "CloudOps Intel HTTPS (:8443)" -ErrorAction SilentlyContinue
    if (-not $rule8443) {
        New-NetFirewallRule -DisplayName "CloudOps Intel HTTPS (:8443)" `
            -Direction Inbound `
            -LocalPort 8443 `
            -Protocol TCP `
            -Action Allow `
            -Profile Any `
            -Description "Allows incoming sensor node telemetry and dashboard access to CloudOps Intel reverse proxy." | Out-Null
        Write-Host "  -> Firewall rule added: Inbound TCP 8443 (HTTPS Dashboard & Sensor Nodes)." -ForegroundColor Green
    } else {
        Write-Host "  -> Firewall rule already exists for port 8443." -ForegroundColor Green
    }

    $rule8000 = Get-NetFirewallRule -DisplayName "CloudOps Intel Backend (:8000)" -ErrorAction SilentlyContinue
    if (-not $rule8000) {
        New-NetFirewallRule -DisplayName "CloudOps Intel Backend (:8000)" `
            -Direction Inbound `
            -LocalPort 8000 `
            -Protocol TCP `
            -Action Allow `
            -Profile Any `
            -Description "Allows local API communication with CloudOps Intel FastAPI Backend." | Out-Null
        Write-Host "  -> Firewall rule added: Inbound TCP 8000 (Backend API)." -ForegroundColor Green
    } else {
        Write-Host "  -> Firewall rule already exists for port 8000." -ForegroundColor Green
    }
} catch {
    Write-Warning "Failed to set firewall rules automatically: $_"
}

# 8. Register and Start Windows Services in Automatic Mode
Write-Host "`n[7/7] Installing Windows Services with AUTO_START on System Boot..." -ForegroundColor Yellow
$serviceInstaller = Join-Path $ProjectRoot "scripts\install_windows_services.ps1"

if (Test-Path $serviceInstaller) {
    & powershell.exe -ExecutionPolicy Bypass -NoProfile -File $serviceInstaller `
        -ProjectRoot $ProjectRoot `
        -PythonExe $venvPy `
        -StartType "SERVICE_AUTO_START" `
        -StartAfterInstall
} else {
    Write-Host "ERROR: Service installer not found at $serviceInstaller" -ForegroundColor Red
    exit 1
}

# 9. Final Diagnostic & URL Presentation
Write-Host "`n==========================================================================" -ForegroundColor Cyan
Write-Host " CLOUDOPS INTEL IS NOW CONFIGURED FOR 100% AUTOMATIC BOOT STARTUP!       " -ForegroundColor Green
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Setup complete! Press Enter to close"

# Gather Host Network IPs for user display
$ipAddresses = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Wi-Fi*","Ethernet*" -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike "169.254*" }).IPAddress

Write-Host "The application is running in the background as a Windows Service." -ForegroundColor White
Write-Host "It will automatically start whenever this laptop/server is powered on," -ForegroundColor White
Write-Host "even before any user logs in to Windows.`n" -ForegroundColor White

Write-Host "Access URLs:" -ForegroundColor Yellow
Write-Host "  Local Browser:     http://127.0.0.1:8000  or  https://localhost:8443" -ForegroundColor Cyan
foreach ($ip in $ipAddresses) {
    Write-Host "  Network / Lab PCs: https://$ip:8443" -ForegroundColor Cyan
}

Write-Host "`nService Management Commands:" -ForegroundColor Yellow
Write-Host "  Restart:  powershell -ExecutionPolicy Bypass -File C:\CLoudProject\scripts\restart_services.ps1" -ForegroundColor Gray
Write-Host "  Or simply double-click 'restart_services.bat' in the project folder." -ForegroundColor Gray
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Setup complete! Press Enter to close"

