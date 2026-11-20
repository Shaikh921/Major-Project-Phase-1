/**
 * Super Admin Management View - CloudOps Intel SRE Command Center.
 * 
 * Provides Super Admin control over:
 * 1. Admin registration request review, email verification tracking, and approval/rejection.
 * 2. Administrator directory, role visibility, active session revocation.
 * 3. Administrative account lifecycle (enable, disable, force password reset, safe soft-deletion).
 * 4. Summary metrics and security guardrails.
 */

import { api } from "../api.js";
import { authManager } from "../auth.js";
import { escapeHtml, formatTimestamp } from "../sanitizer.js";
import { renderIcon } from "../components/Icons.js";
import { openModal, closeModal } from "../components/Modal.js";

let currentTab = "requests"; // "requests" | "directory" | "assignments" | "explorer"
let cachedExplorerStatus = { enabled: false };

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
    const [stats, requests, users, explorerStatus] = await Promise.all([
      api.getAdminStats(),
      api.getAdminRequests(),
      api.getAdminUsers(),
      api.getDatabaseExplorerStatus().catch(() => ({ enabled: false }))
    ]);

    cachedExplorerStatus = explorerStatus || { enabled: false };
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
      <button class="tab-btn ${currentTab === "assignments" ? "active" : ""}" id="tab-assignments-btn" style="display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: none; border: none; border-bottom: 2px solid ${currentTab === "assignments" ? "var(--primary)" : "transparent"}; color: ${currentTab === "assignments" ? "var(--text-primary)" : "var(--text-muted)"}; cursor: pointer; font-weight: 600; font-size: 13px;">
        ${renderIcon("key", { size: "sm" })}
        Resource Assignments (Hybrid RBAC)
      </button>
      ${cachedExplorerStatus.enabled ? `
      <button class="tab-btn ${currentTab === "explorer" ? "active" : ""}" id="tab-explorer-btn" style="display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: none; border: none; border-bottom: 2px solid ${currentTab === "explorer" ? "var(--primary)" : "transparent"}; color: ${currentTab === "explorer" ? "var(--text-primary)" : "var(--text-muted)"}; cursor: pointer; font-weight: 600; font-size: 13px;">
        ${renderIcon("database", { size: "sm" })}
        Database &amp; Storage Explorer
        <span class="badge badge-info" style="font-size: 9.5px; margin-left: 4px; padding: 2px 6px;">READ-ONLY</span>
      </button>
      ` : ""}
    </div>

    <!-- Tab Content Area -->
    <div id="admin-tab-content">
      ${currentTab === "requests" ? renderRequestsTab(requests) :
      (currentTab === "directory" ? renderDirectoryTab(users) :
        (currentTab === "assignments" ? renderAssignmentsTabPlaceholder() :
          renderExplorerTabPlaceholder()))}
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

  const tabAssignmentsBtn = document.getElementById("tab-assignments-btn");
  if (tabAssignmentsBtn) {
    tabAssignmentsBtn.onclick = () => {
      currentTab = "assignments";
      renderDashboard(container, stats, requests, users);
      loadAndRenderAssignments(users);
    };
  }

  const tabExplorerBtn = document.getElementById("tab-explorer-btn");
  if (tabExplorerBtn) {
    tabExplorerBtn.onclick = () => {
      currentTab = "explorer";
      renderDashboard(container, stats, requests, users);
      loadAndRenderExplorer();
    };
  }

  if (currentTab === "assignments") {
    loadAndRenderAssignments(users);
  } else if (currentTab === "explorer") {
    loadAndRenderExplorer();
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


function renderAssignmentsTabPlaceholder() {
  return `
    <div id="assignments-mount-point" style="padding: 10px 0;">
      <div class="state-container" style="padding: 30px;">
        <div class="state-icon">${renderIcon("loader", { size: "lg", className: "icon-spin" })}</div>
        <div class="state-title">Loading Hybrid RBAC Assignments...</div>
      </div>
    </div>
  `;
}

async function loadAndRenderAssignments(users) {
  const mount = document.getElementById("assignments-mount-point");
  if (!mount) return;

  try {
    const [assignments, hosts] = await Promise.all([
      api.getAssignments(false),
      api.getHosts(),
    ]);

    const activeAssignments = assignments.filter(a => a.status === "ACTIVE");

    mount.innerHTML = `
      <!-- Assignment Creation Card -->
      <div class="card" style="margin-bottom: 20px; padding: 16px;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
          <span style="color: var(--primary); display: inline-flex;">${renderIcon("key", { size: "sm" })}</span>
          <h3 style="margin: 0; font-size: 14px; font-weight: 600;">Grant Resource Scope Assignment</h3>
        </div>
        <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 16px;">
          Assign users explicit access to environment tiers (e.g. production, staging) or individual hosts under the Phase 9A.1 Hybrid RBAC policy.
        </p>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; align-items: end;">
          <div>
            <label style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">Target User</label>
            <select id="assign-user-select" class="select-control" style="width: 100%;">
              ${users.map(u => `<option value="${u.id}">${escapeHtml(u.email)} (${escapeHtml(u.role)})</option>`).join("")}
            </select>
          </div>

          <div>
            <label style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">Scope Type</label>
            <select id="assign-type-select" class="select-control" style="width: 100%;">
              <option value="ENVIRONMENT">Deployment Environment</option>
              <option value="HOST">Individual Host</option>
            </select>
          </div>

          <div id="assign-env-wrap">
            <label style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">Environment Tier</label>
            <select id="assign-env-select" class="select-control" style="width: 100%;">
              <option value="production">production</option>
              <option value="staging">staging</option>
              <option value="development">development</option>
              <option value="lab">lab</option>
              <option value="local">local</option>
            </select>
          </div>

          <div id="assign-host-wrap" style="display: none;">
            <label style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--text-muted);">Target Host</label>
            <select id="assign-host-select" class="select-control" style="width: 100%;">
              ${hosts.map(h => `<option value="${h.id}">${escapeHtml(h.hostname)} (${escapeHtml(h.environment || 'local')})</option>`).join("")}
            </select>
          </div>

          <div>
            <button class="btn btn-primary" id="btn-submit-assignment" style="width: 100%;">
              ${renderIcon("check", { size: "xs" })} Grant Assignment
            </button>
          </div>
        </div>
        <div id="assignment-alert-box" style="margin-top: 12px; display: none; padding: 8px 12px; border-radius: var(--radius-sm); font-size: 12px;"></div>
      </div>

      <!-- Active Assignments Table -->
      <div class="card" style="padding: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <h3 style="margin: 0; font-size: 14px; font-weight: 600;">Active Scoped Assignments (${activeAssignments.length})</h3>
        </div>

        ${activeAssignments.length === 0 ? `
          <div class="text-muted" style="text-align: center; padding: 24px; font-size: 13px;">
            No active environment or host assignments found. Super Admins retain global access.
          </div>
        ` : `
          <div class="table-container" style="overflow-x: auto;">
            <table class="table" style="width: 100%; border-collapse: collapse; font-size: 12px;">
              <thead>
                <tr style="border-bottom: 1px solid var(--border-subtle); text-align: left;">
                  <th style="padding: 8px;">User Email</th>
                  <th style="padding: 8px;">Scope Type</th>
                  <th style="padding: 8px;">Assigned Target</th>
                  <th style="padding: 8px;">Status</th>
                  <th style="padding: 8px;">Granted At</th>
                  <th style="padding: 8px; text-align: right;">Action</th>
                </tr>
              </thead>
              <tbody>
                ${activeAssignments.map(a => `
                  <tr style="border-bottom: 1px solid var(--border-subtle);">
                    <td style="padding: 8px;" class="mono">${escapeHtml(a.user_email || `User #${a.user_id}`)}</td>
                    <td style="padding: 8px;">
                      <span class="badge ${a.scope_type === 'ENVIRONMENT' ? 'badge-info' : 'badge-healthy'}">${escapeHtml(a.scope_type)}</span>
                    </td>
                    <td style="padding: 8px; font-weight: 600;">${escapeHtml(a.scope_value)}</td>
                    <td style="padding: 8px;"><span class="badge badge-healthy">ACTIVE</span></td>
                    <td style="padding: 8px;" class="mono text-muted">${formatTimestamp(a.created_at)}</td>
                    <td style="padding: 8px; text-align: right;">
                      <button class="btn btn-sm btn-revoke-assignment" data-id="${a.id}" data-type="${a.scope_type}" style="color: var(--critical);">
                        Revoke
                      </button>
                    </td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;

    // Type toggle
    const typeSelect = document.getElementById("assign-type-select");
    const envWrap = document.getElementById("assign-env-wrap");
    const hostWrap = document.getElementById("assign-host-wrap");
    if (typeSelect) {
      typeSelect.onchange = () => {
        if (typeSelect.value === "ENVIRONMENT") {
          envWrap.style.display = "block";
          hostWrap.style.display = "none";
        } else {
          envWrap.style.display = "none";
          hostWrap.style.display = "block";
        }
      };
    }

    // Submit handler
    const submitBtn = document.getElementById("btn-submit-assignment");
    const alertBox = document.getElementById("assignment-alert-box");
    if (submitBtn) {
      submitBtn.onclick = async () => {
        const userId = parseInt(document.getElementById("assign-user-select").value, 10);
        const scopeType = typeSelect.value;
        submitBtn.disabled = true;

        try {
          if (scopeType === "ENVIRONMENT") {
            const env = document.getElementById("assign-env-select").value;
            await api.assignEnvironment(userId, env);
          } else {
            const hostId = parseInt(document.getElementById("assign-host-select").value, 10);
            await api.assignHost(userId, hostId);
          }
          alertBox.style.display = "block";
          alertBox.style.background = "rgba(16, 185, 129, 0.1)";
          alertBox.style.color = "var(--healthy)";
          alertBox.textContent = "Assignment granted successfully!";
          setTimeout(() => loadAndRenderAssignments(users), 800);
        } catch (err) {
          alertBox.style.display = "block";
          alertBox.style.background = "rgba(239, 68, 68, 0.1)";
          alertBox.style.color = "var(--critical)";
          alertBox.textContent = err.message || "Failed to grant assignment.";
        } finally {
          submitBtn.disabled = false;
        }
      };
    }

    // Revoke handlers
    mount.querySelectorAll(".btn-revoke-assignment").forEach(btn => {
      btn.onclick = async () => {
        const id = parseInt(btn.getAttribute("data-id"), 10);
        const type = btn.getAttribute("data-type");
        if (!confirm(`Are you sure you want to revoke this ${type} assignment?`)) return;

        btn.disabled = true;
        try {
          if (type === "ENVIRONMENT") {
            await api.revokeEnvironmentAssignment(id);
          } else {
            await api.revokeHostAssignment(id);
          }
          loadAndRenderAssignments(users);
        } catch (err) {
          alert("Failed to revoke: " + err.message);
          btn.disabled = false;
        }
      };
    });

  } catch (err) {
    mount.innerHTML = `
      <div class="state-container" style="padding: 20px;">
        <div class="state-icon text-critical">${renderIcon("triangle-alert", { size: "lg" })}</div>
        <div class="state-title">Failed to load assignments</div>
        <div class="state-desc">${escapeHtml(err.message)}</div>
      </div>
    `;
  }
}


// ============================================================================
// FEATURE B: SECURE DATABASE & STORAGE EXPLORER COMPONENT
// ============================================================================

let explorerState = {
  overview: null,
  tables: [],
  selectedTableName: "hosts",
  activeView: "records", // "records" | "schema"
  searchQuery: "",
  tierFilter: "ALL",     // "ALL" | "TIER_1_OPERATIONAL" | "TIER_2_SANITIZED" | "TIER_3_ZERO_PREVIEW"
  page: 1,
  limit: 25,
  cursor: null,
  cursorHistory: [],
  currentRecords: null,
  currentSchema: null,
  isLoadingRecords: false,
  isLoadingSchema: false,
};

function renderExplorerTabPlaceholder() {
  return `
    <div id="explorer-mount-point" style="padding: 10px 0;">
      <div class="state-container" style="padding: 40px;">
        <div class="state-icon">${renderIcon("loader", { size: "xl", className: "icon-spin" })}</div>
        <div class="state-title" style="margin-top: 12px; font-weight: 600;">Loading Database & Storage Explorer...</div>
        <div class="state-desc">Inspecting authoritative SQLite storage engine under strict read-only guarantees...</div>
      </div>
    </div>
  `;
}

async function loadAndRenderExplorer() {
  const mount = document.getElementById("explorer-mount-point");
  if (!mount) return;

  try {
    if (!explorerState.overview || !explorerState.tables.length) {
      const [overview, tables] = await Promise.all([
        api.getDatabaseExplorerOverview(),
        api.getDatabaseExplorerTables()
      ]);
      explorerState.overview = overview;
      explorerState.tables = tables;

      if (!tables.find(t => t.name === explorerState.selectedTableName) && tables.length > 0) {
        explorerState.selectedTableName = tables[0].name;
      }
    }

    renderExplorerMainLayout(mount);
  } catch (err) {
    mount.innerHTML = `
      <div class="state-container" style="padding: 30px;">
        <div class="state-icon text-critical">${renderIcon("shield-alert", { size: "xl" })}</div>
        <div class="state-title">Database Explorer Error</div>
        <div class="state-desc">${escapeHtml(err.message || "Failed to initialize Database Explorer.")}</div>
        <div style="margin-top: 16px;">
          <button class="btn btn-sm" id="explorer-retry-init-btn">
            ${renderIcon("refresh-cw", { size: "sm" })} Retry
          </button>
        </div>
      </div>
    `;
    const retryBtn = document.getElementById("explorer-retry-init-btn");
    if (retryBtn) retryBtn.onclick = () => loadAndRenderExplorer();
  }
}

function renderExplorerMainLayout(mount) {
  const ov = explorerState.overview;
  const tables = explorerState.tables;

  mount.innerHTML = `
    <!-- Top Database Overview Strip -->
    <div class="card" style="margin-bottom: 20px; padding: 16px; background: var(--bg-surface);">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 12px;">
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="color: var(--primary); display: inline-flex;">${renderIcon("database", { size: "md" })}</span>
          <div>
            <h3 style="margin: 0; font-size: 15px; font-weight: 700; display: flex; align-items: center; gap: 8px;">
              SQLite Storage Engine Overview
              <span class="badge badge-healthy" style="font-size: 10px; display: inline-flex; align-items: center; gap: 4px;">
                ${renderIcon("check", { size: "xs" })} ONLINE
              </span>
              <span class="badge badge-info" style="font-size: 10px; display: inline-flex; align-items: center; gap: 4px;">
                ${renderIcon("lock", { size: "xs" })} READ-ONLY ENFORCED
              </span>
            </h3>
            <p style="margin: 2px 0 0 0; font-size: 12px; color: var(--text-muted);">
              File: <code class="mono">${escapeHtml(ov.database_file)}</code> &bull; Engine: ${escapeHtml(ov.sqlite_version)} (Journal Mode: <strong>${escapeHtml(ov.journal_mode.toUpperCase())}</strong>)
            </p>
          </div>
        </div>
        <button class="btn btn-sm" id="explorer-refresh-meta-btn" title="Refresh database storage metrics">
          ${renderIcon("refresh-cw", { size: "sm" })} Refresh Overview
        </button>
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px;">
        <div style="padding: 10px 14px; background: var(--bg-surface-elevated); border: 1px solid var(--border-default); border-radius: 6px;">
          <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Total Application Tables</div>
          <div style="font-size: 20px; font-weight: 700; margin-top: 4px;">${ov.total_tables} Tables</div>
          <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
            <span class="text-healthy">${ov.tier_breakdown.TIER_1_OPERATIONAL || 0} Oper.</span> &bull; 
            <span class="text-warning">${ov.tier_breakdown.TIER_2_SANITIZED || 0} Sanit.</span> &bull; 
            <span class="text-critical">${ov.tier_breakdown.TIER_3_ZERO_PREVIEW || 0} Vault</span>
          </div>
        </div>

        <div style="padding: 10px 14px; background: var(--bg-surface-elevated); border: 1px solid var(--border-default); border-radius: 6px;">
          <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Total Records Stored</div>
          <div style="font-size: 20px; font-weight: 700; margin-top: 4px;" class="mono">${ov.total_records.toLocaleString()}</div>
          <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Live across 23 tables</div>
        </div>

        <div style="padding: 10px 14px; background: var(--bg-surface-elevated); border: 1px solid var(--border-default); border-radius: 6px;">
          <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Physical Database Size</div>
          <div style="font-size: 20px; font-weight: 700; margin-top: 4px;">${ov.database_size_mb} MB</div>
          <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${ov.database_size_bytes.toLocaleString()} bytes</div>
        </div>

        <div style="padding: 10px 14px; background: var(--bg-surface-elevated); border: 1px solid var(--border-default); border-radius: 6px;">
          <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Concurrency & Safety</div>
          <div style="font-size: 20px; font-weight: 700; margin-top: 4px; color: var(--healthy);">Zero Ingestion Lock</div>
          <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">WAL multi-reader isolated</div>
        </div>
      </div>
    </div>

    <!-- Main Explorer Split Interface -->
    <div style="display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap;">
      
      <!-- Left Column: Table Navigator Sidebar -->
      <div class="card" style="width: 320px; flex-shrink: 0; padding: 14px; background: var(--bg-surface);">
        <div style="margin-bottom: 12px;">
          <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px;">
            Application Table Catalog (${tables.length})
          </div>
          <div style="position: relative;">
            <input type="text" id="explorer-table-search-input" class="form-control" placeholder="Search tables..." style="width: 100%; font-size: 12px; padding: 6px 10px;" value="${escapeHtml(explorerState.searchQuery)}">
          </div>
        </div>

        <!-- Tier Filter Buttons -->
        <div style="display: flex; gap: 4px; margin-bottom: 12px; flex-wrap: wrap;">
          <button class="btn btn-sm ${explorerState.tierFilter === 'ALL' ? 'btn-primary' : ''} tier-filter-btn" data-tier="ALL" style="font-size: 10.5px; padding: 2px 7px;">All</button>
          <button class="btn btn-sm ${explorerState.tierFilter === 'TIER_1_OPERATIONAL' ? 'btn-primary' : ''} tier-filter-btn" data-tier="TIER_1_OPERATIONAL" style="font-size: 10.5px; padding: 2px 7px;">Oper.</button>
          <button class="btn btn-sm ${explorerState.tierFilter === 'TIER_2_SANITIZED' ? 'btn-primary' : ''} tier-filter-btn" data-tier="TIER_2_SANITIZED" style="font-size: 10.5px; padding: 2px 7px;">Sanitized</button>
          <button class="btn btn-sm ${explorerState.tierFilter === 'TIER_3_ZERO_PREVIEW' ? 'btn-primary' : ''} tier-filter-btn" data-tier="TIER_3_ZERO_PREVIEW" style="font-size: 10.5px; padding: 2px 7px;">Vault</button>
        </div>

        <!-- Table List -->
        <div id="explorer-table-list-items" style="max-height: 580px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px;">
          ${renderTableListItems()}
        </div>
      </div>

      <!-- Right Column: Table Viewer & Data Pane -->
      <div id="explorer-detail-pane" style="flex: 1; min-width: 480px;">
        ${renderTableDetailPane()}
      </div>

    </div>
  `;

  // Attach Explorer Event Handlers
  const refreshMetaBtn = document.getElementById("explorer-refresh-meta-btn");
  if (refreshMetaBtn) {
    refreshMetaBtn.onclick = async () => {
      explorerState.overview = null;
      explorerState.tables = [];
      await loadAndRenderExplorer();
    };
  }

  const searchInput = document.getElementById("explorer-table-search-input");
  if (searchInput) {
    searchInput.oninput = (e) => {
      explorerState.searchQuery = e.target.value.toLowerCase().trim();
      const listContainer = document.getElementById("explorer-table-list-items");
      if (listContainer) listContainer.innerHTML = renderTableListItems();
      attachTableListClickHandlers();
    };
  }

  mount.querySelectorAll(".tier-filter-btn").forEach(btn => {
    btn.onclick = () => {
      explorerState.tierFilter = btn.getAttribute("data-tier");
      mount.querySelectorAll(".tier-filter-btn").forEach(b => b.classList.remove("btn-primary"));
      btn.classList.add("btn-primary");
      const listContainer = document.getElementById("explorer-table-list-items");
      if (listContainer) listContainer.innerHTML = renderTableListItems();
      attachTableListClickHandlers();
    };
  });

  attachTableListClickHandlers();
  attachDetailPaneHandlers();
}

function renderTableListItems() {
  const q = explorerState.searchQuery;
  const tier = explorerState.tierFilter;

  const filtered = explorerState.tables.filter(t => {
    if (q && !t.name.toLowerCase().includes(q) && !t.category.toLowerCase().includes(q)) return false;
    if (tier !== "ALL" && t.security_tier !== tier) return false;
    return true;
  });

  if (filtered.length === 0) {
    return `<div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 12px;">No tables match filters.</div>`;
  }

  return filtered.map(t => {
    const isSelected = t.name === explorerState.selectedTableName;
    let badgeClass = "badge-healthy";
    let badgeLabel = "OPERATIONAL";

    if (t.security_tier === "TIER_2_SANITIZED") {
      badgeClass = "badge-warning";
      badgeLabel = "SANITIZED";
    } else if (t.security_tier === "TIER_3_ZERO_PREVIEW") {
      badgeClass = "badge-critical";
      badgeLabel = "RESTRICTED";
    }

    return `
      <div class="explorer-table-item ${isSelected ? 'active' : ''}" data-table-name="${escapeHtml(t.name)}" style="
        padding: 8px 10px;
        border-radius: 6px;
        cursor: pointer;
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: ${isSelected ? 'rgba(59, 130, 246, 0.12)' : 'transparent'};
        border: 1px solid ${isSelected ? 'var(--primary)' : 'transparent'};
        transition: all 0.15s ease;
      ">
        <div style="min-width: 0;">
          <div style="font-size: 12.5px; font-weight: 600; font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: ${isSelected ? 'var(--primary)' : 'var(--text-primary)'};">
            ${escapeHtml(t.name)}
          </div>
          <div style="font-size: 10px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            ${escapeHtml(t.category)}
          </div>
        </div>
        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 2px; flex-shrink: 0;">
          <span class="badge ${badgeClass}" style="font-size: 8.5px; padding: 1px 4px;">${badgeLabel}</span>
          <span class="mono text-muted" style="font-size: 10.5px;">${t.row_count.toLocaleString()} rows</span>
        </div>
      </div>
    `;
  }).join("");
}

function attachTableListClickHandlers() {
  document.querySelectorAll(".explorer-table-item").forEach(item => {
    item.onclick = () => {
      const tableName = item.getAttribute("data-table-name");
      if (tableName === explorerState.selectedTableName) return;

      explorerState.selectedTableName = tableName;
      explorerState.page = 1;
      explorerState.cursor = null;
      explorerState.cursorHistory = [];
      explorerState.currentRecords = null;
      explorerState.currentSchema = null;

      // Select active table in state
      const targetTable = explorerState.tables.find(t => t.name === tableName);
      if (targetTable && targetTable.security_tier === "TIER_3_ZERO_PREVIEW") {
        explorerState.activeView = "schema";
      } else {
        explorerState.activeView = "records";
      }

      // Re-render table list selection and detail pane
      const listContainer = document.getElementById("explorer-table-list-items");
      if (listContainer) listContainer.innerHTML = renderTableListItems();
      attachTableListClickHandlers();

      const detailPane = document.getElementById("explorer-detail-pane");
      if (detailPane) {
        detailPane.innerHTML = renderTableDetailPane();
        attachDetailPaneHandlers();
      }
    };
  });
}

function renderTableDetailPane() {
  const currentTable = explorerState.tables.find(t => t.name === explorerState.selectedTableName);
  if (!currentTable) {
    return `
      <div class="card" style="padding: 30px; text-align: center; color: var(--text-muted);">
        Please select a table from the catalog sidebar.
      </div>
    `;
  }

  const isTier3 = currentTable.security_tier === "TIER_3_ZERO_PREVIEW";

  let tierBadge = `<span class="badge badge-healthy" style="font-size: 10px;">TIER 1 &bull; OPERATIONAL PREVIEW</span>`;
  if (currentTable.security_tier === "TIER_2_SANITIZED") {
    tierBadge = `<span class="badge badge-warning" style="font-size: 10px;">TIER 2 &bull; SANITIZED PROJECTION (SECRETS OMITTED)</span>`;
  } else if (isTier3) {
    tierBadge = `<span class="badge badge-critical" style="font-size: 10px;">TIER 3 &bull; ZERO PREVIEW (CREDENTIAL VAULT)</span>`;
  }

  return `
    <div class="card" style="padding: 18px; background: var(--bg-surface);">
      <!-- Table Header & Controls -->
      <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 14px;">
        <div>
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <h2 style="margin: 0; font-size: 18px; font-weight: 700; font-family: monospace;">${escapeHtml(currentTable.name)}</h2>
            ${tierBadge}
            <span class="badge badge-info" style="font-size: 10px;">${escapeHtml(currentTable.pagination_type)} PAGINATION</span>
          </div>
          <p style="margin: 4px 0 0 0; font-size: 12px; color: var(--text-muted);">
            Category: <strong>${escapeHtml(currentTable.category)}</strong> &bull; Total Columns: <strong>${currentTable.total_columns}</strong> (${currentTable.projected_columns} projected) &bull; Rows: <strong class="mono">${currentTable.row_count.toLocaleString()}</strong>
          </p>
        </div>

        <div style="display: flex; gap: 8px;">
          ${!isTier3 ? `
          <button class="btn btn-sm ${explorerState.activeView === 'records' ? 'btn-primary' : ''}" id="explorer-toggle-records-btn">
            ${renderIcon("layout-dashboard", { size: "xs" })} Records Preview
          </button>
          ` : ""}
          <button class="btn btn-sm ${explorerState.activeView === 'schema' || isTier3 ? 'btn-primary' : ''}" id="explorer-toggle-schema-btn">
            ${renderIcon("file-text", { size: "xs" })} Schema &amp; Indexes
          </button>
        </div>
      </div>

      <!-- Detail View Area -->
      <div id="explorer-view-content">
        ${isTier3 ? renderTier3SecurityNotice(currentTable) : ""}
        ${explorerState.activeView === "records" && !isTier3 ? renderRecordsViewPlaceholder() : renderSchemaViewPlaceholder()}
      </div>
    </div>
  `;
}

function renderTier3SecurityNotice(table) {
  return `
    <div style="padding: 14px 16px; background: rgba(239, 68, 68, 0.08); border-left: 4px solid var(--critical); border-radius: 6px; margin-bottom: 18px;">
      <div style="display: flex; align-items: center; gap: 8px; color: var(--critical); font-weight: 700; font-size: 13px;">
        ${renderIcon("shield-alert", { size: "sm" })} Record Preview Strictly Blocked by Security Policy
      </div>
      <p style="margin: 6px 0 0 0; font-size: 12px; color: var(--text-secondary); line-height: 1.5;">
        Table <code>${escapeHtml(table.name)}</code> contains cryptographic tokens, hashed authentication keys, or active session credentials. Direct record previews are disabled at the SQL projection engine layer. Schema metadata, column specifications, and backing index structures remain inspectable below for administrative compliance.
      </p>
    </div>
  `;
}

function renderRecordsViewPlaceholder() {
  return `
    <div id="explorer-records-container" style="padding: 24px 0; text-align: center;">
      <div class="state-icon">${renderIcon("loader", { size: "md", className: "icon-spin" })}</div>
      <div class="state-desc" style="margin-top: 8px;">Fetching sanitized table records...</div>
    </div>
  `;
}

function renderSchemaViewPlaceholder() {
  return `
    <div id="explorer-schema-container" style="padding: 24px 0; text-align: center;">
      <div class="state-icon">${renderIcon("loader", { size: "md", className: "icon-spin" })}</div>
      <div class="state-desc" style="margin-top: 8px;">Introspecting database schema and index metadata...</div>
    </div>
  `;
}

function attachDetailPaneHandlers() {
  const toggleRecordsBtn = document.getElementById("explorer-toggle-records-btn");
  if (toggleRecordsBtn) {
    toggleRecordsBtn.onclick = () => {
      explorerState.activeView = "records";
      const detailPane = document.getElementById("explorer-detail-pane");
      if (detailPane) {
        detailPane.innerHTML = renderTableDetailPane();
        attachDetailPaneHandlers();
      }
    };
  }

  const toggleSchemaBtn = document.getElementById("explorer-toggle-schema-btn");
  if (toggleSchemaBtn) {
    toggleSchemaBtn.onclick = () => {
      explorerState.activeView = "schema";
      const detailPane = document.getElementById("explorer-detail-pane");
      if (detailPane) {
        detailPane.innerHTML = renderTableDetailPane();
        attachDetailPaneHandlers();
      }
    };
  }

  // Load content based on view
  const currentTable = explorerState.tables.find(t => t.name === explorerState.selectedTableName);
  if (!currentTable) return;

  if (currentTable.security_tier === "TIER_3_ZERO_PREVIEW" || explorerState.activeView === "schema") {
    fetchAndRenderSchema(currentTable.name);
  } else {
    fetchAndRenderRecords(currentTable.name);
  }
}

async function fetchAndRenderRecords(tableName) {
  const container = document.getElementById("explorer-records-container");
  if (!container) return;

  try {
    const params = {
      limit: explorerState.limit,
      page: explorerState.page,
      cursor: explorerState.cursor,
      sort_by: "id",
      sort_order: "desc"
    };

    const res = await api.getDatabaseExplorerRecords(tableName, params);
    explorerState.currentRecords = res;
    renderRecordsTable(container, res);
  } catch (err) {
    container.innerHTML = `
      <div class="state-container" style="padding: 20px;">
        <div class="state-icon text-critical">${renderIcon("triangle-alert", { size: "md" })}</div>
        <div class="state-title">Query Execution Failed</div>
        <div class="state-desc">${escapeHtml(err.message)}</div>
      </div>
    `;
  }
}

function renderRecordsTable(container, data) {
  const isKeyset = data.pagination_type === "KEYSET";

  if (!data.records || data.records.length === 0) {
    container.innerHTML = `
      <div style="padding: 30px; text-align: center; color: var(--text-muted); font-size: 13px;">
        Table <code>${escapeHtml(data.table)}</code> contains zero records.
      </div>
    `;
    return;
  }

  const cols = data.columns;

  container.innerHTML = `
    <!-- Top Table Actions & Pagination Header -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
      <div style="font-size: 12px; color: var(--text-muted);">
        Displaying <strong>${data.records.length}</strong> of <strong>${data.total_records.toLocaleString()}</strong> records
        ${isKeyset ? `<span class="badge badge-info" style="font-size: 9.5px; margin-left: 6px;">Keyset Kept (id DESC)</span>` : `(Page ${data.page} of ${data.total_pages})`}
      </div>

      <div style="display: flex; gap: 6px; align-items: center;">
        ${isKeyset ? `
          <button class="btn btn-sm" id="keyset-prev-btn" ${explorerState.cursorHistory.length === 0 ? 'disabled' : ''}>
            &larr; Previous Page
          </button>
          <button class="btn btn-sm btn-primary" id="keyset-next-btn" ${!data.has_more ? 'disabled' : ''}>
            Next Page (${data.limit}) &rarr;
          </button>
        ` : `
          <button class="btn btn-sm" id="offset-prev-btn" ${data.page <= 1 ? 'disabled' : ''}>
            &larr; Previous
          </button>
          <span class="mono" style="font-size: 11px; padding: 0 4px;">Page ${data.page}</span>
          <button class="btn btn-sm" id="offset-next-btn" ${!data.has_more ? 'disabled' : ''}>
            Next &rarr;
          </button>
        `}
        <button class="btn btn-sm" id="records-refresh-btn" title="Refresh Table Records">
          ${renderIcon("refresh-cw", { size: "xs" })}
        </button>
      </div>
    </div>

    <!-- Data Grid -->
    <div class="table-container" style="overflow-x: auto; max-height: 520px; border: 1px solid var(--border-subtle); border-radius: 6px;">
      <table class="ops-table" style="width: 100%; font-size: 12px;">
        <thead style="position: sticky; top: 0; background: var(--bg-surface); z-index: 10;">
          <tr>
            ${cols.map(c => `
              <th style="padding: 8px 12px; white-space: nowrap;">
                <span class="mono">${escapeHtml(c)}</span>
                ${c === "id" ? `<span class="badge badge-info" style="font-size: 8.5px; margin-left: 4px;">PK</span>` : ""}
              </th>
            `).join("")}
          </tr>
        </thead>
        <tbody>
          ${data.records.map(row => `
            <tr>
              ${cols.map(c => {
    const val = row[c];
    let displayVal = val === null || val === undefined ? '<span class="text-muted">NULL</span>' : escapeHtml(String(val));
    if (typeof val === "boolean") {
      displayVal = val ? '<span class="text-healthy">TRUE</span>' : '<span class="text-muted">FALSE</span>';
    }
    return `<td style="padding: 6px 12px; white-space: nowrap; max-width: 280px; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(String(val ?? ''))}">${displayVal}</td>`;
  }).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

  // Attach Pagination Event Handlers
  if (isKeyset) {
    const prevBtn = document.getElementById("keyset-prev-btn");
    if (prevBtn) {
      prevBtn.onclick = () => {
        if (explorerState.cursorHistory.length > 0) {
          explorerState.cursor = explorerState.cursorHistory.pop();
          fetchAndRenderRecords(data.table);
        }
      };
    }

    const nextBtn = document.getElementById("keyset-next-btn");
    if (nextBtn) {
      nextBtn.onclick = () => {
        if (data.next_cursor) {
          explorerState.cursorHistory.push(explorerState.cursor);
          explorerState.cursor = data.next_cursor;
          fetchAndRenderRecords(data.table);
        }
      };
    }
  } else {
    const prevBtn = document.getElementById("offset-prev-btn");
    if (prevBtn) {
      prevBtn.onclick = () => {
        if (explorerState.page > 1) {
          explorerState.page -= 1;
          fetchAndRenderRecords(data.table);
        }
      };
    }

    const nextBtn = document.getElementById("offset-next-btn");
    if (nextBtn) {
      nextBtn.onclick = () => {
        if (data.has_more) {
          explorerState.page += 1;
          fetchAndRenderRecords(data.table);
        }
      };
    }
  }

  const refreshBtn = document.getElementById("records-refresh-btn");
  if (refreshBtn) {
    refreshBtn.onclick = () => fetchAndRenderRecords(data.table);
  }
}

async function fetchAndRenderSchema(tableName) {
  const container = document.getElementById("explorer-schema-container");
  if (!container) return;

  try {
    const schema = await api.getDatabaseExplorerSchema(tableName);
    explorerState.currentSchema = schema;
    renderSchemaTables(container, schema);
  } catch (err) {
    container.innerHTML = `
      <div class="state-container" style="padding: 20px;">
        <div class="state-icon text-critical">${renderIcon("triangle-alert", { size: "md" })}</div>
        <div class="state-title">Schema Introspection Failed</div>
        <div class="state-desc">${escapeHtml(err.message)}</div>
      </div>
    `;
  }
}

function renderSchemaTables(container, schema) {
  container.innerHTML = `
    <!-- 1. Physical Columns Definition -->
    <div style="margin-bottom: 24px;">
      <div style="font-size: 13px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 10px; display: flex; align-items: center; gap: 6px;">
        ${renderIcon("sliders", { size: "xs" })} Physical Column Specifications (${schema.columns.length})
      </div>
      <div class="table-container" style="border: 1px solid var(--border-subtle); border-radius: 6px; overflow-x: auto;">
        <table class="ops-table" style="width: 100%; font-size: 12px;">
          <thead>
            <tr>
              <th style="width: 50px;">CID</th>
              <th>Column Name</th>
              <th>Physical SQLite Type</th>
              <th>Primary Key</th>
              <th>Nullable</th>
              <th>Default</th>
              <th>Explorer Projection</th>
            </tr>
          </thead>
          <tbody>
            ${schema.columns.map(c => `
              <tr>
                <td class="mono text-muted">${c.cid}</td>
                <td style="font-weight: 600;" class="mono">${escapeHtml(c.name)}</td>
                <td class="mono text-healthy">${escapeHtml(c.type || 'BLOB')}</td>
                <td>${c.primary_key ? `<span class="badge badge-info" style="font-size: 9px;">PRIMARY KEY</span>` : `<span class="text-muted">—</span>`}</td>
                <td>${c.notnull ? `<span class="text-critical" style="font-size: 11px;">NOT NULL</span>` : `<span class="text-muted" style="font-size: 11px;">NULLABLE</span>`}</td>
                <td class="mono text-muted" style="font-size: 11px;">${escapeHtml(c.default_value || '—')}</td>
                <td>
                  ${c.is_projected ? `
                    <span class="badge badge-healthy" style="font-size: 9px;">PROJECTED</span>
                  ` : `
                    <span class="badge badge-critical" style="font-size: 9px;">EXCLUDED (SECURITY)</span>
                  `}
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>

    <!-- 2. Backing Indexes -->
    <div style="margin-bottom: 24px;">
      <div style="font-size: 13px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 10px; display: flex; align-items: center; gap: 6px;">
        ${renderIcon("activity", { size: "xs" })} Physical Storage Indexes (${schema.indexes.length})
      </div>
      ${schema.indexes.length === 0 ? `
        <div style="padding: 14px; background: var(--bg-surface-elevated); border: 1px solid var(--border-default); border-radius: 6px; color: var(--text-muted); font-size: 12px;">
          No explicit secondary indexes defined for table <code>${escapeHtml(schema.table)}</code>.
        </div>
      ` : `
        <div class="table-container" style="border: 1px solid var(--border-subtle); border-radius: 6px; overflow-x: auto;">
          <table class="ops-table" style="width: 100%; font-size: 12px;">
            <thead>
              <tr>
                <th>Index Name</th>
                <th>Unique Constraint</th>
                <th>Indexed Columns</th>
                <th>Index Type</th>
              </tr>
            </thead>
            <tbody>
              ${schema.indexes.map(idx => `
                <tr>
                  <td class="mono font-weight-bold">${escapeHtml(idx.name)}</td>
                  <td>${idx.unique ? `<span class="badge badge-healthy" style="font-size: 9px;">UNIQUE</span>` : `<span class="text-muted">—</span>`}</td>
                  <td class="mono" style="color: var(--primary);">${escapeHtml(idx.columns.join(", "))}</td>
                  <td>${idx.is_autoindex ? `<span class="badge badge-info" style="font-size: 9px;">SQLITE AUTOINDEX</span>` : `<span class="badge badge-warning" style="font-size: 9px;">USER DEFINED</span>`}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `}
    </div>

    <!-- 3. Foreign Key Constraints -->
    <div>
      <div style="font-size: 13px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 10px; display: flex; align-items: center; gap: 6px;">
        ${renderIcon("arrow-right-left", { size: "xs" })} Foreign Key Referential Constraints (${schema.foreign_keys.length})
      </div>
      ${schema.foreign_keys.length === 0 ? `
        <div style="padding: 14px; background: var(--bg-surface-elevated); border: 1px solid var(--border-default); border-radius: 6px; color: var(--text-muted); font-size: 12px;">
          No foreign key clauses defined for table <code>${escapeHtml(schema.table)}</code>.
        </div>
      ` : `
        <div class="table-container" style="border: 1px solid var(--border-subtle); border-radius: 6px; overflow-x: auto;">
          <table class="ops-table" style="width: 100%; font-size: 12px;">
            <thead>
              <tr>
                <th>Local Column</th>
                <th>Referenced Parent Table</th>
                <th>Target Primary Key</th>
              </tr>
            </thead>
            <tbody>
              ${schema.foreign_keys.map(fk => `
                <tr>
                  <td class="mono font-weight-bold" style="color: var(--primary);">${escapeHtml(fk.from_column)}</td>
                  <td class="mono">${escapeHtml(fk.table)}</td>
                  <td class="mono text-muted">${escapeHtml(fk.to_column)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `}
    </div>
  `;
}
