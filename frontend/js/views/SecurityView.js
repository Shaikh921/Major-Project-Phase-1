/**
 * Security View - Security Operation Center (SOC) & Intrusion Detection (Module 4).
 */

import { api } from "../api.js";
import { escapeHtml, formatRelativeTime, formatTimestamp, maskSensitive } from "../sanitizer.js";
import { renderStatusBadge, renderSeverityBadge } from "../components/StatusBadge.js";
import { renderIcon } from "../components/Icons.js";

export async function renderSecurityView(container) {
  container.innerHTML = `
    <div class="state-container">
      <div class="state-icon">${renderIcon("loader", { size: "xl", className: "icon-spin" })}</div>
      <div class="state-title">Loading Security Telemetry & Threat Stream...</div>
    </div>
  `;

  try {
    const [summary, events] = await Promise.all([
      api.getSecuritySummary().catch(() => ({ total_events: 0, critical_events: 0, high_events: 0, open_incidents: 0 })),
      api.getSecurityEvents({ limit: 50 }).catch(() => []),
    ]);

    container.innerHTML = `
      <div class="view-header">
        <div class="view-title-group">
          <h1>Security Operations Center (SOC) & Threat Detection</h1>
          <p>Real-time network flow inspection, authentication threat logging, and intrusion detection (M4).</p>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-sm" id="security-refresh-btn">
            ${renderIcon("refresh-cw", { size: "sm" })} Refresh
          </button>
        </div>
      </div>

      <!-- Security Status Summary Cards -->
      <div class="summary-grid">
        <div class="summary-card ${summary.critical_events > 0 ? 'status-critical' : 'status-healthy'}">
          <div class="summary-card-header">
            <span>Critical Threats</span>
            <span class="badge badge-critical">IMMEDIATE</span>
          </div>
          <div class="summary-card-value">${summary.critical_events}</div>
          <div class="summary-card-sub">
            <span>Data exfiltration / high-risk exploits</span>
          </div>
        </div>

        <div class="summary-card ${summary.high_events > 0 ? 'status-warning' : 'status-info'}">
          <div class="summary-card-header">
            <span>High Severity</span>
            <span class="badge badge-warning">ELEVATED</span>
          </div>
          <div class="summary-card-value">${summary.high_events}</div>
          <div class="summary-card-sub">
            <span>Brute-force & unauthorized privilege attempts</span>
          </div>
        </div>

        <div class="summary-card status-info">
          <div class="summary-card-header">
            <span>Total Tracked Incidents</span>
            <span class="mono">Audit Trail</span>
          </div>
          <div class="summary-card-value">${summary.total_events}</div>
          <div class="summary-card-sub">
            <span>${summary.open_incidents} currently open/active</span>
          </div>
        </div>
      </div>

      <!-- Threat Events Table -->
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">${renderIcon("shield", { size: "sm" })} Intrusion & Security Event Log (${events.length})</span>
          <span class="text-muted mono" style="font-size: 11px;">Append-Only Tamper-Evident Stream</span>
        </div>

        <div class="table-container">
          <table class="ops-table">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Event Type</th>
                <th>Target Resource</th>
                <th>Source IP</th>
                <th>Port</th>
                <th>Description</th>
                <th>Status</th>
                <th>Detected</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${events.length === 0 ? `
                <tr><td colspan="9" class="text-muted" style="text-align: center; padding: 24px;">No security threats or intrusion signatures detected.</td></tr>
              ` : events.map(e => `
                <tr>
                  <td>${renderSeverityBadge(e.severity)}</td>
                  <td class="mono" style="font-weight: 600;">${escapeHtml(e.event_type)}</td>
                  <td class="mono">${escapeHtml(e.hostname || (e.host_id ? `Host-${e.host_id}` : 'Perimeter Gateway'))}</td>
                  <td class="mono">${escapeHtml(e.source_ip || '—')}</td>
                  <td class="mono">${escapeHtml(e.destination_port || '—')}</td>
                  <td style="max-width: 260px;">${escapeHtml(e.description)}</td>
                  <td>${renderStatusBadge(e.status)}</td>
                  <td class="mono text-muted" style="font-size: 11px;">${formatRelativeTime(e.timestamp)}</td>
                  <td>
                    <div style="display: flex; gap: 4px;">
                      ${e.status === 'open' ? `
                        <button class="btn btn-sm" onclick="setSecStatus(${e.id}, 'investigating')">Investigate</button>
                        <button class="btn btn-sm btn-primary" onclick="setSecStatus(${e.id}, 'mitigated')">Mitigate</button>
                      ` : `
                        <span class="text-muted mono" style="font-size: 10.5px;">CLOSED</span>
                      `}
                    </div>
                  </td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;

    const refreshBtn = document.getElementById("security-refresh-btn");
    if (refreshBtn) refreshBtn.onclick = () => renderSecurityView(container);

    window.setSecStatus = async (id, status) => {
      try {
        await api.updateSecurityStatus(id, status);
        renderSecurityView(container);
      } catch (err) {
        alert(`Failed to update status: ${err.message}`);
      }
    };

  } catch (err) {
    container.innerHTML = `
      <div class="state-container">
        <div class="state-icon text-critical">${renderIcon("triangle-alert", { size: "xl" })}</div>
        <div class="state-title">Failed to load security view</div>
        <div class="state-desc">${escapeHtml(err.message)}</div>
      </div>
    `;
  }
}
