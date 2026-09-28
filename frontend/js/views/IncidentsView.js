/**
 * Incidents View - Chronological Incident Timeline & Triage.
 */

import { api } from "../api.js";
import { escapeHtml, formatRelativeTime, formatTimestamp } from "../sanitizer.js";
import { renderStatusBadge, renderSeverityBadge } from "../components/StatusBadge.js";
import { renderIcon } from "../components/Icons.js";

export async function renderIncidentsView(container) {
  container.innerHTML = `
    <div class="state-container">
      <div class="state-icon">${renderIcon("loader", { size: "xl", className: "icon-spin" })}</div>
      <div class="state-title">Loading Incident Stream...</div>
    </div>
  `;

  try {
    const alerts = await api.getAlerts({ limit: 50 });

    container.innerHTML = `
      <div class="view-header">
        <div class="view-title-group">
          <h1>Active Incidents & Degradation Timeline</h1>
          <p>Chronological incident progression, root cause triage, and resolution lifecycle.</p>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-sm" id="incidents-refresh-btn">
            ${renderIcon("refresh-cw", { size: "sm" })} Refresh
          </button>
        </div>
      </div>

      <!-- Incident Stream Panel -->
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">${renderIcon("zap", { size: "sm" })} Chronological Incident Stream (${alerts.length})</span>
          <span class="text-muted" style="font-size: 11px;">Sorted by occurrence time</span>
        </div>

        <div class="timeline-list">
          ${alerts.length === 0 ? `
            <div class="state-container" style="padding: 30px;">
              <span class="state-icon">${renderIcon("circle-check", { size: "xl", className: "text-healthy" })}</span>
              <span class="state-title">Zero Active Incidents</span>
              <p class="state-desc">All telemetry signals are within normal operating parameters.</p>
            </div>
          ` : alerts.map(a => `
            <div class="timeline-item ${escapeHtml(a.severity || 'info')}">
              <div class="timeline-header">
                ${renderSeverityBadge(a.severity)}
                ${renderStatusBadge(a.status)}
                <span class="timeline-time">${formatTimestamp(a.created_at)} (${formatRelativeTime(a.created_at)})</span>
                <span class="mono" style="font-weight: 600; color: var(--text-primary);">
                  ${escapeHtml(a.hostname || `Host-${a.host_id}`)}
                </span>
              </div>
              <div class="timeline-body" style="display: flex; justify-content: space-between; align-items: center; gap: 14px;">
                <div>
                  <div style="font-weight: 600; margin-bottom: 2px;">${escapeHtml(a.message)}</div>
                  <div class="text-muted mono" style="font-size: 11px;">
                    Metric: ${escapeHtml(a.metric)} | Value: ${a.value ? a.value.toFixed(1) : '—'}% | Threshold: ${a.threshold ? a.threshold.toFixed(1) : '—'}%
                  </div>
                </div>
                <div>
                  ${a.status === 'active' ? `
                    <button class="btn btn-sm" onclick="ackIncident(${a.id})">Acknowledge</button>
                  ` : `<span class="text-muted mono" style="font-size: 11px;">ACKED</span>`}
                </div>
              </div>
            </div>
          `).join("")}
        </div>
      </div>
    `;

    const refreshBtn = document.getElementById("incidents-refresh-btn");
    if (refreshBtn) refreshBtn.onclick = () => renderIncidentsView(container);

    window.ackIncident = async (id) => {
      try {
        await api.acknowledgeAlert(id);
        renderIncidentsView(container);
      } catch (err) {
        alert(`Failed to ack incident: ${err.message}`);
      }
    };

  } catch (err) {
    container.innerHTML = `
      <div class="state-container">
        <div class="state-icon text-critical">${renderIcon("triangle-alert", { size: "xl" })}</div>
        <div class="state-title">Failed to load incident stream</div>
        <div class="state-desc">${escapeHtml(err.message)}</div>
      </div>
    `;
  }
}
