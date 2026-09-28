/**
 * Overview View - Operational Command Center.
 */

import { api } from "../api.js";
import { escapeHtml, formatRelativeTime, formatTimestamp } from "../sanitizer.js";
import { renderStatusBadge, renderSeverityBadge, renderSourceBadge } from "../components/StatusBadge.js";
import { renderSparkbar } from "../components/Sparkbar.js";
import { store } from "../config.js";
import { renderIcon } from "../components/Icons.js";

export async function renderOverviewView(container) {
  container.innerHTML = `
    <div class="state-container">
      <div class="state-icon">${renderIcon("loader", { size: "xl", className: "icon-spin" })}</div>
      <div class="state-title">Loading Operational Telemetry...</div>
    </div>
  `;

  try {
    const [summary, alerts, secSummary] = await Promise.all([
      api.getFleetSummary().catch(() => ({ total_hosts: 0, healthy_hosts: 0, hosts_with_warnings: 0, hosts_with_critical_alerts: 0, hosts: [] })),
      api.getAlerts({ limit: 10 }).catch(() => []),
      api.getSecuritySummary().catch(() => ({ open_incidents: 0, critical_events: 0, recent_events: [] })),
    ]);

    const activeAlerts = alerts.filter(a => a.status === "active");
    const isDegraded = summary.hosts_with_critical_alerts > 0 || secSummary.critical_events > 0;
    const realCount = (summary.hosts || []).filter(h => h.source_type === "REAL_AGENT").length;
    const simCount = (summary.hosts || []).filter(h => h.source_type === "SIMULATED").length;

    container.innerHTML = `
      <div class="view-header">
        <div class="view-title-group">
          <h1>Fleet Operations & Intelligence Overview</h1>
          <p>Real-time operational health, incident load, and cross-module telemetry across all clusters.</p>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-sm" id="overview-refresh-btn">
            ${renderIcon("refresh-cw", { size: "sm" })} Refresh Snapshot
          </button>
        </div>
      </div>

      <!-- Top Metric Summary Grid -->
      <div class="summary-grid">
        <div class="summary-card ${isDegraded ? 'status-critical' : 'status-healthy'}">
          <div class="summary-card-header">
            <span>System Status</span>
            ${renderStatusBadge(isDegraded ? "degraded" : "operational")}
          </div>
          <div class="summary-card-value">${isDegraded ? "DEGRADED" : "OPERATIONAL"}</div>
          <div class="summary-card-sub">
            <span>${realCount} real agent · ${simCount} simulated nodes</span>
          </div>
        </div>

        <div class="summary-card ${activeAlerts.length > 0 ? 'status-warning' : 'status-healthy'}">
          <div class="summary-card-header">
            <span>Active Incidents</span>
            <span class="mono">${activeAlerts.length} total</span>
          </div>
          <div class="summary-card-value">${activeAlerts.length}</div>
          <div class="summary-card-sub">
            <span class="text-critical">${summary.hosts_with_critical_alerts ?? summary.critical_hosts ?? 0} critical</span> · 
            <span class="text-warning">${summary.hosts_with_warnings ?? summary.warning_hosts ?? 0} warning</span>
          </div>
        </div>

        <div class="summary-card ${secSummary.open_incidents > 0 ? 'status-critical' : 'status-info'}">
          <div class="summary-card-header">
            <span>Security Threats</span>
            <span class="mono">SOC Stream</span>
          </div>
          <div class="summary-card-value">${secSummary.open_incidents}</div>
          <div class="summary-card-sub">
            <span class="text-critical">${secSummary.critical_events} critical</span> · 
            <span>${secSummary.recent_events.length} tracked events</span>
          </div>
        </div>

        <div class="summary-card status-ai">
          <div class="summary-card-header">
            <span>AI Anomaly Stream</span>
            <span class="badge badge-ai">LSTM + IF</span>
          </div>
          <div class="summary-card-value">${alerts.filter(a => a.kind === 'anomaly').length}</div>
          <div class="summary-card-sub">
            <span>Multivariate continuous scoring</span>
          </div>
        </div>
      </div>

      <!-- Two-Column Operations Layout -->
      <div class="overview-grid">
        <!-- Left: Live Infrastructure Health -->
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">${renderIcon("server", { size: "sm" })} Fleet Nodes Health Snapshot</span>
            <span class="text-muted" style="font-size: 11px;">Showing ${summary.hosts.length} nodes</span>
          </div>
          
          <div class="table-container">
            <table class="ops-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Source</th>
                  <th>Hostname</th>
                  <th>Env</th>
                  <th>CPU Usage</th>
                  <th>Memory</th>
                  <th>Disk</th>
                  <th>Last Seen</th>
                </tr>
              </thead>
              <tbody>
                ${summary.hosts.length === 0 ? `
                  <tr><td colspan="8" class="text-muted" style="text-align: center; padding: 24px;">No active hosts registered.</td></tr>
                ` : summary.hosts.map(h => {
                  const m = h.latest_metric || h.latest_metrics;
                  return `
                  <tr class="clickable host-row" data-host-id="${h.host_id}">
                    <td>${renderStatusBadge(h.status)}</td>
                    <td>${renderSourceBadge(h.source_type)}</td>
                    <td class="mono" style="font-weight: 600;">${escapeHtml(h.hostname)}</td>
                    <td><span class="badge badge-info">${escapeHtml(h.environment || 'default')}</span></td>
                    <td>${renderSparkbar(m ? m.cpu_percent : 0)}</td>
                    <td>${renderSparkbar(m ? m.memory_percent : 0)}</td>
                    <td>${renderSparkbar(m ? m.disk_percent : 0)}</td>
                    <td class="text-muted mono">${formatRelativeTime(h.last_seen)}</td>
                  </tr>
                `}).join("")}
              </tbody>
            </table>
          </div>
        </div>

        <!-- Right: Recent Incident Timeline -->
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">${renderIcon("zap", { size: "sm" })} Incident & Anomaly Timeline</span>
            <button class="btn btn-sm" id="view-all-incidents-btn">All Events ${renderIcon("arrow-right", { size: "xs" })}</button>
          </div>

          <div class="timeline-list">
            ${alerts.length === 0 ? `
              <div class="state-container" style="padding: 20px;">
                <span class="state-icon">${renderIcon("circle-check", { size: "xl", className: "text-healthy" })}</span>
                <span class="state-title" style="font-size: 13px;">No recent incidents</span>
                <p class="state-desc" style="font-size: 11px;">All metrics are running within nominal bounds.</p>
              </div>
            ` : alerts.slice(0, 5).map(a => `
              <div class="timeline-item ${escapeHtml(a.severity || 'info')}">
                <div class="timeline-header">
                  ${renderSeverityBadge(a.severity)}
                  <span class="timeline-time">${formatRelativeTime(a.created_at)}</span>
                  <span class="mono" style="color: var(--text-primary); font-weight: 600;">${escapeHtml(a.hostname || 'Host')}</span>
                </div>
                <div class="timeline-body">
                  ${escapeHtml(a.message)}
                </div>
              </div>
            `).join("")}
          </div>
        </div>
      </div>
    `;

    // Bind event listeners
    const refreshBtn = document.getElementById("overview-refresh-btn");
    if (refreshBtn) refreshBtn.onclick = () => renderOverviewView(container);

    const viewAllIncidents = document.getElementById("view-all-incidents-btn");
    if (viewAllIncidents) {
      viewAllIncidents.onclick = () => store.setState({ currentView: "incidents" });
    }

    const hostRows = container.querySelectorAll(".host-row");
    hostRows.forEach(row => {
      row.onclick = () => {
        const hostId = row.getAttribute("data-host-id");
        store.setState({ selectedHost: hostId, currentView: "resources" });
      };
    });

  } catch (err) {
    container.innerHTML = `
      <div class="state-container">
        <div class="state-icon text-critical">${renderIcon("triangle-alert", { size: "xl" })}</div>
        <div class="state-title">Failed to load overview data</div>
        <div class="state-desc">${escapeHtml(err.message)}</div>
        <button class="btn btn-primary" id="retry-overview-btn">Retry</button>
      </div>
    `;
    const retryBtn = document.getElementById("retry-overview-btn");
    if (retryBtn) retryBtn.onclick = () => renderOverviewView(container);
  }
}
