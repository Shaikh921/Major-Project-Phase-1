/**
 * Global Configuration & State Store
 */

export const CONFIG = {
  APP_NAME: "Cloud Intelligence",
  APP_VERSION: "3.0.0",
  API_BASE_URL: "/api/v1",
  POLL_INTERVAL_MS: 30000, // 30 seconds default
  DEFAULT_ENVIRONMENT: "all",
  DEFAULT_TIME_RANGE: "1h",
};

export const TIME_RANGES = [
  { label: "Last 15 Minutes", value: "15m", minutes: 15 },
  { label: "Last 1 Hour", value: "1h", minutes: 60 },
  { label: "Last 6 Hours", value: "6h", minutes: 360 },
  { label: "Last 24 Hours", value: "24h", minutes: 1440 },
  { label: "Last 7 Days", value: "7d", minutes: 10080 },
];

export const ENVIRONMENTS = [
  { label: "All Environments", value: "all" },
  { label: "Production", value: "production" },
  { label: "Staging", value: "staging" },
  { label: "Development", value: "development" },
];

class StateStore {
  constructor() {
    this.currentView = "overview";
    this.currentEnvironment = "all";
    this.currentTimeRange = "1h";
    this.autoRefreshEnabled = true;
    this.refreshInterval = 30; // seconds
    this.searchQuery = "";
    this.notifications = [];
    this.unreadNotificationsCount = 0;
    this.selectedHost = null;
    this.listeners = new Set();
  }

  setState(updates) {
    Object.assign(this, updates);
    this.notify();
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify() {
    for (const listener of this.listeners) {
      listener(this);
    }
  }
}

export const store = new StateStore();
