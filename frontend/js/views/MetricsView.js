/**
 * Metrics & Analytics View - Time-Series Multi-Metric Correlation Charts.
 */

import { api } from "../api.js";
import { escapeHtml, formatRelativeTime, formatTimestamp } from "../sanitizer.js";

export async function renderMetricsView(container) {
  container.innerHTML = `
    <div class="state-container">
      <div class="state-icon">⏳</div>
      <div class="state-title">Loading Time-Series Telemetry...</div>
    </div>
  `;

  try {
    const hosts = await api.getHosts({ active_only: true });
    if (hosts.length === 0) {
      container.innerHTML = `
        <div class="state-container">
          <div class="state-icon">🖥️</div>
          <div class="state-title">No active hosts available</div>
          <p class="state-desc">Register a host in Infrastructure to begin streaming telemetry.</p>
        </div>
      `;
      return;
    }

    const defaultHost = hosts[0];

    container.innerHTML = `
      <div class="view-header">
        <div class="view-title-group">
          <h1>Time-Series Telemetry & Metric Correlation</h1>
          <p>Multi-dimensional resource correlation (CPU, Memory, Disk, Network) with threshold markers.</p>
        </div>
        <div style="display: flex; gap: 8px;">
          <select id="metric-host-select" class="select-control">
            ${hosts.map(h => `<option value="${h.id}">${escapeHtml(h.hostname)} (${escapeHtml(h.environment)})</option>`).join("")}
          </select>
          <select id="metric-limit-select" class="select-control">
            <option value="30">Last 30 Samples</option>
            <option value="60" selected>Last 60 Samples</option>
            <option value="120">Last 120 Samples</option>
          </select>
        </div>
      </div>

      <!-- Metric Charts Container -->
      <div class="panel" style="display: flex; flex-direction: column; gap: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-subtle); padding-bottom: 8px;">
          <span class="panel-title" id="active-host-chart-title">📈 Telemetry Stream: ${escapeHtml(defaultHost.hostname)}</span>
          <div style="display: flex; gap: 14px; font-size: 11px;">
            <span style="color: #3b82f6;">● CPU %</span>
            <span style="color: #10b981;">● Memory %</span>
            <span style="color: #f59e0b;">● Disk %</span>
            <span style="color: #ef4444; border-bottom: 1px dashed #ef4444;">- - 95% Critical Threshold</span>
          </div>
        </div>

        <div style="position: relative; width: 100%; height: 320px;">
          <canvas id="telemetry-canvas" style="width: 100%; height: 100%;"></canvas>
        </div>

        <div id="chart-metrics-summary" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; padding-top: 8px; border-top: 1px solid var(--border-subtle);">
          <!-- Populated by JS -->
        </div>
      </div>
    `;

    const hostSelect = document.getElementById("metric-host-select");
    const limitSelect = document.getElementById("metric-limit-select");

    const loadAndDrawMetrics = async () => {
      const hostId = hostSelect ? hostSelect.value : defaultHost.id;
      const limit = limitSelect ? parseInt(limitSelect.value, 10) : 60;
      
      const selectedHostObj = hosts.find(h => String(h.id) === String(hostId)) || defaultHost;
      const titleEl = document.getElementById("active-host-chart-title");
      if (titleEl) titleEl.textContent = `📈 Telemetry Stream: ${selectedHostObj.hostname}`;

      try {
        const data = await api.getHostMetrics(hostId, limit);
        drawTelemetryCanvas(data.time_series || []);
        renderChartSummary(data.time_series || []);
      } catch (err) {
        console.error("Failed to load metrics", err);
      }
    };

    if (hostSelect) hostSelect.onchange = loadAndDrawMetrics;
    if (limitSelect) limitSelect.onchange = loadAndDrawMetrics;

    await loadAndDrawMetrics();

  } catch (err) {
    container.innerHTML = `
      <div class="state-container">
        <div class="state-icon text-critical">⚠️</div>
        <div class="state-title">Failed to load metrics view</div>
        <div class="state-desc">${escapeHtml(err.message)}</div>
      </div>
    `;
  }
}

function drawTelemetryCanvas(series) {
  const canvas = document.getElementById("telemetry-canvas");
  if (!canvas) return;

  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * window.devicePixelRatio || 800;
  canvas.height = rect.height * window.devicePixelRatio || 320;

  const ctx = canvas.getContext("2d");
  ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);

  const W = rect.width;
  const H = rect.height;
  const padL = 40;
  const padR = 20;
  const padT = 20;
  const padB = 30;

  ctx.clearRect(0, 0, W, H);

  // Background Grid Lines
  ctx.strokeStyle = "#1c263c";
  ctx.lineWidth = 1;

  for (let p = 0; p <= 100; p += 25) {
    const y = padT + (1 - p / 100) * (H - padT - padB);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(W - padR, y);
    ctx.stroke();

    ctx.fillStyle = "#64748b";
    ctx.font = "10px monospace";
    ctx.fillText(`${p}%`, 8, y + 3);
  }

  // Critical threshold line at 95%
  const critY = padT + (1 - 0.95) * (H - padT - padB);
  ctx.strokeStyle = "rgba(239, 68, 68, 0.6)";
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(padL, critY);
  ctx.lineTo(W - padR, critY);
  ctx.stroke();
  ctx.setLineDash([]);

  if (series.length < 2) {
    ctx.fillStyle = "#94a3b8";
    ctx.font = "12px sans-serif";
    ctx.fillText("Insufficient telemetry data points for visualization (minimum 2 required).", W / 2 - 160, H / 2);
    return;
  }

  const stepX = (W - padL - padR) / (series.length - 1);

  const plotLine = (metricKey, color) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();

    series.forEach((pt, idx) => {
      const val = Math.max(0, Math.min(100, Number(pt[metricKey]) || 0));
      const x = padL + idx * stepX;
      const y = padT + (1 - val / 100) * (H - padT - padB);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.stroke();
  };

  plotLine("cpu_percent", "#3b82f6");
  plotLine("memory_percent", "#10b981");
  plotLine("disk_percent", "#f59e0b");
}

function renderChartSummary(series) {
  const container = document.getElementById("chart-metrics-summary");
  if (!container) return;

  if (series.length === 0) {
    container.innerHTML = "";
    return;
  }

  const latest = series[series.length - 1];
  const avgCpu = series.reduce((acc, s) => acc + s.cpu_percent, 0) / series.length;
  const peakCpu = Math.max(...series.map(s => s.cpu_percent));

  container.innerHTML = `
    <div class="panel" style="padding: 8px;">
      <div class="text-muted" style="font-size: 10.5px;">CURRENT CPU</div>
      <div class="mono" style="font-size: 16px; font-weight: 700; color: #3b82f6;">${latest.cpu_percent.toFixed(1)}%</div>
    </div>
    <div class="panel" style="padding: 8px;">
      <div class="text-muted" style="font-size: 10.5px;">PEAK OBSERVED CPU</div>
      <div class="mono" style="font-size: 16px; font-weight: 700;">${peakCpu.toFixed(1)}%</div>
    </div>
    <div class="panel" style="padding: 8px;">
      <div class="text-muted" style="font-size: 10.5px;">CURRENT MEMORY</div>
      <div class="mono" style="font-size: 16px; font-weight: 700; color: #10b981;">${latest.memory_percent.toFixed(1)}%</div>
    </div>
    <div class="panel" style="padding: 8px;">
      <div class="text-muted" style="font-size: 10.5px;">CURRENT DISK</div>
      <div class="mono" style="font-size: 16px; font-weight: 700; color: #f59e0b;">${latest.disk_percent.toFixed(1)}%</div>
    </div>
  `;
}
