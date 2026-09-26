/**
 * High-Density Sparkbar Component.
 */

import { escapeHtml } from "../sanitizer.js";

export function renderSparkbar(value, unit = "%", warnThreshold = 80, critThreshold = 90) {
  const val = Math.max(0, Math.min(100, Number(value) || 0));
  let stateCls = "healthy";
  if (val >= critThreshold) stateCls = "critical";
  else if (val >= warnThreshold) stateCls = "warning";

  return `
    <div class="sparkbar-container" title="${val.toFixed(1)}${escapeHtml(unit)}" aria-label="Resource load ${val.toFixed(1)} percent">
      <div class="sparkbar-track">
        <div class="sparkbar-fill ${stateCls}" style="width: ${val}%"></div>
      </div>
      <span class="sparkbar-val ${val >= warnThreshold ? (val >= critThreshold ? 'text-critical' : 'text-warning') : 'text-secondary'}">
        ${val.toFixed(0)}${escapeHtml(unit)}
      </span>
    </div>
  `;
}
