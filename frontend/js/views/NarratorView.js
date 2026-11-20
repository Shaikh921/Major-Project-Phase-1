/**
 * Narrator View - AI Incident Narrator & Cross-Module Reasoning (Module 5).
 */

import { api } from "../api.js?v=3.6.1";
import { escapeHtml, renderSafeMarkdown, formatTimestamp } from "../sanitizer.js";
import { renderIcon } from "../components/Icons.js";

export async function renderNarratorView(container) {
  container.innerHTML = `
    <div class="view-header">
      <div class="view-title-group">
        <h1>AI Incident Narrator & Cross-Module Reasoning</h1>
        <p>Conversational root-cause investigation grounded across Telemetry, Alerts, Security, and Cost (M5).</p>
      </div>
      <div>
        <span class="badge badge-ai">RAG-Augmented SRE Intelligence (Gemini 2.0)</span>
      </div>
    </div>

    <!-- Narrator Main Workspace -->
    <div class="narrator-container">
      <!-- Chat Interface -->
      <div class="narrator-chat-box">
        <div class="narrator-messages" id="narrator-chat-history">
          <div class="message-bubble assistant">
            <div style="font-weight: 700; color: var(--status-ai); margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
              ${renderIcon("bot", { size: "sm" })} SRE Incident Intelligence Agent
            </div>
            <div>
              Welcome to the <strong>AI Incident Narrator</strong>. I continuously correlate multi-domain signals across Performance Metrics, Isolation Forest & LSTM Anomaly Residuals, Security Flow Logs, and Cloud Cost Catalogs.
              <br><br>
              Select an investigation preset below or enter a custom operational inquiry.
            </div>
          </div>
        </div>

        <div class="narrator-input-bar">
          <input type="text" id="narrator-input" class="input-control" placeholder="Ask about fleet health, root cause, security correlations..." style="flex: 1;" aria-label="Narrator inquiry">
          <button class="btn btn-primary" id="narrator-send-btn">Ask Narrator ⏎</button>
        </div>
      </div>

      <!-- Quick Investigation Presets -->
      <div class="panel" style="display: flex; flex-direction: column; gap: 12px;">
        <span class="panel-title">${renderIcon("zap", { size: "sm" })} Investigation Presets</span>

        <button class="btn btn-sm narrator-preset" data-query="What is the current health status and any active incident alerts across the fleet?">
          ${renderIcon("search", { size: "xs" })} Fleet Health & Incidents
        </button>

        <button class="btn btn-sm narrator-preset" data-query="Correlate recent security intrusion events with CPU or network anomalies.">
          ${renderIcon("shield", { size: "xs" })} Correlate Security & Performance
        </button>

        <button class="btn btn-sm narrator-preset" data-query="Identify idle or over-provisioned cloud instances and summarize potential monthly savings.">
          ${renderIcon("wallet", { size: "xs" })} Cost Optimization Opportunities
        </button>

        <button class="btn btn-sm narrator-preset" data-query="Are there any persistent memory leaks or disk exhaustion trends predicted?">
          ${renderIcon("activity", { size: "xs" })} Predictive Failure & Forecasts
        </button>

        <div style="margin-top: auto; padding: 10px; background: var(--bg-surface-elevated); border-radius: var(--radius-sm); font-size: 11px; color: var(--text-muted); display: flex; align-items: flex-start; gap: 6px;">
          <span style="flex-shrink: 0; margin-top: 2px;">${renderIcon("lock", { size: "xs" })}</span>
          <div>
            <strong>Grounded AI Guarantee:</strong> Responses are deterministically joined from active database records and telemetry models. Inferences must be verified before executing remediation.
          </div>
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

      const struct = resp.structured_explanation || {};
      const modelBadge = struct.model_used || "RAG-Augmented SRE Engine";
      const retrievedChunks = struct.retrieved_chunks || [];
      const citations = struct.cited_data_sources || [];

      let chunksHtml = "";
      if (retrievedChunks.length > 0) {
        chunksHtml = `
          <div style="margin-top: 14px; background: #F8FAFC; border: 1px solid var(--border-default); border-radius: var(--radius-md); padding: 12px;">
            <div style="font-size: 11px; font-weight: 700; color: var(--text-secondary); margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
              <span style="display: flex; align-items: center; gap: 5px;">
                ${renderIcon("file-text", { size: "xs" })} Retrieved Knowledge & Operational Signals (${retrievedChunks.length})
              </span>
              <span class="badge badge-healthy badge-sm">
                BM25 + Dense Hybrid
              </span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 6px;">
              ${retrievedChunks.map(rc => {
          const isRunbook = rc.source_type === "runbook" || (rc.reference_id && rc.reference_id.startsWith("RUNBOOK"));
          const typeLabel = isRunbook
            ? `<span class="badge badge-info badge-sm">Runbook</span>`
            : `<span class="badge badge-warning badge-sm">Telemetry</span>`;
          return `
                  <div style="padding: 6px 10px; background: #FFFFFF; border: 1px solid var(--border-default); border-radius: 4px; font-size: 11.5px; display: flex; justify-content: space-between; align-items: center; gap: 8px;">
                    <div style="display: flex; align-items: center; gap: 6px; overflow: hidden;">
                      ${typeLabel}
                      <span style="font-weight: 600; color: var(--text-primary); white-space: nowrap;">[${escapeHtml(rc.reference_id || 'DOC')}]</span>
                      <span style="color: var(--text-secondary); text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${escapeHtml(rc.title || 'Signal')}</span>
                      ${rc.section ? `<span style="color: var(--text-muted); font-size: 10px; white-space: nowrap;"> &rsaquo; ${escapeHtml(rc.section)}</span>` : ''}
                    </div>
                    <span class="mono" style="font-size: 10px; color: var(--text-muted); background: #F1F5F9; border: 1px solid var(--border-subtle); padding: 2px 6px; border-radius: 3px; white-space: nowrap;">
                      Match: ${(rc.score * 100).toFixed(0)}%
                    </span>
                  </div>
                `;
        }).join("")
          }
            </div >
          </div >
    `;
      }

      loadingMsg.innerHTML = `
    < div style = "font-weight: 700; color: var(--status-ai); margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;" >
          <div style="display: flex; align-items: center; gap: 6px;">
            ${renderIcon("bot", { size: "sm" })} Grounded Incident Explanation
          </div>
          <span class="badge badge-sm badge-ai" style="font-size: 10px;">${escapeHtml(modelBadge)}</span>
        </div >
    <div>${renderSafeMarkdown(resp.raw_markdown_narrative)}</div>
        ${chunksHtml}
  <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid var(--border-subtle); font-size: 10.5px; color: var(--text-muted);">
    <strong>CITED DATA SOURCES:</strong> ${citations.map(s => `<code class="mono" style="background: var(--bg-app); padding: 1px 4px; border-radius: 2px; margin-right: 4px; display: inline-block; margin-top: 2px;">${escapeHtml(s)}</code>`).join(" ")}
  </div>
  `;
    } catch (err) {
      loadingMsg.innerHTML = `< span class="text-critical" > Failed to execute reasoning inquiry: ${escapeHtml(err.message)}</span > `;
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
