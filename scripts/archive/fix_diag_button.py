"""
Fix modal-run-diag-btn and close button in ResourcesView.js.
"""

from pathlib import Path

path = Path("frontend/js/views/ResourcesView.js")
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Remove the premature setTimeout before openModal
bad_snippet = """    setTimeout(() => {
      const diagBtn = document.getElementById("modal-run-diag-btn");
      if (diagBtn) {
        diagBtn.onclick = () => openDiagnosticModal(hostId, host.hostname);
      }
    }, 50);
"""
if bad_snippet in code:
    code = code.replace(bad_snippet, "")

# 2. Fix the footer Close button and attach diagBtn right after openModal
old_open_modal_block = """    openModal(`Host Telemetry: ${host.hostname}`, content, footer);

    const deactBtn = document.getElementById("deactivate-host-btn");"""

new_open_modal_block = """    openModal(`Host Telemetry: ${host.hostname}`, content, footer);

    // Attach Run Diagnostics button handler
    const diagBtn = document.getElementById("modal-run-diag-btn");
    if (diagBtn) {
      diagBtn.onclick = () => openDiagnosticModal(hostId, host.hostname);
    }

    // Attach Close button handler
    const closeFooterBtn = document.getElementById("modal-close-footer-btn");
    if (closeFooterBtn) {
      closeFooterBtn.onclick = closeModal;
    }

    const deactBtn = document.getElementById("deactivate-host-btn");"""

if old_open_modal_block in code:
    code = code.replace(old_open_modal_block, new_open_modal_block)

# 3. Clean up the footer markup
code = code.replace(
    '<button class="btn btn-sm" class="btn btn-sm btn-close-modal">Close</button>',
    '<button class="btn btn-sm btn-close-modal" id="modal-close-footer-btn">Close</button>'
)

with open(path, "w", encoding="utf-8") as f:
    f.write(code)

print("[+] Successfully fixed ResourcesView.js!")

