/**
 * Super Admin Device Management View - CloudOps Intel Lab PC Fleet Command.
 * 
 * Provides Super Admin control over:
 * 1. Time-limited enrollment code generation and revocation.
 * 2. Pending sensor device review, physical lab/room/PC mapping, and approval/rejection.
 * 3. Workstation fleet monitoring (Online, Offline, Stale, Spool Queue Backlog).
 * 4. Device lifecycle governance (Disable, Re-enable, Decommission/Retire).
 * 5. Telemetry diagnostics and actionable health alert triage.
 */

import { api } from "../api.js";
import { authManager } from "../auth.js";
import { escapeHtml, formatTimestamp } from "../sanitizer.js";
import { renderIcon } from "../components/Icons.js";
import { openModal, closeModal } from "../components/Modal.js";

let currentTab = "fleet"; // "fleet" | "pending" | "codes" | "retired"

export async function renderDeviceManagementView(container) {
  if (!authManager.isSuperAdmin()) {
    container.innerHTML = `
      <div class="state-container">
        <div class="state-icon text-critical">${renderIcon("shield-alert", { size: "xl" })}</div>
        <div class="state-title">Super Admin Access Required</div>
        <div class="state-desc">Lab PC sensor enrollment, hardware authorization, and credential management are restricted to Super Administrators.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="state-container">
      <div class="state-icon">${renderIcon("loader", { size: "xl", className: "icon-spin" })}</div>
      <div class="state-title">Loading Lab PC Fleet & Sensor Management...</div>
    </div>
  `;

  try {
    const [stats, devices, codes] = await Promise.all([
      api.getDeviceStats(),
      api.getDevices(),
      api.listEnrollmentCodes(),
    ]);

    renderDashboard(container, stats, devices, codes);
  } catch (err) {
    container.innerHTML = `
      <div class="state-container">
        <div class="state-icon text-critical">${renderIcon("triangle-alert", { size: "xl" })}</div>
        <div class="state-title">Failed to load Device Management data</div>
        <div class="state-desc">${escapeHtml(err.message || "An unexpected error occurred.")}</div>
        <div style="margin-top: 16px;">
          <button class="btn btn-sm" id="devices-retry-btn">
            ${renderIcon("refresh-cw", { size: "sm" })} Retry
          </button>
        </div>
      </div>
    `;
    const retryBtn = document.getElementById("devices-retry-btn");
    if (retryBtn) retryBtn.onclick = () => renderDeviceManagementView(container);
  }
}

function renderDashboard(container, stats, devices, codes) {
  const pendingDevices = devices.filter(d => d.status === "PENDING");
  const approvedDevices = devices.filter(d => d.status === "APPROVED");
  const disabledDevices = devices.filter(d => d.status === "DISABLED");
  const retiredDevices = devices.filter(d => d.status === "RETIRED");

  container.innerHTML = `
    <div class="view-header">
      <div class="view-title-group">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="color: var(--accent-cyan, #06b6d4); display: inline-flex;">
            ${renderIcon("monitor", { size: "lg" })}
          </span>
          <h1 style="margin: 0;">Lab PC Enrollment & Fleet Management</h1>
        </div>
        <p>Enterprise sensor enrollment, cryptographic approval, physical lab PC mapping, and reliable telemetry lifecycle.</p>
      </div>
      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <button class="btn btn-sm btn-primary" id="btn-generate-code">
          ${renderIcon("plus-circle", { size: "sm" })} Generate Enrollment Code
        </button>
        <button class="btn btn-sm" id="btn-refresh-devices">
          ${renderIcon("refresh-cw", { size: "sm" })} Refresh Fleet
        </button>
      </div>
    </div>

    <!-- Summary Stats KPI Row -->
    <div class="grid grid-cols-4" style="gap: 16px; margin-bottom: 24px;">
      <div class="kpi-card">
        <div class="kpi-label">Total Fleet Registered</div>
        <div class="kpi-value">${stats.total_devices}</div>
        <div class="kpi-subtext">${stats.approved_active} Active | ${stats.disabled} Disabled</div>
      </div>
      <div class="kpi-card" style="${pendingDevices.length > 0 ? 'border-color: var(--accent-amber); box-shadow: 0 0 12px rgba(245, 158, 11, 0.2);' : ''}">
        <div class="kpi-label">Pending Approval</div>
        <div class="kpi-value text-${pendingDevices.length > 0 ? 'warning' : 'muted'}">${stats.pending_approval}</div>
        <div class="kpi-subtext">${pendingDevices.length > 0 ? 'Action required: physical mapping' : 'All devices triaged'}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Online Workstations</div>
        <div class="kpi-value text-healthy">${stats.online_count}</div>
        <div class="kpi-subtext">Heartbeat &lt; 180s threshold</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Offline / Telemetry Lapsed</div>
        <div class="kpi-value text-${stats.offline_count > 0 ? 'critical' : 'healthy'}">${stats.offline_count}</div>
        <div class="kpi-subtext">${stats.stale_telemetry} telemetry stale or offline</div>
      </div>
    </div>

    <!-- Tab Navigation -->
    <div class="tabs-nav" style="display: flex; gap: 8px; border-bottom: 1px solid var(--border-subtle); margin-bottom: 20px;">
      <button class="tab-btn ${currentTab === 'fleet' ? 'active' : ''}" data-tab="fleet">
        ${renderIcon("cpu", { size: "sm" })} Active Fleet (${approvedDevices.length})
      </button>
      <button class="tab-btn ${currentTab === 'pending' ? 'active' : ''}" data-tab="pending" style="position: relative;">
        ${renderIcon("clock", { size: "sm" })} Pending Approval (${pendingDevices.length})
        ${pendingDevices.length > 0 ? '<span class="badge badge-warning" style="margin-left: 6px; font-size: 11px;">NEW</span>' : ''}
      </button>
      <button class="tab-btn ${currentTab === 'codes' ? 'active' : ''}" data-tab="codes">
        ${renderIcon("key", { size: "sm" })} Enrollment Codes (${codes.length})
      </button>
      <button class="tab-btn ${currentTab === 'retired' ? 'active' : ''}" data-tab="retired">
        ${renderIcon("archive", { size: "sm" })} Inactive / Retired (${disabledDevices.length + retiredDevices.length})
      </button>
    </div>

    <!-- Tab Contents Container -->
    <div id="device-tab-content"></div>
  `;

  // Attach tab switchers
  container.querySelectorAll(".tab-btn").forEach(btn => {
    btn.onclick = () => {
      currentTab = btn.getAttribute("data-tab");
      container.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      renderActiveTabContent(container, stats, devices, codes);
    };
  });

  // Attach Header Actions
  const btnGenCode = document.getElementById("btn-generate-code");
  if (btnGenCode) {
    btnGenCode.onclick = () => showGenerateCodeModal(container);
  }

  const btnRefresh = document.getElementById("btn-refresh-devices");
  if (btnRefresh) {
    btnRefresh.onclick = () => renderDeviceManagementView(container);
  }

  // Render initial tab
  renderActiveTabContent(container, stats, devices, codes);
}

function renderActiveTabContent(container, stats, devices, codes) {
  const tabContent = document.getElementById("device-tab-content");
  if (!tabContent) return;

  if (currentTab === "fleet") {
    renderFleetTab(tabContent, devices.filter(d => d.status === "APPROVED"), container);
  } else if (currentTab === "pending") {
    renderPendingTab(tabContent, devices.filter(d => d.status === "PENDING"), container);
  } else if (currentTab === "codes") {
    renderCodesTab(tabContent, codes, container);
  } else if (currentTab === "retired") {
    renderRetiredTab(tabContent, devices.filter(d => d.status === "DISABLED" || d.status === "RETIRED"), container);
  }
}

// -------------------------------------------------------------
// TAB 1: ACTIVE FLEET
// -------------------------------------------------------------
function renderFleetTab(target, devices, rootContainer) {
  if (devices.length === 0) {
    target.innerHTML = `
      <div class="state-container" style="padding: 40px; border: 1px dashed var(--border-subtle); border-radius: 8px;">
        <div class="state-icon text-muted">${renderIcon("monitor-x", { size: "lg" })}</div>
        <div class="state-title">No Active Lab PCs Enrolled</div>
        <div class="state-desc">Generate an enrollment code and run the sensor installer on a lab workstation to enroll it.</div>
      </div>
    `;
    return;
  }

  target.innerHTML = `
    <div class="table-container">
      <table class="table" style="width: 100%;">
        <thead>
          <tr>
            <th>Status / Health</th>
            <th>Assigned PC Label</th>
            <th>Location</th>
            <th>Reported Hostname & IP</th>
            <th>Agent Version</th>
            <th>Queue Backlog</th>
            <th>Last Upload</th>
            <th style="text-align: right;">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${devices.map(d => {
            const isOnline = d.is_online;
            const healthStatus = d.telemetry_health || "UNKNOWN";
            
            let statusBadge = `<span class="badge badge-healthy">ONLINE</span>`;
            if (!isOnline) {
              statusBadge = `<span class="badge badge-critical" title="No telemetry received in > 180s">OFFLINE</span>`;
            } else if (healthStatus === "STALE") {
              statusBadge = `<span class="badge badge-warning" title="Online but metrics collection stale">STALE</span>`;
            }

            return `
              <tr>
                <td>
                  <div style="display: flex; align-items: center; gap: 6px;">
                    ${statusBadge}
                  </div>
                </td>
                <td>
                  <strong class="text-primary">${escapeHtml(d.assigned_name || d.reported_hostname)}</strong>
                  <div class="mono text-muted" style="font-size: 11px;">UUID: ${escapeHtml(d.device_uuid.substring(0, 8))}...</div>
                </td>
                <td>
                  <div>${escapeHtml(d.lab_name || "Lab")}</div>
                  <div class="text-muted" style="font-size: 12px;">${escapeHtml(d.room_number || "Room")} / PC ${escapeHtml(d.pc_number || "-")}</div>
                </td>
                <td>
                  <div class="mono">${escapeHtml(d.reported_hostname)}</div>
                  <div class="mono text-muted" style="font-size: 12px;">${escapeHtml(d.ip_address || "Unknown IP")}</div>
                </td>
                <td>
                  <span class="badge badge-subtle">v${escapeHtml(d.agent_version || "1.0.0")}</span>
                </td>
                <td>
                  <span class="badge ${d.queue_backlog > 0 ? 'badge-warning' : 'badge-subtle'}">
                    ${d.queue_backlog} unsent
                  </span>
                </td>
                <td>
                  <div title="${d.last_upload_at || ''}">${d.last_upload_at ? formatTimestamp(d.last_upload_at) : 'Never'}</div>
                  ${!isOnline ? '<div class="text-critical" style="font-size: 11px;">&gt; 180s elapsed</div>' : ''}
                </td>
                <td style="text-align: right;">
                  <button class="btn btn-sm btn-icon btn-action-disable" data-id="${d.id}" data-name="${escapeHtml(d.assigned_name || d.reported_hostname)}" title="Disable Ingestion">
                    ${renderIcon("pause-circle", { size: "sm" })}
                  </button>
                  <button class="btn btn-sm btn-icon text-critical btn-action-retire" data-id="${d.id}" data-name="${escapeHtml(d.assigned_name || d.reported_hostname)}" title="Decommission / Retire Device">
                    ${renderIcon("trash-2", { size: "sm" })}
                  </button>
                </td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;

  // Attach actions
  target.querySelectorAll(".btn-action-disable").forEach(btn => {
    btn.onclick = () => {
      const id = btn.getAttribute("data-id");
      const name = btn.getAttribute("data-name");
      confirmDisableDevice(id, name, rootContainer);
    };
  });

  target.querySelectorAll(".btn-action-retire").forEach(btn => {
    btn.onclick = () => {
      const id = btn.getAttribute("data-id");
      const name = btn.getAttribute("data-name");
      confirmRetireDevice(id, name, rootContainer);
    };
  });
}

// -------------------------------------------------------------
// TAB 2: PENDING APPROVAL
// -------------------------------------------------------------
function renderPendingTab(target, pendingDevices, rootContainer) {
  if (pendingDevices.length === 0) {
    target.innerHTML = `
      <div class="state-container" style="padding: 40px; border: 1px dashed var(--border-subtle); border-radius: 8px;">
        <div class="state-icon text-healthy">${renderIcon("check-circle-2", { size: "lg" })}</div>
        <div class="state-title">No Pending Requests</div>
        <div class="state-desc">All enrolled lab workstations have been reviewed and mapped.</div>
      </div>
    `;
    return;
  }

  target.innerHTML = `
    <div style="background: var(--bg-surface-secondary); padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; border-left: 4px solid var(--accent-amber);">
      <strong>Physical Device Mapping Protocol:</strong> Verify the reported hostname and MAC address against the physical computer tag in the lab before approving. Telemetry ingestion is strictly blocked until approved.
    </div>
    <div class="table-container">
      <table class="table" style="width: 100%;">
        <thead>
          <tr>
            <th>Reported Hostname</th>
            <th>Hardware UUID</th>
            <th>IP Address & OS</th>
            <th>Requested At</th>
            <th style="text-align: right;">Review Actions</th>
          </tr>
        </thead>
        <tbody>
          ${pendingDevices.map(d => `
            <tr>
              <td>
                <strong class="mono text-primary">${escapeHtml(d.reported_hostname)}</strong>
                <div><span class="badge badge-warning">AWAITING APPROVAL</span></div>
              </td>
              <td class="mono" style="font-size: 12px;">${escapeHtml(d.device_uuid)}</td>
              <td>
                <div class="mono">${escapeHtml(d.ip_address || "Unknown IP")}</div>
                <div class="text-muted" style="font-size: 12px;">${escapeHtml(d.os_version || "Windows")}</div>
              </td>
              <td>${formatTimestamp(d.requested_at)}</td>
              <td style="text-align: right;">
                <button class="btn btn-sm btn-primary btn-approve-device" data-device='${JSON.stringify(d)}'>
                  ${renderIcon("check", { size: "sm" })} Approve & Map
                </button>
                <button class="btn btn-sm text-critical btn-reject-device" data-id="${d.id}" data-name="${escapeHtml(d.reported_hostname)}">
                  ${renderIcon("x", { size: "sm" })} Reject
                </button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

  target.querySelectorAll(".btn-approve-device").forEach(btn => {
    btn.onclick = () => {
      const dev = JSON.parse(btn.getAttribute("data-device"));
      showApproveModal(dev, rootContainer);
    };
  });

  target.querySelectorAll(".btn-reject-device").forEach(btn => {
    btn.onclick = () => {
      const id = btn.getAttribute("data-id");
      const name = btn.getAttribute("data-name");
      showRejectModal(id, name, rootContainer);
    };
  });
}

// -------------------------------------------------------------
// TAB 3: ENROLLMENT CODES
// -------------------------------------------------------------
function renderCodesTab(target, codes, rootContainer) {
  target.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
      <div>
        <strong>Single-Use Enrollment Codes</strong>
        <p class="text-muted" style="margin: 0; font-size: 13px;">Codes expire in 15 minutes by default and can only be used once to initiate enrollment.</p>
      </div>
      <button class="btn btn-sm btn-primary" id="btn-tab-generate-code">
        ${renderIcon("plus-circle", { size: "sm" })} Generate New Code
      </button>
    </div>
    <div class="table-container">
      <table class="table" style="width: 100%;">
        <thead>
          <tr>
            <th>Code Prefix</th>
            <th>Status</th>
            <th>Expires At</th>
            <th>Created At</th>
            <th style="text-align: right;">Action</th>
          </tr>
        </thead>
        <tbody>
          ${codes.length === 0 ? `
            <tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">No enrollment codes generated.</td></tr>
          ` : codes.map(c => {
            const isExpired = new Date(c.expires_at) < new Date();
            let badge = `<span class="badge badge-healthy">ACTIVE</span>`;
            if (c.revoked_at) {
              badge = `<span class="badge badge-critical">REVOKED</span>`;
            } else if (c.is_used) {
              badge = `<span class="badge badge-subtle">USED</span>`;
            } else if (isExpired) {
              badge = `<span class="badge badge-warning">EXPIRED</span>`;
            }

            return `
              <tr>
                <td class="mono font-weight-bold">${escapeHtml(c.code_prefix)}••••••••</td>
                <td>${badge}</td>
                <td>${formatTimestamp(c.expires_at)}</td>
                <td>${formatTimestamp(c.created_at)}</td>
                <td style="text-align: right;">
                  ${(!c.is_used && !c.revoked_at && !isExpired) ? `
                    <button class="btn btn-sm text-critical btn-revoke-code" data-id="${c.id}" title="Revoke Code">
                      ${renderIcon("ban", { size: "sm" })} Revoke
                    </button>
                  ` : '<span class="text-muted">-</span>'}
                </td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;

  const btnTabGen = target.querySelector("#btn-tab-generate-code");
  if (btnTabGen) btnTabGen.onclick = () => showGenerateCodeModal(rootContainer);

  target.querySelectorAll(".btn-revoke-code").forEach(btn => {
    btn.onclick = async () => {
      const id = btn.getAttribute("data-id");
      if (confirm("Are you sure you want to revoke this enrollment code immediately?")) {
        try {
          await api.revokeEnrollmentCode(id);
          renderDeviceManagementView(rootContainer);
        } catch (err) {
          alert(`Failed to revoke code: ${err.message}`);
        }
      }
    };
  });
}

// -------------------------------------------------------------
// TAB 4: RETIRED & DISABLED
// -------------------------------------------------------------
function renderRetiredTab(target, devices, rootContainer) {
  if (devices.length === 0) {
    target.innerHTML = `
      <div class="state-container" style="padding: 40px; border: 1px dashed var(--border-subtle); border-radius: 8px;">
        <div class="state-icon text-muted">${renderIcon("archive", { size: "lg" })}</div>
        <div class="state-title">No Disabled or Retired Devices</div>
        <div class="state-desc">All workstations are currently in active service.</div>
      </div>
    `;
    return;
  }

  target.innerHTML = `
    <div class="table-container">
      <table class="table" style="width: 100%;">
        <thead>
          <tr>
            <th>Status</th>
            <th>Assigned Label</th>
            <th>Location</th>
            <th>Reported Hostname</th>
            <th>Retirement Reason / Notes</th>
            <th style="text-align: right;">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${devices.map(d => `
            <tr>
              <td>
                <span class="badge ${d.status === 'DISABLED' ? 'badge-warning' : 'badge-critical'}">
                  ${d.status}
                </span>
                ${d.retirement_requested && !d.retirement_confirmed ? '<div class="text-warning" style="font-size: 11px;">Uninstall notice pending</div>' : ''}
              </td>
              <td><strong>${escapeHtml(d.assigned_name || d.reported_hostname)}</strong></td>
              <td>${escapeHtml(d.lab_name || "Lab")} / Room ${escapeHtml(d.room_number || "-")}</td>
              <td class="mono">${escapeHtml(d.reported_hostname)}</td>
              <td class="text-muted" style="font-size: 12px;">${escapeHtml(d.rejection_reason || "Administrative state change")}</td>
              <td style="text-align: right;">
                ${d.status === 'DISABLED' ? `
                  <button class="btn btn-sm btn-primary btn-enable-device" data-id="${d.id}" data-name="${escapeHtml(d.assigned_name || d.reported_hostname)}">
                    ${renderIcon("play-circle", { size: "sm" })} Re-enable
                  </button>
                  <button class="btn btn-sm text-critical btn-retire-disabled" data-id="${d.id}" data-name="${escapeHtml(d.assigned_name || d.reported_hostname)}">
                    ${renderIcon("trash-2", { size: "sm" })} Retire
                  </button>
                ` : `
                  <span class="badge badge-subtle">CREDENTIAL REVOKED</span>
                `}
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

  target.querySelectorAll(".btn-enable-device").forEach(btn => {
    btn.onclick = async () => {
      const id = btn.getAttribute("data-id");
      const name = btn.getAttribute("data-name");
      if (confirm(`Re-enable telemetry ingestion for '${name}'?`)) {
        try {
          await api.enableDevice(id);
          renderDeviceManagementView(rootContainer);
        } catch (err) {
          alert(`Failed to enable device: ${err.message}`);
        }
      }
    };
  });

  target.querySelectorAll(".btn-retire-disabled").forEach(btn => {
    btn.onclick = () => {
      const id = btn.getAttribute("data-id");
      const name = btn.getAttribute("data-name");
      confirmRetireDevice(id, name, rootContainer);
    };
  });
}

// -------------------------------------------------------------
// MODALS & ACTIONS
// -------------------------------------------------------------
function showGenerateCodeModal(rootContainer) {
  const modalContent = `
    <div style="padding: 8px;">
      <h3 style="margin-top: 0;">Generate Sensor Enrollment Code</h3>
      <p class="text-muted">Generates a single-use cryptographically random enrollment code for an authorized Windows workstation.</p>
      
      <div class="form-group" style="margin-bottom: 16px;">
        <label for="code-expiry">Expiration Window</label>
        <select id="code-expiry" class="form-control" style="width: 100%;">
          <option value="15" selected>15 Minutes (Recommended / High Security)</option>
          <option value="30">30 Minutes</option>
          <option value="60">1 Hour</option>
          <option value="1440">24 Hours (Lab Rollout Session)</option>
        </select>
      </div>

      <div class="form-group" style="margin-bottom: 20px;">
        <label for="code-notes">Notes / Target PC Reference</label>
        <input type="text" id="code-notes" class="form-control" placeholder="e.g. Lab 1 - Bench 3 rollout" style="width: 100%;">
      </div>

      <div id="code-result-container" style="display: none; margin-bottom: 20px;">
        <div style="background: var(--bg-surface-secondary); padding: 16px; border-radius: 6px; border: 1px solid var(--accent-cyan);">
          <div style="font-size: 12px; color: var(--accent-cyan); font-weight: bold; margin-bottom: 6px;">ONE-TIME ENROLLMENT CODE</div>
          <div style="display: flex; gap: 8px; align-items: center;">
            <input type="text" id="raw-code-display" readonly class="form-control mono" style="font-size: 18px; font-weight: bold; letter-spacing: 2px;">
            <button class="btn btn-primary" id="btn-copy-code">Copy</button>
          </div>
          <div class="text-critical" style="font-size: 11px; margin-top: 8px;">
            This raw code is shown only once and is never stored in plaintext. Copy it into the sensor installer now.
          </div>
        </div>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: 8px;">
        <button class="btn btn-sm" id="btn-close-modal">Cancel</button>
        <button class="btn btn-sm btn-primary" id="btn-submit-code-gen">Generate Code</button>
      </div>
    </div>
  `;

  openModal("Enrollment Code Provisioning", modalContent);

  const submitBtn = document.getElementById("btn-submit-code-gen");
  const closeBtn = document.getElementById("btn-close-modal");
  const resultBox = document.getElementById("code-result-container");
  const rawInput = document.getElementById("raw-code-display");
  const copyBtn = document.getElementById("btn-copy-code");

  if (closeBtn) closeBtn.onclick = () => closeModal();

  if (submitBtn) {
    submitBtn.onclick = async () => {
      const exp = parseInt(document.getElementById("code-expiry").value, 10);
      const notes = document.getElementById("code-notes").value;
      submitBtn.disabled = true;
      submitBtn.innerText = "Generating...";

      try {
        const res = await api.generateEnrollmentCode(exp, notes);
        resultBox.style.display = "block";
        rawInput.value = res.raw_code;
        submitBtn.style.display = "none";
        closeBtn.innerText = "Done";
        closeBtn.onclick = () => {
          closeModal();
          renderDeviceManagementView(rootContainer);
        };

        if (copyBtn) {
          copyBtn.onclick = () => {
            navigator.clipboard.writeText(res.raw_code);
            copyBtn.innerText = "Copied!";
            setTimeout(() => { copyBtn.innerText = "Copy"; }, 2000);
          };
        }
      } catch (err) {
        alert(`Error generating enrollment code: ${err.message}`);
        submitBtn.disabled = false;
        submitBtn.innerText = "Generate Code";
      }
    };
  }
}

function showApproveModal(device, rootContainer) {
  const modalContent = `
    <div style="padding: 8px;">
      <h3 style="margin-top: 0;">Approve & Map Physical Workstation</h3>
      <p class="text-muted">Map reported hardware <strong>${escapeHtml(device.reported_hostname)}</strong> (UUID: ${escapeHtml(device.device_uuid.substring(0, 8))}...) to its physical laboratory location.</p>

      <div class="form-group" style="margin-bottom: 12px;">
        <label for="assign-label">Assigned Device Label *</label>
        <input type="text" id="assign-label" class="form-control" value="PC-${escapeHtml(device.reported_hostname)}" style="width: 100%;">
      </div>

      <div class="grid grid-cols-3" style="gap: 12px; margin-bottom: 20px;">
        <div class="form-group">
          <label for="assign-lab">Lab Name</label>
          <input type="text" id="assign-lab" class="form-control" value="Main Lab" style="width: 100%;">
        </div>
        <div class="form-group">
          <label for="assign-room">Room Number</label>
          <input type="text" id="assign-room" class="form-control" value="Room 101" style="width: 100%;">
        </div>
        <div class="form-group">
          <label for="assign-pc">PC Number</label>
          <input type="text" id="assign-pc" class="form-control" value="01" style="width: 100%;">
        </div>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: 8px;">
        <button class="btn btn-sm" id="btn-cancel-approve">Cancel</button>
        <button class="btn btn-sm btn-primary" id="btn-confirm-approve">Approve & Issue Credential</button>
      </div>
    </div>
  `;

  openModal("Workstation Physical Mapping", modalContent);

  const cancelBtn = document.getElementById("btn-cancel-approve");
  const confirmBtn = document.getElementById("btn-confirm-approve");

  if (cancelBtn) cancelBtn.onclick = () => closeModal();

  if (confirmBtn) {
    confirmBtn.onclick = async () => {
      const assignedName = document.getElementById("assign-label").value.trim();
      const labName = document.getElementById("assign-lab").value.trim();
      const roomNumber = document.getElementById("assign-room").value.trim();
      const pcNumber = document.getElementById("assign-pc").value.trim();

      if (!assignedName) {
        alert("Assigned device label is required.");
        return;
      }

      confirmBtn.disabled = true;
      confirmBtn.innerText = "Approving...";

      try {
        await api.approveDevice(device.id, {
          assigned_name: assignedName,
          lab_name: labName,
          room_number: roomNumber,
          pc_number: pcNumber,
        });
        closeModal();
        renderDeviceManagementView(rootContainer);
      } catch (err) {
        alert(`Approval failed: ${err.message}`);
        confirmBtn.disabled = false;
        confirmBtn.innerText = "Approve & Issue Credential";
      }
    };
  }
}

function showRejectModal(deviceId, hostname, rootContainer) {
  const reason = prompt(`Reject enrollment for '${hostname}'? Enter rejection reason:`, "Unauthorized hardware or invalid location");
  if (reason !== null) {
    api.rejectDevice(deviceId, reason).then(() => {
      renderDeviceManagementView(rootContainer);
    }).catch(err => {
      alert(`Rejection failed: ${err.message}`);
    });
  }
}

function confirmDisableDevice(deviceId, name, rootContainer) {
  if (confirm(`Disable workstation '${name}'?\n\nThis immediately blocks all telemetry ingestion on the server. Historical data is preserved.`)) {
    api.disableDevice(deviceId, "Disabled by Super Admin").then(() => {
      renderDeviceManagementView(rootContainer);
    }).catch(err => {
      alert(`Disable failed: ${err.message}`);
    });
  }
}

function confirmRetireDevice(deviceId, name, rootContainer) {
  if (confirm(`PERMANENT ACTION: Decommission and retire '${name}'?\n\nThe sensor's ingestion API key will be permanently revoked on the server. Historical data is preserved, but this PC cannot submit metrics without re-enrolling.`)) {
    api.retireDevice(deviceId, "Decommissioned by Super Admin").then(() => {
      renderDeviceManagementView(rootContainer);
    }).catch(err => {
      alert(`Retirement failed: ${err.message}`);
    });
  }
}
