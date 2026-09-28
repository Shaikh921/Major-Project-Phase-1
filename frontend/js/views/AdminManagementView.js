/**
 * Super Admin Management View - CloudOps Intel SRE Command Center.
 * 
 * Provides Super Admin control over:
 * 1. Admin registration request review, email verification tracking, and approval/rejection.
 * 2. Administrator directory, role visibility, active session revocation.
 * 3. Administrative account lifecycle (enable, disable, force password reset, safe soft-deletion).
 * 4. Summary metrics and security guardrails.
 */

import { api } from "../api.js?v=3.3.0";
import { authManager } from "../auth.js?v=3.3.0";
import { escapeHtml, formatTimestamp } from "../sanitizer.js?v=3.3.0";
import { renderIcon } from "../components/Icons.js?v=3.3.0";
import { openModal, closeModal } from "../components/Modal.js?v=3.3.0";

let currentTab = "requests"; // "requests" | "directory"

export async function renderAdminManagementView(container) {
  if (!authManager.isSuperAdmin()) {
    container.innerHTML = `
      <div class="state-container">
        <div class="state-icon text-critical">${renderIcon("shield-alert", { size: "xl" })}</div>
        <div class="state-title">Access Denied</div>
        <div class="state-desc">Super Administrator privileges are strictly required to access the Admin Management Panel.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="state-container">
      <div class="state-icon">${renderIcon("loader", { size: "xl", className: "icon-spin" })}</div>
      <div class="state-title">Loading Super Admin Control Plane...</div>
    </div>
  `;

  try {
    const [stats, requests, users] = await Promise.all([
      api.getAdminStats(),
      api.getAdminRequests(),
      api.getAdminUsers()
    ]);

    renderDashboard(container, stats, requests, users);
  } catch (err) {
    container.innerHTML = `
      <div class="state-container">
        <div class="state-icon text-critical">${renderIcon("triangle-alert", { size: "xl" })}</div>
        <div class="state-title">Failed to load Super Admin data</div>
        <div class="state-desc">${escapeHtml(err.message || "An unexpected error occurred.")}</div>
        <div style="margin-top: 16px;">
          <button class="btn btn-sm" id="admin-retry-btn">
            ${renderIcon("refresh-cw", { size: "sm" })} Retry
          </button>
        </div>
      </div>
    `;
    const retryBtn = document.getElementById("admin-retry-btn");
    if (retryBtn) retryBtn.onclick = () => renderAdminManagementView(container);
  }
}

function renderDashboard(container, stats, requests, users) {
  const pendingRequestsCount = requests.filter(r => r.status === "PENDING_SUPER_ADMIN_APPROVAL").length;

  container.innerHTML = `
    <div class="view-header">
      <div class="view-title-group">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="color: var(--accent-amber); display: inline-flex;">
            ${renderIcon("shield-check", { size: "lg" })}
          </span>
          <h1 style="margin: 0;">Super Admin Management Panel</h1>
        </div>
        <p>Authoritative identity lifecycle, pending applicant approvals, administrative directory, and security session governance.</p>
      </div>
      <div style="display: flex; gap: 8px;">
        <button class="btn btn-sm" id="admin-test-smtp-btn" title="Send a diagnostic verification email">
          ${renderIcon("send", { size: "sm" })} Test Email / SMTP
        </button>
        <button class="btn btn-sm" id="admin-panel-refresh-btn">
          ${renderIcon("refresh-cw", { size: "sm" })} Refresh
        </button>
      </div>
    </div>

    <!-- Summary KPI Cards -->
    <div class="kpi-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px;">
      <div class="card kpi-card">
        <div class="kpi-header">
          <span class="kpi-title">Total Administrators</span>
          <span class="kpi-icon">${renderIcon("users", { size: "sm" })}</span>
        </div>
        <div class="kpi-value">${stats.total_admins}</div>
        <div class="kpi-subtitle text-muted">Super Admins & Admins</div>
      </div>

      <div class="card kpi-card">
        <div class="kpi-header">
          <span class="kpi-title">Active Administrators</span>
          <span class="kpi-icon text-healthy">${renderIcon("user-check", { size: "sm" })}</span>
        </div>
        <div class="kpi-value text-healthy">${stats.active_admins}</div>
        <div class="kpi-subtitle text-muted">Authorized to sign in</div>
      </div>

      <div class="card kpi-card">
        <div class="kpi-header">
          <span class="kpi-title">Pending Requests</span>
          <span class="kpi-icon text-warning">${renderIcon("user-plus", { size: "sm" })}</span>
        </div>
        <div class="kpi-value text-warning">${stats.pending_requests}</div>
        <div class="kpi-subtitle text-muted">${pendingRequestsCount} verified awaiting review</div>
      </div>

      <div class="card kpi-card">
        <div class="kpi-header">
          <span class="kpi-title">Disabled Accounts</span>
          <span class="kpi-icon text-critical">${renderIcon("user-x", { size: "sm" })}</span>
        </div>
        <div class="kpi-value text-critical">${stats.disabled_admins}</div>
        <div class="kpi-subtitle text-muted">Deactivated or locked</div>
      </div>
    </div>

    <!-- Tab Navigation -->
    <div class="tab-bar" style="display: flex; gap: 8px; border-bottom: 1px solid var(--border-subtle); margin-bottom: 16px;">
      <button class="tab-btn ${currentTab === "requests" ? "active" : ""}" id="tab-requests-btn" style="display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: none; border: none; border-bottom: 2px solid ${currentTab === "requests" ? "var(--primary)" : "transparent"}; color: ${currentTab === "requests" ? "var(--text-primary)" : "var(--text-muted)"}; cursor: pointer; font-weight: 600; font-size: 13px;">
        ${renderIcon("user-plus", { size: "sm" })}
        Pending Registration Requests
        ${pendingRequestsCount > 0 ? `<span class="badge badge-critical" style="font-size: 10px; margin-left: 4px;">${pendingRequestsCount}</span>` : ""}
      </button>
      <button class="tab-btn ${currentTab === "directory" ? "active" : ""}" id="tab-directory-btn" style="display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: none; border: none; border-bottom: 2px solid ${currentTab === "directory" ? "var(--primary)" : "transparent"}; color: ${currentTab === "directory" ? "var(--text-primary)" : "var(--text-muted)"}; cursor: pointer; font-weight: 600; font-size: 13px;">
        ${renderIcon("users", { size: "sm" })}
        Administrator Directory (${users.length})
      </button>
    </div>

    <!-- Tab Content Area -->
    <div id="admin-tab-content">
      ${currentTab === "requests" ? renderRequestsTab(requests) : renderDirectoryTab(users)}
    </div>
  `;

  // Attach event handlers
  const refreshBtn = document.getElementById("admin-panel-refresh-btn");
  if (refreshBtn) refreshBtn.onclick = () => renderAdminManagementView(container);

  const tabRequestsBtn = document.getElementById("tab-requests-btn");
  if (tabRequestsBtn) {
    tabRequestsBtn.onclick = () => {
      currentTab = "requests";
      renderDashboard(container, stats, requests, users);
    };
  }

  const tabDirectoryBtn = document.getElementById("tab-directory-btn");
  if (tabDirectoryBtn) {
    tabDirectoryBtn.onclick = () => {
      currentTab = "directory";
      renderDashboard(container, stats, requests, users);
    };
  }

  attachTableActionListeners(container);
}

function renderRequestsTab(requests) {
  return `
    <div class="panel">
      <div class="panel-header" style="display: flex; justify-content: space-between; align-items: center;">
        <span class="panel-title">${renderIcon("clipboard-list", { size: "sm" })} Admin Registration Request Queue (${requests.length})</span>
        <span class="text-muted mono" style="font-size: 11px;">Requires Email Verification Before Super Admin Approval</span>
      </div>

      <div class="table-container">
        <table class="ops-table">
          <thead>
            <tr>
              <th>Applicant Name</th>
              <th>Email Address</th>
              <th>Organization</th>
              <th>Reason for Access</th>
              <th>Email Verified</th>
              <th>Requested Date</th>
              <th>Status</th>
              <th style="text-align: right;">Review Actions</th>
            </tr>
          </thead>
          <tbody>
            ${requests.length === 0 ? `
              <tr><td colspan="8" class="text-muted" style="text-align: center; padding: 24px;">No administrator registration requests recorded.</td></tr>
            ` : requests.map(r => {
              const isPendingApproval = r.status === "PENDING_SUPER_ADMIN_APPROVAL";
              const isUnverified = r.status === "EMAIL_UNVERIFIED";
              const isApproved = r.status === "APPROVED" || r.status === "ACTIVE";
              const isRejected = r.status === "REJECTED";

              let statusBadge = `<span class="badge badge-info">${escapeHtml(r.status)}</span>`;
              if (isPendingApproval) statusBadge = `<span class="badge badge-warning">AWAITING APPROVAL</span>`;
              else if (isUnverified) statusBadge = `<span class="badge badge-info" style="opacity: 0.75;">EMAIL UNVERIFIED</span>`;
              else if (isApproved) statusBadge = `<span class="badge badge-healthy">${escapeHtml(r.status)}</span>`;
              else if (isRejected) statusBadge = `<span class="badge badge-critical">REJECTED</span>`;

              return `
                <tr data-request-id="${escapeHtml(r.id)}">
                  <td style="font-weight: 600;">${escapeHtml(r.full_name)}</td>
                  <td class="mono">${escapeHtml(r.email)}</td>
                  <td>${escapeHtml(r.organization || "—")}</td>
                  <td style="max-width: 240px; font-size: 12px;" title="${escapeHtml(r.reason)}">${escapeHtml(r.reason)}</td>
                  <td>
                    ${r.email_verified ? `
                      <span class="badge badge-healthy" style="display: inline-flex; align-items: center; gap: 4px;">
                        ${renderIcon("check", { size: "xs" })} Verified
                      </span>
                    ` : `
                      <span class="badge badge-info" style="display: inline-flex; align-items: center; gap: 4px; opacity: 0.8;">
                        ${renderIcon("circle-alert", { size: "xs" })} Pending
                      </span>
                    `}
                  </td>
                  <td class="mono text-muted" style="font-size: 11px;">${formatTimestamp(r.requested_at)}</td>
                  <td>${statusBadge}</td>
                  <td style="text-align: right;">
                    ${isPendingApproval ? `
                      <div style="display: inline-flex; gap: 6px;">
                        <button class="btn btn-sm btn-primary request-approve-btn" data-id="${escapeHtml(r.id)}" data-name="${escapeHtml(r.full_name)}" data-email="${escapeHtml(r.email)}" style="font-size: 11.5px; padding: 3px 8px;">
                          ${renderIcon("check", { size: "xs" })} Approve
                        </button>
                        <button class="btn btn-sm request-reject-btn" data-id="${escapeHtml(r.id)}" data-name="${escapeHtml(r.full_name)}" data-email="${escapeHtml(r.email)}" style="font-size: 11.5px; padding: 3px 8px; color: var(--critical);">
                          ${renderIcon("x", { size: "xs" })} Reject
                        </button>
                      </div>
                    ` : (isUnverified ? `
                      <span class="text-muted mono" style="font-size: 11px;">Awaiting User Email</span>
                    ` : `
                      <span class="text-muted mono" style="font-size: 11px;">Processed</span>
                    `)}
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderDirectoryTab(users) {
  return `
    <div class="panel">
      <div class="panel-header" style="display: flex; justify-content: space-between; align-items: center;">
        <span class="panel-title">${renderIcon("users", { size: "sm" })} Administrator Directory & Security Lifecycle (${users.length})</span>
        <span class="text-muted mono" style="font-size: 11px;">Authoritative RBAC Directory</span>
      </div>

      <div class="table-container">
        <table class="ops-table">
          <thead>
            <tr>
              <th>Account / Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Email Verified</th>
              <th>Created Date</th>
              <th>Last Sign In</th>
              <th>Active Sessions</th>
              <th style="text-align: right;">Administrative Actions</th>
            </tr>
          </thead>
          <tbody>
            ${users.length === 0 ? `
              <tr><td colspan="8" class="text-muted" style="text-align: center; padding: 24px;">No administrator accounts found.</td></tr>
            ` : users.map(u => {
              const isSuper = u.role === "SUPER_ADMIN";
              const isActive = u.is_active;

              const roleBadge = isSuper
                ? `<span class="badge badge-warning" style="font-weight: 700; border: 1px solid var(--accent-amber);">${escapeHtml(u.role)}</span>`
                : `<span class="badge badge-critical">${escapeHtml(u.role)}</span>`;

              const statusBadge = isActive
                ? `<span class="badge badge-healthy">ACTIVE</span>`
                : `<span class="badge badge-critical">DISABLED</span>`;

              return `
                <tr data-user-id="${escapeHtml(u.id)}">
                  <td class="mono font-weight-bold">${escapeHtml(u.email)}</td>
                  <td>${roleBadge}</td>
                  <td>${statusBadge}</td>
                  <td>
                    ${u.is_verified ? `
                      <span class="badge badge-healthy" style="display: inline-flex; align-items: center; gap: 4px;">
                        ${renderIcon("check", { size: "xs" })} Verified
                      </span>
                    ` : `
                      <span class="badge badge-critical" style="display: inline-flex; align-items: center; gap: 4px;">
                        ${renderIcon("circle-alert", { size: "xs" })} Unverified
                      </span>
                    `}
                  </td>
                  <td class="mono text-muted" style="font-size: 11px;">${formatTimestamp(u.created_at)}</td>
                  <td class="mono text-muted" style="font-size: 11px;">${u.last_login_at ? formatTimestamp(u.last_login_at) : "Never"}</td>
                  <td class="mono" style="font-size: 12px;">
                    <span class="badge badge-info">${u.active_sessions_count || 0} session(s)</span>
                  </td>
                  <td style="text-align: right;">
                    <div style="display: inline-flex; gap: 6px; justify-content: flex-end;">
                      ${isActive ? `
                        <button class="btn btn-sm btn-action-disable" data-id="${escapeHtml(u.id)}" data-email="${escapeHtml(u.email)}" data-role="${escapeHtml(u.role)}" title="Disable Account" style="font-size: 11px; padding: 2px 7px;">
                          ${renderIcon("user-x", { size: "xs" })} Disable
                        </button>
                      ` : `
                        <button class="btn btn-sm btn-action-enable" data-id="${escapeHtml(u.id)}" data-email="${escapeHtml(u.email)}" data-role="${escapeHtml(u.role)}" title="Enable Account" style="font-size: 11px; padding: 2px 7px; color: var(--healthy);">
                          ${renderIcon("user-check", { size: "xs" })} Enable
                        </button>
                      `}
                      <button class="btn btn-sm btn-action-revoke" data-id="${escapeHtml(u.id)}" data-email="${escapeHtml(u.email)}" title="Revoke Active Sessions" style="font-size: 11px; padding: 2px 7px;">
                        ${renderIcon("log-out", { size: "xs" })} Revoke Sessions
                      </button>
                      <button class="btn btn-sm btn-action-reset" data-id="${escapeHtml(u.id)}" data-email="${escapeHtml(u.email)}" title="Force Password Reset" style="font-size: 11px; padding: 2px 7px;">
                        ${renderIcon("key", { size: "xs" })} Force Reset
                      </button>
                      ${!isSuper ? `
                        <button class="btn btn-sm btn-action-delete" data-id="${escapeHtml(u.id)}" data-email="${escapeHtml(u.email)}" data-role="${escapeHtml(u.role)}" title="Deactivate / Soft Delete" style="font-size: 11px; padding: 2px 7px; color: var(--critical);">
                          ${renderIcon("trash-2", { size: "xs" })}
                        </button>
                      ` : `
                        <span class="badge badge-info" style="font-size: 9.5px; opacity: 0.65;" title="Root Super Admin Protected">PROTECTED</span>
                      `}
                    </div>
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function attachTableActionListeners(container) {
  // 1. Approve Request
  container.querySelectorAll(".request-approve-btn").forEach(btn => {
    btn.onclick = () => {
      const id = btn.getAttribute("data-id");
      const name = btn.getAttribute("data-name");
      const email = btn.getAttribute("data-email");

      openModal(
        "Approve Administrator Request",
        `
          <p>Are you sure you want to approve administrator access for <strong>${escapeHtml(name)}</strong> (<code>${escapeHtml(email)}</code>)?</p>
          <div style="padding: 10px 12px; background: rgba(59, 130, 246, 0.08); border-left: 3px solid var(--accent-blue); border-radius: 4px; margin-top: 12px; font-size: 12px;">
            <strong>Workflow Security:</strong> An inactive <code>ADMIN</code> account will be created. A single-use, cryptographically secure activation token will be generated and dispatched to the development email outbox for account setup.
          </div>
        `,
        `
          <button class="btn btn-sm" id="modal-cancel-btn">Cancel</button>
          <button class="btn btn-sm btn-primary" id="modal-confirm-approve-btn">
            ${renderIcon("check", { size: "xs" })} Confirm Approval
          </button>
        `
      );

      const cancelBtn = document.getElementById("modal-cancel-btn");
      if (cancelBtn) cancelBtn.onclick = closeModal;

      const confirmBtn = document.getElementById("modal-confirm-approve-btn");
      if (confirmBtn) {
        confirmBtn.onclick = async () => {
          confirmBtn.disabled = true;
          confirmBtn.innerText = "Processing...";
          try {
            await api.approveAdminRequest(id);
            closeModal();
            renderAdminManagementView(container);
          } catch (err) {
            alert(`Approval failed: ${err.message}`);
            confirmBtn.disabled = false;
            confirmBtn.innerText = "Confirm Approval";
          }
        };
      }
    };
  });

  // 2. Reject Request
  container.querySelectorAll(".request-reject-btn").forEach(btn => {
    btn.onclick = () => {
      const id = btn.getAttribute("data-id");
      const name = btn.getAttribute("data-name");
      const email = btn.getAttribute("data-email");

      openModal(
        "Reject Administrator Request",
        `
          <p>Are you sure you want to reject the administrator application for <strong>${escapeHtml(name)}</strong> (<code>${escapeHtml(email)}</code>)?</p>
          <div style="margin-top: 12px;">
            <label class="form-label" for="reject-reason-input">Rejection Reason (Optional)</label>
            <input type="text" id="reject-reason-input" class="form-control" placeholder="e.g., Insufficient authorization credentials." maxlength="255">
          </div>
        `,
        `
          <button class="btn btn-sm" id="modal-cancel-btn">Cancel</button>
          <button class="btn btn-sm btn-critical" id="modal-confirm-reject-btn">
            ${renderIcon("x", { size: "xs" })} Confirm Rejection
          </button>
        `
      );

      const cancelBtn = document.getElementById("modal-cancel-btn");
      if (cancelBtn) cancelBtn.onclick = closeModal;

      const confirmBtn = document.getElementById("modal-confirm-reject-btn");
      if (confirmBtn) {
        confirmBtn.onclick = async () => {
          const reason = document.getElementById("reject-reason-input")?.value || "";
          confirmBtn.disabled = true;
          confirmBtn.innerText = "Processing...";
          try {
            await api.rejectAdminRequest(id, reason);
            closeModal();
            renderAdminManagementView(container);
          } catch (err) {
            alert(`Rejection failed: ${err.message}`);
            confirmBtn.disabled = false;
            confirmBtn.innerText = "Confirm Rejection";
          }
        };
      }
    };
  });

  // 3. Disable Administrator
  container.querySelectorAll(".btn-action-disable").forEach(btn => {
    btn.onclick = () => {
      const id = btn.getAttribute("data-id");
      const email = btn.getAttribute("data-email");

      openModal(
        "Disable Administrator Account",
        `
          <p>Disable administrator <code>${escapeHtml(email)}</code>?</p>
          <p class="text-muted" style="font-size: 12px; margin-top: 8px;">
            This will immediately revoke active refresh sessions and prevent any future sign-in attempts until explicitly re-enabled.
          </p>
        `,
        `
          <button class="btn btn-sm" id="modal-cancel-btn">Cancel</button>
          <button class="btn btn-sm btn-critical" id="modal-confirm-disable-btn">
            ${renderIcon("user-x", { size: "xs" })} Disable Administrator
          </button>
        `
      );

      const cancelBtn = document.getElementById("modal-cancel-btn");
      if (cancelBtn) cancelBtn.onclick = closeModal;

      const confirmBtn = document.getElementById("modal-confirm-disable-btn");
      if (confirmBtn) {
        confirmBtn.onclick = async () => {
          confirmBtn.disabled = true;
          try {
            await api.disableAdminUser(id);
            closeModal();
            renderAdminManagementView(container);
          } catch (err) {
            alert(`Disable failed: ${err.message}`);
            confirmBtn.disabled = false;
          }
        };
      }
    };
  });

  // 4. Enable Administrator
  container.querySelectorAll(".btn-action-enable").forEach(btn => {
    btn.onclick = () => {
      const id = btn.getAttribute("data-id");
      const email = btn.getAttribute("data-email");

      openModal(
        "Enable Administrator Account",
        `
          <p>Re-enable administrator <code>${escapeHtml(email)}</code>?</p>
          <p class="text-muted" style="font-size: 12px; margin-top: 8px;">
            This will restore operational access and allow the administrator to sign in.
          </p>
        `,
        `
          <button class="btn btn-sm" id="modal-cancel-btn">Cancel</button>
          <button class="btn btn-sm btn-primary" id="modal-confirm-enable-btn">
            ${renderIcon("user-check", { size: "xs" })} Enable Administrator
          </button>
        `
      );

      const cancelBtn = document.getElementById("modal-cancel-btn");
      if (cancelBtn) cancelBtn.onclick = closeModal;

      const confirmBtn = document.getElementById("modal-confirm-enable-btn");
      if (confirmBtn) {
        confirmBtn.onclick = async () => {
          confirmBtn.disabled = true;
          try {
            await api.enableAdminUser(id);
            closeModal();
            renderAdminManagementView(container);
          } catch (err) {
            alert(`Enable failed: ${err.message}`);
            confirmBtn.disabled = false;
          }
        };
      }
    };
  });

  // 5. Revoke Sessions
  container.querySelectorAll(".btn-action-revoke").forEach(btn => {
    btn.onclick = () => {
      const id = btn.getAttribute("data-id");
      const email = btn.getAttribute("data-email");

      openModal(
        "Revoke Administrator Sessions",
        `
          <p>Revoke all active sessions for <code>${escapeHtml(email)}</code>?</p>
          <p class="text-muted" style="font-size: 12px; margin-top: 8px;">
            All active refresh tokens and server sessions will be immediately invalidated. The administrator will be required to re-authenticate.
          </p>
        `,
        `
          <button class="btn btn-sm" id="modal-cancel-btn">Cancel</button>
          <button class="btn btn-sm btn-warning" id="modal-confirm-revoke-btn">
            ${renderIcon("log-out", { size: "xs" })} Revoke All Sessions
          </button>
        `
      );

      const cancelBtn = document.getElementById("modal-cancel-btn");
      if (cancelBtn) cancelBtn.onclick = closeModal;

      const confirmBtn = document.getElementById("modal-confirm-revoke-btn");
      if (confirmBtn) {
        confirmBtn.onclick = async () => {
          confirmBtn.disabled = true;
          try {
            await api.revokeAdminUserSessions(id);
            closeModal();
            renderAdminManagementView(container);
          } catch (err) {
            alert(`Session revocation failed: ${err.message}`);
            confirmBtn.disabled = false;
          }
        };
      }
    };
  });

  // 6. Force Password Reset
  container.querySelectorAll(".btn-action-reset").forEach(btn => {
    btn.onclick = () => {
      const id = btn.getAttribute("data-id");
      const email = btn.getAttribute("data-email");

      openModal(
        "Force Password Reset",
        `
          <p>Force password reset for <code>${escapeHtml(email)}</code>?</p>
          <p class="text-muted" style="font-size: 12px; margin-top: 8px;">
            A secure single-use password reset token will be generated, hashed, and dispatched via the development email service.
          </p>
        `,
        `
          <button class="btn btn-sm" id="modal-cancel-btn">Cancel</button>
          <button class="btn btn-sm btn-primary" id="modal-confirm-reset-btn">
            ${renderIcon("key", { size: "xs" })} Dispatch Reset Link
          </button>
        `
      );

      const cancelBtn = document.getElementById("modal-cancel-btn");
      if (cancelBtn) cancelBtn.onclick = closeModal;

      const confirmBtn = document.getElementById("modal-confirm-reset-btn");
      if (confirmBtn) {
        confirmBtn.onclick = async () => {
          confirmBtn.disabled = true;
          try {
            await api.forceAdminPasswordReset(id);
            closeModal();
            renderAdminManagementView(container);
          } catch (err) {
            alert(`Password reset dispatch failed: ${err.message}`);
            confirmBtn.disabled = false;
          }
        };
      }
    };
  });

  // 7. Deactivate / Soft Delete
  container.querySelectorAll(".btn-action-delete").forEach(btn => {
    btn.onclick = () => {
      const id = btn.getAttribute("data-id");
      const email = btn.getAttribute("data-email");

      openModal(
        "Deactivate Administrator",
        `
          <p>Deactivate administrator <code>${escapeHtml(email)}</code>?</p>
          <div style="padding: 10px 12px; background: rgba(239, 68, 68, 0.08); border-left: 3px solid var(--critical); border-radius: 4px; margin-top: 12px; font-size: 12px;">
            <strong>Safe Soft-Deletion:</strong> The account will be deactivated (<code>is_active = False</code>) and all active sessions revoked. The user record and historical audit logs will be permanently preserved in the database.
          </div>
        `,
        `
          <button class="btn btn-sm" id="modal-cancel-btn">Cancel</button>
          <button class="btn btn-sm btn-critical" id="modal-confirm-delete-btn">
            ${renderIcon("trash-2", { size: "xs" })} Deactivate Account
          </button>
        `
      );

      const cancelBtn = document.getElementById("modal-cancel-btn");
      if (cancelBtn) cancelBtn.onclick = closeModal;

      const confirmBtn = document.getElementById("modal-confirm-delete-btn");
      if (confirmBtn) {
        confirmBtn.onclick = async () => {
          confirmBtn.disabled = true;
          try {
            await api.softDeleteAdminUser(id);
            closeModal();
            renderAdminManagementView(container);
          } catch (err) {
            alert(`Deactivation failed: ${err.message}`);
            confirmBtn.disabled = false;
          }
        };
      }
    };
  });

  // 8. SMTP Diagnostic Test Modal
  const testSmtpBtn = container.querySelector("#admin-test-smtp-btn");
  if (testSmtpBtn) {
    testSmtpBtn.onclick = () => {
      const currentEmail = authManager.currentUser?.email || "";
      openModal(
        "SMTP Relay Diagnostic Test",
        `
          <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 14px;">
            Send a diagnostic verification email to validate SMTP delivery configuration, TLS/SSL connectivity, and relay response times.
          </p>
          <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px;">
            <label style="font-size: 11.5px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">
              Recipient Email Address
            </label>
            <input type="email" id="smtp-test-recipient-input" class="input-control" value="${escapeHtml(currentEmail)}" placeholder="admin@example.com" style="width: 100%; padding: 8px 12px; font-size: 13px;">
          </div>
          <div id="smtp-test-result-box" style="display: none; padding: 12px; border-radius: 4px; font-size: 12px; margin-top: 12px;"></div>
        `,
        `
          <button class="btn btn-sm" id="modal-cancel-btn">Close</button>
          <button class="btn btn-sm btn-primary" id="modal-confirm-smtp-test-btn">
            ${renderIcon("send", { size: "xs" })} Dispatch Test Email
          </button>
        `
      );

      const cancelBtn = document.getElementById("modal-cancel-btn");
      if (cancelBtn) cancelBtn.onclick = closeModal;

      const confirmBtn = document.getElementById("modal-confirm-smtp-test-btn");
      const recipientInput = document.getElementById("smtp-test-recipient-input");
      const resultBox = document.getElementById("smtp-test-result-box");

      if (confirmBtn && recipientInput && resultBox) {
        confirmBtn.onclick = async () => {
          const recipient = recipientInput.value.trim();
          if (!recipient) {
            resultBox.style.display = "block";
            resultBox.style.background = "rgba(239, 68, 68, 0.1)";
            resultBox.style.border = "1px solid var(--critical)";
            resultBox.style.color = "var(--critical)";
            resultBox.innerHTML = "Please enter a valid recipient email address.";
            return;
          }

          confirmBtn.disabled = true;
          recipientInput.disabled = true;
          confirmBtn.innerHTML = `${renderIcon("loader", { size: "xs", className: "icon-spin" })} Dispatching...`;
          resultBox.style.display = "none";

          try {
            const res = await api.sendSmtpTestEmail(recipient);
            resultBox.style.display = "block";
            if (res.success) {
              resultBox.style.background = "rgba(16, 185, 129, 0.1)";
              resultBox.style.border = "1px solid var(--healthy)";
              resultBox.style.color = "var(--healthy)";
              resultBox.innerHTML = `<strong>Status (${escapeHtml(res.mode)}):</strong> ${escapeHtml(res.message)}`;
            } else {
              resultBox.style.background = "rgba(239, 68, 68, 0.1)";
              resultBox.style.border = "1px solid var(--critical)";
              resultBox.style.color = "var(--critical)";
              resultBox.innerHTML = `<strong>Delivery Failed:</strong> ${escapeHtml(res.message)}`;
            }
          } catch (err) {
            resultBox.style.display = "block";
            resultBox.style.background = "rgba(239, 68, 68, 0.1)";
            resultBox.style.border = "1px solid var(--critical)";
            resultBox.style.color = "var(--critical)";
            resultBox.innerHTML = `<strong>Error:</strong> ${escapeHtml(err.message || "Failed to execute SMTP test.")}`;
          } finally {
            confirmBtn.disabled = false;
            recipientInput.disabled = false;
            confirmBtn.innerHTML = `${renderIcon("send", { size: "xs" })} Dispatch Test Email`;
          }
        };
      }
    };
  }
}
