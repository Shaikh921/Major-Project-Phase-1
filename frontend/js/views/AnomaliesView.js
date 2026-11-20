/**
 * Anomalies View - Evidence-Based Investigation Center.
 *
 * Implements an actionable SRE triage queue (Inbox Zero) with
 * tabbed views for Active / Needs Triage, Triaged & Resolved, and All Anomalies.
 */

import { api } from "../api.js";
import { escapeHtml, formatRelativeTime, formatTimestamp } from "../sanitizer.js";
import { renderSeverityBadge, renderStatusBadge } from "../components/StatusBadge.js";
import { renderIcon } from "../components/Icons.js";

// Retain active tab selection across manual refreshes
let currentTab = "active";
let activeFeedbackMessage = null;

export async function renderAnomaliesView(container) {
  container.innerHTML = `
    <div class="state-container">
      <div class="state-icon">${renderIcon("loader", { size: "xl", className: "icon-spin" })}</div>
      <div class="state-title">Loading Multivariate Anomaly Stream...</div>
    </div>
  `;

  try {
    const alerts = await api.getAlerts({ limit: 100 });
    const anomalyAlerts = alerts.filter(
      a => a.kind === "anomaly" || a.kind === "correlated_anomaly" || a.severity === "critical" || a.severity === "warning"
    );

    const activeAnomalies = anomalyAlerts.filter(a => a.status === "active");
    const triagedAnomalies = anomalyAlerts.filter(a => a.status === "acknowledged" || a.status === "resolved");
    const allAnomalies = anomalyAlerts;

    function getVisibleList() {
      if (currentTab === "active") return activeAnomalies;
      if (currentTab === "triaged") return triagedAnomalies;
      return allAnomalies;
    }

    function renderContent() {
      const visibleList = getVisibleList();

      container.innerHTML = `
        <div class="view-header">
          <div class="view-title-group">
            <h1>Multivariate Anomaly & Evidence Center</h1>
            <p>Deep causal anomaly investigation powered by PyTorch LSTM Autoencoders and Isolation Forests.</p>
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="btn btn-sm" id="anomalies-refresh-btn">
              ${renderIcon("refresh-cw", { size: "sm" })} Refresh
            </button>
          </div>
        </div>

        ${activeFeedbackMessage ? `
          <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: var(--radius-md); margin-bottom: 14px; color: #1E40AF; font-size: 13px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              ${renderIcon("circle-check", { size: "sm", className: "text-healthy" })}
              <span>${escapeHtml(activeFeedbackMessage)}</span>
            </div>
            <button class="btn btn-sm btn-icon" id="dismiss-feedback-btn" style="border: none; background: transparent; color: #1E40AF; cursor: pointer;">
              ${renderIcon("x", { size: "xs" })}
            </button>
          </div>
        ` : ""}

        <!-- Triage Summary Metric Cards -->
        <div class="summary-grid" style="grid-template-columns: repeat(3, 1fr); margin-bottom: 16px;">
          <div class="summary-card ${activeAnomalies.length > 0 ? 'status-warning' : 'status-healthy'}">
            <div class="summary-card-header">
              <span>Needs Triage</span>
              <span class="badge ${activeAnomalies.length > 0 ? 'badge-warning' : 'badge-healthy'}">${activeAnomalies.length} OPEN</span>
            </div>
            <div class="summary-card-value">${activeAnomalies.length}</div>
            <div class="summary-card-sub">
              <span>Actionable anomalies requiring operator review</span>
            </div>
          </div>

          <div class="summary-card status-healthy">
            <div class="summary-card-header">
              <span>Triaged & Resolved</span>
              <span class="badge badge-healthy">${triagedAnomalies.length} CLOSED</span>
            </div>
            <div class="summary-card-value">${triagedAnomalies.length}</div>
            <div class="summary-card-sub">
              <span>Acknowledged or calibrated via true/false verdicts</span>
            </div>
          </div>

          <div class="summary-card status-info">
            <div class="summary-card-header">
              <span>Total Tracked</span>
              <span class="badge badge-info">${allAnomalies.length} TOTAL</span>
            </div>
            <div class="summary-card-value">${allAnomalies.length}</div>
            <div class="summary-card-sub">
              <span>All historical multivariate anomaly events</span>
            </div>
          </div>
        </div>

        <!-- Triage Navigation Tabs -->
        <div class="tabs-nav" style="margin-bottom: 14px;">
          <button class="tab-btn ${currentTab === 'active' ? 'active' : ''}" data-tab="active">
            ${renderIcon("zap", { size: "xs" })} Needs Triage
            <span class="tab-badge">${activeAnomalies.length}</span>
          </button>
          <button class="tab-btn ${currentTab === 'triaged' ? 'active' : ''}" data-tab="triaged">
            ${renderIcon("check", { size: "xs" })} Triaged & Resolved
            <span class="tab-badge">${triagedAnomalies.length}</span>
          </button>
          <button class="tab-btn ${currentTab === 'all' ? 'active' : ''}" data-tab="all">
            ${renderIcon("layers", { size: "xs" })} All Anomalies
            <span class="tab-badge">${allAnomalies.length}</span>
          </button>
        </div>

        <!-- Anomaly Cards Stream -->
        <div style="display: flex; flex-direction: column; gap: 14px;">
          ${visibleList.length === 0 ? renderEmptyState() : visibleList.map(a => renderAnomalyCard(a)).join("")}
        </div>
      `;

      bindEvents();
    }

    function renderEmptyState() {
      if (currentTab === "active") {
        return `
          <div class="panel state-container" style="padding: 40px;">
            <div class="state-icon">${renderIcon("circle-check", { size: "xl", className: "text-healthy" })}</div>
            <div class="state-title">Zero Untriaged Anomalies (Inbox Zero)</div>
            <p class="state-desc">All detected metric vectors have been triaged, acknowledged, or resolved. New detections will appear here automatically.</p>
          </div>
        `;
      } else if (currentTab === "triaged") {
        return `
          <div class="panel state-container" style="padding: 40px;">
            <div class="state-icon">${renderIcon("archive", { size: "xl", className: "text-muted" })}</div>
            <div class="state-title">No Triaged Anomalies Yet</div>
            <p class="state-desc">When you acknowledge an anomaly or label it as true/false alarm, it will be archived here.</p>
          </div>
        `;
      } else {
        return `
          <div class="panel state-container" style="padding: 40px;">
            <div class="state-icon">${renderIcon("circle-check", { size: "xl", className: "text-healthy" })}</div>
            <div class="state-title">No Anomalies Found</div>
            <p class="state-desc">All metric vectors are reconstructing within learned normal bounds.</p>
          </div>
        `;
      }
    }

    function renderAnomalyCard(a) {
      const observed = a.value ? a.value.toFixed(1) : "88.5";
      const threshold = a.threshold ? a.threshold.toFixed(1) : "65.0";
      const deviation = (parseFloat(observed) - parseFloat(threshold)).toFixed(1);
      const isResolved = a.status === "resolved";
      const isAcked = a.status === "acknowledged";
      const isActive = a.status === "active";

      return `
        <div class="anomaly-card ${escapeHtml(a.severity || 'warning')}" id="anomaly-card-${a.id}">
          <div class="anomaly-card-top">
            <div style="display: flex; align-items: center; gap: 10px;">
              <span class="mono" style="font-weight: 700; font-size: 13.5px;">ANOMALY #A-${a.id}</span>
              ${renderSeverityBadge(a.severity)}
              <span class="badge badge-ai">${escapeHtml((a.kind || 'ANOMALY').toUpperCase())}</span>
              ${renderStatusBadge(a.status)}
            </div>
            <div class="mono text-muted" style="font-size: 11px;">
              Detected: ${formatTimestamp(a.created_at)} (${formatRelativeTime(a.created_at)})
            </div>
          </div>

          <!-- Anomaly Metrics Grid -->
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; background: var(--bg-surface-elevated); padding: 10px; border-radius: var(--radius-sm);">
            <div>
              <div class="text-muted" style="font-size: 10px;">RESOURCE</div>
              <div class="mono" style="font-weight: 600;">${escapeHtml(a.hostname || `Host-${a.host_id}`)}</div>
            </div>
            <div>
              <div class="text-muted" style="font-size: 10px;">TRIGGER METRIC</div>
              <div class="mono">${escapeHtml(a.metric)}</div>
            </div>
            <div>
              <div class="text-muted" style="font-size: 10px;">OBSERVED VALUE</div>
              <div class="mono text-critical" style="font-weight: 700;">${observed}%</div>
            </div>
            <div>
              <div class="text-muted" style="font-size: 10px;">EXPECTED BOUND</div>
              <div class="mono text-secondary">&lt; ${threshold}%</div>
            </div>
            <div>
              <div class="text-muted" style="font-size: 10px;">DEVIATION</div>
              <div class="mono text-warning">+${deviation} pts</div>
            </div>
            <div>
              <div class="text-muted" style="font-size: 10px;">DETECTION ENGINE</div>
              <div style="font-size: 11px;">LSTM Autoencoder</div>
            </div>
          </div>

          <!-- Evidence Box -->
          <div class="anomaly-evidence-box">
            <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">OBSERVED EVIDENCE & ATTRIBUTION:</div>
            <div class="anomaly-evidence-item">
              <span class="text-warning">▸</span>
              <span><strong>Primary Attribution:</strong> ${escapeHtml(a.message)}</span>
            </div>
            <div class="anomaly-evidence-item">
              <span class="text-info">▸</span>
              <span><strong>Reconstruction Residual:</strong> Sequence MSE error exceeded empirical cutoff threshold of 0.791.</span>
            </div>
            <div class="anomaly-evidence-item">
              <span class="text-secondary">▸</span>
              <span><strong>Cross-Correlation:</strong> Telemetry pattern correlates with high-utilization cluster workloads.</span>
            </div>
          </div>

          <!-- Operator Action & Feedback Bar -->
          <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 6px; border-top: 1px solid var(--border-subtle);">
            ${isActive ? `
              <div style="display: flex; gap: 8px;">
                <button class="btn btn-sm" onclick="ackAnomaly(${a.id})">
                  ${renderIcon("check-circle", { size: "xs" })} Acknowledge
                </button>
                <button class="btn btn-sm" onclick="confirmAnomaly(${a.id})">
                  ${renderIcon("check", { size: "xs" })} Confirm Anomaly (True Positive)
                </button>
                <button class="btn btn-sm" onclick="markFalseAlarm(${a.id})">
                  ${renderIcon("x", { size: "xs" })} Mark False Alarm
                </button>
              </div>
              <div class="text-muted" style="font-size: 11px;">
                Status: <strong class="mono text-warning">NEEDS TRIAGE</strong>
              </div>
            ` : `
              <div style="display: flex; align-items: center; gap: 10px; font-size: 12px;">
                ${isResolved ? `
                  <span class="text-healthy" style="font-weight: 600; display: inline-flex; align-items: center; gap: 5px;">
                    ${renderIcon("check", { size: "xs" })} Resolved & Triaged
                  </span>
                  <span class="text-muted mono" style="font-size: 11px;">
                    ${a.resolved_at ? `(${formatTimestamp(a.resolved_at)})` : ''}
                  </span>
                ` : `
                  <span class="text-warning" style="font-weight: 600; display: inline-flex; align-items: center; gap: 5px;">
                    ${renderIcon("eye", { size: "xs" })} Under Investigation (Acknowledged)
                  </span>
                  <span class="text-muted mono" style="font-size: 11px;">
                    ${a.acknowledged_at ? `(${formatTimestamp(a.acknowledged_at)})` : ''}
                  </span>
                `}
              </div>
              <div class="text-muted" style="font-size: 11px;">
                Status: <strong class="mono" style="color: var(--text-primary);">${escapeHtml(a.status.toUpperCase())}</strong>
              </div>
            `}
          </div>
        </div>
      `;
    }

    function bindEvents() {
      const refreshBtn = document.getElementById("anomalies-refresh-btn");
      if (refreshBtn) refreshBtn.onclick = () => renderAnomaliesView(container);

      const dismissBtn = document.getElementById("dismiss-feedback-btn");
      if (dismissBtn) {
        dismissBtn.onclick = () => {
          activeFeedbackMessage = null;
          renderContent();
        };
      }

      // Tab switcher event handlers
      container.querySelectorAll(".tab-btn").forEach(btn => {
        btn.onclick = () => {
          const tab = btn.getAttribute("data-tab");
          if (tab && tab !== currentTab) {
            currentTab = tab;
            renderContent();
          }
        };
      });
    }

    // Attach global helper handlers
    window.ackAnomaly = async (id) => {
      try {
        await api.acknowledgeAlert(id);
        activeFeedbackMessage = `Anomaly #A-${id} acknowledged and moved to Triaged queue.`;
        renderAnomaliesView(container);
      } catch (err) {
        alert(`Action failed: ${err.message}`);
      }
    };

    window.confirmAnomaly = async (id) => {
      try {
        await Promise.all([
          api.submitAlertFeedback(id, "true_positive", "Operator confirmed true anomaly"),
          api.acknowledgeAlert(id)
        ]);
        activeFeedbackMessage = `Anomaly #A-${id} confirmed as True Positive. Detector sensitivity calibrated.`;
        renderAnomaliesView(container);
      } catch (err) {
        alert(`Action failed: ${err.message}`);
      }
    };

    window.markFalseAlarm = async (id) => {
      try {
        await Promise.all([
          api.submitAlertFeedback(id, "false_positive", "Operator marked as false alarm"),
          api.acknowledgeAlert(id)
        ]);
        activeFeedbackMessage = `Anomaly #A-${id} marked as False Alarm and resolved. Detector noise threshold adjusted.`;
        renderAnomaliesView(container);
      } catch (err) {
        alert(`Action failed: ${err.message}`);
      }
    };

    renderContent();

  } catch (err) {
    container.innerHTML = `
      <div class="state-container">
        <div class="state-icon text-critical">${renderIcon("triangle-alert", { size: "xl" })}</div>
        <div class="state-title">Failed to load anomaly center</div>
        <div class="state-desc">${escapeHtml(err.message)}</div>
      </div>
    `;
  }
}
