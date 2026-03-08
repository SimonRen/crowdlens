# Dashboard Page Overrides

> **PROJECT:** Live Monitor
> **Page:** Main Monitoring Dashboard

> Rules in this file **override** the Master file (`design-system/MASTER.md`).
> Only deviations from the Master are documented here.

---

## Page-Specific Rules

### Layout Overrides

- **Max Width:** Full viewport width (no max-width constraint)
- **Grid:** Three-zone layout:
  - **Top bar:** Channel selector (left) + Start/Stop controls (right), height ~60px
  - **Main area (flex row):** Live Preview (2/3 width) | Stats Panel (1/3 width)
  - **Bottom area:** Time-series area chart, full width below the main area
- **Responsive:** On screens < 1024px, stack preview above stats panel (single column)

### Spacing Overrides

- **Content Density:** High — monitoring dashboard, minimize whitespace
- **Card Padding:** `16px` (tighter than Master's `24px`) for stats cards
- **Gap between zones:** `16px`

### Color Overrides

- **Classification colors (bounding boxes + stats):**
  - Man: `#3B82F6` (blue-500)
  - Woman: `#EC4899` (pink-500)
  - Child: `#22C55E` (green-500)
  - Unknown: `#6B7280` (gray-500)
- **Active session indicator:** `#22C55E` pulse glow
- **Stopped/idle state:** `#6B7280` (gray-500)

### Component Overrides

- **Live Preview:** `<img>` tag pointing at MJPEG endpoint. Aspect ratio 16:9. Dark border (`#1E293B`). Rounded corners `8px`. Object-fit `contain` on dark `#020617` background.
- **Stats Panel:** Two sections stacked vertically — "In Frame Now" (current counts) and "Session Total" (cumulative unique counts). Each stat row: colored dot + label + number.
- **Channel Selector:** shadcn Select component. Dark surface (`#0F172A`).
- **Start/Stop Button:** Green (`#22C55E`) when idle → Red (`#EF4444`) when active session is running.

---

## Page-Specific Components

- **ConnectionStatus:** Small dot indicator (green=connected, red=disconnected) near the live preview, showing MJPEG/SSE health.
- **FPS Counter:** Small monospace text in the top-right of the preview area showing current FPS.

---

## Recommendations

- **Effects:** Smooth number transitions on stat changes (CSS transitions, not count-up animations). Pulse glow on the active session indicator. Chart area updates via Recharts animation.
- **prefers-reduced-motion:** Disable pulse glow and chart animations.
- **MJPEG reconnection:** If stream disconnects, show "Reconnecting..." overlay on preview and retry `src` every 2 seconds.
