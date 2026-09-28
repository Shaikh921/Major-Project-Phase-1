/**
 * Main Application Orchestrator & View Router.
 *
 * Implements centralized authentication gating, role-based view permissions,
 * header user session controls, and background polling.
 */

import { store, ENVIRONMENTS, TIME_RANGES } from "./config.js?v=3.3.0";
import { api } from "./api.js?v=3.3.0";
import { authManager } from "./auth.js?v=3.3.0";
import { currencyManager } from "./currency.js?v=3.3.0";
import { escapeHtml } from "./sanitizer.js?v=3.3.0";
import { renderIcon } from "./components/Icons.js?v=3.3.0";
import { openCommandPalette } from "./components/CommandPalette.js?v=3.3.0";
import { renderNotificationDrawer } from "./components/NotificationCenter.js?v=3.3.0";

// View Imports
import { renderAuthView } from "./views/AuthView.js?v=3.3.0";
import { renderOverviewView } from "./views/OverviewView.js?v=3.3.0";
import { renderResourcesView } from "./views/ResourcesView.js?v=3.3.0";
import { renderMetricsView } from "./views/MetricsView.js?v=3.3.0";
import { renderAnomaliesView } from "./views/AnomaliesView.js?v=3.3.0";
import { renderIncidentsView } from "./views/IncidentsView.js?v=3.3.0";
import { renderSecurityView } from "./views/SecurityView.js?v=3.3.0";
import { renderCostView } from "./views/CostView.js?v=3.3.0";
import { renderNarratorView } from "./views/NarratorView.js?v=3.3.0";
import { renderReportsView } from "./views/ReportsView.js?v=3.3.0";
import { renderAuditView } from "./views/AuditView.js?v=3.3.0";
import { renderSettingsView } from "./views/SettingsView.js?v=3.3.0";
import { renderAdminManagementView } from "./views/AdminManagementView.js?v=3.3.0";

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
  "admin-management": renderAdminManagementView,
};

let pollTimer = null;

export async function initApp() {
  bindGlobalShortcuts();
  bindHeaderControls();
  bindSidebarNavigation();

  // Subscribe to Auth state changes
  authManager.subscribe((event) => {
    updateAuthUiState();
    if (authManager.isAuthenticated) {
      navigateTo(store.currentView);
      startPolling();
    } else {
      stopPolling();
      renderUnauthenticatedView();
    }
  });

  // Subscribe to Currency changes to refresh active financial view
  currencyManager.subscribe(() => {
    if (authManager.isAuthenticated) {
      navigateTo(store.currentView);
    }
  });

  // Subscribe to general State Store changes
  store.subscribe((state) => {
    if (authManager.isAuthenticated) {
      navigateTo(state.currentView);
    }
  });

  // Listen to hash changes (e.g. #verify-email or #reset-password)
  window.addEventListener("hashchange", handleHashChange);

  // Check if active session exists in HttpOnly cookie or direct hash route
  const hasSession = await authManager.checkExistingSession();
  updateAuthUiState();

  if (hasSession) {
    navigateTo(store.currentView);
    startPolling();
  } else {
    handleHashChange();
  }
}

function handleHashChange() {
  const hash = window.location.hash || "";
  const container = document.getElementById("view-container");
  if (!container) return;

  if (
    hash.startsWith("#verify-email") ||
    hash.startsWith("#reset-password") ||
    hash.startsWith("#verify-admin-request") ||
    hash.startsWith("#activate-admin")
  ) {
    renderAuthView(container);
  } else if (!authManager.isAuthenticated) {
    renderUnauthenticatedView();
  } else {
    navigateTo(store.currentView);
  }
}

function renderUnauthenticatedView() {
  const container = document.getElementById("view-container");
  if (!container) return;

  // Clear sidebar active highlights
  document.querySelectorAll(".nav-item").forEach(item => item.classList.remove("active"));
  renderAuthView(container);
}

function updateAuthUiState() {
  const userContainer = document.getElementById("header-user-container");
  const sidebarNav = document.querySelector(".sidebar-nav");

  if (authManager.isAuthenticated) {
    const user = authManager.currentUser;
    let roleBadgeClass = "badge-healthy";
    let roleLabel = user.role || "USER";

    if (user.role === "SUPER_ADMIN") {
      roleBadgeClass = "badge-warning";
      roleLabel = "SUPER ADMIN";
    } else if (user.role === "ADMIN") {
      roleBadgeClass = "badge-critical";
      roleLabel = "ADMIN";
    } else if (user.role === "OPERATOR") {
      roleBadgeClass = "badge-info";
      roleLabel = "OPERATOR";
    }

    if (userContainer) {
      userContainer.innerHTML = `
        <div class="header-user-profile">
          <div class="header-user-details">
            <span class="mono text-primary font-weight-bold header-user-email" title="${escapeHtml(user.email)}">${escapeHtml(user.email)}</span>
            <span class="badge ${roleBadgeClass} header-user-badge">${escapeHtml(roleLabel)}</span>
          </div>
          <button class="btn btn-sm btn-icon" id="header-logout-btn" title="Sign Out (${escapeHtml(user.email)})" aria-label="Sign Out" style="color: var(--text-muted); flex-shrink: 0;">
            ${renderIcon("log-out", { size: "sm" })}
          </button>
        </div>
      `;

      const logoutBtn = document.getElementById("header-logout-btn");
      if (logoutBtn) {
        logoutBtn.onclick = async () => {
          try {
            await api.logout();
          } catch {
            // ignore network errors on logout
          }
          authManager.clearSession();
        };
      }
    }

    // Role-based visibility for Sidebar navigation items
    document.querySelectorAll(".nav-item").forEach(item => {
      const view = item.getAttribute("data-view");
      if (view === "admin-management") {
        item.style.display = authManager.isSuperAdmin() ? "flex" : "none";
      } else if (view === "audit" || view === "settings") {
        item.style.display = authManager.isAdmin() ? "flex" : "none";
      } else {
        item.style.display = "flex";
      }
    });

  } else {
    if (userContainer) {
      userContainer.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px; padding-left: 8px; border-left: 1px solid var(--border-subtle);">
          <span class="badge badge-info" style="font-size: 10px;">GUEST / UNAUTHENTICATED</span>
        </div>
      `;
    }

    // Hide administrative navigation tabs for unauthenticated users
    document.querySelectorAll(".nav-item").forEach(item => {
      const view = item.getAttribute("data-view");
      if (view === "admin-management" || view === "audit" || view === "settings") {
        item.style.display = "none";
      }
    });
  }
}

function navigateTo(viewKey) {
  if (!authManager.isAuthenticated) {
    renderUnauthenticatedView();
    return;
  }

  // Guard super admin and admin views
  if (viewKey === "admin-management" && !authManager.isSuperAdmin()) {
    viewKey = "overview";
  } else if ((viewKey === "audit" || viewKey === "settings") && !authManager.isAdmin()) {
    viewKey = "overview";
  }

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

function bindGlobalShortcuts() {
  document.addEventListener("keydown", (e) => {
    // Ctrl + K or Cmd + K for Command Palette
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (authManager.isAuthenticated) {
        openCommandPalette();
      }
    }
  });

  const searchTrigger = document.getElementById("global-search-trigger");
  if (searchTrigger) {
    searchTrigger.onclick = () => {
      if (authManager.isAuthenticated) {
        openCommandPalette();
      }
    };
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

  const currencySelect = document.getElementById("global-currency-select");
  if (currencySelect) {
    currencySelect.value = currencyManager.displayCurrency;
    currencySelect.onchange = async (e) => {
      await currencyManager.setDisplayCurrency(e.target.value);
    };
  }

  const notifBtn = document.getElementById("notif-drawer-toggle");
  const notifDrawer = document.getElementById("notification-drawer");
  if (notifBtn && notifDrawer) {
    notifBtn.onclick = () => {
      if (authManager.isAuthenticated) {
        notifDrawer.classList.toggle("active");
        fetchNotifications();
      }
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
        if (!authManager.isAuthenticated) {
          renderUnauthenticatedView();
        } else {
          store.setState({ currentView: view });
        }
      }
    };
  });
}

async function fetchNotifications() {
  if (!authManager.isAuthenticated) return;
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
    if (store.autoRefreshEnabled && authManager.isAuthenticated) {
      fetchNotifications();
    }
  }, store.refreshInterval * 1000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

// Auto-boot on DOM ready
document.addEventListener("DOMContentLoaded", initApp);
