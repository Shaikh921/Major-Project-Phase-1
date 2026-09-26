/**
 * Global Command Palette (Ctrl + K) for rapid operational navigation & search.
 */

import { escapeHtml } from "../sanitizer.js";
import { store } from "../config.js";
import { openModal, closeModal } from "./Modal.js";

export function openCommandPalette() {
  const content = `
    <div style="display: flex; flex-direction: column; gap: 10px;">
      <input type="text" id="cmd-search-input" class="input-control" placeholder="Search hosts, alerts, security events, or jump to view..." style="width: 100%; font-size: 13px;" autofocus>
      <div id="cmd-results-list" style="display: flex; flex-direction: column; gap: 4px; max-height: 280px; overflow-y: auto; padding-top: 4px;">
        <div class="nav-item" data-view="overview">⚡ Jump to Overview</div>
        <div class="nav-item" data-view="resources">🖥️ Jump to Infrastructure / Resources</div>
        <div class="nav-item" data-view="metrics">📈 Jump to Metric Telemetry</div>
        <div class="nav-item" data-view="anomalies">🔍 Jump to Anomaly Center</div>
        <div class="nav-item" data-view="security">🛡️ Jump to Security Operation Center</div>
        <div class="nav-item" data-view="cost">💰 Jump to Cost Intelligence</div>
        <div class="nav-item" data-view="narrator">🤖 Jump to AI Incident Narrator</div>
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
