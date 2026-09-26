/**
 * Notification Center Flyout Drawer.
 */

import { escapeHtml, formatRelativeTime } from "../sanitizer.js";
import { store } from "../config.js";

export function renderNotificationDrawer(notifications = []) {
  const drawer = document.getElementById("notification-drawer");
  if (!drawer) return;

  if (notifications.length === 0) {
    drawer.innerHTML = `
      <div class="panel-header" style="padding: 14px; margin: 0;">
        <span class="panel-title">Notifications</span>
        <button class="btn btn-sm btn-icon" id="close-notif-btn">✕</button>
      </div>
      <div class="state-container">
        <span class="state-icon">🔔</span>
        <span class="state-title">No notifications</span>
        <p class="state-desc">All monitored systems are operating normally.</p>
      </div>
    `;
  } else {
    drawer.innerHTML = `
      <div class="panel-header" style="padding: 14px; margin: 0;">
        <span class="panel-title">Notifications (${notifications.length})</span>
        <button class="btn btn-sm btn-icon" id="close-notif-btn">✕</button>
      </div>
      <div style="flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 8px;">
        ${notifications.map(n => `
          <div class="panel" style="padding: 10px; border-left: 3px solid var(--status-${escapeHtml(n.severity || 'info')});">
            <div style="display: flex; justify-content: space-between; font-size: 10.5px; color: var(--text-muted); margin-bottom: 4px;">
              <span>${escapeHtml(n.source || 'SYSTEM')}</span>
              <span class="mono">${formatRelativeTime(n.timestamp)}</span>
            </div>
            <div style="font-size: 12px; color: var(--text-primary); font-weight: 500;">
              ${escapeHtml(n.message)}
            </div>
          </div>
        `).join("")}
      </div>
    `;
  }

  const closeBtn = document.getElementById("close-notif-btn");
  if (closeBtn) {
    closeBtn.onclick = () => {
      drawer.classList.remove("active");
    };
  }
}
