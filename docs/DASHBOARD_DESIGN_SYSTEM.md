# Cloud Resource Monitoring & Intelligence Platform
## Command Center Design System & Token Specifications

**Theme**: SRE / SOC High-Density Dark Interface  
**Compliance**: WCAG 2.1 AA (Contrast Ratio $\ge 4.5:1$)  

---

## 1. Color Palette Tokens

| Token | Hex / Value | Semantics & Usage |
| :--- | :--- | :--- |
| `--bg-app` | `#080c14` | Primary viewport backdrop |
| `--bg-sidebar` | `#0c101b` | Navigation panel backdrop |
| `--bg-surface` | `#111728` | Default panel and card background |
| `--bg-surface-elevated`| `#161e33` | Hover states, table headers, elevated cards |
| `--border-subtle` | `#1c263c` | Panel dividers and inactive borders |
| `--border-default` | `#24324f` | Active borders and input boundaries |
| `--text-primary` | `#f1f5f9` | Main titles, values, and primary labels |
| `--text-secondary` | `#94a3b8` | Metadata, subtitles, column headers |
| `--text-muted` | `#64748b` | Timestamps, units, inactive helpers |

---

## 2. Semantic State Tokens

* **Healthy / Operational**:
  * Color: `#10b981` (Emerald Green)
  * Background: `rgba(16, 185, 129, 0.12)`
  * Border: `rgba(16, 185, 129, 0.35)`
* **Warning / Degraded**:
  * Color: `#f59e0b` (Amber)
  * Background: `rgba(245, 158, 11, 0.12)`
  * Border: `rgba(245, 158, 11, 0.35)`
* **Critical / Breach**:
  * Color: `#ef4444` (Ruby Red)
  * Background: `rgba(239, 68, 68, 0.14)`
  * Border: `rgba(239, 68, 68, 0.40)`
* **Informational**:
  * Color: `#3b82f6` (Sapphire Blue)
  * Background: `rgba(59, 130, 246, 0.12)`
  * Border: `rgba(59, 130, 246, 0.35)`
* **AI & Intelligence**:
  * Color: `#8b5cf6` (Deep Violet)
  * Background: `rgba(139, 92, 246, 0.14)`
  * Border: `rgba(139, 92, 246, 0.40)`

---

## 3. Typography & Monospaced Rules

* **Sans-serif Font Stack**: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
* **Monospaced Font Stack**: `'JetBrains Mono', 'Fira Code', 'Consolas', monospace`
* **Rule**: All IP addresses, host identifiers, metric numbers, percentage values, and timestamps **MUST** be rendered in monospaced font for optimal tabular alignment.

---

## 4. Accessibility & Non-Color Dependent Signifiers

To ensure accessibility for colorblind operators, color is **never** the sole indicator of state:
* Every badge contains explicit uppercase text (`CRITICAL`, `WARNING`, `HEALTHY`).
* Status indicators include distinct shapes and pulsating animation on critical events.
* Screen reader tags (`aria-label`, `role="status"`, `aria-live="polite"`) are attached to all dynamic panels.
