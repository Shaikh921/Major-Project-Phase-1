/**
 * Reports View - SRE Observability & Performance Report Generator.
 * Provides two distinct reporting capabilities:
 * 1. Overall System Report — consolidated fleet telemetry, incidents, security & cost
 * 2. Individual Sensor / PC Report — dedicated workstation diagnostics, telemetry stats & charts
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
  // State variables
  let currentTab = "overall"; // "overall" | "sensor"
  let cachedHosts = [];
  let selectedHostId = null;

  container.innerHTML = `
    <div class="view-header">
      <div class="view-title-group">
        <h1>System & Sensor Operational Reports</h1>
        <p>Generate publication-grade PDF documentation and on-demand SRE telemetry audits across monitored infrastructure.</p>
      </div>
    </div>

    <!-- Mode Selector Tabs (Option A vs Option B) -->
    <div class="no-print" style="display: flex; gap: 8px; margin-bottom: 16px;">
      <button class="btn btn-sm ${currentTab === 'overall' ? 'btn-primary' : 'btn-secondary'}" id="tab-overall-btn" style="padding: 7px 16px; font-weight: 600;">
        ${renderIcon("server", { size: "xs" })} Option A: Overall System Report
      </button>
      <button class="btn btn-sm ${currentTab === 'sensor' ? 'btn-primary' : 'btn-secondary'}" id="tab-sensor-btn" style="padding: 7px 16px; font-weight: 600;">
        ${renderIcon("cpu", { size: "xs" })} Option B: Individual Sensor / PC Report
      </button>
    </div>

    <!-- Controls Panel: Option A (Overall Report) -->
    <div id="controls-overall-panel" class="report-controls-bar no-print">
      <div class="report-controls-group">
        <label for="report-horizon-select" style="font-size: 12px; font-weight: 600; color: var(--text-secondary);">Horizon:</label>
        <select id="report-horizon-select" class="select-control" style="font-size: 12px; padding: 4px 8px;">
          <option value="1">Last 1 Hour</option>
          <option value="6">Last 6 Hours</option>
          <option value="12">Last 12 Hours</option>
          <option value="24" selected>Last 24 Hours</option>
          <option value="48">Last 48 Hours</option>
          <option value="168">Last 7 Days (168h)</option>
          <option value="720">Last 30 Days (720h)</option>
        </select>

        <label for="report-env-select" style="font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-left: 8px;">Scope:</label>
        <select id="report-env-select" class="select-control" style="font-size: 12px; padding: 4px 8px;">
          <option value="All Environments" selected>All Environments</option>
          <option value="lab">lab (Physical Nodes)</option>
          <option value="production">production</option>
          <option value="staging">staging</option>
        </select>

        <label for="report-offline-thresh" style="font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-left: 8px;">Heartbeat Cutoff:</label>
        <select id="report-offline-thresh" class="select-control" style="font-size: 12px; padding: 4px 8px;">
          <option value="60">60 seconds</option>
          <option value="90" selected>90 seconds (Standard)</option>
          <option value="180">180 seconds</option>
          <option value="300">300 seconds</option>
        </select>
      </div>

      <div class="report-controls-group" style="gap: 8px;">
        <button class="btn btn-secondary btn-sm" id="gen-report-btn">
          ${renderIcon("eye", { size: "xs" })} Preview Report
        </button>
        <button class="btn btn-primary btn-sm" id="download-overall-pdf-btn">
          ${renderIcon("download", { size: "xs" })} Download Official PDF
        </button>
      </div>
    </div>

    <!-- Controls Panel: Option B (Individual Sensor Report) -->
    <div id="controls-sensor-panel" class="report-controls-bar no-print" style="display: none; flex-direction: column; gap: 12px; align-items: stretch;">
      <div style="display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between;">
        <div style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center; flex: 1;">
          <label for="sensor-host-search" style="font-size: 12px; font-weight: 600; color: var(--text-secondary);">Select Sensor / PC:</label>
          <input type="text" id="sensor-host-search" class="input-control" placeholder="Filter by name, IP, room..." style="font-size: 12px; padding: 4px 8px; width: 170px;" />

          <select id="sensor-host-select" class="select-control" style="font-size: 12px; padding: 4px 8px; min-width: 280px;">
            <option value="">Loading registered hosts from database...</option>
          </select>
        </div>

        <div style="display: flex; gap: 8px; align-items: center;">
          <label for="sensor-horizon-select" style="font-size: 12px; font-weight: 600; color: var(--text-secondary);">Period:</label>
          <select id="sensor-horizon-select" class="select-control" style="font-size: 12px; padding: 4px 8px;">
            <option value="1">Last 1 Hour</option>
            <option value="6">Last 6 Hours</option>
            <option value="12">Last 12 Hours</option>
            <option value="24" selected>Last 24 Hours</option>
            <option value="48">Last 48 Hours</option>
            <option value="168">Last 7 Days (168h)</option>
            <option value="720">Last 30 Days (720h)</option>
          </select>

          <button class="btn btn-secondary btn-sm" id="gen-sensor-report-btn">
            ${renderIcon("eye", { size: "xs" })} Preview Sensor Report
          </button>
          <button class="btn btn-primary btn-sm" id="download-sensor-pdf-btn">
            ${renderIcon("download", { size: "xs" })} Download Sensor PDF
          </button>
        </div>
      </div>

      <!-- Host Identification Strip -->
      <div id="sensor-selected-badge" style="display: none; padding: 8px 12px; background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: 4px; font-size: 12px;">
      </div>
    </div>

    <!-- Main Output Viewport -->
    <div id="report-output-container">
      <div class="panel" style="padding: 40px 20px; text-align: center;">
        <div class="state-container">
          <div class="state-icon">${renderIcon("file-text", { size: "xl" })}</div>
          <div class="state-title">Ready to Generate Operational Report</div>
          <p class="state-desc">Select either Option A (Overall Infrastructure) or Option B (Individual Sensor PC) above to synthesize telemetry and produce publication-ready PDF documentation.</p>
        </div>
      </div>
    </div>
  `;

  // DOM Elements
  const tabOverallBtn = document.getElementById("tab-overall-btn");
  const tabSensorBtn = document.getElementById("tab-sensor-btn");
  const controlsOverall = document.getElementById("controls-overall-panel");
  const controlsSensor = document.getElementById("controls-sensor-panel");
  const outputContainer = document.getElementById("report-output-container");

  const overallHorizonSelect = document.getElementById("report-horizon-select");
  const overallEnvSelect = document.getElementById("report-env-select");
  const overallThreshSelect = document.getElementById("report-offline-thresh");
  const genOverallBtn = document.getElementById("gen-report-btn");
  const downloadOverallPdfBtn = document.getElementById("download-overall-pdf-btn");

  const sensorSearchInput = document.getElementById("sensor-host-search");
  const sensorHostSelect = document.getElementById("sensor-host-select");
  const sensorHorizonSelect = document.getElementById("sensor-horizon-select");
  const sensorBadge = document.getElementById("sensor-selected-badge");
  const genSensorBtn = document.getElementById("gen-sensor-report-btn");
  const downloadSensorPdfBtn = document.getElementById("download-sensor-pdf-btn");

  // Load real hosts from backend
  async function loadHosts() {
    try {
      cachedHosts = await api.getHosts();
      cachedHosts.sort((a, b) => (a.hostname || "").localeCompare(b.hostname || ""));
      populateHostSelect(cachedHosts);
    } catch (err) {
      sensorHostSelect.innerHTML = `<option value="">Failed to load hosts: ${escapeHtml(err.message)}</option>`;
    }
  }

  function populateHostSelect(hosts) {
    if (!hosts || hosts.length === 0) {
      sensorHostSelect.innerHTML = `<option value="">No registered hosts found</option>`;
      sensorBadge.style.display = "none";
      return;
    }

    sensorHostSelect.innerHTML = hosts.map(h => `
      <option value="${h.id}">
        ${escapeHtml(h.hostname)} (ID: ${h.id}) — ${escapeHtml(h.ip_address || 'No IP')} [${escapeHtml(h.environment)}] ${h.region ? '• ' + escapeHtml(h.region) : ''}
      </option>
    `).join("");

    if (hosts.length > 0) {
      sensorHostSelect.value = String(hosts[0].id);
      selectedHostId = hosts[0].id;
      updateSelectedHostBadge(hosts[0]);
    }
  }

  function updateSelectedHostBadge(host) {
    if (!host) {
      sensorBadge.style.display = "none";
      return;
    }
    sensorBadge.style.display = "flex";
    sensorBadge.innerHTML = `
      <div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: center; width: 100%;">
        <div><strong>Selected PC:</strong> <span style="color: var(--accent-primary); font-weight: 700;">${escapeHtml(host.hostname)}</span> (ID: <span class="mono">${host.id}</span>)</div>
        <div><strong>IP:</strong> <span class="mono">${escapeHtml(host.ip_address || '—')}</span></div>
        <div><strong>Scope:</strong> <span class="badge badge-info">${escapeHtml(host.environment)}</span></div>
        <div><strong>Location / Room:</strong> ${escapeHtml(host.region || 'Lab Unit')}</div>
        <div><strong>Status:</strong> ${host.is_active ? '<span class="badge badge-healthy">ACTIVE INVENTORY</span>' : '<span class="badge badge-critical">DEACTIVATED</span>'}</div>
      </div>
    `;
  }

  // Filter host dropdown on search
  sensorSearchInput?.addEventListener("input", (e) => {
    const q = (e.target.value || "").toLowerCase().trim();
    const filtered = cachedHosts.filter(h =>
      (h.hostname || "").toLowerCase().includes(q) ||
      (h.ip_address || "").toLowerCase().includes(q) ||
      (h.region || "").toLowerCase().includes(q) ||
      (h.environment || "").toLowerCase().includes(q) ||
      String(h.id).includes(q)
    );
    populateHostSelect(filtered);
  });

  sensorHostSelect?.addEventListener("change", (e) => {
    selectedHostId = parseInt(e.target.value, 10);
    const host = cachedHosts.find(h => h.id === selectedHostId);
    updateSelectedHostBadge(host);
  });

  // Switch tabs
  tabOverallBtn.onclick = () => {
    currentTab = "overall";
    tabOverallBtn.className = "btn btn-sm btn-primary";
    tabSensorBtn.className = "btn btn-sm btn-secondary";
    controlsOverall.style.display = "flex";
    controlsSensor.style.display = "none";
    outputContainer.innerHTML = `
      <div class="panel" style="padding: 40px 20px; text-align: center;">
        <div class="state-container">
          <div class="state-icon">${renderIcon("server", { size: "xl" })}</div>
          <div class="state-title">Overall System Report Ready</div>
          <p class="state-desc">Select the reporting horizon and environment scope above, then click <strong>Preview Report</strong> to inspect or <strong>Download Official PDF</strong>.</p>
        </div>
      </div>
    `;
  };

  tabSensorBtn.onclick = () => {
    currentTab = "sensor";
    tabOverallBtn.className = "btn btn-sm btn-secondary";
    tabSensorBtn.className = "btn btn-sm btn-primary";
    controlsOverall.style.display = "none";
    controlsSensor.style.display = "flex";
    if (cachedHosts.length === 0) {
      loadHosts();
    }
    outputContainer.innerHTML = `
      <div class="panel" style="padding: 40px 20px; text-align: center;">
        <div class="state-container">
          <div class="state-icon">${renderIcon("cpu", { size: "xl" })}</div>
          <div class="state-title">Individual Sensor Report Ready</div>
          <p class="state-desc">Choose a monitored workstation from the dropdown above, select your timeframe, then click <strong>Preview Sensor Report</strong> or <strong>Download Sensor PDF</strong>.</p>
        </div>
      </div>
    `;
  };

  // ============================================================================
  // OPTION A: PREVIEW OVERALL REPORT
  // ============================================================================
  const runOverallReportPreview = async () => {
    const hours = parseInt(overallHorizonSelect?.value || "24", 10);
    const envVal = overallEnvSelect?.value || "All Environments";
    const thresholdSec = parseInt(overallThreshSelect?.value || "90", 10);

    genOverallBtn.disabled = true;
    outputContainer.innerHTML = `
      <div class="panel" style="padding: 40px 20px; text-align: center;">
        <div class="state-container">
          <div class="state-icon">${renderIcon("loader", { size: "xl", className: "icon-spin" })}</div>
          <div class="state-title">Synthesizing Overall Infrastructure Telemetry...</div>
          <p class="state-desc">Aggregating telemetry heartbeats, active incidents, and catalog cost efficiency across ${escapeHtml(envVal)}.</p>
        </div>
      </div>
    `;

    try {
      const rep = await api.generateReport(hours, envVal, thresholdSec);
      const freshnessText = rep.data_freshness_timestamp
        ? `${formatTimestamp(rep.data_freshness_timestamp)} (${formatRelativeTime(rep.data_freshness_timestamp)})`
        : "No Ingested Telemetry";

      outputContainer.innerHTML = `
        <div class="no-print" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
          <div style="font-size: 12.5px; color: var(--text-secondary);">
            Previewing report <strong>${escapeHtml(rep.report_id)}</strong>. Ready to review or download as PDF.
          </div>
          <button class="btn btn-primary btn-sm" id="export-overall-pdf-trigger">
            ${renderIcon("download", { size: "xs" })} Download PDF
          </button>
        </div>

        <div class="report-document" id="printable-report">
          <!-- Document Header -->
          <div class="report-doc-header">
            <div>
              <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); margin-bottom: 4px;">
                CloudOps Intel — SRE Command Center & Observability
              </div>
              <h1 class="report-doc-title">${escapeHtml(rep.title)}</h1>
              <div class="report-doc-subtitle">
                Overall Infrastructure Monitoring Report &bull; Scope: ${escapeHtml(rep.environment)}
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
              <span class="report-meta-val">${hours} Hours Horizon</span>
            </div>
            <div class="report-meta-item">
              <span class="report-meta-label">Data Freshness</span>
              <span class="report-meta-val">${freshnessText}</span>
            </div>
          </div>

          <!-- Executive KPI Grid -->
          <div class="report-kpi-grid">
            <div class="report-kpi-card">
              <span class="report-kpi-title">Monitored Fleet</span>
              <span class="report-kpi-val">${rep.summary_metrics.total_hosts}</span>
              <span class="report-kpi-sub">${rep.online_hosts_count} Online &bull; ${rep.offline_hosts_count} Offline &bull; ${rep.unseen_hosts_count} No Telemetry</span>
            </div>
            <div class="report-kpi-card">
              <span class="report-kpi-title">Active Incidents</span>
              <span class="report-kpi-val" style="color: ${rep.active_incidents_count > 0 ? 'var(--color-critical)' : 'var(--color-healthy)'};">
                ${rep.active_incidents_count}
              </span>
              <span class="report-kpi-sub">${rep.summary_metrics.critical_alerts || 0} Critical &bull; ${rep.summary_metrics.warning_alerts || 0} Warning</span>
            </div>
            <div class="report-kpi-card">
              <span class="report-kpi-title">Fleet Resource Averages</span>
              <span class="report-kpi-val mono" style="font-size: 16px;">
                ${rep.avg_cpu_percent !== null && rep.avg_cpu_percent !== undefined ? `CPU: ${rep.avg_cpu_percent}%` : 'CPU: —'}
              </span>
              <span class="report-kpi-sub mono">
                RAM: ${rep.avg_memory_percent !== null && rep.avg_memory_percent !== undefined ? `${rep.avg_memory_percent}%` : '—'} &bull; Disk: ${rep.avg_disk_percent !== null && rep.avg_disk_percent !== undefined ? `${rep.avg_disk_percent}%` : '—'}
              </span>
            </div>
            <div class="report-kpi-card">
              <span class="report-kpi-title">Security & Cost</span>
              <span class="report-kpi-val mono" style="font-size: 16px; color: var(--color-healthy);">
                $${(rep.potential_savings_usd || 0).toFixed(2)}/mo
              </span>
              <span class="report-kpi-sub">${rep.security_events_count} Security Event(s) Flagged</span>
            </div>
          </div>

          <!-- Section 1: Fleet Inventory & Connectivity -->
          <div class="report-section">
            <div class="report-section-heading">1. Fleet Inventory & Workstation Liveness</div>
            <div class="report-table-wrapper">
              <table class="report-table">
                <thead>
                  <tr>
                    <th>Hostname</th>
                    <th>ID</th>
                    <th>IP Address</th>
                    <th>Environment</th>
                    <th>Room / Location</th>
                    <th>Status</th>
                    <th>Last Heartbeat</th>
                    <th>CPU</th>
                    <th>RAM</th>
                    <th>Disk</th>
                  </tr>
                </thead>
                <tbody>
                  ${rep.host_inventories && rep.host_inventories.length > 0
                    ? rep.host_inventories.map(h => `
                      <tr>
                        <td style="font-weight: 600;">${escapeHtml(h.hostname)}</td>
                        <td class="mono">${h.host_id}</td>
                        <td class="mono">${escapeHtml(h.ip_address || "—")}</td>
                        <td><span class="badge badge-info">${escapeHtml(h.environment)}</span></td>
                        <td>${escapeHtml(h.room || "—")}</td>
                        <td>
                          <span class="badge ${h.status === 'ONLINE' ? 'badge-healthy' : h.status === 'OFFLINE' ? 'badge-critical' : 'badge-info'}">
                            ${escapeHtml(h.status)}
                          </span>
                        </td>
                        <td class="mono" style="font-size: 11px;">
                          ${h.last_seen ? formatTimestamp(h.last_seen) : '<span class="text-muted">No telemetry</span>'}
                        </td>
                        <td class="mono">${h.cpu_percent !== null ? `${h.cpu_percent}%` : '<span class="text-muted">—</span>'}</td>
                        <td class="mono">${h.memory_percent !== null ? `${h.memory_percent}%` : '<span class="text-muted">—</span>'}</td>
                        <td class="mono">${h.disk_percent !== null ? `${h.disk_percent}%` : '<span class="text-muted">—</span>'}</td>
                      </tr>
                    `).join("")
                    : `<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 18px;">No monitored host nodes registered in this scope.</td></tr>`
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

          <!-- Section 3: Recommendations -->
          <div class="report-section">
            <div class="report-section-heading">3. Evidence-Based Operational Recommendations</div>
            <div class="panel" style="padding: 14px; background: var(--bg-surface-elevated);">
              <ul style="margin: 0; padding-left: 20px; font-size: 12.5px; color: var(--text-primary); line-height: 1.6;">
                ${rep.recommendations && rep.recommendations.length > 0
                  ? rep.recommendations.map(r => `<li>${escapeHtml(r)}</li>`).join("")
                  : `<li>All monitored compute instances are operating within nominal boundaries.</li>`
                }
              </ul>
            </div>
          </div>

          <!-- Section 4: Technical Integrity & Security Audit Disclaimer -->
          <div class="report-section">
            <div class="report-section-heading">4. Technical Integrity, Liveness Model & Security Disclaimer</div>
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

      // Attach PDF download handler inside preview
      document.getElementById("export-overall-pdf-trigger")?.addEventListener("click", () => {
        downloadOverallPdfBtn.click();
      });
    } catch (err) {
      outputContainer.innerHTML = `
        <div class="panel" style="padding: 24px; border-color: var(--color-critical);">
          <div style="display: flex; align-items: center; gap: 10px; color: var(--color-critical); margin-bottom: 8px;">
            ${renderIcon("alert-triangle", { size: "sm" })}
            <strong style="font-size: 14px;">Failed to Generate Overall Report</strong>
          </div>
          <div style="font-size: 12.5px; color: var(--text-secondary);">${escapeHtml(err.message)}</div>
        </div>
      `;
    } finally {
      genOverallBtn.disabled = false;
    }
  };

  // Download Overall PDF
  const downloadOverallPdf = async () => {
    const hours = parseInt(overallHorizonSelect?.value || "24", 10);
    const envVal = overallEnvSelect?.value || "All Environments";
    const thresholdSec = parseInt(overallThreshSelect?.value || "90", 10);

    downloadOverallPdfBtn.disabled = true;
    const origText = downloadOverallPdfBtn.innerHTML;
    downloadOverallPdfBtn.innerHTML = `${renderIcon("loader", { size: "xs", className: "icon-spin" })} Building PDF...`;

    try {
      await api.generateReportPdf(hours, envVal, thresholdSec);
    } catch (err) {
      alert(`Failed to download Overall Report PDF: ${err.message}`);
    } finally {
      downloadOverallPdfBtn.disabled = false;
      downloadOverallPdfBtn.innerHTML = origText;
    }
  };

  // ============================================================================
  // OPTION B: PREVIEW INDIVIDUAL SENSOR / PC REPORT
  // ============================================================================
  const runSensorReportPreview = async () => {
    if (!selectedHostId) {
      alert("Please select a registered host / PC from the dropdown.");
      return;
    }

    const hours = parseInt(sensorHorizonSelect?.value || "24", 10);
    const thresholdSec = 90;

    genSensorBtn.disabled = true;
    outputContainer.innerHTML = `
      <div class="panel" style="padding: 40px 20px; text-align: center;">
        <div class="state-container">
          <div class="state-icon">${renderIcon("loader", { size: "xl", className: "icon-spin" })}</div>
          <div class="state-title">Synthesizing Sensor Diagnostics & Telemetry...</div>
          <p class="state-desc">Querying hardware metrics, heartbeat reliability, and alert incidents for Host ID ${selectedHostId}.</p>
        </div>
      </div>
    `;

    try {
      const rep = await api.generateHostReport(selectedHostId, hours, thresholdSec);
      const hi = rep.host_identity;

      outputContainer.innerHTML = `
        <div class="no-print" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
          <div style="font-size: 12.5px; color: var(--text-secondary);">
            Previewing Sensor Performance Report for <strong>${escapeHtml(hi.hostname)}</strong> (ID: ${hi.host_id}).
          </div>
          <button class="btn btn-primary btn-sm" id="export-sensor-pdf-trigger">
            ${renderIcon("download", { size: "xs" })} Download Sensor PDF
          </button>
        </div>

        <div class="report-document" id="printable-report">
          <!-- Document Header -->
          <div class="report-doc-header">
            <div>
              <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); margin-bottom: 4px;">
                CloudOps Intel — Workstation Telemetry & Sensor Diagnostics
              </div>
              <h1 class="report-doc-title">${escapeHtml(rep.title)}</h1>
              <div class="report-doc-subtitle">
                Hardware Health, Resource Profiling & Incident Audit &bull; Horizon: ${rep.reporting_period_hours} Hours
              </div>
            </div>
            <div style="text-align: right;" class="no-print">
              <span class="badge ${rep.connectivity_status === 'ONLINE' ? 'badge-healthy' : rep.connectivity_status === 'OFFLINE' ? 'badge-critical' : 'badge-info'}" style="font-size: 11px;">
                ${escapeHtml(rep.connectivity_status)}
              </span>
            </div>
          </div>

          <!-- Metadata Strip -->
          <div class="report-meta-grid">
            <div class="report-meta-item">
              <span class="report-meta-label">Hostname</span>
              <span class="report-meta-val">${escapeHtml(hi.hostname)}</span>
            </div>
            <div class="report-meta-item">
              <span class="report-meta-label">IP & MAC Address</span>
              <span class="report-meta-val mono">${escapeHtml(hi.ip_address || "—")} &bull; ${escapeHtml(hi.mac_address || "—")}</span>
            </div>
            <div class="report-meta-item">
              <span class="report-meta-label">Environment & Location</span>
              <span class="report-meta-val">${escapeHtml(hi.environment)} &bull; ${escapeHtml(hi.room || hi.lab_name || "Lab Workstation")}</span>
            </div>
            <div class="report-meta-item">
              <span class="report-meta-label">Last Heartbeat</span>
              <span class="report-meta-val mono">${rep.last_heartbeat ? formatTimestamp(rep.last_heartbeat) : "No telemetry recorded"}</span>
            </div>
          </div>

          <!-- Executive KPI Grid -->
          <div class="report-kpi-grid">
            <div class="report-kpi-card">
              <span class="report-kpi-title">CPU Utilization</span>
              <span class="report-kpi-val mono">${rep.cpu_stats.latest !== null ? `${rep.cpu_stats.latest}%` : '—'}</span>
              <span class="report-kpi-sub">Avg: ${rep.cpu_stats.avg !== null ? `${rep.cpu_stats.avg}%` : '—'} &bull; Peak: ${rep.cpu_stats.max !== null ? `${rep.cpu_stats.max}%` : '—'}</span>
            </div>
            <div class="report-kpi-card">
              <span class="report-kpi-title">Memory (RAM)</span>
              <span class="report-kpi-val mono">${rep.memory_stats.latest !== null ? `${rep.memory_stats.latest}%` : '—'}</span>
              <span class="report-kpi-sub">Avg: ${rep.memory_stats.avg !== null ? `${rep.memory_stats.avg}%` : '—'} &bull; Peak: ${rep.memory_stats.max !== null ? `${rep.memory_stats.max}%` : '—'}</span>
            </div>
            <div class="report-kpi-card">
              <span class="report-kpi-title">Disk Storage</span>
              <span class="report-kpi-val mono">${rep.disk_stats.latest !== null ? `${rep.disk_stats.latest}%` : '—'}</span>
              <span class="report-kpi-sub">Avg: ${rep.disk_stats.avg !== null ? `${rep.disk_stats.avg}%` : '—'}</span>
            </div>
            <div class="report-kpi-card">
              <span class="report-kpi-title">Telemetry & Incidents</span>
              <span class="report-kpi-val mono" style="font-size: 16px;">${rep.telemetry_availability_pct !== null ? `${rep.telemetry_availability_pct}%` : '—'}</span>
              <span class="report-kpi-sub">${rep.total_samples} Samples &bull; ${rep.active_alerts_count} Active Alert(s)</span>
            </div>
          </div>

          <!-- Subsystem Statistics Table -->
          <div class="report-section">
            <div class="report-section-heading">1. Detailed Subsystem Telemetry Statistics</div>
            <div class="report-table-wrapper">
              <table class="report-table">
                <thead>
                  <tr>
                    <th>Subsystem Metric</th>
                    <th>Latest Value</th>
                    <th>Average</th>
                    <th>Peak (Maximum)</th>
                    <th>Peak Timestamp</th>
                    <th>Minimum</th>
                    <th>Valid Samples</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td style="font-weight: 600;">CPU Utilization</td>
                    <td class="mono">${rep.cpu_stats.latest !== null ? `${rep.cpu_stats.latest}%` : '—'}</td>
                    <td class="mono">${rep.cpu_stats.avg !== null ? `${rep.cpu_stats.avg}%` : '—'}</td>
                    <td class="mono" style="font-weight: 700;">${rep.cpu_stats.max !== null ? `${rep.cpu_stats.max}%` : '—'}</td>
                    <td class="mono" style="font-size: 11px;">${rep.cpu_stats.peak_timestamp ? formatTimestamp(rep.cpu_stats.peak_timestamp) : '—'}</td>
                    <td class="mono">${rep.cpu_stats.min !== null ? `${rep.cpu_stats.min}%` : '—'}</td>
                    <td class="mono">${rep.cpu_stats.sample_count}</td>
                  </tr>
                  <tr>
                    <td style="font-weight: 600;">Memory (RAM)</td>
                    <td class="mono">${rep.memory_stats.latest !== null ? `${rep.memory_stats.latest}%` : '—'}</td>
                    <td class="mono">${rep.memory_stats.avg !== null ? `${rep.memory_stats.avg}%` : '—'}</td>
                    <td class="mono" style="font-weight: 700;">${rep.memory_stats.max !== null ? `${rep.memory_stats.max}%` : '—'}</td>
                    <td class="mono" style="font-size: 11px;">${rep.memory_stats.peak_timestamp ? formatTimestamp(rep.memory_stats.peak_timestamp) : '—'}</td>
                    <td class="mono">${rep.memory_stats.min !== null ? `${rep.memory_stats.min}%` : '—'}</td>
                    <td class="mono">${rep.memory_stats.sample_count}</td>
                  </tr>
                  <tr>
                    <td style="font-weight: 600;">Storage (Disk)</td>
                    <td class="mono">${rep.disk_stats.latest !== null ? `${rep.disk_stats.latest}%` : '—'}</td>
                    <td class="mono">${rep.disk_stats.avg !== null ? `${rep.disk_stats.avg}%` : '—'}</td>
                    <td class="mono" style="font-weight: 700;">${rep.disk_stats.max !== null ? `${rep.disk_stats.max}%` : '—'}</td>
                    <td class="mono" style="font-size: 11px;">${rep.disk_stats.peak_timestamp ? formatTimestamp(rep.disk_stats.peak_timestamp) : '—'}</td>
                    <td class="mono">${rep.disk_stats.min !== null ? `${rep.disk_stats.min}%` : '—'}</td>
                    <td class="mono">${rep.disk_stats.sample_count}</td>
                  </tr>
                  <tr>
                    <td style="font-weight: 600;">Network Outbound (MB)</td>
                    <td class="mono">${rep.network_sent_stats.latest !== null ? rep.network_sent_stats.latest : '—'}</td>
                    <td class="mono">${rep.network_sent_stats.avg !== null ? rep.network_sent_stats.avg : '—'}</td>
                    <td class="mono" style="font-weight: 700;">${rep.network_sent_stats.max !== null ? rep.network_sent_stats.max : '—'}</td>
                    <td class="mono" style="font-size: 11px;">${rep.network_sent_stats.peak_timestamp ? formatTimestamp(rep.network_sent_stats.peak_timestamp) : '—'}</td>
                    <td class="mono">${rep.network_sent_stats.min !== null ? rep.network_sent_stats.min : '—'}</td>
                    <td class="mono">${rep.network_sent_stats.sample_count}</td>
                  </tr>
                  <tr>
                    <td style="font-weight: 600;">Network Inbound (MB)</td>
                    <td class="mono">${rep.network_recv_stats.latest !== null ? rep.network_recv_stats.latest : '—'}</td>
                    <td class="mono">${rep.network_recv_stats.avg !== null ? rep.network_recv_stats.avg : '—'}</td>
                    <td class="mono" style="font-weight: 700;">${rep.network_recv_stats.max !== null ? rep.network_recv_stats.max : '—'}</td>
                    <td class="mono" style="font-size: 11px;">${rep.network_recv_stats.peak_timestamp ? formatTimestamp(rep.network_recv_stats.peak_timestamp) : '—'}</td>
                    <td class="mono">${rep.network_recv_stats.min !== null ? rep.network_recv_stats.min : '—'}</td>
                    <td class="mono">${rep.network_recv_stats.sample_count}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Section 2: Individual PC Alert History -->
          <div class="report-section">
            <div class="report-section-heading">2. Incident & Alert History for this Workstation</div>
            <div class="report-table-wrapper">
              <table class="report-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Severity</th>
                    <th>Category</th>
                    <th>Metric</th>
                    <th>Reason / Threshold</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  ${rep.alerts && rep.alerts.length > 0
                    ? rep.alerts.map(a => `
                      <tr>
                        <td class="mono" style="font-size: 11px;">${formatTimestamp(a.timestamp)}</td>
                        <td>
                          <span class="badge ${a.severity.toLowerCase() === 'critical' ? 'badge-critical' : a.severity.toLowerCase() === 'warning' ? 'badge-warning' : 'badge-info'}">
                            ${escapeHtml(a.severity.toUpperCase())}
                          </span>
                        </td>
                        <td>${escapeHtml(a.kind)}</td>
                        <td class="mono">${escapeHtml(a.metric)}</td>
                        <td>${escapeHtml(a.message)} ${a.threshold ? `(Threshold: ${a.threshold})` : ''}</td>
                        <td class="mono">${escapeHtml(a.status.toUpperCase())}</td>
                      </tr>
                    `).join("")
                    : `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 18px;">Zero active or historical alerts recorded for this workstation in the selected horizon.</td></tr>`
                  }
                </tbody>
              </table>
            </div>
          </div>

          <!-- Section 3: Technical Assessment & Recommendations -->
          <div class="report-section">
            <div class="report-section-heading">3. Technical Assessment & SRE Recommendations</div>
            <div class="panel" style="padding: 14px; background: var(--bg-surface-elevated); margin-bottom: 10px;">
              <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); margin-bottom: 6px;">Observability Assessment</div>
              <div style="font-size: 12.5px; line-height: 1.5; color: var(--text-secondary);">${escapeHtml(rep.technical_assessment)}</div>
            </div>

            <div class="panel" style="padding: 14px; background: var(--bg-surface-elevated);">
              <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); margin-bottom: 6px;">Actionable Recommendations</div>
              <ul style="margin: 0; padding-left: 20px; font-size: 12.5px; color: var(--text-primary); line-height: 1.6;">
                ${rep.recommendations && rep.recommendations.length > 0
                  ? rep.recommendations.map(r => `<li>${escapeHtml(r)}</li>`).join("")
                  : `<li>Workstation performance is nominal. Maintain active telemetry polling.</li>`
                }
              </ul>
            </div>
          </div>

          <!-- Section 4: Security Notice & Disclaimer -->
          <div class="report-section">
            <div class="report-section-heading">4. Workstation Security Integrity Notice</div>
            <div class="report-disclaimer-box">
              <strong>Security Audit Qualification:</strong> ${escapeHtml(rep.security_disclaimer)}
            </div>
          </div>

          <!-- Document Footer -->
          <div class="report-footer">
            <div>
              CloudOps Intel Sensor Telemetry Audit &bull; Workstation: ${escapeHtml(hi.hostname)} (ID: ${hi.host_id}) &bull; Confidential
            </div>
            <div class="mono">
              Audit Ref: ${escapeHtml(rep.report_id)}
            </div>
          </div>
        </div>
      `;

      // Attach PDF download handler inside preview
      document.getElementById("export-sensor-pdf-trigger")?.addEventListener("click", () => {
        downloadSensorPdfBtn.click();
      });
    } catch (err) {
      outputContainer.innerHTML = `
        <div class="panel" style="padding: 24px; border-color: var(--color-critical);">
          <div style="display: flex; align-items: center; gap: 10px; color: var(--color-critical); margin-bottom: 8px;">
            ${renderIcon("alert-triangle", { size: "sm" })}
            <strong style="font-size: 14px;">Failed to Generate Sensor Report</strong>
          </div>
          <div style="font-size: 12.5px; color: var(--text-secondary);">${escapeHtml(err.message)}</div>
        </div>
      `;
    } finally {
      genSensorBtn.disabled = false;
    }
  };

  // Download Sensor PDF
  const downloadSensorPdf = async () => {
    if (!selectedHostId) {
      alert("Please select a registered host / PC first.");
      return;
    }

    const hours = parseInt(sensorHorizonSelect?.value || "24", 10);
    const thresholdSec = 90;

    downloadSensorPdfBtn.disabled = true;
    const origText = downloadSensorPdfBtn.innerHTML;
    downloadSensorPdfBtn.innerHTML = `${renderIcon("loader", { size: "xs", className: "icon-spin" })} Building PDF...`;

    try {
      await api.generateHostReportPdf(selectedHostId, hours, thresholdSec);
    } catch (err) {
      alert(`Failed to download Sensor Report PDF: ${err.message}`);
    } finally {
      downloadSensorPdfBtn.disabled = false;
      downloadSensorPdfBtn.innerHTML = origText;
    }
  };

  // Attach button event listeners
  genOverallBtn?.addEventListener("click", runOverallReportPreview);
  downloadOverallPdfBtn?.addEventListener("click", downloadOverallPdf);

  genSensorBtn?.addEventListener("click", runSensorReportPreview);
  downloadSensorPdfBtn?.addEventListener("click", downloadSensorPdf);

  // Initial load
  loadHosts();
}
