/**
 * Global Command Palette (Ctrl + K) for rapid operational navigation & search.
 */

import { escapeHtml } from "../sanitizer.js";
import { store } from "../config.js";
import { openModal, closeModal } from "./Modal.js";
import { renderIcon } from "./Icons.js";

export function openCommandPalette() {
  const content = `
    <div style="display: flex; flex-direction: column; gap: 10px;">
      <input type="text" id="cmd-search-input" class="input-control" placeholder="Search hosts, alerts, security events, or jump to view..." style="width: 100%; font-size: 13px;" autofocus aria-label="Search or jump to view">
      <div id="cmd-results-list" style="display: flex; flex-direction: column; gap: 4px; max-height: 280px; overflow-y: auto; padding-top: 4px;">
        <div class="nav-item" data-view="overview">${renderIcon("layout-dashboard", { size: "sm" })} Jump to Overview</div>
        <div class="nav-item" data-view="resources">${renderIcon("server", { size: "sm" })} Jump to Infrastructure / Resources</div>
        <div class="nav-item" data-view="metrics">${renderIcon("activity", { size: "sm" })} Jump to Metric Telemetry</div>
        <div class="nav-item" data-view="anomalies">${renderIcon("scan-search", { size: "sm" })} Jump to Anomaly Center</div>
        <div class="nav-item" data-view="incidents">${renderIcon("zap", { size: "sm" })} Jump to Incidents</div>
        <div class="nav-item" data-view="security">${renderIcon("shield", { size: "sm" })} Jump to Security Operation Center</div>
        <div class="nav-item" data-view="cost">${renderIcon("wallet", { size: "sm" })} Jump to Cost Intelligence</div>
        <div class="nav-item" data-view="narrator">${renderIcon("bot", { size: "sm" })} Jump to AI Incident Narrator</div>
        <div class="nav-item" data-view="reports">${renderIcon("file-text", { size: "sm" })} Jump to Reports & Export</div>
        <div class="nav-item" data-view="audit">${renderIcon("clipboard-list", { size: "sm" })} Jump to Audit Trail</div>
        <div class="nav-item" data-view="settings">${renderIcon("sliders", { size: "sm" })} Jump to Threshold Rules</div>
      </div>
    </div>
  `;

  openModal("Command Center Navigation (Ctrl + K)", content);

  setTimeout(() => {
    const input = document.getElementById("cmd-search-input");
    if (input) {
      input.focus();
      input.oninput = (e) => filterCommandResults(e.target.value);
    }

    const items = document.querySelectorAll("#cmd-results-list .nav-item");
    items.forEach(item => {
      item.onclick = () => {
        const view = item.getAttribute("data-view");
        if (view) {
          store.setState({ currentView: view });
          closeModal();
        }
      };
    });
  }, 50);
}

function filterCommandResults(query) {
  const q = query.toLowerCase().trim();
  const items = document.querySelectorAll("#cmd-results-list .nav-item");
  items.forEach(item => {
    const text = item.textContent.toLowerCase();
    item.style.display = text.includes(q) ? "flex" : "none";
  });
}
