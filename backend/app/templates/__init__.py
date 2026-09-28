"""
Email templates package.
"""
from backend.app.templates.email_templates import (
    get_admin_verification_email,
    get_super_admin_new_request_notification_email,
    get_admin_approval_activation_email,
    get_admin_rejection_email,
    get_password_reset_email,
    get_critical_alert_email,
    get_smtp_test_email,
)

__all__ = [
    "get_admin_verification_email",
    "get_super_admin_new_request_notification_email",
    "get_admin_approval_activation_email",
    "get_admin_rejection_email",
    "get_password_reset_email",
    "get_critical_alert_email",
    "get_smtp_test_email",
]
