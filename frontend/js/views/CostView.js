/**
 * Cost View - Cloud Spend Optimization & Rightsizing (Module 3).
 */

import { api } from "../api.js?v=3.3.0";
import { currencyManager } from "../currency.js?v=3.3.0";
import { escapeHtml, formatRelativeTime, formatTimestamp } from "../sanitizer.js?v=3.3.0";
import { renderIcon } from "../components/Icons.js?v=3.3.0";

export async function renderCostView(container) {
  container.innerHTML = `
    <div class="state-container">
      <div class="state-icon">${renderIcon("loader", { size: "xl", className: "icon-spin" })}</div>
      <div class="state-title">Analyzing Resource Spend & Rightsizing Opportunities...</div>
    </div>
  `;

  try {
    const cost = await api.getCostSummary();
    const rateMeta = currencyManager.getRateMetadata();

    container.innerHTML = `
      <div class="view-header">
        <div class="view-title-group">
          <h1>Cloud Cost Intelligence & Rightsizing</h1>
          <p>Telemetry-driven spend estimation and rightsizing recommendations based on observed workload peaks (M3).</p>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
          ${rateMeta.isConverted ? `
            <div class="badge badge-info" style="padding: 6px 10px; font-size: 11px; display: flex; align-items: center; gap: 6px;">
              ${renderIcon("info", { size: "xs" })}
              <span>Converted @ <strong>${escapeHtml(rateMeta.rateFormatted)}</strong> (${escapeHtml(rateMeta.source)})</span>
            </div>
          ` : ''}
          <button class="btn btn-sm" id="cost-refresh-btn">
            ${renderIcon("refresh-cw", { size: "sm" })} Refresh
          </button>
        </div>
      </div>

      <!-- Cost Summary Cards -->
      <div class="summary-grid">
        <div class="summary-card status-info">
          <div class="summary-card-header">
            <span>Estimated Monthly Spend</span>
            <span class="badge badge-info">${escapeHtml(cost.billing_status)}</span>
          </div>
          <div class="summary-card-value">${currencyManager.format(cost.estimated_monthly_spend_usd)}</div>
          <div class="summary-card-sub">
            <span>${cost.total_monitored_resources} active cloud nodes</span>
            ${rateMeta.isConverted ? `<span class="text-muted mono" style="font-size: 10.5px;">(Base: $${cost.estimated_monthly_spend_usd.toFixed(2)})</span>` : ''}
          </div>
        </div>

        <div class="summary-card status-healthy">
          <div class="summary-card-header">
            <span>Potential Monthly Savings</span>
            <span class="badge badge-healthy">OPPORTUNITY</span>
          </div>
          <div class="summary-card-value text-healthy">${currencyManager.format(cost.estimated_potential_savings_usd)}</div>
          <div class="summary-card-sub">
            <span>${cost.active_recommendations.length} active rightsizing targets</span>
            ${rateMeta.isConverted ? `<span class="text-muted mono" style="font-size: 10.5px;">(Base: $${cost.estimated_potential_savings_usd.toFixed(2)})</span>` : ''}
          </div>
        </div>

        <div class="summary-card status-warning">
          <div class="summary-card-header">
            <span>Idle / Underutilized Nodes</span>
            <span class="mono">Resource Waste</span>
          </div>
          <div class="summary-card-value">${cost.idle_resources_count + cost.underutilized_resources_count}</div>
          <div class="summary-card-sub">
            <span class="text-warning">${cost.idle_resources_count} idle nodes</span> · <span>${cost.underutilized_resources_count} oversized</span>
          </div>
        </div>
      </div>

      <!-- Rightsizing Recommendations Table -->
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">${renderIcon("lightbulb", { size: "sm" })} Actionable Rightsizing & Termination Recommendations</span>
          <span class="badge badge-healthy">${cost.active_recommendations.length} Open Proposals</span>
        </div>

        <div class="table-container">
          <table class="ops-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Target Host</th>
                <th>Current Spec</th>
                <th>Suggested Spec</th>
                <th>Current Spend (${escapeHtml(currencyManager.displayCurrency)})</th>
                <th>Estimated Spend (${escapeHtml(currencyManager.displayCurrency)})</th>
                <th>Est. Savings (${escapeHtml(currencyManager.displayCurrency)})</th>
                <th>Confidence</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${cost.active_recommendations.length === 0 ? `
                <tr><td colspan="9" class="text-muted" style="text-align: center; padding: 24px;">All active infrastructure is currently provisioned with optimal compute allocation.</td></tr>
              ` : cost.active_recommendations.map(r => `
                <tr>
                  <td><span class="badge badge-warning">${escapeHtml(r.recommendation_type)}</span></td>
                  <td class="mono" style="font-weight: 600;">${escapeHtml(r.hostname || `Host-${r.host_id}`)}</td>
                  <td class="mono">${escapeHtml(r.current_instance_type)}</td>
                  <td class="mono text-healthy">${escapeHtml(r.suggested_instance_type || '— (Terminate)')}</td>
                  <td class="mono">${currencyManager.format(r.current_monthly_spend_usd)}/mo</td>
                  <td class="mono">${currencyManager.format(r.estimated_monthly_spend_usd)}/mo</td>
                  <td class="mono text-healthy" style="font-weight: 700;">+${currencyManager.format(r.estimated_monthly_savings_usd)}/mo</td>
                  <td class="mono">${(r.confidence_score * 100).toFixed(0)}%</td>
                  <td>
                    <div style="display: flex; gap: 4px;">
                      <button class="btn btn-sm btn-primary" onclick="actCostRec(${r.id}, 'accepted')">Accept</button>
                      <button class="btn btn-sm" onclick="actCostRec(${r.id}, 'dismissed')">Dismiss</button>
                    </div>
                  </td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Resource Spend Breakdown -->
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">${renderIcon("bar-chart", { size: "sm" })} Infrastructure Spend Ranking by Node</span>
        </div>
        <div class="table-container">
          <table class="ops-table">
            <thead>
              <tr>
                <th>Hostname</th>
                <th>Environment</th>
                <th>Instance Type</th>
                <th>Avg CPU %</th>
                <th>Estimated Monthly Cost (${escapeHtml(currencyManager.displayCurrency)})</th>
                <th>Savings Potential</th>
              </tr>
            </thead>
            <tbody>
              ${cost.top_cost_resources.map(res => `
                <tr>
                  <td class="mono" style="font-weight: 600;">${escapeHtml(res.hostname)}</td>
                  <td><span class="badge badge-info">${escapeHtml(res.environment)}</span></td>
                  <td class="mono">${escapeHtml(res.instance_type)}</td>
                  <td class="mono">${res.utilization_score.toFixed(1)}%</td>
                  <td class="mono" style="font-weight: 600;">${currencyManager.format(res.monthly_spend_usd)}/mo</td>
                  <td class="mono text-healthy">${res.optimization_potential > 0 ? `+${currencyManager.format(res.optimization_potential)}/mo` : '—'}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;

    const refreshBtn = document.getElementById("cost-refresh-btn");
    if (refreshBtn) refreshBtn.onclick = () => renderCostView(container);

    window.actCostRec = async (id, status) => {
      try {
        await api.updateCostRecommendation(id, status);
        renderCostView(container);
      } catch (err) {
        alert(`Failed to update recommendation: ${err.message}`);
      }
    };

  } catch (err) {
    container.innerHTML = `
      <div class="state-container">
        <div class="state-icon text-critical">${renderIcon("triangle-alert", { size: "xl" })}</div>
        <div class="state-title">Failed to load cost intelligence</div>
        <div class="state-desc">${escapeHtml(err.message)}</div>
      </div>
    `;
  }
}
