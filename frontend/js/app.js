/**
 * Main Application Orchestrator & View Router.
 */

import { store, ENVIRONMENTS, TIME_RANGES } from "./config.js";
import { api } from "./api.js";
import { escapeHtml } from "./sanitizer.js";
import { openCommandPalette } from "./components/CommandPalette.js";
import { renderNotificationDrawer } from "./components/NotificationCenter.js";

// View Imports
import { renderOverviewView } from "./views/OverviewView.js";
import { renderResourcesView } from "./views/ResourcesView.js";
import { renderMetricsView } from "./views/MetricsView.js";
import { renderAnomaliesView } from "./views/AnomaliesView.js";
import { renderIncidentsView } from "./views/IncidentsView.js";
import { renderSecurityView } from "./views/SecurityView.js";
import { renderCostView } from "./views/CostView.js";
import { renderNarratorView } from "./views/NarratorView.js";
import { renderReportsView } from "./views/ReportsView.js";
import { renderAuditView } from "./views/AuditView.js";
import { renderSettingsView } from "./views/SettingsView.js";

const VIEW_MAP = {
  overview: renderOverviewView,
  resources: renderResourcesView,
  metrics: renderMetricsView,
  anomalies: renderAnomaliesView,
  incidents: renderIncidentsView,
  security: renderSecurityView,
  cost: renderCostView,
  narrator: renderNarratorView,
  reports: renderReportsView,
  audit: renderAuditView,
  settings: renderSettingsView,
};

let pollTimer = null;

export function initApp() {
  bindGlobalShortcuts();
  bindHeaderControls();
  bindSidebarNavigation();

  // Subscribe to state changes
  store.subscribe(onStateChange);

  // Initial Route Render
  navigateTo(store.currentView);

  // Start background notification & telemetry polling
  startPolling();
}

function navigateTo(viewKey) {
  const renderFn = VIEW_MAP[viewKey] || renderOverviewView;
  const container = document.getElementById("view-container");
  if (!container) return;

  // Update Sidebar active state
  document.querySelectorAll(".nav-item").forEach(item => {
    if (item.getAttribute("data-view") === viewKey) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });

  renderFn(container);
}

function onStateChange(state) {
  navigateTo(state.currentView);
}

function bindGlobalShortcuts() {
  document.addEventListener("keydown", (e) => {
    // Ctrl + K or Cmd + K for Command Palette
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      openCommandPalette();
    }
  });

  const searchTrigger = document.getElementById("global-search-trigger");
  if (searchTrigger) {
    searchTrigger.onclick = openCommandPalette;
  }
}

function bindHeaderControls() {
  const envSelect = document.getElementById("global-env-select");
  if (envSelect) {
    envSelect.onchange = (e) => {
      store.setState({ currentEnvironment: e.target.value });
    };
  }

  const timeSelect = document.getElementById("global-time-select");
  if (timeSelect) {
    timeSelect.onchange = (e) => {
      store.setState({ currentTimeRange: e.target.value });
    };
  }

  const notifBtn = document.getElementById("notif-drawer-toggle");
  const notifDrawer = document.getElementById("notification-drawer");
  if (notifBtn && notifDrawer) {
    notifBtn.onclick = () => {
      notifDrawer.classList.toggle("active");
      fetchNotifications();
    };
  }

  const sidebarToggle = document.getElementById("sidebar-collapse-btn");
  const sidebar = document.getElementById("sidebar");
  if (sidebarToggle && sidebar) {
    sidebarToggle.onclick = () => {
      sidebar.classList.toggle("collapsed");
    };
  }
}

function bindSidebarNavigation() {
  document.querySelectorAll(".nav-item").forEach(item => {
    item.onclick = () => {
      const view = item.getAttribute("data-view");
      if (view) {
        store.setState({ currentView: view });
      }
    };
  });
}

async function fetchNotifications() {
  try {
    const alerts = await api.getAlerts({ limit: 15 });
    const secEvents = await api.getSecurityEvents({ limit: 10 }).catch(() => []);

    const notifs = [
      ...alerts.map(a => ({
        source: a.kind.toUpperCase(),
        severity: a.severity,
        message: `${a.hostname || 'Host'}: ${a.message}`,
        timestamp: a.created_at,
      })),
      ...secEvents.map(s => ({
        source: "SECURITY",
        severity: s.severity,
        message: `${s.event_type}: ${s.description}`,
        timestamp: s.timestamp,
      })),
    ];

    notifs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

    const badge = document.getElementById("notif-badge");
    if (badge) {
      const activeCount = alerts.filter(a => a.status === "active").length;
      badge.textContent = activeCount;
      badge.style.display = activeCount > 0 ? "inline-block" : "none";
    }

    renderNotificationDrawer(notifs);
  } catch (err) {
    console.error("Failed to fetch notifications", err);
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  fetchNotifications();
  pollTimer = setInterval(() => {
    if (store.autoRefreshEnabled) {
      fetchNotifications();
    }
  }, store.refreshInterval * 1000);
}

// Auto-boot on DOM ready
document.addEventListener("DOMContentLoaded", initApp);
