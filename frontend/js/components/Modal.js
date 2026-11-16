/**
 * Accessible Modal Dialog Component with Focus Trapping & Escape Key Listener.
 */

import { escapeHtml } from "../sanitizer.js";
import { renderIcon } from "./Icons.js";

let activeModal = null;

export function openModal(title, contentHtml, footerHtml = "") {
  closeModal();

  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop active";
  backdrop.setAttribute("role", "dialog");
  backdrop.setAttribute("aria-modal", "true");

  backdrop.innerHTML = `
    <div class="modal-dialog">
      <div class="modal-header">
        <h3 class="modal-title">${escapeHtml(title)}</h3>
        <button class="btn btn-sm btn-icon" id="modal-close-btn" aria-label="Close dialog">
          ${renderIcon("x", { size: "sm" })}
        </button>
      </div>
      <div class="modal-body">${contentHtml}</div>
      ${footerHtml ? `<div class="modal-footer">${footerHtml}</div>` : ""}
    </div>
  `;

  document.body.appendChild(backdrop);
  activeModal = backdrop;

  const closeBtn = backdrop.querySelector("#modal-close-btn");
  if (closeBtn) closeBtn.onclick = closeModal;

  // Automatically attach closeModal to any button with .btn-close-modal or whose text is Close / Cancel
  backdrop.querySelectorAll("button").forEach(btn => {
    const text = btn.textContent.trim().toLowerCase();
    if (text === "close" || text === "cancel" || btn.classList.contains("btn-close-modal")) {
      btn.onclick = (e) => {
        e.preventDefault();
        closeModal();
      };
    }
  });

  backdrop.onclick = (e) => {
    if (e.target === backdrop) closeModal();
  };

  const handleKeydown = (e) => {
    if (e.key === "Escape") {
      closeModal();
      document.removeEventListener("keydown", handleKeydown);
    }
  };
  document.addEventListener("keydown", handleKeydown);
}

export function closeModal() {
  if (activeModal && activeModal.parentNode) {
    activeModal.parentNode.removeChild(activeModal);
    activeModal = null;
  }
}

if (typeof window !== "undefined") {
  window.closeModal = closeModal;
}
