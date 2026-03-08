# History Page Overrides

> **PROJECT:** Live Monitor
> **Page:** Session History

> Rules in this file **override** the Master file (`design-system/MASTER.md`).
> Only deviations from the Master are documented here.

---

## Page-Specific Rules

### Layout Overrides

- **Max Width:** `1200px` centered
- **Layout:** Single column — header + session table + (optional) session detail panel
- **Sections:**
  1. Page header with "Session History" title
  2. Session table (shadcn DataTable)
  3. Session detail view (when a row is clicked — expanded inline or separate route)

### Color Overrides

- **Table row hover:** `#1E293B` (slate-800) — subtle hover on dark background
- **Alternating rows:** Not used — use uniform `#0F172A` surface with hover highlight instead (dark theme, alternating light/grey rows would break the palette)
- **Session status badge:** Active = `#22C55E` (green), Stopped = `#6B7280` (gray)

### Component Overrides

- **Session Table columns:** Channel | Started | Duration | Total People | Men | Women | Children | Actions
- **Actions column:** "View" link/button navigating to session detail
- **Session Detail view:** Summary stat cards (same style as dashboard stats panel) + time-series area chart replaying the session's snapshot data
- **Empty state:** "No sessions yet. Start monitoring from the Dashboard." with link to dashboard.

---

## Page-Specific Components

- **DurationCell:** Formats seconds into human-readable duration (e.g., "5m 32s")
- **StatBadge:** Small inline badge with colored dot + count (used in table cells for men/women/children columns)

---

## Recommendations

- **Effects:** Smooth row hover transitions (`150ms`). Number display uses tabular-nums for alignment.
- **Responsive:** On mobile (< 768px), hide less important columns (Men/Women/Children breakdown) and show only Total People. Provide expandable row for full details.
