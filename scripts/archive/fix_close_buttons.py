"""
Fixes modal close button bindings in frontend views.
"""

from pathlib import Path

targets = [
    Path("frontend/js/views/ResourcesView.js"),
    Path("frontend/js/views/SettingsView.js"),
]

for p in targets:
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            code = f.read()

        # Replace invalid inline string representation with class btn-close-modal
        fixed = code.replace('onclick="(${closeModal})()"', 'class="btn btn-sm btn-close-modal"')
        with open(p, "w", encoding="utf-8") as f:
            f.write(fixed)
        print(f"[+] Fixed modal close button in {p}")

