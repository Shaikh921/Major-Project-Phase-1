"""
Administrator Bootstrap CLI Command.

Usage:
    python -m backend.app.cli.bootstrap_admin
    python -m backend.app.cli.bootstrap_admin --email admin@ops.local

Prompts securely for password using getpass to avoid leaking credentials
into process tables or shell command history.
"""

import sys
import argparse
import getpass
from sqlalchemy import select

from backend.app.database.session import SessionLocal
from backend.app.database.init_db import init_db
from backend.app.models.user import User, UserRole
from backend.app.services.auth_service import create_bootstrap_admin


def main():
    parser = argparse.ArgumentParser(description="Bootstrap the initial CloudOps Intel Administrator.")
    parser.add_argument("--email", help="Administrator email address", default=None)
    parser.add_argument("--password", help="Administrator password (not recommended in shell history)", default=None)
    args = parser.parse_args()

    # Ensure database schema is initialized
    init_db()

    with SessionLocal() as db:
        # Check if a super administrator already exists
        existing_super = db.scalar(select(User).where(User.role == UserRole.SUPER_ADMIN).limit(1))
        if existing_super:
            print(f"[ERROR] A Super Administrator account already exists ({existing_super.email}).")
            print("First-run bootstrap is disabled. Use the Super Admin management portal to manage administrators.")
            sys.exit(1)

        email = args.email
        if not email:
            email = input("Enter Super Administrator Email: ").strip()
        
        if not email or "@" not in email:
            print("[ERROR] Invalid email address provided.")
            sys.exit(1)

        password = args.password
        if not password:
            password = getpass.getpass("Enter Super Administrator Password (min 8 chars): ")
            confirm = getpass.getpass("Confirm Super Administrator Password: ")
            if password != confirm:
                print("[ERROR] Passwords do not match.")
                sys.exit(1)

        if len(password) < 8:
            print("[ERROR] Password must be at least 8 characters long.")
            sys.exit(1)

        try:
            admin = create_bootstrap_admin(db, email=email, password=password)
            print(f"\n[SUCCESS] Super Administrator '{admin.email}' created successfully.")
            print(f"Role: {admin.role} | Active: {admin.is_active} | Verified: {admin.is_verified}")
            print("You may now log in to the CloudOps Intel Command Center with Super Administrator authority.\n")
        except Exception as e:
            print(f"[ERROR] Failed to bootstrap administrator: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
