"""
Frontend View Enhancement Script for Phase 9A.1.

1. Enhances AdminManagementView.js with a Resource Assignments tab (Hybrid RBAC).
2. Enhances ResourcesView.js with a Predefined Remote Diagnostics launcher & live console.
"""

from pathlib import Path

admin_view_path = Path("frontend/js/views/AdminManagementView.js")
resources_view_path = Path("frontend/js/views/ResourcesView.js")

# --- 1. AdminManagementView.js Enhancement ---
with open(admin_view_path, "r", encoding="utf-8") as f:
    admin_code = f.read()

# Replace tab buttons
if "tab-assignments-btn" not in admin_code:
    old_tabs_anchor = 'id="tab-directory-btn"'
    idx = admin_code.find(old_tabs_anchor)
    if idx != -1:
        # Find closing tag of directory button
        btn_close = admin_code.find("</button>", idx) + len("</button>")
        tab_btn_insert = """
      <button class="tab-btn ${currentTab === "assignments" ? "active" : ""}" id="tab-assignments-btn" style="display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: none; border: none; border-bottom: 2px solid ${currentTab === "assignments" ? "var(--primary)" : "transparent"}; color: ${currentTab === "assignments" ? "var(--text-primary)" : "var(--text-muted)"}; cursor: pointer; font-weight: 600; font-size: 13px;">
        ${renderIcon("key", { size: "sm" })}
        Resource Assignments (Hybrid RBAC)
      </button>"""
        admin_code = admin_code[:btn_close] + tab_btn_insert + admin_code[btn_close:]

# Update currentTab definition comment
admin_code = admin_code.replace(
    'let currentTab = "requests"; // "requests" | "directory"',
    'let currentTab = "requests"; // "requests" | "directory" | "assignments"'
)

# Update tab content conditional
old_content_render = '${currentTab === "requests" ? renderRequestsTab(requests) : renderDirectoryTab(users)}'
new_content_render = '${currentTab === "requests" ? renderRequestsTab(requests) : (currentTab === "directory" ? renderDirectoryTab(users) : renderAssignmentsTabPlaceholder())}'
if old_content_render in admin_code:
    admin_code = admin_code.replace(old_content_render, new_content_render)

# Add listener attachment for assignments tab
old_listener_anchor = 'const tabDirectoryBtn = document.getElementById("tab-directory-btn");'
if 'const tabAssignmentsBtn = document.getElementById("tab-assignments-btn");' not in admin_code:
    idx_listener = admin_code.find(old_listener_anchor)
    if idx_listener != -1:
        # Find the end of tabDirectoryBtn block
        brace_close = admin_code.find("}", admin_code.find("if (tabDirectoryBtn)", idx_listener)) + 1
        listener_insert = """

  const tabAssignmentsBtn = document.getElementById("tab-assignments-btn");
  if (tabAssignmentsBtn) {
    tabAssignmentsBtn.onclick = () => {
      currentTab = "assignments";
      renderDashboard(container, stats, requests, users);
      loadAndRenderAssignments(users);
    };
  }
  if (currentTab === "assignments") {
    loadAndRenderAssignments(users);
  }"""
        admin_code = admin_code[:brace_close] + listener_insert + admin_code[brace_close:]

# Append assignment helper functions if not present
if "function renderAssignmentsTabPlaceholder" not in admin_code:
    assignment_funcs = """

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
"""
    admin_code += assignment_funcs

with open(admin_view_path, "w", encoding="utf-8") as f:
    f.write(admin_code)
print("[+] AdminManagementView.js successfully updated with Resource Assignments tab!")

# --- 2. ResourcesView.js Enhancement ---
with open(resources_view_path, "r", encoding="utf-8") as f:
    res_code = f.read()

# Add diagnostics modal trigger helper
if "openDiagnosticModal" not in res_code:
    diag_funcs = """

async function openDiagnosticModal(hostId, hostname) {
  openModal(`Predefined Diagnostics Console — ${escapeHtml(hostname || 'Host #' + hostId)}`, `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      <!-- Action Selection Card -->
      <div class="panel" style="padding: 14px;">
        <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 10px;">
          Select Predefined Diagnostic Action
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr auto; gap: 10px; align-items: end;">
          <div>
            <label style="font-size: 10.5px; color: var(--text-muted);">ACTION</label>
            <select id="diag-action-select" class="select-control" style="width: 100%;">
              <option value="PING_GATEWAY">PING_GATEWAY (Network Reachability)</option>
              <option value="DNS_LOOKUP">DNS_LOOKUP (Name Resolution)</option>
              <option value="SYSTEM_SUMMARY">SYSTEM_SUMMARY (Hardware & OS Status)</option>
              <option value="SCHEDULED_TASK_STATUS">SCHEDULED_TASK_STATUS (Sensor Task Health)</option>
              <option value="SERVICE_STATUS">SERVICE_STATUS (Windows Core Services)</option>
            </select>
          </div>

          <div>
            <label style="font-size: 10.5px; color: var(--text-muted);">TARGET / PARAMETER</label>
            <input type="text" id="diag-target-input" class="input-control" placeholder="e.g. 127.0.0.1 or localhost" style="width: 100%;">
          </div>

          <div>
            <button class="btn btn-primary" id="btn-dispatch-diag" style="display: flex; align-items: center; gap: 6px;">
              ${renderIcon("play", { size: "xs" })} Dispatch Diagnostic
            </button>
          </div>
        </div>
        <div id="diag-validation-error" style="display: none; margin-top: 8px; color: var(--critical); font-size: 11px;"></div>
      </div>

      <!-- Execution Output Box -->
      <div class="panel" style="padding: 14px; background: #0a0d14;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-secondary);">Command Output Terminal</span>
            <span id="diag-status-pill" class="badge badge-info" style="font-size: 10px;">IDLE</span>
          </div>
          <span id="diag-exec-time" class="mono text-muted" style="font-size: 11px;">—</span>
        </div>

        <pre id="diag-output-console" class="mono" style="margin: 0; padding: 12px; background: #000; border-radius: var(--radius-sm); color: #00ff66; font-size: 11.5px; min-height: 140px; max-height: 220px; overflow-y: auto; white-space: pre-wrap; word-break: break-all;">Awaiting diagnostic dispatch...</pre>
      </div>

      <!-- Past Diagnostics on Host -->
      <div>
        <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 6px;">Recent Diagnostics on this Host</div>
        <div id="diag-history-mount" style="max-height: 120px; overflow-y: auto;">
          <div class="text-muted" style="font-size: 11px; text-align: center; padding: 10px;">Loading historical diagnostics...</div>
        </div>
      </div>
    </div>
  `);

  const actionSelect = document.getElementById("diag-action-select");
  const targetInput = document.getElementById("diag-target-input");
  const dispatchBtn = document.getElementById("btn-dispatch-diag");
  const statusPill = document.getElementById("diag-status-pill");
  const execTime = document.getElementById("diag-exec-time");
  const consoleBox = document.getElementById("diag-output-console");
  const errorBox = document.getElementById("diag-validation-error");
  const historyMount = document.getElementById("diag-history-mount");

  // Load past diagnostics
  const refreshHistory = async () => {
    try {
      const history = await api.getDiagnosticHistory(hostId, null, 5);
      if (history.length === 0) {
        historyMount.innerHTML = `<div class="text-muted" style="font-size: 11px; text-align: center; padding: 8px;">No past diagnostics run on this host.</div>`;
      } else {
        historyMount.innerHTML = `
          <div style="display: flex; flex-direction: column; gap: 4px;">
            ${history.map(h => `
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; background: var(--bg-surface-elevated); border-radius: 4px; font-size: 11px;">
                <span class="mono" style="font-weight: 600;">${escapeHtml(h.action)}</span>
                <span class="badge ${h.status === 'COMPLETED' ? 'badge-healthy' : (h.status === 'FAILED' ? 'badge-critical' : 'badge-info')}" style="font-size: 10px;">${escapeHtml(h.status)}</span>
                <span class="mono text-muted">${formatTimestamp(h.created_at)}</span>
              </div>
            `).join("")}
          </div>
        `;
      }
    } catch (e) {
      historyMount.innerHTML = `<div class="text-muted" style="font-size: 11px;">Unable to load history.</div>`;
    }
  };

  refreshHistory();

  // Dispatch handler
  if (dispatchBtn) {
    dispatchBtn.onclick = async () => {
      const action = actionSelect.value;
      const target = targetInput.value.trim() || null;
      errorBox.style.display = "none";
      dispatchBtn.disabled = true;
      statusPill.className = "badge badge-info";
      statusPill.textContent = "DISPATCHING";
      consoleBox.textContent = `[*] Dispatching predefined diagnostic '${action}' to host #${hostId}...\\n`;

      try {
        const cmd = await api.dispatchDiagnostic(hostId, action, target, 30);
        statusPill.textContent = "PENDING CLAIM";
        consoleBox.textContent += `[+] Diagnostic registered with UUID: ${cmd.id}\\n[*] Waiting for agent to claim and execute...\\n`;

        // Poll command status for up to 30 seconds
        const startTime = Date.now();
        const pollInterval = setInterval(async () => {
          try {
            const updated = await api.getDiagnosticCommand(cmd.id);
            const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
            execTime.textContent = `${elapsed}s`;

            if (updated.status === "CLAIMED") {
              statusPill.textContent = "CLAIMED (RUNNING)";
              statusPill.className = "badge badge-warning";
            } else if (updated.status === "COMPLETED" || updated.status === "FAILED" || updated.status === "TIMED_OUT") {
              clearInterval(pollInterval);
              dispatchBtn.disabled = false;
              statusPill.textContent = updated.status;
              statusPill.className = updated.status === "COMPLETED" ? "badge badge-healthy" : "badge badge-critical";

              if (updated.result) {
                consoleBox.textContent = `=== DIAGNOSTIC EXECUTION RESULT (Exit Code: ${updated.result.exit_code}) ===\\n` +
                  (updated.result.stdout ? `--- STDOUT ---\\n${updated.result.stdout}\\n` : "") +
                  (updated.result.stderr ? `--- STDERR ---\\n${updated.result.stderr}\\n` : "");
              } else {
                consoleBox.textContent += `[-] Finished with status: ${updated.status} (${updated.failure_reason || 'No output recorded'})\\n`;
              }
              refreshHistory();
            }
          } catch (pollErr) {
            clearInterval(pollInterval);
            dispatchBtn.disabled = false;
          }
        }, 1500);

      } catch (err) {
        dispatchBtn.disabled = false;
        statusPill.className = "badge badge-critical";
        statusPill.textContent = "ERROR";
        errorBox.style.display = "block";
        errorBox.textContent = err.message || "Failed to dispatch diagnostic.";
        consoleBox.textContent += `[!] Error: ${err.message}\\n`;
      }
    };
  }
}
"""
    res_code += diag_funcs

# Add "Run Diagnostics" button in openHostDetailsModal
if 'id="modal-run-diag-btn"' not in res_code:
    # Insert next to Live Resource Gauge
    anchor = '<h4 style="font-size: 12px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 8px;">Live Resource Gauge</h4>'
    diag_button_html = """
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <h4 style="font-size: 12px; text-transform: uppercase; color: var(--text-secondary); margin: 0;">Remote Diagnostics & Operations</h4>
          <button class="btn btn-sm btn-primary" id="modal-run-diag-btn" style="display: flex; align-items: center; gap: 6px;">
            ${renderIcon("terminal", { size: "xs" })} Run Diagnostics
          </button>
        </div>"""
    res_code = res_code.replace(anchor, diag_button_html + "\n\n        " + anchor)

    # Attach listener inside openHostDetailsModal
    listener_anchor = 'openModal(`Host Telemetry & Details (ID: ${hostId})`'
    modal_event_insert = """
    setTimeout(() => {
      const diagBtn = document.getElementById("modal-run-diag-btn");
      if (diagBtn) {
        diagBtn.onclick = () => openDiagnosticModal(hostId, host.hostname);
      }
    }, 50);
"""
    idx_modal = res_code.find("openModal(`Host Telemetry & Details")
    if idx_modal != -1:
        # Find closing of try block or after openModal
        res_code = res_code[:idx_modal] + modal_event_insert + res_code[idx_modal:]

with open(resources_view_path, "w", encoding="utf-8") as f:
    f.write(res_code)
print("[+] ResourcesView.js successfully updated with Diagnostics Modal!")

