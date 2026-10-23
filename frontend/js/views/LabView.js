/**
/**
 * Lab PC Monitoring View - High-Density Room-Grouped SRE Dashboard.
 * 
 * Displays physical computer lab hardware utilization (CPU, RAM, Disk),
 * automated heartbeat-based online/offline classification, busiest machines triage,
 * and room summaries with visibility-aware background polling.
 */

import { api } from "../api.js?v=3.3.0";
import { escapeHtml, formatRelativeTime, formatTimestamp } from "../sanitizer.js?v=3.3.0";
import { renderIcon } from "../components/Icons.js?v=3.3.0";

const REFRESH_INTERVAL_MS = 10000;

// Module-level lifecycle state
let activePollTimer = null;
let activeVisibilityHandler = null;
let currentContainer = null;

const labState = {
  environment: "lab",
  offlineAfterSeconds: 90,
  realAgentsOnly: true,
  isLoading: false,
};

/**
 * Main render function invoked by the application view router.
 * 
 * @param {HTMLElement} container - Target workspace DOM element.
 */
export async function renderLabView(container) {
  // Teardown any existing active polling from prior view mounts
  destroyLabView();
  currentContainer = container;

  // Initial skeleton loading view
  container.innerHTML = `
    <div class="view-header">
      <div class="view-title-group">
        <h1>Lab PC Monitoring</h1>
        <p>Real-time room-grouped physical machine telemetry, live CPU/RAM/Disk metrics, and offline heartbeat tracking.</p>
      </div>
    </div>
    <div class="state-container" style="min-height: 280px;">
      <div class="state-icon">${renderIcon("loader", { size: "xl", className: "icon-spin" })}</div>
      <div class="state-title">Querying Lab Hardware Telemetry...</div>
      <div class="state-description">Aggregating latest metric snapshots and evaluating heartbeat status across lab rooms.</div>
    </div>
  `;

  await fetchAndRenderLabData();

  // Initialize visibility-aware background polling
  startVisibilityAwarePolling();
}

/**
 * Fetches latest lab summary payload and updates the dashboard DOM.
 */
async function fetchAndRenderLabData() {
  if (!currentContainer) return;

  try {
    const data = await api.getLabSummary({
      environment: labState.environment,
      offline_after_seconds: labState.offlineAfterSeconds,
      real_agents_only: labState.realAgentsOnly,
    });

    if (!currentContainer) return;
    renderDashboardDom(data);
  } catch (err) {
    if (!currentContainer) return;
    renderErrorDom(err.message || "Failed to retrieve lab summary");
  }
}

/**
 * Builds and mounts the complete dashboard DOM tree.
 * 
 * @param {object} data - LabSummaryResponse payload from backend.
 */
function renderDashboardDom(data) {
  const totals = data.totals || { total_pcs: 0, online: 0, offline: 0, avg_cpu: null };
  const rooms = data.rooms || [];
  const busiest = data.busiest_pcs || [];

  currentContainer.innerHTML = `
    <div class="view-header">
      <div class="view-title-group">
        <div style="display: flex; align-items: center; gap: 10px;">
          <h1>Lab PC Monitoring</h1>
          <span class="badge badge-info" style="font-size: 11px; text-transform: uppercase;">
            ${escapeHtml(data.environment)}
          </span>
        </div>
        <p>Live physical workstation monitoring grouped by room coordinates. Auto-refreshes every 10 seconds.</p>
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <button class="btn btn-sm" id="lab-refresh-btn" title="Refresh Now">
          ${renderIcon("refresh-cw", { size: "sm" })} Refresh
        </button>
      </div>
    </div>

    <!-- Filter & Configuration Toolbar -->
    <div class="panel" style="padding: 10px 14px; margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
      <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
        <div style="display: flex; align-items: center; gap: 6px;">
          <label for="lab-env-input" style="font-size: 12px; color: var(--text-secondary); font-weight: 500;">Environment:</label>
          <input type="text" id="lab-env-input" class="input-control" value="${escapeHtml(labState.environment)}" style="width: 110px; height: 30px; font-size: 12px;" />
        </div>

        <div style="display: flex; align-items: center; gap: 6px;">
          <label for="lab-timeout-input" style="font-size: 12px; color: var(--text-secondary); font-weight: 500;">Heartbeat Cutoff:</label>
          <select id="lab-timeout-input" class="input-control" style="height: 30px; font-size: 12px; width: 110px;">
            <option value="60" ${labState.offlineAfterSeconds === 60 ? "selected" : ""}>60s (strict)</option>
            <option value="90" ${labState.offlineAfterSeconds === 90 ? "selected" : ""}>90s (default)</option>
            <option value="120" ${labState.offlineAfterSeconds === 120 ? "selected" : ""}>120s (2m)</option>
            <option value="300" ${labState.offlineAfterSeconds === 300 ? "selected" : ""}>300s (5m)</option>
          </select>
        </div>

        <label style="display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-secondary); cursor: pointer; user-select: none;">
          <input type="checkbox" id="lab-real-only-check" ${labState.realAgentsOnly ? "checked" : ""} style="cursor: pointer;" />
          <span>Real Agents Only</span>
        </label>
      </div>

      <div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">
        Last Synced: ${escapeHtml(new Date(data.generated_at).toLocaleTimeString())}
      </div>
    </div>

    <!-- Metric Metric Summary Cards -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 20px;">
      <div class="panel" style="padding: 14px 16px;">
        <div style="font-size: 12px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Total Workstations</div>
        <div style="font-size: 28px; font-weight: 700; color: var(--text-primary); margin-top: 4px;">
          ${totals.total_pcs}
        </div>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">Registered in inventory</div>
      </div>

      <div class="panel" style="padding: 14px 16px; border-left: 3px solid var(--status-healthy);">
        <div style="font-size: 12px; color: var(--status-healthy); text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Online & Streaming</div>
        <div style="font-size: 28px; font-weight: 700; color: var(--status-healthy); margin-top: 4px;">
          ${totals.online}
        </div>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">Active within ${data.offline_after_seconds}s</div>
      </div>

      <div class="panel" style="padding: 14px 16px; border-left: 3px solid ${totals.offline > 0 ? "var(--status-critical)" : "var(--border-subtle)"};">
        <div style="font-size: 12px; color: ${totals.offline > 0 ? "var(--status-critical)" : "var(--text-muted)"}; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Offline / Inactive</div>
        <div style="font-size: 28px; font-weight: 700; color: ${totals.offline > 0 ? "var(--status-critical)" : "var(--text-muted)"}; margin-top: 4px;">
          ${totals.offline}
        </div>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">Heartbeat missing or stopped</div>
      </div>

      <div class="panel" style="padding: 14px 16px; border-left: 3px solid var(--status-info);">
        <div style="font-size: 12px; color: var(--status-info); text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Fleet Avg CPU Load</div>
        <div style="font-size: 28px; font-weight: 700; color: var(--status-info); margin-top: 4px;">
          ${totals.avg_cpu !== null ? totals.avg_cpu.toFixed(1) + "%" : "--"}
        </div>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">Calculated across active PCs</div>
      </div>
    </div>

    <!-- Busiest Machines Triage Panel -->
    ${busiest.length > 0 ? renderBusiestPcsPanel(busiest) : ""}

    <!-- Room Sections or Empty State -->
    ${rooms.length > 0 ? renderRoomSections(rooms) : renderEmptyState(data.environment)}
  `;

  bindToolbarEvents();
}

/**
 * Renders the Busiest PCs ranking widget.
 */
function renderBusiestPcsPanel(busiest) {
  return `
    <div class="panel" style="padding: 14px 16px; margin-bottom: 20px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="color: var(--status-warning);">${renderIcon("zap", { size: "sm" })}</span>
          <span style="font-weight: 600; font-size: 13px;">Busiest Active Workstations (High Load Triage)</span>
        </div>
        <span style="font-size: 11px; color: var(--text-muted);">Top ${busiest.length} saturated nodes</span>
      </div>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px;">
        ${busiest.map(pc => `
          <div style="padding: 10px 12px; border-radius: 6px; background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: center;">
            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding-right: 8px;">
              <div class="mono" style="font-weight: 600; font-size: 12px;" title="${escapeHtml(pc.hostname)}">${escapeHtml(pc.hostname)}</div>
              <div style="font-size: 10px; color: var(--text-muted);">${escapeHtml(pc.room)} &middot; ${escapeHtml(pc.ip_address || "no IP")}</div>
            </div>
            <div style="text-align: right;">
              <span class="badge ${getCpuBadgeClass(pc.cpu_level)}" style="font-size: 11px; font-weight: 700;">
                ${pc.cpu_percent !== null ? pc.cpu_percent.toFixed(1) + "%" : "--"}
              </span>
            </div>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

/**
 * Renders room grouping containers and nested PC cards.
 */
function renderRoomSections(rooms) {
  return rooms.map(room => `
    <div class="panel" style="padding: 16px 18px; margin-bottom: 20px;">
      <!-- Room Header -->
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 1px solid var(--border-subtle);">
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="color: var(--status-info);">${renderIcon("server", { size: "md" })}</span>
          <h2 style="font-size: 15px; font-weight: 700; margin: 0; color: var(--text-primary); text-transform: uppercase;">
            ${escapeHtml(room.room)}
          </h2>
          <span class="badge badge-neutral" style="font-size: 11px;">
            ${room.total} ${room.total === 1 ? "PC" : "PCs"}
          </span>
        </div>
        <div style="display: flex; align-items: center; gap: 16px; font-size: 12px;">
          <div><span style="color: var(--status-healthy); font-weight: 600;">${room.online}</span> online</div>
          <div><span style="color: ${room.offline > 0 ? "var(--status-critical)" : "var(--text-muted)"}; font-weight: 600;">${room.offline}</span> offline</div>
          <div>Avg CPU: <strong style="color: var(--text-primary);">${room.avg_cpu !== null ? room.avg_cpu.toFixed(1) + "%" : "--"}</strong></div>
        </div>
      </div>

      <!-- Room PC Cards Grid -->
      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 12px;">
        ${room.pcs.map(pc => renderPcCard(pc)).join("")}
      </div>
    </div>
  `).join("");
}

/**
 * Renders an individual PC card with live telemetry indicators.
 */
function renderPcCard(pc) {
  const isOnline = pc.online;
  const statusColor = getStatusColor(pc.cpu_level, isOnline);
  const statusBadge = isOnline ? "ONLINE" : "OFFLINE";
  const cpuVal = pc.cpu_percent !== null ? pc.cpu_percent.toFixed(1) + "%" : "--";
  const memVal = pc.memory_percent !== null ? pc.memory_percent.toFixed(1) + "%" : "--";
  const diskVal = pc.disk_percent !== null ? pc.disk_percent.toFixed(1) + "%" : "--";
  const barWidth = isOnline && pc.cpu_percent !== null ? Math.min(100, Math.max(0, pc.cpu_percent)) : 0;

  return `
    <div style="padding: 12px 14px; border-radius: 8px; border: 1px solid ${statusColor.border}; background: var(--bg-surface); transition: border-color 0.2s ease; position: relative;">
      <!-- Card Top: Hostname and Status Badge -->
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 6px; margin-bottom: 6px;">
        <span class="mono" style="font-size: 12px; font-weight: 700; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(pc.hostname)}">
          ${escapeHtml(pc.hostname)}
        </span>
        <span style="font-size: 9px; font-weight: 700; padding: 2px 5px; border-radius: 3px; background: ${statusColor.bg}; color: ${statusColor.text}; letter-spacing: 0.5px;">
          ${statusBadge}
        </span>
      </div>

      <!-- Large Primary Metric (CPU Load or Offline indicator) -->
      <div style="display: flex; align-items: baseline; justify-content: space-between; margin: 4px 0;">
        <div style="font-size: 20px; font-weight: 700; color: ${statusColor.text};">
          ${isOnline ? cpuVal : "OFFLINE"}
        </div>
        <div style="font-size: 10px; color: var(--text-muted); font-family: var(--font-mono);">
          ${escapeHtml(pc.ip_address || "127.0.0.1")}
        </div>
      </div>

      <!-- CPU Utilization Progress Bar -->
      <div style="height: 4px; border-radius: 2px; background: rgba(255, 255, 255, 0.08); overflow: hidden; margin-bottom: 8px;">
        <div style="height: 100%; width: ${barWidth}%; background: ${statusColor.bar}; transition: width 0.3s ease;"></div>
      </div>

      <!-- Secondary Metrics: Memory, Disk, & Last Seen -->
      <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--text-secondary); margin-top: 4px;">
        <span>RAM: <strong style="color: var(--text-primary);">${memVal}</strong></span>
        <span>Disk: <strong style="color: var(--text-primary);">${diskVal}</strong></span>
      </div>

      <div style="font-size: 10px; color: var(--text-muted); margin-top: 6px; text-align: right;">
        ${pc.last_seen ? formatRelativeTime(pc.last_seen) : "never seen"}
      </div>
    </div>
  `;
}

/**
 * Empty state rendered when no PCs match the environment filter.
 */
function renderEmptyState(environment) {
  return `
    <div class="panel state-container" style="min-height: 260px;">
      <div class="state-icon" style="color: var(--text-muted);">${renderIcon("server", { size: "xl" })}</div>
      <div class="state-title">No Lab PCs Discovered in Environment "${escapeHtml(environment)}"</div>
      <div class="state-description" style="max-width: 480px; margin: 8px auto;">
        To monitor physical lab workstations, launch the monitoring agent on target machines pointing to this server:
      </div>
      <div class="mono" style="background: var(--bg-app); padding: 8px 14px; border-radius: 6px; font-size: 11px; color: var(--text-primary); display: inline-block; border: 1px solid var(--border-subtle);">
        python -m monitoring_agent.agent --env ${escapeHtml(environment)} --region lab-1 --api-key &lt;YOUR_AGENT_KEY&gt;
      </div>
    </div>
  `;
}

/**
 * Error state rendered when the API request fails.
 */
function renderErrorDom(errorMessage) {
  currentContainer.innerHTML = `
    <div class="view-header">
      <div class="view-title-group">
        <h1>Lab PC Monitoring</h1>
      </div>
    </div>
    <div class="panel state-container" style="min-height: 260px; border-left: 3px solid var(--status-critical);">
      <div class="state-icon" style="color: var(--status-critical);">${renderIcon("circle-alert", { size: "xl" })}</div>
      <div class="state-title">Failed to Load Lab Monitoring Data</div>
      <div class="state-description" style="color: var(--status-critical);">${escapeHtml(errorMessage)}</div>
      <div style="margin-top: 14px;">
        <button class="btn btn-primary btn-sm" id="lab-retry-btn">
          ${renderIcon("refresh-cw", { size: "sm" })} Retry Query
        </button>
      </div>
    </div>
  `;

  const retryBtn = document.getElementById("lab-retry-btn");
  if (retryBtn) {
    retryBtn.onclick = () => renderLabView(currentContainer);
  }
}

/**
 * Binds DOM event listeners for toolbar inputs and controls.
 */
function bindToolbarEvents() {
  const refreshBtn = document.getElementById("lab-refresh-btn");
  if (refreshBtn) {
    refreshBtn.onclick = async () => {
      refreshBtn.disabled = true;
      await fetchAndRenderLabData();
      refreshBtn.disabled = false;
    };
  }

  const envInput = document.getElementById("lab-env-input");
  if (envInput) {
    envInput.onchange = (e) => {
      labState.environment = e.target.value.trim() || "lab";
      fetchAndRenderLabData();
    };
  }

  const timeoutSelect = document.getElementById("lab-timeout-input");
  if (timeoutSelect) {
    timeoutSelect.onchange = (e) => {
      labState.offlineAfterSeconds = parseInt(e.target.value, 10) || 90;
      fetchAndRenderLabData();
    };
  }

  const realCheck = document.getElementById("lab-real-only-check");
  if (realCheck) {
    realCheck.onchange = (e) => {
      labState.realAgentsOnly = e.target.checked;
      fetchAndRenderLabData();
    };
  }
}

/**
 * Maps operational status level to theme design token colors.
 */
function getStatusColor(cpuLevel, isOnline) {
  if (!isOnline || cpuLevel === "offline") {
    return {
      border: "var(--border-subtle)",
      bg: "rgba(100, 116, 139, 0.15)",
      text: "var(--text-muted)",
      bar: "var(--text-muted)",
    };
  }
  if (cpuLevel === "high") {
    return {
      border: "var(--status-critical-border)",
      bg: "var(--status-critical-bg)",
      text: "var(--status-critical)",
      bar: "var(--status-critical)",
    };
  }
  if (cpuLevel === "warning") {
    return {
      border: "var(--status-warning-border)",
      bg: "var(--status-warning-bg)",
      text: "var(--status-warning)",
      bar: "var(--status-warning)",
    };
  }
  return {
    border: "var(--status-healthy-border)",
    bg: "var(--status-healthy-bg)",
    text: "var(--status-healthy)",
    bar: "var(--status-healthy)",
  };
}

function getCpuBadgeClass(cpuLevel) {
  if (cpuLevel === "high") return "badge-critical";
  if (cpuLevel === "warning") return "badge-warning";
  if (cpuLevel === "normal") return "badge-healthy";
  return "badge-neutral";
}

/**
 * Initializes tab-visibility aware background polling.
 * Automatically halts requests when the tab is backgrounded.
 */
function startVisibilityAwarePolling() {
  activePollTimer = setInterval(() => {
    if (document.visibilityState === "visible") {
      fetchAndRenderLabData();
    }
  }, REFRESH_INTERVAL_MS);

  activeVisibilityHandler = () => {
    if (document.visibilityState === "visible") {
      fetchAndRenderLabData();
    }
  };

  document.addEventListener("visibilitychange", activeVisibilityHandler);
}

/**
 * Tears down intervals and listeners to prevent memory and network leaks.
 */
export function destroyLabView() {
  if (activePollTimer) {
    clearInterval(activePollTimer);
    activePollTimer = null;
  }
  if (activeVisibilityHandler) {
    document.removeEventListener("visibilitychange", activeVisibilityHandler);
    activeVisibilityHandler = null;
  }
  currentContainer = null;
}
