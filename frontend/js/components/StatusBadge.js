/**
 * Status and Severity Badges with Icons & Accessible Text.
 */

import { escapeHtml } from "../sanitizer.js";

export function renderStatusBadge(status) {
  const s = String(status || "unknown").toLowerCase();
  let label = "Unknown";
  let cls = "badge-info";
  let dotCls = "info";

  if (s === "healthy" || s === "operational" || s === "resolved" || s === "mitigated" || s === "normal") {
    label = s === "healthy" ? "Healthy" : (s === "operational" ? "Operational" : "Resolved");
    cls = "badge-healthy";
    dotCls = "healthy";
  } else if (s === "warning" || s === "degraded" || s === "investigating" || s === "acknowledged") {
    label = s.charAt(0).toUpperCase() + s.slice(1);
    cls = "badge-warning";
    dotCls = "warning";
  } else if (s === "critical" || s === "outage" || s === "open" || s === "active") {
    label = s.charAt(0).toUpperCase() + s.slice(1);
    cls = "badge-critical";
    dotCls = "critical";
  } else if (s === "ai" || s === "anomaly" || s === "forecast") {
    label = s.toUpperCase();
    cls = "badge-ai";
    dotCls = "info";
  }

  return `
    <span class="badge ${cls}" role="status" aria-label="Status: ${escapeHtml(label)}">
      <span class="status-dot ${dotCls}" aria-hidden="true"></span>
      <span>${escapeHtml(label)}</span>
    </span>
  `;
}

export function renderSeverityBadge(severity) {
  const sev = String(severity || "info").toLowerCase();
  let cls = "badge-info";
  if (sev === "critical") cls = "badge-critical";
  else if (sev === "warning" || sev === "high") cls = "badge-warning";
  else if (sev === "low" || sev === "info") cls = "badge-info";

  return `
    <span class="badge ${cls}">
      <span>${escapeHtml(sev.toUpperCase())}</span>
    </span>
  `;
}

export function renderSourceBadge(sourceType) {
  const src = String(sourceType || "UNKNOWN").toUpperCase();
  let label = "UNKNOWN";
  let cls = "badge-info";
  let dotCls = "info";

  if (src === "REAL_AGENT") {
    label = "REAL AGENT";
    cls = "badge-healthy";
    dotCls = "healthy";
  } else if (src === "SIMULATED") {
    label = "SIMULATED";
    cls = "badge-info";
    dotCls = "info";
  } else if (src === "CLOUD_PROVIDER") {
    label = "CLOUD API";
    cls = "badge-warning";
    dotCls = "warning";
  }

  return `
    <span class="badge ${cls}" role="status" aria-label="Source: ${escapeHtml(label)}" style="letter-spacing: 0.5px; font-weight: 600;">
      <span class="status-dot ${dotCls}" aria-hidden="true"></span>
      <span>${escapeHtml(label)}</span>
    </span>
  `;
}
