"""
Sensor Agent Packaging Utility.

Builds a clean, self-contained distribution package for Windows Lab PCs.
Includes public CA root certificate, installer script, agent code, and documentation.
STRICTLY AUDITED TO NEVER INCLUDE:
- root.key (private CA key)
- .env (server environment variables)
- cloud_intelligence.db (server database)
- any admin or backend credentials
"""

import hashlib
import os
import shutil
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
PACKAGE_ZIP = DIST_DIR / "cloudops-sensor-package.zip"
CHECKSUM_FILE = DIST_DIR / "cloudops-sensor-package.zip.sha256"

# Source files
PUBLIC_CA_CERT = PROJECT_ROOT / "data" / "caddy" / "pki" / "authorities" / "local" / "root.crt"
INSTALL_SCRIPT = PROJECT_ROOT / "scripts" / "install_sensor_client.ps1"
UNINSTALL_SCRIPT = PROJECT_ROOT / "scripts" / "uninstall_sensor_client.ps1"
AGENT_DIR = PROJECT_ROOT / "monitoring_agent"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements-agent.txt"
README_FILE = PROJECT_ROOT / "README_SENSOR.md"

FORBIDDEN_FILES = ["root.key", ".env", "cloud_intelligence.db", ".git", "__pycache__"]


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def build_package():
    print("=" * 60)
    print(" CloudOps Intel — Lab PC Sensor Packaging Utility")
    print("=" * 60)

    if not PUBLIC_CA_CERT.exists():
        print(f"[-] ERROR: Public CA certificate not found at {PUBLIC_CA_CERT}")
        sys.exit(1)

    DIST_DIR.mkdir(parents=True, exist_ok=True)

    print("[*] Assembling sensor package contents...")
    temp_build_dir = DIST_DIR / "build_sensor_pkg"
    if temp_build_dir.exists():
        shutil.rmtree(temp_build_dir)
    temp_build_dir.mkdir(parents=True)

    # 1. Copy monitoring agent files
    target_agent_dir = temp_build_dir / "monitoring_agent"
    target_agent_dir.mkdir(parents=True)
    for agent_file in ["agent.py", "buffer.py", "collector.py", "__init__.py"]:
        src = AGENT_DIR / agent_file
        if src.exists():
            shutil.copy2(src, target_agent_dir / agent_file)
            print(f"    + monitoring_agent/{agent_file}")

    # 2. Copy scripts and docs
    shutil.copy2(INSTALL_SCRIPT, temp_build_dir / "install_sensor_client.ps1")
    print("    + install_sensor_client.ps1")

    shutil.copy2(UNINSTALL_SCRIPT, temp_build_dir / "uninstall_sensor_client.ps1")
    print("    + uninstall_sensor_client.ps1")

    shutil.copy2(REQUIREMENTS_FILE, temp_build_dir / "requirements.txt")
    print("    + requirements.txt")

    shutil.copy2(README_FILE, temp_build_dir / "README.md")
    print("    + README.md")

    # 3. Copy public root.crt ONLY
    shutil.copy2(PUBLIC_CA_CERT, temp_build_dir / "root.crt")
    print("    + root.crt (Public Caddy Authority Certificate)")

    # 4. Strict security audit of staged files
    print("[*] Performing security audit against staged files...")
    for root, _, files in os.walk(temp_build_dir):
        for fname in files:
            for forbidden in FORBIDDEN_FILES:
                if forbidden.lower() in fname.lower():
                    raise RuntimeError(f"SECURITY VIOLATION: Forbidden file '{fname}' detected in package!")

    # 5. Create zip archive
    if PACKAGE_ZIP.exists():
        PACKAGE_ZIP.unlink()

    with zipfile.ZipFile(PACKAGE_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(temp_build_dir):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(temp_build_dir)
                zf.write(full_path, arcname=str(rel_path))

    # Clean up temp dir
    shutil.rmtree(temp_build_dir)

    # 6. Generate SHA-256 checksum
    checksum = compute_sha256(PACKAGE_ZIP)
    with open(CHECKSUM_FILE, "w", encoding="utf-8") as f:
        f.write(f"{checksum} *{PACKAGE_ZIP.name}\n")

    pkg_size_kb = PACKAGE_ZIP.stat().st_size / 1024

    print("[+] Package successfully created:")
    print(f"    File:     {PACKAGE_ZIP}")
    print(f"    Size:     {pkg_size_kb:.1f} KB")
    print(f"    SHA-256:  {checksum}")
    print(f"    Checksum: {CHECKSUM_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    build_package()
