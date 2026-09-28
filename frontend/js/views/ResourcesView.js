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
      <button class="btn btn-sm" onclick="(${closeModal})()">Close</button>
    `;

    openModal(`Host Telemetry: ${host.hostname}`, content, footer);

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
    <button class="btn btn-sm" onclick="(${closeModal})()">Cancel</button>
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
