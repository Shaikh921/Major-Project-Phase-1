/**
 * Data Sanitizer & HTML Escaper for XSS Immunity (WCAG / OWASP compliance).
 */

export function escapeHtml(unsafe) {
  if (unsafe === null || unsafe === undefined) return "";
  return String(unsafe)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export function maskSensitive(text) {
  if (!text) return "";
  const str = String(text);
  if (str.length <= 8) return "••••••••";
  return str.slice(0, 3) + "••••••••" + str.slice(-3);
}

export function formatTimestamp(isoString) {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return escapeHtml(isoString);
    return d.toISOString().replace("T", " ").substring(0, 19) + " UTC";
  } catch {
    return escapeHtml(isoString);
  }
}

export function formatRelativeTime(isoString) {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    const diffSec = Math.floor((Date.now() - d.getTime()) / 1000);
    if (diffSec < 10) return "just now";
    if (diffSec < 60) return `${diffSec}s ago`;
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    return `${Math.floor(diffSec / 86400)}d ago`;
  } catch {
    return "—";
  }
}

export function renderSafeMarkdown(markdown) {
  if (!markdown) return "";
  // Escape raw HTML first
  let safe = escapeHtml(markdown);
  
  // Headers
  safe = safe.replace(/^### (.*$)/gim, '<h4 class="md-h4">$1</h4>');
  safe = safe.replace(/^## (.*$)/gim, '<h3 class="md-h3">$1</h3>');
  safe = safe.replace(/^# (.*$)/gim, '<h2 class="md-h2">$1</h2>');

  // Bold & Italic
  safe = safe.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
  safe = safe.replace(/\*(.*?)\*/gim, '<em>$1</em>');

  // Code inline
  safe = safe.replace(/`([^`]+)`/gim, '<code class="mono md-code">$1</code>');

  // Blockquotes
  safe = safe.replace(/^\> (.*$)/gim, '<blockquote class="md-blockquote">$1</blockquote>');

  // Lists
  safe = safe.replace(/^\- (.*$)/gim, '<li class="md-li">$1</li>');
  safe = safe.replace(/^\d+\. (.*$)/gim, '<li class="md-li-num">$1</li>');

  // Line breaks
  safe = safe.replace(/\n/gim, '<br>');

  return safe;
}
