"""
Centralized Responsive Email Templates for CloudOps Intel Command Center.

Generates HTML (multipart/alternative) and clean plaintext alternatives for:
1. Admin Registration Verification
2. Super Admin New Request Notification
3. Admin Approval & Account Activation
4. Admin Request Rejection Notice
5. Password Reset Instructions
6. Critical SRE Alert & Security Incident
7. SMTP Relay Diagnostic Test

Design: Resilient inline styling compatible with major mail clients (Gmail, Outlook, Apple Mail).
Constraint: Zero emojis, professional SRE aesthetics, strict security boundaries.
"""

from typing import Tuple, Optional
from datetime import datetime, timezone
import html

from backend.app.core.config import settings


def _escape(text: Optional[str]) -> str:
    """Safely escapes HTML characters."""
    if text is None:
        return ""
    return html.escape(str(text))


def _base_html_layout(title: str, content_html: str, action_url: Optional[str] = None, action_label: Optional[str] = None) -> str:
    """
    Standard responsive email wrapper with CloudOps Intel branding and footer.
    """
    cta_block = ""
    if action_url and action_label:
        cta_block = f"""
        <table border="0" cellpadding="0" cellspacing="0" style="margin: 28px 0;">
          <tr>
            <td align="center" style="border-radius: 6px; background-color: #2563eb;">
              <a href="{_escape(action_url)}" target="_blank" style="font-size: 14px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-weight: 600; color: #ffffff; text-decoration: none; display: inline-block; padding: 12px 24px; border-radius: 6px; letter-spacing: 0.02em;">
                {_escape(action_label)}
              </a>
            </td>
          </tr>
        </table>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_escape(title)}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #e2e8f0; -webkit-font-smoothing: antialiased;">
  <table width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color: #0b0f19; padding: 32px 16px;">
    <tr>
      <td align="center">
        <!-- Main Card Container -->
        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="max-width: 580px; background-color: #131b2e; border: 1px solid #1e293b; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);">
          <!-- Header Bar -->
          <tr>
            <td style="padding: 24px 32px; background-color: #0f172a; border-bottom: 1px solid #1e293b;">
              <table width="100%" border="0" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <div style="font-size: 15px; font-weight: 700; letter-spacing: -0.01em; color: #38bdf8;">
                      CLOUDOPS INTEL
                    </div>
                    <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; margin-top: 2px;">
                      SRE Command Center
                    </div>
                  </td>
                  <td align="right">
                    <span style="display: inline-block; font-size: 10px; font-family: 'JetBrains Mono', Consolas, Monaco, monospace; color: #38bdf8; background-color: #0369a120; border: 1px solid #0284c740; padding: 2px 8px; border-radius: 4px; font-weight: 600;">
                      SECURITY DISPATCH
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Main Content Body -->
          <tr>
            <td style="padding: 32px 32px 24px 32px; font-size: 14px; line-height: 1.6; color: #cbd5e1;">
              {content_html}
              {cta_block}
            </td>
          </tr>

          <!-- Security Footer -->
          <tr>
            <td style="padding: 20px 32px; background-color: #0f172a; border-top: 1px solid #1e293b; font-size: 11px; color: #64748b; line-height: 1.5;">
              <p style="margin: 0 0 6px 0;">This is an automated operational notification from the CloudOps Intel platform.</p>
              <p style="margin: 0;">If you did not initiate or authorize this request, please notify your Lead Systems Administrator immediately.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ==============================================================================
# 1. Admin Registration Verification Template
# ==============================================================================
def get_admin_verification_email(email: str, full_name: str, raw_token: str) -> Tuple[str, str, str]:
    subject = f"[{settings.app_name}] Verify Your Administrator Access Request"
    verify_url = f"{settings.frontend_url}/#verify-admin-request?token={raw_token}"
    expires_hours = settings.verification_token_expire_hours

    html_content = _base_html_layout(
        title="Verify Your Administrator Access Request",
        content_html=f"""
          <h2 style="font-size: 18px; font-weight: 600; color: #f8fafc; margin: 0 0 16px 0;">
            Verify Your Email Address
          </h2>
          <p style="margin: 0 0 14px 0;">Hello {_escape(full_name)},</p>
          <p style="margin: 0 0 14px 0;">
            We received your registration request for Administrator access to the <strong style="color: #f8fafc;">{_escape(settings.app_name)}</strong>.
          </p>
          <p style="margin: 0 0 14px 0;">
            To confirm your email address and submit your request for Super Administrator review, click the button below:
          </p>
          <div style="background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 12px 16px; margin: 20px 0; font-size: 12px; color: #94a3b8;">
            <strong style="color: #cbd5e1;">Security Notice:</strong> This verification link is single-use and will expire in <strong style="color: #38bdf8;">{expires_hours} hours</strong>.
          </div>
          <p style="margin: 16px 0 0 0; font-size: 12px; color: #64748b;">
            Direct verification URL:<br>
            <span style="font-family: monospace; color: #94a3b8; word-break: break-all;">{_escape(verify_url)}</span>
          </p>
        """,
        action_url=verify_url,
        action_label="Verify Email Address",
    )

    text_content = f"""CLOUDOPS INTEL - SRE COMMAND CENTER
VERIFY YOUR ADMINISTRATOR ACCESS REQUEST

Hello {full_name},

We received your registration request for Administrator access to {settings.app_name}.

Please verify your email address by opening the URL below:
{verify_url}

This verification link will expire in {expires_hours} hours.
Once verified, your request will be queued for Super Administrator approval.

If you did not submit this request, you may safely disregard this message.
"""
    return subject, html_content, text_content


# ==============================================================================
# 2. Super Admin New Request Notification Template
# ==============================================================================
def get_super_admin_new_request_notification_email(
    super_admin_email: str,
    applicant_email: str,
    applicant_name: str,
    organization: Optional[str] = None,
    reason: Optional[str] = None,
) -> Tuple[str, str, str]:
    subject = f"[{settings.app_name}] ACTION REQUIRED: New Administrator Access Request"
    admin_panel_url = f"{settings.frontend_url}/#admin-management"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    org_row = f"<tr><td style='padding: 6px 0; color: #64748b;'>Organization:</td><td style='padding: 6px 0; color: #f8fafc; font-weight: 500;'>{_escape(organization or 'N/A')}</td></tr>"
    reason_row = f"<tr><td style='padding: 6px 0; color: #64748b;'>Justification:</td><td style='padding: 6px 0; color: #f8fafc; font-style: italic;'>{_escape(reason or 'None provided')}</td></tr>"

    html_content = _base_html_layout(
        title="New Administrator Access Request Pending Review",
        content_html=f"""
          <h2 style="font-size: 18px; font-weight: 600; color: #f8fafc; margin: 0 0 16px 0;">
            New Administrator Access Request
          </h2>
          <p style="margin: 0 0 16px 0;">
            An applicant has verified their email address and is awaiting your review and authorization:
          </p>
          <table width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 14px 18px; margin: 16px 0; font-size: 13px;">
            <tr>
              <td style="padding: 6px 0; color: #64748b; width: 120px;">Applicant:</td>
              <td style="padding: 6px 0; color: #f8fafc; font-weight: 600;">{_escape(applicant_name)}</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Email:</td>
              <td style="padding: 6px 0; color: #38bdf8; font-family: monospace;">{_escape(applicant_email)}</td>
            </tr>
            {org_row}
            {reason_row}
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Verified At:</td>
              <td style="padding: 6px 0; color: #94a3b8; font-family: monospace;">{_escape(now_str)}</td>
            </tr>
          </table>
          <p style="margin: 16px 0 0 0;">
            Please log in to the Super Admin Management Panel to review, approve, or reject this request.
          </p>
        """,
        action_url=admin_panel_url,
        action_label="Review in Admin Panel",
    )

    text_content = f"""CLOUDOPS INTEL - SRE COMMAND CENTER
ACTION REQUIRED: NEW ADMINISTRATOR ACCESS REQUEST

A prospective administrator has completed email verification and is awaiting Super Admin review:

Applicant: {applicant_name}
Email: {applicant_email}
Organization: {organization or 'N/A'}
Justification: {reason or 'None provided'}
Timestamp: {now_str}

Review this request in the Super Admin Management Panel:
{admin_panel_url}
"""
    return subject, html_content, text_content


# ==============================================================================
# 3. Admin Approval / Activation Template
# ==============================================================================
def get_admin_approval_activation_email(email: str, full_name: str, raw_token: str) -> Tuple[str, str, str]:
    subject = f"[{settings.app_name}] Your Administrator Access Request Was Approved"
    activate_url = f"{settings.frontend_url}/#activate-admin?token={raw_token}"

    html_content = _base_html_layout(
        title="Administrator Request Approved - Activate Account",
        content_html=f"""
          <h2 style="font-size: 18px; font-weight: 600; color: #10b981; margin: 0 0 16px 0;">
            Access Request Approved
          </h2>
          <p style="margin: 0 0 14px 0;">Hello {_escape(full_name)},</p>
          <p style="margin: 0 0 14px 0;">
            Your request for Administrator privileges on <strong style="color: #f8fafc;">{_escape(settings.app_name)}</strong> has been <strong style="color: #10b981;">APPROVED</strong> by a Super Administrator.
          </p>
          <p style="margin: 0 0 14px 0;">
            Click the button below to configure your password and complete account activation:
          </p>
          <div style="background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 12px 16px; margin: 20px 0; font-size: 12px; color: #94a3b8;">
            <strong style="color: #cbd5e1;">Single-Use Link:</strong> This activation token is valid for <strong style="color: #38bdf8;">24 hours</strong>. For security compliance, password configuration is required before first sign-in.
          </div>
          <p style="margin: 16px 0 0 0; font-size: 12px; color: #64748b;">
            Direct activation link:<br>
            <span style="font-family: monospace; color: #94a3b8; word-break: break-all;">{_escape(activate_url)}</span>
          </p>
        """,
        action_url=activate_url,
        action_label="Set Password & Activate Account",
    )

    text_content = f"""CLOUDOPS INTEL - SRE COMMAND CENTER
ADMINISTRATOR ACCESS APPROVED

Hello {full_name},

Your request for Administrator access to {settings.app_name} has been APPROVED by a Super Administrator.

Click the link below to configure your password and activate your account:
{activate_url}

This activation link is single-use and will expire in 24 hours.
"""
    return subject, html_content, text_content


# ==============================================================================
# 4. Admin Rejection Template
# ==============================================================================
def get_admin_rejection_email(email: str, full_name: str, reason: Optional[str] = None) -> Tuple[str, str, str]:
    subject = f"[{settings.app_name}] Update Regarding Your Administrator Access Request"
    reason_block = ""
    if reason:
        reason_block = f"""
        <div style="background-color: #1e293b; border-left: 3px solid #ef4444; padding: 12px 16px; margin: 18px 0; font-size: 13px; color: #cbd5e1;">
          <strong style="color: #f8fafc;">Reviewer Notes:</strong><br>
          {_escape(reason)}
        </div>
        """

    html_content = _base_html_layout(
        title="Administrator Request Status Update",
        content_html=f"""
          <h2 style="font-size: 18px; font-weight: 600; color: #f8fafc; margin: 0 0 16px 0;">
            Administrator Access Request Update
          </h2>
          <p style="margin: 0 0 14px 0;">Hello {_escape(full_name)},</p>
          <p style="margin: 0 0 14px 0;">
            Thank you for your interest in {_escape(settings.app_name)}. After administrative evaluation, your request for Administrator access was not approved at this time.
          </p>
          {reason_block}
          <p style="margin: 14px 0 0 0; font-size: 13px; color: #94a3b8;">
            If you believe this is an error or require operational clearance, please contact your organization's Systems Operations Lead.
          </p>
        """,
    )

    reason_text = f"\nReviewer Notes:\n{reason}\n" if reason else ""
    text_content = f"""CLOUDOPS INTEL - SRE COMMAND CENTER
ADMINISTRATOR ACCESS REQUEST UPDATE

Hello {full_name},

Thank you for your interest in {settings.app_name}.
After administrative evaluation, your request for Administrator access was not approved at this time.
{reason_text}
If you have questions, please reach out to your systems operations lead.
"""
    return subject, html_content, text_content


# ==============================================================================
# 5. Password Reset Template
# ==============================================================================
def get_password_reset_email(email: str, raw_token: str) -> Tuple[str, str, str]:
    subject = f"[{settings.app_name}] Password Reset Instructions"
    reset_url = f"{settings.frontend_url}/#reset-password?token={raw_token}"
    expires_min = settings.password_reset_token_expire_minutes

    html_content = _base_html_layout(
        title="Password Reset Request",
        content_html=f"""
          <h2 style="font-size: 18px; font-weight: 600; color: #f8fafc; margin: 0 0 16px 0;">
            Password Reset Request
          </h2>
          <p style="margin: 0 0 14px 0;">
            A password recovery request was received for the account associated with <strong style="color: #38bdf8;">{_escape(email)}</strong>.
          </p>
          <p style="margin: 0 0 14px 0;">
            To set a new password, click the button below:
          </p>
          <div style="background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 12px 16px; margin: 20px 0; font-size: 12px; color: #94a3b8;">
            <strong style="color: #cbd5e1;">Security Notice:</strong> This link is single-use and will expire in <strong style="color: #38bdf8;">{expires_min} minutes</strong>. All existing active sessions will be terminated upon reset.
          </div>
          <p style="margin: 16px 0 0 0; font-size: 12px; color: #64748b;">
            Direct reset link:<br>
            <span style="font-family: monospace; color: #94a3b8; word-break: break-all;">{_escape(reset_url)}</span>
          </p>
        """,
        action_url=reset_url,
        action_label="Reset Account Password",
    )

    text_content = f"""CLOUDOPS INTEL - SRE COMMAND CENTER
PASSWORD RESET INSTRUCTIONS

A password reset request was received for account: {email}

Click the link below to set a new password:
{reset_url}

This link is single-use and will expire in {expires_min} minutes.
If you did not request this reset, you may safely ignore this message.
"""
    return subject, html_content, text_content


# ==============================================================================
# 6. Critical SRE Alert Template
# ==============================================================================
def get_critical_alert_email(
    alert_id: int,
    host_name: str,
    metric: str,
    value: float,
    threshold: float,
    operator: str,
    message: str,
    timestamp: Optional[datetime] = None,
) -> Tuple[str, str, str]:
    subject = f"[{settings.app_name}] CRITICAL ALERT: {host_name} - {metric}"
    dashboard_url = f"{settings.frontend_url}/#incidents"
    ts_str = (timestamp or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S UTC")

    html_content = _base_html_layout(
        title="Critical SRE Incident Alert",
        content_html=f"""
          <div style="display: inline-block; background-color: #ef444420; border: 1px solid #ef444460; color: #f87171; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 4px; text-transform: uppercase; margin-bottom: 12px; font-family: monospace;">
            SEVERITY: CRITICAL
          </div>
          <h2 style="font-size: 18px; font-weight: 600; color: #f8fafc; margin: 0 0 16px 0;">
            Operational Threshold Breach Detected
          </h2>
          <p style="margin: 0 0 14px 0;">
            A critical infrastructure threshold breach has been triggered and recorded in the telemetry stream:
          </p>
          <table width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 14px 18px; margin: 16px 0; font-size: 13px;">
            <tr>
              <td style="padding: 6px 0; color: #64748b; width: 120px;">Host / Node:</td>
              <td style="padding: 6px 0; color: #f8fafc; font-family: monospace; font-weight: 600;">{_escape(host_name)}</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Metric:</td>
              <td style="padding: 6px 0; color: #38bdf8; font-family: monospace;">{_escape(metric)}</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Breached Value:</td>
              <td style="padding: 6px 0; color: #ef4444; font-weight: 700; font-family: monospace;">{value:.2f}% (Threshold: {operator} {threshold:.2f}%)</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Alert Message:</td>
              <td style="padding: 6px 0; color: #cbd5e1;">{_escape(message)}</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Timestamp:</td>
              <td style="padding: 6px 0; color: #94a3b8; font-family: monospace;">{_escape(ts_str)}</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Incident ID:</td>
              <td style="padding: 6px 0; color: #64748b; font-family: monospace;">#{alert_id}</td>
            </tr>
          </table>
          <p style="margin: 16px 0 0 0;">
            Investigate this incident immediately in the SRE Command Center.
          </p>
        """,
        action_url=dashboard_url,
        action_label="Open Incident Center",
    )

    text_content = f"""CLOUDOPS INTEL - CRITICAL SRE ALERT

SEVERITY: CRITICAL
Host: {host_name}
Metric: {metric}
Value: {value:.2f}% (Condition: {operator} {threshold:.2f}%)
Message: {message}
Timestamp: {ts_str}
Incident ID: #{alert_id}

Investigate at:
{dashboard_url}
"""
    return subject, html_content, text_content


# ==============================================================================
# 7. SMTP Test Email Template
# ==============================================================================
def get_smtp_test_email(recipient_email: str) -> Tuple[str, str, str]:
    subject = f"[{settings.app_name}] SMTP Relay Diagnostic Test"
    ts_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    html_content = _base_html_layout(
        title="SMTP Diagnostic Verification",
        content_html=f"""
          <div style="display: inline-block; background-color: #10b98120; border: 1px solid #10b98160; color: #34d399; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 4px; text-transform: uppercase; margin-bottom: 12px; font-family: monospace;">
            DIAGNOSTIC STATUS: OK
          </div>
          <h2 style="font-size: 18px; font-weight: 600; color: #f8fafc; margin: 0 0 16px 0;">
            SMTP Delivery Channel Verified
          </h2>
          <p style="margin: 0 0 14px 0;">
            This email confirms that the <strong style="color: #f8fafc;">{_escape(settings.app_name)}</strong> email delivery subsystem is operating correctly.
          </p>
          <table width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 14px 18px; margin: 16px 0; font-size: 13px;">
            <tr>
              <td style="padding: 6px 0; color: #64748b; width: 140px;">Recipient:</td>
              <td style="padding: 6px 0; color: #38bdf8; font-family: monospace;">{_escape(recipient_email)}</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Sender Address:</td>
              <td style="padding: 6px 0; color: #94a3b8; font-family: monospace;">{_escape(settings.smtp_from_email or 'system@ops.local')}</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Relay Mode:</td>
              <td style="padding: 6px 0; color: #10b981; font-weight: 600;">{'Live SMTP Transport' if settings.smtp_enabled else 'Development Outbox Mock'}</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Timestamp:</td>
              <td style="padding: 6px 0; color: #94a3b8; font-family: monospace;">{_escape(ts_str)}</td>
            </tr>
          </table>
          <p style="margin: 16px 0 0 0; font-size: 12px; color: #64748b;">
            All system notifications, security tokens, and administrative activations will route through this delivery engine.
          </p>
        """,
    )

    text_content = f"""CLOUDOPS INTEL - SRE COMMAND CENTER
SMTP RELAY DIAGNOSTIC TEST

Status: OPERATIONAL
Recipient: {recipient_email}
Sender: {settings.smtp_from_email or 'system@ops.local'}
Mode: {'Live SMTP Transport' if settings.smtp_enabled else 'Development Outbox Mock'}
Timestamp: {ts_str}

This confirms that the CloudOps Intel email delivery subsystem is configured and operational.
"""
    return subject, html_content, text_content


# ==============================================================================
# 8. Correlated ML Anomaly (Threshold + Isolation Forest + LSTM) Template
# ==============================================================================
def get_correlated_anomaly_email(
    alert_id: int,
    host_name: str,
    ip_address: Optional[str],
    environment: str,
    metric_name: str,
    metric_value: float,
    threshold_value: float,
    iso_score: float,
    lstm_score: float,
    lstm_threshold: float,
    explanation: str,
    timestamp: Optional[datetime] = None,
) -> Tuple[str, str, str]:
    """
    Generates a high-priority correlated anomaly incident notification.
    Dispatched when Resource Threshold + Isolation Forest + LSTM Autoencoder all confirm an anomaly.
    """
    subject = f"[{settings.app_name}] CRITICAL CORRELATED INCIDENT: {host_name} (Threshold + Isolation Forest + LSTM)"
    dashboard_url = f"{settings.frontend_url}/#anomalies"
    ts_str = (timestamp or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S UTC")

    html_content = _base_html_layout(
        title="High-Priority Correlated AI Incident",
        content_html=f"""
          <div style="display: inline-block; background-color: #dc262625; border: 1px solid #ef4444; color: #fca5a5; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 4px; text-transform: uppercase; margin-bottom: 12px; font-family: monospace;">
            AI CONSENSUS: CRITICAL MULTI-MODEL ANOMALY
          </div>
          <h2 style="font-size: 18px; font-weight: 700; color: #ffffff; margin: 0 0 16px 0;">
            Correlated Infrastructure Incident Detected
          </h2>
          <p style="margin: 0 0 14px 0; color: #cbd5e1;">
            A severe incident has been confirmed on host <strong style="color: #38bdf8;">{_escape(host_name)}</strong>. 
            All three diagnostic layers (Resource Thresholds, Multivariate Isolation Forest, and Deep LSTM Autoencoder) have simultaneously flagged this event.
          </p>
          <table width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 14px 18px; margin: 16px 0; font-size: 13px;">
            <tr>
              <td style="padding: 6px 0; color: #64748b; width: 160px;">Target Host:</td>
              <td style="padding: 6px 0; color: #f8fafc; font-family: monospace; font-weight: 600;">{_escape(host_name)} ({_escape(ip_address or 'N/A')})</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Environment:</td>
              <td style="padding: 6px 0; color: #f8fafc; text-transform: uppercase; font-weight: 600;">{_escape(environment)}</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Breached Metric:</td>
              <td style="padding: 6px 0; color: #ef4444; font-weight: 700; font-family: monospace;">{_escape(metric_name)}: {metric_value:.2f}% (Threshold: &gt;= {threshold_value:.2f}%)</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Isolation Forest Score:</td>
              <td style="padding: 6px 0; color: #f59e0b; font-weight: 700; font-family: monospace;">{iso_score:.4f} (Anomaly Boundary: &gt;= 0.60)</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">LSTM Reconstruction Error:</td>
              <td style="padding: 6px 0; color: #ec4899; font-weight: 700; font-family: monospace;">{lstm_score:.4f} MSE (Optimal Threshold: {lstm_threshold:.4f})</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">AI Diagnostic Summary:</td>
              <td style="padding: 6px 0; color: #cbd5e1;">{_escape(explanation)}</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Detection Timestamp:</td>
              <td style="padding: 6px 0; color: #94a3b8; font-family: monospace;">{_escape(ts_str)}</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Incident Reference:</td>
              <td style="padding: 6px 0; color: #64748b; font-family: monospace;">#{alert_id}</td>
            </tr>
          </table>
          <p style="margin: 16px 0 0 0; color: #94a3b8;">
            Please access the SRE Command Center to perform root-cause analysis, review mitigation recommendations, and acknowledge this incident.
          </p>
        """,
        action_url=dashboard_url,
        action_label="Open SRE Command Center",
    )

    text_content = f"""CLOUDOPS INTEL - CRITICAL CORRELATED INCIDENT
SEVERITY: CRITICAL (3-LAYER CONSENSUS)

Host: {host_name} ({ip_address or 'N/A'})
Environment: {environment.upper()}
Breached Metric: {metric_name} = {metric_value:.2f}% (Threshold: >= {threshold_value:.2f}%)
Isolation Forest Score: {iso_score:.4f} (Threshold: >= 0.60)
LSTM Reconstruction Error: {lstm_score:.4f} MSE (Threshold: {lstm_threshold:.4f})
AI Diagnostic Summary: {explanation}
Timestamp: {ts_str}
Incident ID: #{alert_id}

Investigate and remediate at:
{dashboard_url}
"""
    return subject, html_content, text_content

