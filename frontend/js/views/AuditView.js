/**
 * Audit View - Administrative Action Log.
 */

import { api } from "../api.js";
import { escapeHtml, formatRelativeTime, formatTimestamp } from "../sanitizer.js";
import { renderIcon } from "../components/Icons.js";

export async function renderAuditView(container) {
  container.innerHTML = `
    <div class="state-container">
      <div class="state-icon">${renderIcon("loader", { size: "xl", className: "icon-spin" })}</div>
      <div class="state-title">Loading Administrative Audit Trail...</div>
    </div>
  `;

  try {
    const logs = await api.getAuditLogs();

    container.innerHTML = `
      <div class="view-header">
        <div class="view-title-group">
          <h1>Administrative Audit Log</h1>
          <p>Tamper-evident chronological audit records tracking operator actions, configuration changes, and incident triage.</p>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-sm" id="audit-refresh-btn">
            ${renderIcon("refresh-cw", { size: "sm" })} Refresh
          </button>
        </div>
      </div>

      <!-- Audit Log Table -->
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">${renderIcon("clipboard-list", { size: "sm" })} System Audit Records (${logs.length})</span>
          <span class="text-muted mono" style="font-size: 11px;">Append-Only Database Journal</span>
        </div>

        <div class="table-container">
          <table class="ops-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Operator</th>
                <th>Action</th>
                <th>Target Resource</th>
                <th>Details</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              ${logs.length === 0 ? `
                <tr><td colspan="6" class="text-muted" style="text-align: center; padding: 24px;">No administrative audit records logged yet.</td></tr>
              ` : logs.map(l => `
                <tr>
                  <td class="mono text-muted" style="font-size: 11px;">${formatTimestamp(l.timestamp)}</td>
                  <td class="mono" style="font-weight: 600;">${escapeHtml(l.user_email)}</td>
                  <td><span class="badge badge-info">${escapeHtml(l.action)}</span></td>
                  <td class="mono">${escapeHtml(l.target_resource)}</td>
                  <td style="max-width: 320px;">${escapeHtml(l.details)}</td>
                  <td><span class="text-healthy mono font-weight-bold">${escapeHtml(l.result.toUpperCase())}</span></td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;

    const refreshBtn = document.getElementById("audit-refresh-btn");
    if (refreshBtn) refreshBtn.onclick = () => renderAuditView(container);

  } catch (err) {
    container.innerHTML = `
      <div class="state-container">
        <div class="state-icon text-critical">${renderIcon("triangle-alert", { size: "xl" })}</div>
        <div class="state-title">Failed to load audit logs</div>
        <div class="state-desc">${escapeHtml(err.message)}</div>
      </div>
    `;
  }
}
