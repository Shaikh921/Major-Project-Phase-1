/**
 * Resources / Infrastructure View - Searchable, Filterable Fleet Grid with Host Details Modal.
 */

import { api } from "../api.js";
import { escapeHtml, formatRelativeTime, formatTimestamp } from "../sanitizer.js";
import { renderStatusBadge, renderSourceBadge } from "../components/StatusBadge.js";
import { renderSparkbar } from "../components/Sparkbar.js";
import { openModal, closeModal } from "../components/Modal.js";
import { store } from "../config.js";
import { renderIcon } from "../components/Icons.js";

export async function renderResourcesView(container) {
  container.innerHTML = `
    <div class="state-container">
      <div class="state-icon">${renderIcon("loader", { size: "xl", className: "icon-spin" })}</div>
      <div class="state-title">Loading Infrastructure Inventory...</div>
    </div>
  `;

  try {
    const [hosts, summary] = await Promise.all([
      api.getHosts(),
      api.getFleetSummary().catch(() => ({ hosts: [] })),
    ]);

    // Map metrics and summary data to hosts
    const metricsMap = new Map();
    const summaryHostMap = new Map();
    for (const h of summary.hosts || []) {
      metricsMap.set(h.host_id, h.latest_metrics || h.latest_metric);
      summaryHostMap.set(h.host_id, h);
    }

    container.innerHTML = `
      <div class="view-header">
        <div class="view-title-group">
          <h1>Infrastructure & Monitored Fleet</h1>
          <p>Verified compute inventory, telemetry source classification (Real Agent vs. Simulation), and live utilization.</p>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-primary btn-sm" id="register-host-btn">${renderIcon("plus", { size: "xs" })} Register Host</button>
          <button class="btn btn-sm" id="resources-refresh-btn">${renderIcon("refresh-cw", { size: "sm" })} Refresh</button>
        </div>
      </div>

      <!-- Filter Bar -->
      <div class="panel" style="padding: 10px 14px; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
        <div style="display: flex; align-items: center; gap: 10px; flex: 1; flex-wrap: wrap;">
          <input type="text" id="host-filter-input" class="input-control" placeholder="Filter by hostname, IP, region..." style="width: 240px;">
          <select id="source-filter-select" class="select-control">
            <option value="all">All Sources</option>
            <option value="REAL_AGENT">Real Agent</option>
            <option value="SIMULATED">Simulated Fleet</option>
          </select>
          <select id="env-filter-select" class="select-control">
            <option value="all">All Environments</option>
            <option value="production">Production</option>
            <option value="staging">Staging</option>
            <option value="development">Development</option>
            <option value="local">Local</option>
          </select>
        </div>
        <div class="text-muted" style="font-size: 11.5px;">
          <span id="filtered-count">${hosts.length}</span> of ${hosts.length} nodes active
        </div>
      </div>

      <!-- Infrastructure Table -->
      <div class="table-container">
        <table class="ops-table" id="hosts-table">
          <thead>
            <tr>
              <th>Status</th>
              <th>Source</th>
              <th>Hostname</th>
              <th>IP Address</th>
              <th>Environment</th>
              <th>Instance Type</th>
              <th>Provider / Region</th>
              <th>CPU %</th>
              <th>Memory %</th>
              <th>Disk %</th>
              <th>Last Seen</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody id="hosts-table-body">
            ${hosts.map(h => {
      const m = metricsMap.get(h.id);
      const sumHost = summaryHostMap.get(h.id);
      const effectiveStatus = sumHost ? sumHost.status : (h.is_active ? "healthy" : "offline");
      const effectiveSource = h.source_type || (sumHost ? sumHost.source_type : "UNKNOWN");
      const effectiveLastSeen = (m && m.timestamp) || (sumHost && sumHost.last_seen) || h.updated_at;

      return `
                <tr class="host-item-row" data-hostname="${escapeHtml(h.hostname)}" data-ip="${escapeHtml(h.ip_address || '')}" data-env="${escapeHtml(h.environment || '')}" data-source="${escapeHtml(effectiveSource)}">
                  <td>${renderStatusBadge(effectiveStatus)}</td>
                  <td>${renderSourceBadge(effectiveSource)}</td>
                  <td class="mono" style="font-weight: 600;">${escapeHtml(h.hostname)}</td>
                  <td class="mono text-muted">${escapeHtml(h.ip_address || '—')}</td>
                  <td><span class="badge badge-info">${escapeHtml(h.environment || 'default')}</span></td>
                  <td class="mono" style="font-size: 11px;">${escapeHtml(h.instance_type || 'bare-metal')}</td>
                  <td class="text-secondary" style="font-size: 11px;">${escapeHtml(h.provider || 'bare-metal')} / ${escapeHtml(h.region || 'local')}</td>
                  <td>${renderSparkbar(m ? m.cpu_percent : 0)}</td>
                  <td>${renderSparkbar(m ? m.memory_percent : 0)}</td>
                  <td>${renderSparkbar(m ? m.disk_percent : 0)}</td>
                  <td class="text-muted mono" style="font-size: 11px;">${formatRelativeTime(effectiveLastSeen)}</td>
                  <td>
                    <button class="btn btn-sm view-host-btn" data-host-id="${h.id}">Details</button>
                  </td>
                </tr>
              `;
    }).join("")}
          </tbody>
        </table>
      </div>
    `;

    // Filter Logic
    const searchInput = document.getElementById("host-filter-input");
    const sourceSelect = document.getElementById("source-filter-select");
    const envSelect = document.getElementById("env-filter-select");
    const countDisplay = document.getElementById("filtered-count");

    const applyFilters = () => {
      const q = (searchInput ? searchInput.value : "").toLowerCase().trim();
      const sourceFilter = sourceSelect ? sourceSelect.value : "all";
      const env = envSelect ? envSelect.value : "all";
      const rows = container.querySelectorAll(".host-item-row");
      let visible = 0;

      rows.forEach(r => {
        const name = r.getAttribute("data-hostname").toLowerCase();
        const ip = r.getAttribute("data-ip").toLowerCase();
        const rowEnv = r.getAttribute("data-env").toLowerCase();
        const rowSource = r.getAttribute("data-source") || "UNKNOWN";

        const matchesQuery = !q || name.includes(q) || ip.includes(q);
        const matchesEnv = env === "all" || rowEnv === env;
        const matchesSource = sourceFilter === "all" || rowSource === sourceFilter;

        if (matchesQuery && matchesEnv && matchesSource) {
          r.style.display = "";
          visible++;
        } else {
          r.style.display = "none";
        }
      });
      if (countDisplay) countDisplay.textContent = visible;
    };

    if (searchInput) searchInput.oninput = applyFilters;
    if (sourceSelect) sourceSelect.onchange = applyFilters;
    if (envSelect) envSelect.onchange = applyFilters;

    const refreshBtn = document.getElementById("resources-refresh-btn");
    if (refreshBtn) refreshBtn.onclick = () => renderResourcesView(container);

    // View Details Modal
    container.querySelectorAll(".view-host-btn").forEach(btn => {
      btn.onclick = () => openHostDetailsModal(btn.getAttribute("data-host-id"));
    });

    // Register Host Modal
    const regBtn = document.getElementById("register-host-btn");
    if (regBtn) regBtn.onclick = openRegisterHostModal;

    // Check if store selected host
    if (store.selectedHost) {
      openHostDetailsModal(store.selectedHost);
      store.selectedHost = null;
    }

  } catch (err) {
    container.innerHTML = `
      <div class="state-container">
        <div class="state-icon text-critical">${renderIcon("triangle-alert", { size: "xl" })}</div>
        <div class="state-title">Failed to load infrastructure inventory</div>
        <div class="state-desc">${escapeHtml(err.message)}</div>
        <button class="btn btn-primary" id="retry-resources-btn">Retry</button>
      </div>
    `;
    const retryBtn = document.getElementById("retry-resources-btn");
    if (retryBtn) retryBtn.onclick = () => renderResourcesView(container);
  }
}

async function openHostDetailsModal(hostId) {

  openModal(`Host Telemetry & Details (ID: ${hostId})`, `
    <div class="state-container" style="padding: 20px;">
      <div class="state-icon">${renderIcon("loader", { size: "xl", className: "icon-spin" })}</div>
      <div class="state-title">Fetching host metrics...</div>
    </div>
  `);

  try {
    const [host, metricsResp, alerts] = await Promise.all([
      api.getHost(hostId),
      api.getHostMetrics(hostId, 30).catch(() => ({ time_series: [] })),
      api.getAlerts({ host_id: hostId, limit: 10 }).catch(() => []),
    ]);

    const latest = metricsResp.time_series && metricsResp.time_series.length > 0
      ? metricsResp.time_series[metricsResp.time_series.length - 1]
      : null;

    const content = `
      <div style="display: flex; flex-direction: column; gap: 14px;">
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; background: var(--bg-surface-elevated); padding: 12px; border-radius: var(--radius-sm);">
          <div>
            <div class="text-muted" style="font-size: 10.5px;">HOSTNAME</div>
            <div class="mono" style="font-weight: 600;">${escapeHtml(host.hostname)}</div>
          </div>
          <div>
            <div class="text-muted" style="font-size: 10.5px;">SOURCE TYPE</div>
            <div>${renderSourceBadge(host.source_type)}</div>
          </div>
          <div>
            <div class="text-muted" style="font-size: 10.5px;">ENVIRONMENT</div>
            <div><span class="badge badge-info">${escapeHtml(host.environment || 'default')}</span></div>
          </div>
          <div>
            <div class="text-muted" style="font-size: 10.5px;">STATUS</div>
            <div>${renderStatusBadge(host.status)}</div>
          </div>
          <div>
            <div class="text-muted" style="font-size: 10.5px;">IP ADDRESS</div>
            <div class="mono">${escapeHtml(host.ip_address || '—')}</div>
          </div>
          <div>
            <div class="text-muted" style="font-size: 10.5px;">INSTANCE TYPE</div>
            <div class="mono">${escapeHtml(host.instance_type || 'bare-metal')}</div>
          </div>
          <div style="grid-column: span 2;">
            <div class="text-muted" style="font-size: 10.5px;">TELEMETRY LINEAGE</div>
            <div class="mono" style="font-size: 11px; color: var(--text-primary);">
              ${host.source_type === 'REAL_AGENT' ? 'Real Host OS Kernel (psutil daemon)' : (host.source_type === 'SIMULATED' ? 'Synthetic Multi-Node Simulator (Testing Profile)' : 'Cloud Telemetry Feed')}
            </div>
          </div>
        </div>

        <div>
          
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <h4 style="font-size: 12px; text-transform: uppercase; color: var(--text-secondary); margin: 0;">Remote Diagnostics & Operations</h4>
          <button class="btn btn-sm btn-primary" id="modal-run-diag-btn" style="display: flex; align-items: center; gap: 6px;">
            ${renderIcon("terminal", { size: "xs" })} Run Diagnostics
          </button>
        </div>

        <h4 style="font-size: 12px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 8px;">Live Resource Gauge</h4>
          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
            <div class="panel" style="padding: 10px;">
              <div class="text-muted" style="font-size: 11px;">CPU UTILIZATION</div>
              <div style="font-size: 20px; font-weight: 700;" class="mono">${latest ? latest.cpu_percent.toFixed(1) : 0}%</div>
              ${renderSparkbar(latest ? latest.cpu_percent : 0)}
            </div>
            <div class="panel" style="padding: 10px;">
              <div class="text-muted" style="font-size: 11px;">MEMORY USAGE</div>
              <div style="font-size: 20px; font-weight: 700;" class="mono">${latest ? latest.memory_percent.toFixed(1) : 0}%</div>
              ${renderSparkbar(latest ? latest.memory_percent : 0)}
            </div>
            <div class="panel" style="padding: 10px;">
              <div class="text-muted" style="font-size: 11px;">DISK USAGE</div>
              <div style="font-size: 20px; font-weight: 700;" class="mono">${latest ? latest.disk_percent.toFixed(1) : 0}%</div>
              ${renderSparkbar(latest ? latest.disk_percent : 0)}
            </div>
          </div>
        </div>

        <div>
          <h4 style="font-size: 12px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 8px;">Host Incidents & Alerts (${alerts.length})</h4>
          ${alerts.length === 0 ? `
            <div class="text-muted" style="font-size: 11.5px; padding: 12px; background: var(--bg-surface-elevated); border-radius: var(--radius-sm); text-align: center;">
              No active or past alerts recorded for this host.
            </div>
          ` : `
            <div style="display: flex; flex-direction: column; gap: 6px; max-height: 160px; overflow-y: auto;">
              ${alerts.map(a => `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px; background: var(--bg-surface-elevated); border-radius: var(--radius-sm); font-size: 11.5px;">
                  <span>${escapeHtml(a.message)}</span>
                  <span class="mono text-muted">${formatRelativeTime(a.created_at)}</span>
                </div>
              `).join("")}
            </div>
          `}
        </div>
      </div>
    `;

    const footer = `
      <button class="btn btn-sm btn-critical" id="deactivate-host-btn">Deactivate Host</button>
      <button class="btn btn-sm btn-close-modal" id="modal-close-footer-btn">Close</button>
    `;

    openModal(`Host Telemetry: ${host.hostname}`, content, footer);

    // Attach Run Diagnostics button handler
    const diagBtn = document.getElementById("modal-run-diag-btn");
    if (diagBtn) {
      diagBtn.onclick = () => openDiagnosticModal(hostId, host.hostname);
    }

    // Attach Close button handler
    const closeFooterBtn = document.getElementById("modal-close-footer-btn");
    if (closeFooterBtn) {
      closeFooterBtn.onclick = closeModal;
    }

    const deactBtn = document.getElementById("deactivate-host-btn");
    if (deactBtn) {
      deactBtn.onclick = async () => {
        if (confirm(`Confirm deactivation of monitored host '${host.hostname}'?`)) {
          await api.deactivateHost(hostId);
          closeModal();
          renderResourcesView(document.getElementById("view-container"));
        }
      };
    }

  } catch (err) {
    openModal("Error", `<div class="text-critical">${escapeHtml(err.message)}</div>`);
  }
}

function openRegisterHostModal() {
  const content = `
    <form id="register-host-form" style="display: flex; flex-direction: column; gap: 12px;">
      <div>
        <label class="text-muted" style="font-size: 11px;">HOSTNAME *</label>
        <input type="text" id="reg-hostname" class="input-control" style="width: 100%;" required placeholder="e.g. prod-auth-01">
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
        <div>
          <label class="text-muted" style="font-size: 11px;">IP ADDRESS</label>
          <input type="text" id="reg-ip" class="input-control" style="width: 100%;" placeholder="e.g. 10.0.1.50">
        </div>
        <div>
          <label class="text-muted" style="font-size: 11px;">ENVIRONMENT</label>
          <select id="reg-env" class="select-control" style="width: 100%;">
            <option value="production">production</option>
            <option value="staging">staging</option>
            <option value="development">development</option>
          </select>
        </div>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
        <div>
          <label class="text-muted" style="font-size: 11px;">INSTANCE TYPE</label>
          <input type="text" id="reg-type" class="input-control" style="width: 100%;" value="t3.medium">
        </div>
        <div>
          <label class="text-muted" style="font-size: 11px;">PROVIDER / REGION</label>
          <input type="text" id="reg-region" class="input-control" style="width: 100%;" value="us-east-1">
        </div>
      </div>
    </form>
  `;

  const footer = `
    <button class="btn btn-sm" class="btn btn-sm btn-close-modal">Cancel</button>
    <button class="btn btn-primary btn-sm" id="submit-reg-btn">Register Host</button>
  `;

  openModal("Provision & Register Host", content, footer);

  const submitBtn = document.getElementById("submit-reg-btn");
  if (submitBtn) {
    submitBtn.onclick = async () => {
      const hostname = document.getElementById("reg-hostname").value.trim();
      const ip = document.getElementById("reg-ip").value.trim();
      const env = document.getElementById("reg-env").value;
      const type = document.getElementById("reg-type").value.trim();
      const region = document.getElementById("reg-region").value.trim();

      if (!hostname) {
        alert("Hostname is required.");
        return;
      }

      try {
        await api.registerHost({
          hostname,
          ip_address: ip || null,
          environment: env,
          instance_type: type,
          provider: "AWS",
          region: region,
        });
        closeModal();
        renderResourcesView(document.getElementById("view-container"));
      } catch (err) {
        alert(`Failed to register host: ${err.message}`);
      }
    };
  }
}


export async function openDiagnosticModal(hostId, hostname) {
  const safeHostname = hostname || ('Host #' + hostId);
  openModal(`Predefined Diagnostics Console — ${escapeHtml(safeHostname)}`, `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      <!-- Action Selection Card -->
      <div class="panel" style="padding: 14px;">
        <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 10px;">
          Select Predefined Diagnostic Action
        </div>
        <div style="display: grid; grid-template-columns: 1.1fr 1fr auto; gap: 10px; align-items: end;">
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

          <!-- Standard Diagnostic Target Input -->
          <div id="diag-standard-target-wrap">
            <label style="font-size: 10.5px; color: var(--text-muted);">TARGET / PARAMETER</label>
            <input type="text" id="diag-target-input" class="input-control" placeholder="e.g. 127.0.0.1 or localhost" style="width: 100%;">
          </div>

          <!-- Privileged Power Parameters (Hidden for Standard Actions) -->
          <div id="diag-power-param-wrap" style="display: none; display: flex; flex-direction: column; gap: 6px;">
            <div>
              <label style="font-size: 10.5px; color: var(--critical);">NOTIFICATION GRACE COUNTDOWN</label>
              <select id="diag-grace-select" class="select-control" style="width: 100%; border-color: rgba(239, 68, 68, 0.4);">
                <option value="30">30 Seconds Grace</option>
                <option value="60" selected>60 Seconds (Recommended)</option>
                <option value="120">2 Minutes Grace</option>
                <option value="300">5 Minutes Grace</option>
              </select>
            </div>
            <div>
              <label style="font-size: 10.5px; color: var(--text-muted);">REASON (FOR AUDIT LOG)</label>
              <input type="text" id="diag-reason-input" class="input-control" placeholder="e.g. Routine maintenance or system freeze" style="width: 100%;">
            </div>
          </div>

          <div>
            <button class="btn btn-primary" id="btn-dispatch-diag" style="display: flex; align-items: center; gap: 6px;">
              ${renderIcon("play", { size: "xs" })} Dispatch Diagnostic
            </button>
          </div>
        </div>
        <div id="diag-validation-error" style="display: none; margin-top: 8px; color: var(--critical); font-size: 11px;"></div>
      </div>

      <!-- Multi-Step Confirmation Panel for Power Operations -->
      <div id="power-confirm-panel" style="display: none; background: #FEF2F2; border: 1px solid #FECACA; border-radius: var(--radius-md); padding: 14px;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; color: var(--critical); font-weight: 700; font-size: 12px; text-transform: uppercase;">
          ${renderIcon("alert-triangle", { size: "sm" })}
          <span>Double Confirmation Required: High Impact Power Action</span>
        </div>
        <p style="font-size: 11.5px; line-height: 1.5; color: var(--text-secondary); margin-bottom: 10px;">
          You are about to remotely <strong id="power-action-name" style="color: var(--critical);">REBOOT</strong> physical machine
          <strong class="mono" style="color: var(--text-primary); font-weight: 700;">${escapeHtml(safeHostname)}</strong>. Active user sessions will be terminated and telemetry paused.
          Windows will show a system notification balloon for <strong id="power-grace-display" style="color: var(--text-primary); font-weight: 700;">60</strong> seconds before the power action executes.
        </p>
        <div style="margin-bottom: 12px;">
          <label style="font-size: 11px; font-weight: 600; color: var(--text-primary); display: block; margin-bottom: 4px;">
            To confirm, type the exact hostname <code class="mono" style="background: #F1F5F9; padding: 2px 6px; border-radius: 4px; color: var(--primary); border: 1px solid var(--border-default); user-select: all;">${escapeHtml(safeHostname)}</code> below:
          </label>
          <input type="text" id="power-confirm-input" class="input-control mono" placeholder="Type exact hostname here" style="width: 100%; border-color: var(--critical); font-weight: 600;" autocomplete="off">
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <button id="btn-cancel-power" class="btn btn-secondary btn-sm">Cancel</button>
          <button id="btn-execute-power" class="btn btn-critical btn-sm" disabled style="opacity: 0.5;">
            Confirm & Execute
          </button>
        </div>
      </div>

      <!-- Execution Output Box -->
      <div class="panel" style="padding: 14px; background: #FFFFFF; border: 1px solid var(--border-default);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-secondary);">Command Output Terminal</span>
            <span id="diag-status-pill" class="badge badge-info" style="font-size: 10px;">IDLE</span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <button id="btn-emergency-abort" class="btn btn-xs btn-critical" style="display: none; align-items: center; gap: 4px; font-weight: 700;">
              ${renderIcon("alert-triangle", { size: "xs" })} Emergency Abort (Cancel Shutdown)
            </button>
            <span id="diag-exec-time" class="mono text-muted" style="font-size: 11px;">—</span>
          </div>
        </div>

        <pre id="diag-output-console" class="mono" style="margin: 0; padding: 12px; background: #0F172A; border-radius: var(--radius-sm); color: #F1F5F9; border: 1px solid #334155; font-size: 11.5px; min-height: 140px; max-height: 220px; overflow-y: auto; white-space: pre-wrap; word-break: break-all;">Awaiting diagnostic dispatch...</pre>
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
  const standardWrap = document.getElementById("diag-standard-target-wrap");
  const powerWrap = document.getElementById("diag-power-param-wrap");
  const targetInput = document.getElementById("diag-target-input");
  const graceSelect = document.getElementById("diag-grace-select");
  const reasonInput = document.getElementById("diag-reason-input");
  const dispatchBtn = document.getElementById("btn-dispatch-diag");
  const statusPill = document.getElementById("diag-status-pill");
  const execTime = document.getElementById("diag-exec-time");
  const consoleBox = document.getElementById("diag-output-console");
  const errorBox = document.getElementById("diag-validation-error");
  const historyMount = document.getElementById("diag-history-mount");

  const confirmPanel = document.getElementById("power-confirm-panel");
  const confirmActionName = document.getElementById("power-action-name");
  const confirmGraceDisplay = document.getElementById("power-grace-display");
  const confirmInput = document.getElementById("power-confirm-input");
  const confirmCancelBtn = document.getElementById("btn-cancel-power");
  const confirmExecBtn = document.getElementById("btn-execute-power");
  const abortBtn = document.getElementById("btn-emergency-abort");

  // Dynamically load allowed actions according to user role and policy
  try {
    const allowedActions = await api.getDiagnosticActions();
    if (Array.isArray(allowedActions)) {
      const standardList = ["PING_GATEWAY", "DNS_LOOKUP", "SYSTEM_SUMMARY", "SCHEDULED_TASK_STATUS", "SERVICE_STATUS"];
      const powerList = ["REBOOT_HOST", "SHUTDOWN_HOST", "ABORT_SHUTDOWN"];

      let optionsHtml = `<optgroup label="Standard Diagnostics">`;
      standardList.forEach(act => {
        if (allowedActions.includes(act)) {
          optionsHtml += `<option value="${act}">${act}</option>`;
        }
      });
      optionsHtml += `</optgroup>`;

      const hasPower = powerList.some(act => allowedActions.includes(act));
      if (hasPower) {
        optionsHtml += `<optgroup label="Privileged Power Operations (Admin Only)">`;
        if (allowedActions.includes("REBOOT_HOST")) optionsHtml += `<option value="REBOOT_HOST">⚠️ REBOOT_HOST (Remote Reboot)</option>`;
        if (allowedActions.includes("SHUTDOWN_HOST")) optionsHtml += `<option value="SHUTDOWN_HOST">⛔ SHUTDOWN_HOST (Remote Shutdown)</option>`;
        if (allowedActions.includes("ABORT_SHUTDOWN")) optionsHtml += `<option value="ABORT_SHUTDOWN">🛡️ ABORT_SHUTDOWN (Cancel Pending Power Action)</option>`;
        optionsHtml += `</optgroup>`;
      }
      actionSelect.innerHTML = optionsHtml;
    }
  } catch (err) {
    // Keep defaults if network fails
  }

  // Handle action selection change
  const updateUiForAction = () => {
    const act = actionSelect.value;
    confirmPanel.style.display = "none";
    errorBox.style.display = "none";

    if (act === "REBOOT_HOST" || act === "SHUTDOWN_HOST") {
      standardWrap.style.display = "none";
      powerWrap.style.display = "flex";
      dispatchBtn.className = "btn btn-danger";
      dispatchBtn.innerHTML = `⚠️ Authorize Power Operation`;
    } else if (act === "ABORT_SHUTDOWN") {
      standardWrap.style.display = "none";
      powerWrap.style.display = "none";
      dispatchBtn.className = "btn btn-warning";
      dispatchBtn.innerHTML = `🛡️ Dispatch Emergency Abort`;
    } else {
      standardWrap.style.display = "block";
      powerWrap.style.display = "none";
      dispatchBtn.className = "btn btn-primary";
      dispatchBtn.innerHTML = `${renderIcon("play", { size: "xs" })} Dispatch Diagnostic`;
    }
  };

  actionSelect.onchange = updateUiForAction;
  updateUiForAction();

  // Hostname confirmation live input validator
  if (confirmInput) {
    confirmInput.oninput = () => {
      const match = confirmInput.value.trim().toLowerCase() === safeHostname.trim().toLowerCase();
      confirmExecBtn.disabled = !match;
      confirmExecBtn.style.opacity = match ? "1" : "0.5";
    };
  }

  if (confirmCancelBtn) {
    confirmCancelBtn.onclick = () => {
      confirmPanel.style.display = "none";
      confirmInput.value = "";
      confirmExecBtn.disabled = true;
      confirmExecBtn.style.opacity = "0.5";
    };
  }

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

  // Execution dispatch worker
  const executeDispatch = async (action, targetParam) => {
    errorBox.style.display = "none";
    dispatchBtn.disabled = true;
    confirmPanel.style.display = "none";
    statusPill.className = "badge badge-info";
    statusPill.textContent = "DISPATCHING";
    consoleBox.textContent = `[*] Dispatching diagnostic '${action}' to host #${hostId} (${safeHostname})...\n`;

    if (action === "REBOOT_HOST" || action === "SHUTDOWN_HOST") {
      abortBtn.style.display = "flex";
    }

    try {
      const cmd = await api.dispatchDiagnostic(hostId, action, targetParam, 30);
      statusPill.textContent = "PENDING CLAIM";
      consoleBox.textContent += `[+] Diagnostic registered with UUID: ${cmd.id}\n[*] Waiting for agent to claim and execute...\n`;

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
              consoleBox.textContent = `=== DIAGNOSTIC EXECUTION RESULT (Exit Code: ${updated.result.exit_code}) ===\n` +
                (updated.result.stdout ? `--- STDOUT ---\n${updated.result.stdout}\n` : "") +
                (updated.result.stderr ? `--- STDERR ---\n${updated.result.stderr}\n` : "");
            } else {
              consoleBox.textContent += `[-] Finished with status: ${updated.status} (${updated.failure_reason || 'No output recorded'})\n`;
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
      consoleBox.textContent += `[!] Error: ${err.message}\n`;
    }
  };

  // Emergency abort handler
  if (abortBtn) {
    abortBtn.onclick = async () => {
      consoleBox.textContent += `\n[!] Sending EMERGENCY ABORT signal to host #${hostId}...\n`;
      try {
        await api.dispatchDiagnostic(hostId, "ABORT_SHUTDOWN", JSON.stringify({ reason: "Emergency abort from console" }), 30);
        consoleBox.textContent += `[+] Emergency abort dispatched. Pending shutdown/reboot countdown cancelled!\n`;
        abortBtn.style.display = "none";
        refreshHistory();
      } catch (err) {
        consoleBox.textContent += `[!] Failed to send emergency abort: ${err.message}\n`;
      }
    };
  }

  // Primary Dispatch Click Handler
  if (dispatchBtn) {
    dispatchBtn.onclick = async () => {
      const action = actionSelect.value;

      if (action === "REBOOT_HOST" || action === "SHUTDOWN_HOST") {
        // Step 1: Open Double Confirmation Panel
        confirmActionName.textContent = action === "REBOOT_HOST" ? "REBOOT" : "SHUT DOWN";
        confirmGraceDisplay.textContent = graceSelect.value;
        confirmInput.value = "";
        confirmExecBtn.disabled = true;
        confirmExecBtn.style.opacity = "0.5";
        confirmPanel.style.display = "block";
        confirmInput.focus();
        return;
      }

      if (action === "ABORT_SHUTDOWN") {
        await executeDispatch(action, JSON.stringify({ reason: "Manual abort from diagnostics console" }));
        return;
      }

      // Standard diagnostic dispatch
      const target = targetInput.value.trim() || null;
      await executeDispatch(action, target);
    };
  }

  // Double Confirmation Button Click Handler
  if (confirmExecBtn) {
    confirmExecBtn.onclick = async () => {
      const action = actionSelect.value;
      const graceSeconds = parseInt(graceSelect.value, 10) || 60;
      const reason = reasonInput.value.trim() || "Administrative power operation";
      const payload = JSON.stringify({
        grace_seconds: graceSeconds,
        reason: reason,
      });

      await executeDispatch(action, payload);
    };
  }
}
