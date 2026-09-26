/**
 * Reports View - Executive & Operational Summary Generator.
 */

import { api } from "../api.js";
import { escapeHtml, formatTimestamp } from "../sanitizer.js";

export async function renderReportsView(container) {
  container.innerHTML = `
    <div class="view-header">
      <div class="view-title-group">
        <h1>Executive & Technical Operational Reports</h1>
        <p>Generate on-demand cross-module incident and resource efficiency summaries.</p>
      </div>
      <div>
        <button class="btn btn-primary btn-sm" id="gen-report-btn">📄 Generate 24h Report</button>
      </div>
    </div>

    <!-- Report View Container -->
    <div id="report-output-container" class="panel" style="display: flex; flex-direction: column; gap: 16px;">
      <div class="state-container" style="padding: 30px;">
        <div class="state-icon">📄</div>
        <div class="state-title">Ready to Generate Operational Report</div>
        <p class="state-desc">Click 'Generate 24h Report' above to synthesize active fleet telemetry, incidents, security audit, and cost analytics.</p>
      </div>
    </div>
  `;

  const genBtn = document.getElementById("gen-report-btn");
  const outputContainer = document.getElementById("report-output-container");

  const runReport = async () => {
    outputContainer.innerHTML = `
      <div class="state-container" style="padding: 30px;">
        <div class="state-icon">⏳</div>
        <div class="state-title">Synthesizing multi-domain telemetry...</div>
      </div>
    `;

    try {
      const rep = await api.generateReport(24);

      outputContainer.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid var(--border-subtle); padding-bottom: 12px;">
          <div>
            <h2 style="font-size: 16px; font-weight: 700; color: var(--text-primary);">${escapeHtml(rep.title)}</h2>
            <div class="mono text-muted" style="font-size: 11px;">
              Report ID: ${escapeHtml(rep.report_id)} | Generated: ${formatTimestamp(rep.generated_at)}
            </div>
          </div>
          <button class="btn btn-sm" onclick="window.print()">🖨️ Export PDF / Print</button>
        </div>

        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; background: var(--bg-surface-elevated); padding: 12px; border-radius: var(--radius-sm);">
          <div>
            <div class="text-muted" style="font-size: 10.5px;">MONITORED HOSTS</div>
            <div class="mono" style="font-size: 18px; font-weight: 700;">${rep.summary_metrics.total_hosts} (${rep.summary_metrics.active_hosts} active)</div>
          </div>
          <div>
            <div class="text-muted" style="font-size: 10.5px;">ACTIVE INCIDENTS</div>
            <div class="mono text-critical" style="font-size: 18px; font-weight: 700;">${rep.active_incidents_count}</div>
          </div>
          <div>
            <div class="text-muted" style="font-size: 10.5px;">SECURITY EVENTS</div>
            <div class="mono text-warning" style="font-size: 18px; font-weight: 700;">${rep.security_events_count}</div>
          </div>
          <div>
            <div class="text-muted" style="font-size: 10.5px;">ESTIMATED SAVINGS</div>
            <div class="mono text-healthy" style="font-size: 18px; font-weight: 700;">+$${rep.potential_savings_usd.toFixed(2)}/mo</div>
          </div>
        </div>

        <div style="display: flex; flex-direction: column; gap: 12px;">
          <h3 style="font-size: 13px; text-transform: uppercase; color: var(--text-secondary);">Section Findings</h3>
          ${rep.sections.map(sec => `
            <div class="panel" style="padding: 12px; background: var(--bg-surface-elevated);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-weight: 700; color: var(--text-primary);">${escapeHtml(sec.section_title)}</span>
                <span class="badge badge-info">${escapeHtml(sec.status)}</span>
              </div>
              <div style="font-size: 12.5px; color: var(--text-secondary);">${escapeHtml(sec.details)}</div>
            </div>
          `).join("")}
        </div>
      `;
    } catch (err) {
      outputContainer.innerHTML = `<div class="text-critical">${escapeHtml(err.message)}</div>`;
    }
  };

  if (genBtn) genBtn.onclick = runReport;
}
