/**
 * Reports View - Executive & Operational Summary Generator.
 * Supports on-demand multi-domain aggregation with professional A4 print/PDF layout.
 */

import { api } from "../api.js";
import { currencyManager } from "../currency.js";
import { escapeHtml, formatTimestamp, formatRelativeTime } from "../sanitizer.js";
import { renderIcon } from "../components/Icons.js";

function getStatusBadgeClass(status) {
  const s = String(status || "").toLowerCase();
  if (s.includes("healthy") || s.includes("secure") || s.includes("savings") || s.includes("online")) {
    return "badge-healthy";
  }
  if (s.includes("degraded") || s.includes("critical") || s.includes("offline")) {
    return "badge-critical";
  }
  if (s.includes("warning") || s.includes("flagged") || s.includes("events detected")) {
    return "badge-warning";
  }
  return "badge-info";
}

export async function renderReportsView(container) {
  container.innerHTML = `
    <div class="view-header">
      <div class="view-title-group">
        <h1>Executive & Technical Operational Reports</h1>
        <p>Synthesize on-demand cross-module incident, security posture, and resource efficiency summaries.</p>
      </div>
    </div>

    <!-- Controls Bar -->
    <div class="report-controls-bar no-print">
      <div class="report-controls-group">
        <label for="report-horizon-select" style="font-size: 12px; font-weight: 600; color: var(--text-secondary);">Reporting Horizon:</label>
        <select id="report-horizon-select" class="select-control" style="font-size: 12px; padding: 4px 8px;">
          <option value="6">Last 6 Hours</option>
          <option value="12">Last 12 Hours</option>
          <option value="24" selected>Last 24 Hours</option>
          <option value="48">Last 48 Hours</option>
          <option value="168">Last 7 Days (168h)</option>
        </select>

        <label for="report-env-select" style="font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-left: 8px;">Environment Scope:</label>
        <select id="report-env-select" class="select-control" style="font-size: 12px; padding: 4px 8px;">
          <option value="All Environments" selected>All Environments</option>
          <option value="lab">lab (Physical Nodes)</option>
          <option value="production">production</option>
          <option value="staging">staging</option>
        </select>

        <label for="report-offline-thresh" style="font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-left: 8px;">Heartbeat Threshold:</label>
        <select id="report-offline-thresh" class="select-control" style="font-size: 12px; padding: 4px 8px;">
          <option value="60">60 seconds</option>
          <option value="90" selected>90 seconds (Standard)</option>
          <option value="180">180 seconds</option>
          <option value="300">300 seconds</option>
        </select>
      </div>

      <div class="report-controls-group">
        <button class="btn btn-primary btn-sm" id="gen-report-btn">
          ${renderIcon("file-text", { size: "xs" })} Generate Operational Report
        </button>
      </div>
    </div>

    <!-- Report View Output Container -->
    <div id="report-output-container">
      <div class="panel" style="padding: 40px 20px; text-align: center;">
        <div class="state-container">
          <div class="state-icon">${renderIcon("file-text", { size: "xl" })}</div>
          <div class="state-title">Ready to Generate Operational Report</div>
          <p class="state-desc">Configure the time horizon and environment scope above, then click 'Generate Operational Report' to synthesize fleet telemetry, incidents, security events, and cost analytics.</p>
        </div>
      </div>
    </div>
  `;

  const genBtn = document.getElementById("gen-report-btn");
  const horizonSelect = document.getElementById("report-horizon-select");
  const envSelect = document.getElementById("report-env-select");
  const threshSelect = document.getElementById("report-offline-thresh");
  const outputContainer = document.getElementById("report-output-container");

  const runReport = async () => {
    const hours = parseInt(horizonSelect?.value || "24", 10);
    const envVal = envSelect?.value || "All Environments";
    const thresholdSec = parseInt(threshSelect?.value || "90", 10);

    outputContainer.innerHTML = `
      <div class="panel" style="padding: 40px 20px; text-align: center;">
        <div class="state-container">
          <div class="state-icon">${renderIcon("loader", { size: "xl", className: "icon-spin" })}</div>
          <div class="state-title">Synthesizing multi-domain telemetry & security audit...</div>
          <p class="state-desc">Aggregating telemetry heartbeats, active incidents, and catalog cost efficiency across ${escapeHtml(envVal)}.</p>
        </div>
      </div>
    `;

    try {
      const rep = await api.generateReport(hours, envVal, thresholdSec);
      const rateMeta = currencyManager.getRateMetadata();

      const freshnessText = rep.data_freshness_timestamp
        ? `${formatTimestamp(rep.data_freshness_timestamp)} (${formatRelativeTime(rep.data_freshness_timestamp)})`
        : "No Ingested Telemetry";

      outputContainer.innerHTML = `
        <!-- Print Trigger Bar (Hidden during print) -->
        <div class="no-print" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
          <div style="font-size: 12.5px; color: var(--text-secondary);">
            Generated report <strong>${escapeHtml(rep.report_id)}</strong> ready for review or export.
          </div>
          <button class="btn btn-primary btn-sm" id="export-pdf-btn">
            ${renderIcon("printer", { size: "xs" })} Export PDF / Print (A4)
          </button>
        </div>

        <!-- Printable Document Flow -->
        <div class="report-document" id="printable-report">
          <!-- Document Header -->
          <div class="report-doc-header">
            <div>
              <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); margin-bottom: 4px;">
                CloudOps Intel — SRE Command Center & Cloud Intelligence
              </div>
              <h1 class="report-doc-title">${escapeHtml(rep.title)}</h1>
              <div class="report-doc-subtitle">
                System Operational Health, Incident Triage, Security Posture, and Cost Efficiency Audit
              </div>
            </div>
            <div style="text-align: right;" class="no-print">
              <span class="badge ${rep.active_incidents_count === 0 ? 'badge-healthy' : 'badge-critical'}" style="font-size: 11px;">
                ${rep.active_incidents_count === 0 ? 'STATUS: HEALTHY' : `STATUS: ${rep.active_incidents_count} INCIDENTS`}
              </span>
            </div>
          </div>

          <!-- Metadata Strip -->
          <div class="report-meta-grid">
            <div class="report-meta-item">
              <span class="report-meta-label">Report ID</span>
              <span class="report-meta-val mono">${escapeHtml(rep.report_id)}</span>
            </div>
            <div class="report-meta-item">
              <span class="report-meta-label">Generated At</span>
              <span class="report-meta-val">${formatTimestamp(rep.generated_at)}</span>
            </div>
            <div class="report-meta-item">
              <span class="report-meta-label">Reporting Window</span>
              <span class="report-meta-val">${formatTimestamp(rep.time_window_start)}<br>→ ${formatTimestamp(rep.time_window_end)}</span>
            </div>
            <div class="report-meta-item">
              <span class="report-meta-label">Telemetry Freshness</span>
              <span class="report-meta-val">${escapeHtml(freshnessText)}</span>
            </div>
            <div class="report-meta-item">
              <span class="report-meta-label">Environment Scope</span>
              <span class="report-meta-val">${escapeHtml(rep.environment)}</span>
            </div>
            <div class="report-meta-item">
              <span class="report-meta-label">Heartbeat Threshold</span>
              <span class="report-meta-val">${rep.summary_metrics.offline_threshold_seconds || 90}s</span>
            </div>
            <div class="report-meta-item">
              <span class="report-meta-label">Display Currency</span>
              <span class="report-meta-val">${escapeHtml(rateMeta.displayCurrency || 'USD')}${rateMeta.isConverted ? ` (@ ${escapeHtml(rateMeta.rateFormatted)})` : ''}</span>
            </div>
            <div class="report-meta-item">
              <span class="report-meta-label">Audit Authorization</span>
              <span class="report-meta-val">Verified SRE / Viewer</span>
            </div>
          </div>

          <!-- Executive KPI Grid -->
          <div class="report-kpi-grid">
            <div class="report-kpi-card">
              <div class="report-kpi-title">Monitored Fleet</div>
              <div class="report-kpi-val">${rep.summary_metrics.total_hosts}</div>
              <div class="report-kpi-sub">
                <strong style="color: var(--color-healthy, #10b981);">${rep.online_hosts_count}</strong> Online | 
                <strong style="color: var(--color-warning, #f59e0b);">${rep.offline_hosts_count}</strong> Offline | 
                <strong>${rep.unseen_hosts_count}</strong> No Telemetry
              </div>
            </div>

            <div class="report-kpi-card">
              <div class="report-kpi-title">Active Incidents</div>
              <div class="report-kpi-val ${rep.active_incidents_count > 0 ? 'text-critical' : 'text-healthy'}">${rep.active_incidents_count}</div>
              <div class="report-kpi-sub">
                ${rep.summary_metrics.critical_alerts || 0} Critical | ${rep.summary_metrics.warning_alerts || 0} Warning
              </div>
            </div>

            <div class="report-kpi-card">
              <div class="report-kpi-title">Security Events</div>
              <div class="report-kpi-val ${rep.security_events_count > 0 ? 'text-warning' : ''}">${rep.security_events_count}</div>
              <div class="report-kpi-sub">
                ${rep.security_events_count === 0 ? 'No Active Flags Detected' : 'Anomalous Signatures Detected'}
              </div>
            </div>

            <div class="report-kpi-card">
              <div class="report-kpi-title">Est. Savings (${escapeHtml(currencyManager.displayCurrency)})</div>
              <div class="report-kpi-val text-healthy">+${currencyManager.format(rep.potential_savings_usd)}/mo</div>
              <div class="report-kpi-sub">
                Est. Monthly Spend: ${currencyManager.format(rep.estimated_monthly_spend_usd)}
              </div>
            </div>
          </div>

          <!-- Section 1: Monitored Endpoint Inventory & Health Triage -->
          <div class="report-section">
            <div class="report-section-heading">1. Monitored Fleet Inventory & Node Liveness Triage</div>
            <div class="report-table-wrapper">
              <table class="report-table">
                <thead>
                  <tr>
                    <th>Host / Node Name</th>
                    <th>IP Address</th>
                    <th>Environment</th>
                    <th>Room / Region</th>
                    <th>Liveness Status</th>
                    <th>Last Heartbeat</th>
                    <th>CPU %</th>
                    <th>RAM %</th>
                    <th>Disk %</th>
                  </tr>
                </thead>
                <tbody>
                  ${(rep.host_inventories && rep.host_inventories.length > 0)
                    ? rep.host_inventories.map(h => `
                      <tr>
                        <td class="mono" style="font-weight: 600;">${escapeHtml(h.hostname)}</td>
                        <td class="mono">${escapeHtml(h.ip_address || "—")}</td>
                        <td>${escapeHtml(h.environment)}</td>
                        <td>${escapeHtml(h.room || "—")}</td>
                        <td>
                          <span class="badge ${
                            h.status === 'ONLINE' ? 'badge-healthy' :
                            h.status === 'OFFLINE' ? 'badge-warning' : 'badge-info'
                          }">
                            ${h.status === 'NO_DATA' ? 'NO DATA' : escapeHtml(h.status)}
                          </span>
                        </td>
                        <td style="font-size: 11px;">
                          ${h.last_seen ? `${formatTimestamp(h.last_seen)} (${formatRelativeTime(h.last_seen)})` : '<span class="text-muted">No telemetry</span>'}
                        </td>
                        <td class="mono">${h.cpu_percent !== null ? `${h.cpu_percent}%` : '<span class="text-muted">—</span>'}</td>
                        <td class="mono">${h.memory_percent !== null ? `${h.memory_percent}%` : '<span class="text-muted">—</span>'}</td>
                        <td class="mono">${h.disk_percent !== null ? `${h.disk_percent}%` : '<span class="text-muted">—</span>'}</td>
                      </tr>
                    `).join("")
                    : `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 18px;">No monitored host nodes registered in this scope.</td></tr>`
                  }
                </tbody>
              </table>
            </div>
          </div>

          <!-- Section 2: Domain Findings & Operational Analysis -->
          <div class="report-section">
            <div class="report-section-heading">2. Multi-Domain Findings & Operational Observations</div>
            <div style="display: flex; flex-direction: column; gap: 10px;">
              ${rep.sections.map(sec => `
                <div class="report-findings-card">
                  <div class="report-findings-top">
                    <span style="font-size: 13px; font-weight: 700; color: var(--text-primary);">${escapeHtml(sec.section_title)}</span>
                    <span class="badge ${getStatusBadgeClass(sec.status)}">${escapeHtml(sec.status)}</span>
                  </div>
                  <div style="font-size: 12px; line-height: 1.45; color: var(--text-secondary);">${escapeHtml(sec.details)}</div>
                </div>
              `).join("")}
            </div>
          </div>

          <!-- Section 3: Technical Integrity & Security Audit Disclaimer -->
          <div class="report-section">
            <div class="report-section-heading">3. Technical Integrity, Liveness Model & Security Disclaimer</div>
            <div class="report-disclaimer-box">
              <strong>Technical Audit Notice:</strong> ${escapeHtml(rep.security_audit_disclaimer)}
              <br><br>
              <strong>Operational Liveness Model:</strong> Host liveness is dynamically evaluated against an active heartbeat cutoff threshold of 
              <strong>${rep.summary_metrics.offline_threshold_seconds || 90} seconds</strong> based on high-frequency telemetry samples. 
              Nodes exceeding this window without telemetry are marked <em>OFFLINE</em>. Metrics exhibiting '—' indicate missing or uningested 
              sensor samples and must not be misinterpreted as zero system utilization.
            </div>
          </div>

          <!-- Document Footer -->
          <div class="report-footer">
            <div>
              CloudOps Intel Observability Platform &bull; Automated SRE Verification &bull; Confidential
            </div>
            <div class="mono">
              Audit Ref: ${escapeHtml(rep.report_id)} &bull; Window: ${rep.summary_metrics.offline_threshold_seconds || 90}s cutoff
            </div>
          </div>
        </div>
      `;

      // Attach print handler
      const exportBtn = document.getElementById("export-pdf-btn");
      if (exportBtn) {
        exportBtn.onclick = () => window.print();
      }
    } catch (err) {
      outputContainer.innerHTML = `
        <div class="panel" style="padding: 24px; border-color: var(--color-critical);">
          <div style="display: flex; align-items: center; gap: 10px; color: var(--color-critical); margin-bottom: 8px;">
            ${renderIcon("alert-triangle", { size: "sm" })}
            <strong style="font-size: 14px;">Failed to Generate Report</strong>
          </div>
          <div style="font-size: 12.5px; color: var(--text-secondary);">${escapeHtml(err.message)}</div>
        </div>
      `;
    }
  };

  if (genBtn) genBtn.onclick = runReport;
}
