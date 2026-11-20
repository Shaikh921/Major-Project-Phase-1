/**
 * Global Command Palette (Ctrl + K) for rapid operational navigation & search.
 *
 * Supports fuzzy search across all command center views, active host resources,
 * role-gated administration destinations, and keyboard navigation (Up/Down/Enter/Escape).
 */

import { escapeHtml } from "../sanitizer.js";
import { store } from "../config.js";
import { authManager } from "../auth.js";
import { api } from "../api.js";
import { openModal, closeModal } from "./Modal.js";
import { renderIcon } from "./Icons.js";

let cachedHosts = [];
let hostsFetched = false;

function getNavigationCommands() {
  const isSuper = authManager.isSuperAdmin();
  const isAdmin = authManager.isAdmin();

  const commands = [
    {
      view: "overview",
      title: "Jump to Overview",
      category: "Operations",
      keywords: "home dashboard summary fleet health",
      icon: "layout-dashboard",
    },
    {
      view: "resources",
      title: "Jump to Infrastructure / Resources",
      category: "Operations",
      keywords: "hosts servers nodes vms hardware cpu memory",
      icon: "server",
    },
    {
      view: "metrics",
      title: "Jump to Telemetry Stream",
      category: "Operations",
      keywords: "charts metrics telemetry live graphs stream time horizon",
      icon: "activity",
    },
    {
      view: "lab",
      title: "Jump to Lab PCs & Hardware",
      category: "Operations",
      keywords: "lab pcs workstations rooms hardware sensors telemetry physical",
      icon: "monitor",
    },
    {
      view: "anomalies",
      title: "Jump to Anomaly Center",
      category: "Detection & Triage",
      keywords: "anomalies ml isolation forest lstm ai alerts triage scores",
      icon: "scan-search",
    },
    {
      view: "incidents",
      title: "Jump to Incidents",
      category: "Detection & Triage",
      keywords: "incidents critical alerts alarms acknowledge resolution issues",
      icon: "zap",
    },
    {
      view: "security",
      title: "Jump to Security & Threat",
      category: "Detection & Triage",
      keywords: "security threat soc brute force intrusion ban events ip",
      icon: "shield",
    },
    {
      view: "cost",
      title: "Jump to Cost Intelligence",
      category: "Intelligence & Analysis",
      keywords: "cost optimization savings idle currency finops spend dollars",
      icon: "wallet",
    },
    {
      view: "narrator",
      title: "Jump to AI Incident Narrator",
      category: "Intelligence & Analysis",
      keywords: "ai narrator llm assistant chat incident root cause query",
      icon: "bot",
    },
    {
      view: "reports",
      title: "Jump to Reports & Export",
      category: "Intelligence & Analysis",
      keywords: "reports export compliance markdown csv audit download generate",
      icon: "file-text",
    },
  ];

  if (isSuper) {
    commands.push({
      view: "device-management",
      title: "Jump to Lab PC Fleet & Devices",
      category: "Administration",
      keywords: "devices enrollment sensors approval tokens fleet lab management",
      icon: "cpu",
    });
    commands.push({
      view: "admin-management",
      title: "Jump to Admin Management",
      category: "Administration",
      keywords: "admin users roles permissions superadmin accounts privileges",
      icon: "shield-alert",
    });
  }

  if (isAdmin) {
    commands.push({
      view: "audit",
      title: "Jump to Audit Trail",
      category: "Administration",
      keywords: "audit trail security logs tamper proof immutable actions history",
      icon: "clipboard-list",
    });
    commands.push({
      view: "settings",
      title: "Jump to Threshold Rules",
      category: "Administration",
      keywords: "rules settings thresholds alerts limits configuration cpu disk memory",
      icon: "sliders",
    });
  }

  return commands;
}

export function openCommandPalette() {
  const commands = getNavigationCommands();

  const content = `
    <div style="display: flex; flex-direction: column; gap: 12px;">
      <div style="position: relative; display: flex; align-items: center;">
        <span style="position: absolute; left: 12px; color: var(--text-muted); pointer-events: none; display: inline-flex;">
          ${renderIcon("search", { size: "sm" })}
        </span>
        <input
          type="text"
          id="cmd-search-input"
          class="input-control"
          placeholder="Search views, hosts, alerts, or keywords..."
          style="width: 100%; font-size: 13.5px; padding-left: 36px; height: 38px;"
          autofocus
          aria-label="Search or jump to view"
        />
      </div>

      <div style="display: flex; align-items: center; justify-content: space-between; font-size: 11px; color: var(--text-muted); padding: 0 4px;">
        <span>NAVIGATION DESTINATIONS</span>
        <span>Use <kbd style="background: var(--bg-surface-elevated); padding: 1px 4px; border-radius: 3px; border: 1px solid var(--border-subtle);">↑</kbd> <kbd style="background: var(--bg-surface-elevated); padding: 1px 4px; border-radius: 3px; border: 1px solid var(--border-subtle);">↓</kbd> to navigate, <kbd style="background: var(--bg-surface-elevated); padding: 1px 4px; border-radius: 3px; border: 1px solid var(--border-subtle);">↵</kbd> to select</span>
      </div>

      <div id="cmd-results-list" style="display: flex; flex-direction: column; gap: 4px; max-height: 320px; overflow-y: auto; padding: 2px;">
        ${renderCommandItems(commands)}
      </div>
    </div>
  `;

  openModal("Command Center Navigation (Ctrl + K)", content);

  // Background fetch hosts for live search enrichment
  if (!hostsFetched && authManager.isAuthenticated) {
    api.getHosts().then(hosts => {
      cachedHosts = hosts || [];
      hostsFetched = true;
    }).catch(() => { });
  }

  setTimeout(() => {
    const input = document.getElementById("cmd-search-input");
    const resultsContainer = document.getElementById("cmd-results-list");
    if (!input || !resultsContainer) return;

    input.focus();
    bindResultItemClicks();

    let selectedIndex = 0;
    updateSelection(selectedIndex);

    input.oninput = (e) => {
      const q = e.target.value.toLowerCase().trim();
      const filtered = filterCommands(commands, q);
      const hostResults = filterHosts(q);

      resultsContainer.innerHTML = renderCombinedResults(filtered, hostResults);
      bindResultItemClicks();
      selectedIndex = 0;
      updateSelection(selectedIndex);
    };

    input.onkeydown = (e) => {
      const visibleItems = resultsContainer.querySelectorAll(".cmd-item:not([style*='display: none'])");
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (visibleItems.length > 0) {
          selectedIndex = (selectedIndex + 1) % visibleItems.length;
          updateSelection(selectedIndex);
        }
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (visibleItems.length > 0) {
          selectedIndex = (selectedIndex - 1 + visibleItems.length) % visibleItems.length;
          updateSelection(selectedIndex);
        }
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (visibleItems.length > 0 && visibleItems[selectedIndex]) {
          visibleItems[selectedIndex].click();
        }
      }
    };
  }, 50);
}

function renderCommandItems(commands) {
  return commands.map((c, i) => `
    <div
      class="nav-item cmd-item ${i === 0 ? 'active' : ''}"
      data-view="${escapeHtml(c.view)}"
      style="display: flex; align-items: center; justify-content: space-between; padding: 9px 12px; cursor: pointer; border-radius: var(--radius-sm);"
    >
      <div style="display: flex; align-items: center; gap: 10px;">
        <span style="color: var(--primary); display: inline-flex;">
          ${renderIcon(c.icon, { size: "sm" })}
        </span>
        <span style="font-weight: 500;">${escapeHtml(c.title)}</span>
      </div>
      <span class="badge badge-info" style="font-size: 10px; font-weight: 500; text-transform: uppercase;">
        ${escapeHtml(c.category)}
      </span>
    </div>
  `).join("");
}

function renderCombinedResults(filteredCommands, hostResults) {
  let html = "";
  if (filteredCommands.length > 0) {
    html += renderCommandItems(filteredCommands);
  }

  if (hostResults.length > 0) {
    html += `
      <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); padding: 8px 6px 4px 6px; letter-spacing: 0.08em; border-top: 1px solid var(--border-subtle); margin-top: 4px;">
        Matching Host Nodes
      </div>
    `;
    html += hostResults.map(h => `
      <div
        class="nav-item cmd-item"
        data-view="resources"
        data-host-id="${escapeHtml(String(h.id))}"
        style="display: flex; align-items: center; justify-content: space-between; padding: 9px 12px; cursor: pointer; border-radius: var(--radius-sm);"
      >
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="color: var(--status-healthy); display: inline-flex;">
            ${renderIcon("server", { size: "sm" })}
          </span>
          <span style="font-weight: 500;">${escapeHtml(h.hostname || 'Host')}</span>
          <span class="mono text-muted" style="font-size: 11px;">${escapeHtml(h.ip || '')}</span>
        </div>
        <span class="badge badge-healthy" style="font-size: 10px;">HOST NODE</span>
      </div>
    `).join("");
  }

  if (!html) {
    html = `
      <div style="padding: 24px 12px; text-align: center; color: var(--text-muted); font-size: 12.5px;">
        No features, views, or host resources match your search.
      </div>
    `;
  }

  return html;
}

function filterCommands(commands, query) {
  if (!query) return commands;
  return commands.filter(c => {
    const haystack = `${c.title} ${c.category} ${c.keywords} ${c.view}`.toLowerCase();
    return haystack.includes(query);
  });
}

function filterHosts(query) {
  if (!query || query.length < 2) return [];
  return cachedHosts.filter(h => {
    const haystack = `${h.hostname || ''} ${h.ip || ''} ${h.environment || ''} ${h.os || ''}`.toLowerCase();
    return haystack.includes(query);
  }).slice(0, 5);
}

function bindResultItemClicks() {
  const items = document.querySelectorAll("#cmd-results-list .cmd-item");
  items.forEach(item => {
    item.onclick = (e) => {
      e.preventDefault();
      e.stopPropagation();
      const view = item.getAttribute("data-view");
      if (view) {
        executeNavigation(view);
      }
    };
  });
}

function updateSelection(index) {
  const items = document.querySelectorAll("#cmd-results-list .cmd-item");
  items.forEach((item, i) => {
    if (i === index) {
      item.classList.add("active");
      item.scrollIntoView({ block: "nearest" });
    } else {
      item.classList.remove("active");
    }
  });
}

/**
 * Executes view navigation with triple-layer guarantee:
 * 1. Closes modal dialog immediately.
 * 2. Invokes window.navigateTo (or imported router).
 * 3. Updates state store and sidebar active indicators.
 */
export function executeNavigation(viewKey) {
  closeModal();

  if (typeof window.navigateTo === "function") {
    window.navigateTo(viewKey);
  } else {
    // Fallback directly to sidebar element trigger
    const sidebarItem = document.querySelector(`.sidebar-nav .nav-item[data-view="${viewKey}"]`);
    if (sidebarItem) {
      sidebarItem.click();
    }
  }

  store.setState({ currentView: viewKey });
}
