#!/usr/bin/env bash
# ==============================================================================
# CloudOps Intel - Automated Linux Server Provisioner & Systemd Auto-Start Setup
# Supported: Ubuntu 20.04+, Debian 11+, RHEL/Rocky Linux 8+
# ==============================================================================
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Error: This setup script must be run as root (use: sudo ./setup_linux_server.sh)" >&2
  exit 1
fi

PROJECT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
echo "=========================================================================="
echo " CloudOps Intel - Linux Server Provisioner & Auto-Start Setup"
echo " Project Directory: $PROJECT_DIR"
echo "=========================================================================="

# 1. Install prerequisites
echo "[1/6] Installing runtime prerequisites (Python 3, venv, curl)..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y python3 python3-venv python3-pip curl debian-keyring debian-archive-keyring apt-transport-https
elif command -v dnf >/dev/null 2>&1; then
    dnf install -y python3 python3-pip curl
fi

# 2. Install Caddy if not present
echo "[2/6] Verifying Caddy Web Server..."
if ! command -v caddy >/dev/null 2>&1; then
    echo "  - Installing Caddy via official repository..."
    if command -v apt-get >/dev/null 2>&1; then
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg --yes
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
        apt-get update -y
        apt-get install -y caddy
    fi
fi

# 3. Create Python Virtual Environment
echo "[3/6] Setting up Python virtual environment (.venv)..."
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    python3 -m venv "$PROJECT_DIR/.venv"
fi
"$PROJECT_DIR/.venv/bin/pip" install --upgrade pip wheel setuptools
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    echo "  - Installing requirements.txt..."
    "$PROJECT_DIR/.venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
fi

# 4. Configure .env & SQLite Database
echo "[4/6] Initializing configuration and database..."
mkdir -p "$PROJECT_DIR/logs/backend" "$PROJECT_DIR/logs/proxy" "$PROJECT_DIR/data/caddy"
if [ ! -f "$PROJECT_DIR/.env" ]; then
    if [ -f "$PROJECT_DIR/.env.example" ]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    else
        SECRET_KEY=$("$PROJECT_DIR/.venv/bin/python" -c "import secrets; print(secrets.token_urlsafe(48))")
        cat <<EOF > "$PROJECT_DIR/.env"
APP_NAME=CloudOps Intel
ENVIRONMENT=production
HOST=127.0.0.1
PORT=8000
DATABASE_URL=sqlite:///./cloud_intelligence.db
SECRET_KEY=$SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
EOF
    fi
fi
"$PROJECT_DIR/.venv/bin/python" -c "from backend.app.database.init_db import init_db; init_db(); print('Database schemas initialized.')"

# 5. Install Systemd Services
echo "[5/6] Installing and enabling Systemd Services for Automatic Boot Startup..."
# Replace directory paths in service unit templates
sed "s|/opt/cloudops|$PROJECT_DIR|g" "$PROJECT_DIR/scripts/linux/cloudops-backend.service" > /etc/systemd/system/cloudops-backend.service
sed "s|/opt/cloudops|$PROJECT_DIR|g" "$PROJECT_DIR/scripts/linux/cloudops-proxy.service" > /etc/systemd/system/cloudops-proxy.service

systemctl daemon-reload
systemctl enable cloudops-backend.service
systemctl enable cloudops-proxy.service
systemctl restart cloudops-backend.service
systemctl restart cloudops-proxy.service

# 6. Configure UFW Firewall (if active)
echo "[6/6] Checking firewall configuration..."
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
    ufw allow 8443/tcp comment "CloudOps Intel HTTPS"
    ufw reload
fi

echo "=========================================================================="
echo " CloudOps Intel is now running as a Systemd service and will auto-start on boot!"
echo " Status Check: sudo systemctl status cloudops-backend cloudops-proxy"
echo "=========================================================================="

