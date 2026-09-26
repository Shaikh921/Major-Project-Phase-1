/**
 * Settings View - Threshold Rules & Platform Configuration.
 */

import { api } from "../api.js";
import { escapeHtml, formatTimestamp } from "../sanitizer.js";
import { renderSeverityBadge } from "../components/StatusBadge.js";
import { openModal, closeModal } from "../components/Modal.js";

export async function renderSettingsView(container) {
  container.innerHTML = `
    <div class="state-container">
      <div class="state-icon">⏳</div>
      <div class="state-title">Loading Alert Rules & Configuration...</div>
    </div>
  `;

  try {
    const rules = await api.getAlertRules();

    container.innerHTML = `
      <div class="view-header">
        <div class="view-title-group">
          <h1>Platform Configuration & Alert Rules</h1>
          <p>Configure static threshold evaluation boundaries, detection parameters, and sensitivity settings.</p>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-primary btn-sm" id="create-rule-btn">+ New Alert Rule</button>
        </div>
      </div>

      <!-- Configured Alert Rules Table -->
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">⚙️ Active Alert Threshold Rules (${rules.length})</span>
        </div>

        <div class="table-container">
          <table class="ops-table">
            <thead>
              <tr>
                <th>Rule Name</th>
                <th>Target Metric</th>
                <th>Condition</th>
                <th>Threshold</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${rules.map(r => `
                <tr>
                  <td style="font-weight: 600;">${escapeHtml(r.name)}</td>
                  <td class="mono">${escapeHtml(r.metric)}</td>
                  <td class="mono">${escapeHtml(r.operator)}</td>
                  <td class="mono font-weight-bold">${r.threshold.toFixed(1)}%</td>
                  <td>${renderSeverityBadge(r.severity)}</td>
                  <td><span class="badge ${r.is_enabled ? 'badge-healthy' : 'badge-info'}">${r.is_enabled ? 'ENABLED' : 'DISABLED'}</span></td>
                  <td>
                    <button class="btn btn-sm btn-critical" onclick="deleteRule(${r.id})">Delete</button>
                  </td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;

    const createBtn = document.getElementById("create-rule-btn");
    if (createBtn) createBtn.onclick = openCreateRuleModal;

    window.deleteRule = async (id) => {
      if (confirm(`Confirm deletion of alert rule #${id}?`)) {
        try {
          await api.deleteAlertRule(id);
          renderSettingsView(container);
        } catch (err) {
          alert(`Failed to delete rule: ${err.message}`);
        }
      }
    };

  } catch (err) {
    container.innerHTML = `
      <div class="state-container">
        <div class="state-icon text-critical">⚠️</div>
        <div class="state-title">Failed to load rules</div>
        <div class="state-desc">${escapeHtml(err.message)}</div>
      </div>
    `;
  }
}

function openCreateRuleModal() {
  const content = `
    <form id="create-rule-form" style="display: flex; flex-direction: column; gap: 12px;">
      <div>
        <label class="text-muted" style="font-size: 11px;">RULE NAME *</label>
        <input type="text" id="new-rule-name" class="input-control" style="width: 100%;" required placeholder="e.g. Memory Spike Warning">
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
        <div>
          <label class="text-muted" style="font-size: 11px;">METRIC</label>
          <select id="new-rule-metric" class="select-control" style="width: 100%;">
            <option value="cpu_percent">cpu_percent</option>
            <option value="memory_percent">memory_percent</option>
            <option value="disk_percent">disk_percent</option>
          </select>
        </div>
        <div>
          <label class="text-muted" style="font-size: 11px;">THRESHOLD (%)</label>
          <input type="number" id="new-rule-threshold" class="input-control" style="width: 100%;" value="85.0" step="1.0" min="1" max="100">
        </div>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
        <div>
          <label class="text-muted" style="font-size: 11px;">OPERATOR</label>
          <select id="new-rule-op" class="select-control" style="width: 100%;">
            <option value=">=">&gt;= (Greater or Equal)</option>
            <option value=">">&gt; (Strictly Greater)</option>
          </select>
        </div>
        <div>
          <label class="text-muted" style="font-size: 11px;">SEVERITY</label>
          <select id="new-rule-sev" class="select-control" style="width: 100%;">
            <option value="warning">warning</option>
            <option value="critical">critical</option>
            <option value="info">info</option>
          </select>
        </div>
      </div>
    </form>
  `;

  const footer = `
    <button class="btn btn-sm" onclick="(${closeModal})()">Cancel</button>
    <button class="btn btn-primary btn-sm" id="submit-rule-btn">Create Rule</button>
  `;

  openModal("Configure Alert Rule", content, footer);

  const submitBtn = document.getElementById("submit-rule-btn");
  if (submitBtn) {
    submitBtn.onclick = async () => {
      const name = document.getElementById("new-rule-name").value.trim();
      const metric = document.getElementById("new-rule-metric").value;
      const threshold = parseFloat(document.getElementById("new-rule-threshold").value);
      const op = document.getElementById("new-rule-op").value;
      const sev = document.getElementById("new-rule-sev").value;

      if (!name) {
        alert("Rule name is required.");
        return;
      }

      try {
        await api.createAlertRule({
          name,
          metric,
          operator: op,
          threshold,
          severity: sev,
          duration_seconds: 0,
          is_enabled: true,
        });
        closeModal();
        renderSettingsView(document.getElementById("view-container"));
      } catch (err) {
        alert(`Failed to create rule: ${err.message}`);
      }
    };
  }
}
