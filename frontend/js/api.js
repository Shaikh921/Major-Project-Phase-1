/**
 * Centralized REST API Client.
 * Handles request timeouts, status checks, error normalization, and caching.
 */

import { CONFIG } from "./config.js";

class ApiClient {
  constructor(baseUrl = CONFIG.API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), options.timeout || 12000);

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeout);

      if (!response.ok) {
        let errorDetail = `HTTP ${response.status} ${response.statusText}`;
        try {
          const errJson = await response.json();
          if (errJson.detail) errorDetail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
        } catch {
          // ignore json parse error on error response
        }
        throw new Error(errorDetail);
      }

      if (response.status === 204) return null;
      return await response.json();
    } catch (err) {
      clearTimeout(timeout);
      if (err.name === "AbortError") {
        throw new Error("API request timed out. Check backend connectivity.");
      }
      throw err;
    }
  }

  // --- API Methods ---

  // Summary
  getFleetSummary() {
    return this.request("/summary");
  }

  // Hosts
  getHosts(params = {}) {
    const qs = new URLSearchParams();
    if (params.active_only) qs.set("active_only", "true");
    if (params.environment && params.environment !== "all") qs.set("environment", params.environment);
    return this.request(`/hosts?${qs.toString()}`);
  }

  getHost(hostId) {
    return this.request(`/hosts/${hostId}`);
  }

  registerHost(hostData) {
    return this.request("/hosts", {
      method: "POST",
      body: JSON.stringify(hostData),
    });
  }

  deactivateHost(hostId) {
    return this.request(`/hosts/${hostId}`, {
      method: "DELETE",
    });
  }

  // Metrics
  getHostMetrics(hostId, limit = 100, startTime = null, endTime = null) {
    const qs = new URLSearchParams({ host_id: hostId, limit: String(limit) });
    if (startTime) qs.set("start_time", startTime);
    if (endTime) qs.set("end_time", endTime);
    return this.request(`/metrics?${qs.toString()}`);
  }

  // Alerts & Rules
  getAlerts(params = {}) {
    const qs = new URLSearchParams();
    if (params.host_id) qs.set("host_id", String(params.host_id));
    if (params.status) qs.set("status", params.status);
    if (params.severity) qs.set("severity", params.severity);
    if (params.kind) qs.set("kind", params.kind);
    if (params.limit) qs.set("limit", String(params.limit));
    return this.request(`/alerts?${qs.toString()}`);
  }

  acknowledgeAlert(alertId) {
    return this.request(`/alerts/${alertId}/ack`, { method: "POST" });
  }

  submitAlertFeedback(alertId, verdict, notes = "") {
    return this.request(`/alerts/${alertId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ verdict, operator_notes: notes }),
    });
  }

  getAlertRules() {
    return this.request("/alerts/rules");
  }

  createAlertRule(ruleData) {
    return this.request("/alerts/rules", {
      method: "POST",
      body: JSON.stringify(ruleData),
    });
  }

  deleteAlertRule(ruleId) {
    return this.request(`/alerts/rules/${ruleId}`, { method: "DELETE" });
  }

  // AI & Forecasting
  scoreTelemetrySample(features) {
    return this.request("/ai/score", {
      method: "POST",
      body: JSON.stringify({ features }),
    });
  }

  getMetricForecast(hostId, metric = "cpu_percent", horizonHours = 24) {
    const qs = new URLSearchParams({
      host_id: String(hostId),
      metric,
      horizon_hours: String(horizonHours),
    });
    return this.request(`/forecast?${qs.toString()}`);
  }

  getRegisteredModels() {
    return this.request("/ai/models");
  }

  // Security
  getSecuritySummary() {
    return this.request("/security/summary");
  }

  getSecurityEvents(params = {}) {
    const qs = new URLSearchParams();
    if (params.severity) qs.set("severity", params.severity);
    if (params.status) qs.set("status", params.status);
    return this.request(`/security/events?${qs.toString()}`);
  }

  updateSecurityStatus(eventId, status) {
    return this.request(`/security/events/${eventId}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  }

  // Cost
  getCostSummary() {
    return this.request("/cost/summary");
  }

  updateCostRecommendation(recId, status) {
    return this.request(`/cost/recommendations/${recId}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  }

  // Narrator
  queryNarrator(query, hostId = null, env = null, windowMinutes = 60) {
    return this.request("/narrator/query", {
      method: "POST",
      body: JSON.stringify({
        query,
        host_id: hostId,
        environment: env,
        time_window_minutes: windowMinutes,
      }),
    });
  }

  // Reports & Audit
  generateReport(timeRangeHours = 24, environment = null) {
    return this.request("/reports/generate", {
      method: "POST",
      body: JSON.stringify({ time_range_hours: timeRangeHours, environment }),
    });
  }

  getAuditLogs(action = null, limit = 50) {
    const qs = new URLSearchParams({ limit: String(limit) });
    if (action) qs.set("action", action);
    return this.request(`/audit/logs?${qs.toString()}`);
  }
}

export const api = new ApiClient();
