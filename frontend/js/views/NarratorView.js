/**
 * Narrator View - AI Incident Narrator & Cross-Module Reasoning (Module 5).
 */

import { api } from "../api.js";
import { escapeHtml, renderSafeMarkdown, formatTimestamp } from "../sanitizer.js";

export async function renderNarratorView(container) {
  container.innerHTML = `
    <div class="view-header">
      <div class="view-title-group">
        <h1>AI Incident Narrator & Cross-Module Reasoning</h1>
        <p>Conversational root-cause investigation grounded across Telemetry, Alerts, Security, and Cost (M5).</p>
      </div>
      <div>
        <span class="badge badge-ai">LLM & Deterministic Reasoning</span>
      </div>
    </div>

    <!-- Narrator Main Workspace -->
    <div class="narrator-container">
      <!-- Chat Interface -->
      <div class="narrator-chat-box">
        <div class="narrator-messages" id="narrator-chat-history">
          <div class="message-bubble assistant">
            <div style="font-weight: 700; color: var(--status-ai); margin-bottom: 6px;">🤖 SRE Incident Intelligence Agent</div>
            <div>
              Welcome to the <strong>AI Incident Narrator</strong>. I continuously correlate multi-domain signals across Performance Metrics, Isolation Forest & LSTM Anomaly Residuals, Security Flow Logs, and Cloud Cost Catalogs.
              <br><br>
              Select an investigation preset below or enter a custom operational inquiry.
            </div>
          </div>
        </div>

        <div class="narrator-input-bar">
          <input type="text" id="narrator-input" class="input-control" placeholder="Ask about fleet health, root cause, security correlations..." style="flex: 1;">
          <button class="btn btn-primary" id="narrator-send-btn">Ask Narrator ⏎</button>
        </div>
      </div>

      <!-- Quick Investigation Presets -->
      <div class="panel" style="display: flex; flex-direction: column; gap: 12px;">
        <span class="panel-title">⚡ Investigation Presets</span>

        <button class="btn btn-sm narrator-preset" data-query="What is the current health status and any active incident alerts across the fleet?">
          🔍 Fleet Health & Incidents
        </button>

        <button class="btn btn-sm narrator-preset" data-query="Correlate recent security intrusion events with CPU or network anomalies.">
          🛡️ Correlate Security & Performance
        </button>

        <button class="btn btn-sm narrator-preset" data-query="Identify idle or over-provisioned cloud instances and summarize potential monthly savings.">
          💰 Cost Optimization Opportunities
        </button>

        <button class="btn btn-sm narrator-preset" data-query="Are there any persistent memory leaks or disk exhaustion trends predicted?">
          📈 Predictive Failure & Forecasts
        </button>

        <div style="margin-top: auto; padding: 10px; background: var(--bg-surface-elevated); border-radius: var(--radius-sm); font-size: 11px; color: var(--text-muted);">
          <strong>🔒 Grounded AI Guarantee:</strong> Responses are deterministically joined from active database records and telemetry models. Inferences must be verified before executing remediation.
        </div>
      </div>
    </div>
  `;

  const chatHistory = document.getElementById("narrator-chat-history");
  const inputEl = document.getElementById("narrator-input");
  const sendBtn = document.getElementById("narrator-send-btn");

  const submitQuery = async (queryText) => {
    if (!queryText || !queryText.trim()) return;
    const q = queryText.trim();
    if (inputEl) inputEl.value = "";

    // Append User Bubble
    const userMsg = document.createElement("div");
    userMsg.className = "message-bubble user";
    userMsg.textContent = q;
    chatHistory.appendChild(userMsg);

    // Append Assistant Loading
    const loadingMsg = document.createElement("div");
    loadingMsg.className = "message-bubble assistant";
    loadingMsg.innerHTML = `<em>Correlating signals across telemetry, security logs, and cost catalogs...</em>`;
    chatHistory.appendChild(loadingMsg);
    chatHistory.scrollTop = chatHistory.scrollHeight;

    try {
      const resp = await api.queryNarrator(q);
      
      loadingMsg.innerHTML = `
        <div style="font-weight: 700; color: var(--status-ai); margin-bottom: 8px;">🤖 Grounded Incident Explanation</div>
        <div>${renderSafeMarkdown(resp.raw_markdown_narrative)}</div>
        <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid var(--border-subtle); font-size: 10.5px; color: var(--text-muted);">
          <strong>CITED DATA SOURCES:</strong> ${resp.structured_explanation.cited_data_sources.map(s => `<code class="mono" style="background: var(--bg-app); padding: 1px 4px; border-radius: 2px;">${escapeHtml(s)}</code>`).join(" ")}
        </div>
      `;
    } catch (err) {
      loadingMsg.innerHTML = `<span class="text-critical">Failed to execute reasoning inquiry: ${escapeHtml(err.message)}</span>`;
    }

    chatHistory.scrollTop = chatHistory.scrollHeight;
  };

  if (sendBtn) {
    sendBtn.onclick = () => submitQuery(inputEl.value);
  }
  if (inputEl) {
    inputEl.onkeydown = (e) => {
      if (e.key === "Enter") submitQuery(inputEl.value);
    };
  }

  container.querySelectorAll(".narrator-preset").forEach(btn => {
    btn.onclick = () => submitQuery(btn.getAttribute("data-query"));
  });
}
