"""
Production SMTP & Email Notification Service Layer.

Implements centralized email dispatch for:
1. Admin Registration Verification
2. Super Admin New Request Notifications
3. Admin Account Approval & Activation
4. Admin Request Rejection Notices
5. Single-Use Password Reset Instructions
6. Critical SRE Alert & Security Notifications
7. Super Admin SMTP Diagnostic Testing

Features:
- Dual-Mode Delivery: SMTP Transport (STARTTLS / SSL) vs In-Memory Development Outbox.
- Asynchronous Background Dispatch: Non-blocking worker pool for high-throughput HTTP endpoints.
- RFC-Compliant Multipart Messages (HTML + Plaintext).
- Strict Security & Error Sanitization: Never leaks credentials, passwords, or raw tokens in logs or responses.
"""

import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor

from backend.app.core.config import settings
from backend.app.templates.email_templates import (
    get_admin_verification_email,
    get_super_admin_new_request_notification_email,
    get_admin_approval_activation_email,
    get_admin_rejection_email,
    get_password_reset_email,
    get_critical_alert_email,
    get_smtp_test_email,
)

logger = logging.getLogger("cloudops.email_service")


class EmailDeliveryStatus:
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"
    MOCKED = "MOCKED"


class EmailService:
    """
    Centralized email delivery and template orchestration service.
    """

    # Thread pool for non-blocking asynchronous dispatch
    _thread_pool: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="email_dispatch")

    # In-memory mailbox for automated tests and development inspection
    _dev_outbox: List[Dict[str, Any]] = []

    @classmethod
    def _sanitize_error(cls, exc: Exception) -> str:
        """
        Removes sensitive details, file paths, or credentials from SMTP exceptions.
        """
        err_msg = str(exc)
        if isinstance(exc, smtplib.SMTPAuthenticationError):
            return "SMTP authentication failed. Verify SMTP username and password configuration."
        elif isinstance(exc, smtplib.SMTPConnectError):
            return "Could not connect to SMTP server. Verify SMTP host, port, and network availability."
        elif isinstance(exc, smtplib.SMTPServerDisconnected):
            return "SMTP server unexpectedly disconnected during transmission."
        elif isinstance(exc, TimeoutError) or "timed out" in err_msg.lower():
            return f"SMTP connection timed out after {settings.smtp_timeout_seconds}s."
        
        # Generic fallback without raw trace details
        return f"SMTP transmission error: {type(exc).__name__}"

    @classmethod
    def _build_mime_message(
        cls,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> MIMEMultipart:
        """
        Constructs an RFC 5322 compliant multipart/alternative MIME email.
        """
        msg = MIMEMultipart("alternative")
        from_name = settings.smtp_from_name or "CloudOps Intel Command Center"
        from_email = settings.smtp_from_email or (settings.smtp_user or "system@ops.local")

        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=False, usegmt=True)
        msg["Message-ID"] = make_msgid(domain="cloudops.local")

        # RFC standard: Plain text first, HTML second
        part_text = MIMEText(text_content, "plain", "utf-8")
        part_html = MIMEText(html_content, "html", "utf-8")

        msg.attach(part_text)
        msg.attach(part_html)
        return msg

    @classmethod
    def send_smtp_sync(
        cls,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> Tuple[bool, str]:
        """
        Synchronous low-level SMTP dispatch. Handles STARTTLS, SSL, and error reporting.
        Returns: (success_bool, sanitized_status_message)
        """
        if not settings.smtp_enabled:
            # Development Mode: Capture to in-memory outbox
            cls._dev_outbox.append({
                "to": to_email,
                "subject": subject,
                "html": html_content,
                "body": text_content,
                "timestamp": datetime.now(timezone.utc),
                "status": EmailDeliveryStatus.MOCKED,
            })
            logger.info(f"[EmailService] [DEV_OUTBOX] Dispatched to {to_email}: '{subject}'")
            return True, "Email recorded in development outbox (SMTP_ENABLED=false)."

        if not settings.smtp_host:
            logger.error("[EmailService] SMTP is enabled but SMTP_HOST is not configured.")
            return False, "SMTP configuration incomplete: SMTP_HOST is not set."

        from_email = settings.smtp_from_email or (settings.smtp_user or "system@ops.local")
        msg = cls._build_mime_message(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )

        server = None
        try:
            timeout = max(1, settings.smtp_timeout_seconds)

            if settings.smtp_ssl:
                # Direct SSL (typically port 465)
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=timeout, context=context)
            else:
                # Standard connection with optional STARTTLS (typically port 587 or 25)
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)
                server.ehlo()
                if settings.smtp_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.ehlo()

            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)

            server.send_message(msg, from_addr=from_email, to_addrs=[to_email])
            logger.info(f"[EmailService] [SMTP_SENT] Delivered email to {to_email}: '{subject}'")
            return True, "Email successfully delivered via SMTP."

        except Exception as exc:
            sanitized_err = cls._sanitize_error(exc)
            logger.error(f"[EmailService] [SMTP_FAILED] Delivery failed for {to_email}: {sanitized_err}")
            return False, sanitized_err
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    @classmethod
    def _dispatch(
        cls,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
        msg_metadata: Optional[Dict[str, Any]] = None,
        sync: bool = False,
    ) -> bool:
        """
        Internal dispatcher. If sync=True, runs immediately; otherwise runs in worker thread.
        Always records metadata to _dev_outbox when SMTP is disabled.
        """
        # When SMTP is disabled, capture rich metadata for tests immediately
        if not settings.smtp_enabled:
            record = {
                "to": to_email,
                "subject": subject,
                "html": html_content,
                "body": text_content,
                "timestamp": datetime.now(timezone.utc),
                "status": EmailDeliveryStatus.MOCKED,
            }
            if msg_metadata:
                record.update(msg_metadata)
            cls._dev_outbox.append(record)
            logger.info(f"[EmailService] [MOCK] Email dispatched to {to_email}: '{subject}'")
            return True

        if sync:
            success, _ = cls.send_smtp_sync(to_email, subject, html_content, text_content)
            return success

        # Asynchronous background execution via worker pool
        cls._thread_pool.submit(
            cls.send_smtp_sync,
            to_email,
            subject,
            html_content,
            text_content,
        )
        return True

    # ==========================================================================
    # High-Level Notification Dispatchers
    # ==========================================================================

    @classmethod
    def send_verification_email(cls, email: str, raw_token: str, user_id: Optional[int] = None) -> bool:
        """
        Dispatches account verification link for standard user provisioning.
        """
        verify_url = f"{settings.frontend_url}/#verify-email?token={raw_token}"
        subject, html_content, text_content = get_admin_verification_email(
            email=email,
            full_name=email.split("@")[0],
            raw_token=raw_token,
        )
        return cls._dispatch(
            to_email=email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            msg_metadata={
                "type": "EMAIL_VERIFICATION",
                "raw_token": raw_token,
                "url": verify_url,
                "user_id": user_id,
            },
        )

    @classmethod
    def send_password_reset_email(cls, email: str, raw_token: str, user_id: Optional[int] = None) -> bool:
        """
        Dispatches single-use password reset link.
        """
        reset_url = f"{settings.frontend_url}/#reset-password?token={raw_token}"
        subject, html_content, text_content = get_password_reset_email(
            email=email,
            raw_token=raw_token,
        )
        return cls._dispatch(
            to_email=email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            msg_metadata={
                "type": "PASSWORD_RESET",
                "raw_token": raw_token,
                "url": reset_url,
                "user_id": user_id,
            },
        )

    @classmethod
    def send_admin_request_verification_email(cls, email: str, full_name: str, raw_token: str) -> bool:
        """
        Dispatches email address verification link for prospective administrator request.
        """
        verify_url = f"{settings.frontend_url}/#verify-admin-request?token={raw_token}"
        subject, html_content, text_content = get_admin_verification_email(
            email=email,
            full_name=full_name,
            raw_token=raw_token,
        )
        return cls._dispatch(
            to_email=email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            msg_metadata={
                "type": "ADMIN_REQUEST_VERIFICATION",
                "raw_token": raw_token,
                "url": verify_url,
                "full_name": full_name,
            },
        )

    @classmethod
    def send_super_admin_new_request_notification(
        cls,
        super_admin_email: str,
        applicant_email: str,
        applicant_name: str,
        organization: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Notifies an active Super Admin that a new admin request has completed email verification.
        """
        subject, html_content, text_content = get_super_admin_new_request_notification_email(
            super_admin_email=super_admin_email,
            applicant_email=applicant_email,
            applicant_name=applicant_name,
            organization=organization,
            reason=reason,
        )
        return cls._dispatch(
            to_email=super_admin_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            msg_metadata={
                "type": "SUPER_ADMIN_NEW_REQUEST_NOTIFICATION",
                "applicant_email": applicant_email,
                "applicant_name": applicant_name,
                "organization": organization,
            },
        )

    @classmethod
    def send_admin_approval_activation_email(cls, email: str, full_name: str, raw_token: str) -> bool:
        """
        Dispatches account activation link for an approved administrator request.
        """
        activate_url = f"{settings.frontend_url}/#activate-admin?token={raw_token}"
        subject, html_content, text_content = get_admin_approval_activation_email(
            email=email,
            full_name=full_name,
            raw_token=raw_token,
        )
        return cls._dispatch(
            to_email=email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            msg_metadata={
                "type": "ADMIN_APPROVAL_ACTIVATION",
                "raw_token": raw_token,
                "url": activate_url,
                "full_name": full_name,
            },
        )

    @classmethod
    def send_admin_rejection_email(cls, email: str, full_name: str, reason: Optional[str] = None) -> bool:
        """
        Dispatches rejection notification for an unapproved administrator request.
        """
        subject, html_content, text_content = get_admin_rejection_email(
            email=email,
            full_name=full_name,
            reason=reason,
        )
        return cls._dispatch(
            to_email=email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            msg_metadata={
                "type": "ADMIN_REQUEST_REJECTION",
                "full_name": full_name,
                "reason": reason,
            },
        )

    @classmethod
    def send_critical_alert_notification(
        cls,
        recipient_email: str,
        alert_id: int,
        host_name: str,
        metric: str,
        value: float,
        threshold: float,
        operator: str,
        message: str,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Dispatches real-time critical incident notification.
        """
        subject, html_content, text_content = get_critical_alert_email(
            alert_id=alert_id,
            host_name=host_name,
            metric=metric,
            value=value,
            threshold=threshold,
            operator=operator,
            message=message,
            timestamp=timestamp,
        )
        return cls._dispatch(
            to_email=recipient_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            msg_metadata={
                "type": "CRITICAL_ALERT",
                "alert_id": alert_id,
                "host_name": host_name,
                "metric": metric,
                "value": value,
            },
        )

    @classmethod
    def send_test_email(cls, recipient_email: str) -> Tuple[bool, str]:
        """
        Synchronous diagnostic check for Super Admin testing.
        """
        subject, html_content, text_content = get_smtp_test_email(recipient_email=recipient_email)
        return cls.send_smtp_sync(
            to_email=recipient_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )

    # ==========================================================================
    # Test Suite & Development Inspection Helpers
    # ==========================================================================

    @classmethod
    def get_outbox(cls) -> list:
        """Helper returning copy of outbox records."""
        return list(cls._dev_outbox)

    @classmethod
    def get_latest_email_for(cls, email: str) -> Optional[Dict[str, Any]]:
        """Helper retrieving most recent message for specified recipient."""
        for msg in reversed(cls._dev_outbox):
            if msg["to"] == email:
                return msg
        return None

    @classmethod
    def clear_outbox(cls) -> None:
        """Clears in-memory outbox records."""
        cls._dev_outbox.clear()
