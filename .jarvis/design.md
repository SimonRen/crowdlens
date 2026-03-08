# Design: Live Feed Monitor & Analyzer (PoC)

**Source:** prd/PRD.md + brainstorming session + multi-review (Codex + Gemini)
**Date:** 2026-03-08

---

## 1. System Architecture

Two-process Python backend + React SPA frontend, deployed via Docker Compose.

### Backend (Python 3.12 + FastAPI)

**API Process** — FastAPI + Uvicorn serving REST, MJPEG, SSE. Reads from `multiprocessing.Queue`.

**CV Worker Process** — Runs the full CV pipeline: video decode → YOLO26n detection → ByteTrack tracking → InsightFace face classification → supervision annotation → JPEG encode. Writes annotated frames + stats to the shared queue and persists track lifecycle events to SQLite.

Communication: `multiprocessing.Queue(maxsize=2)` for frames/stats (bounded — CV worker drops oldest frame if queue is full to prevent memory growth). SQLite (WAL mode) for persistence. **Write ownership:** CV worker owns all writes (tracks, snapshots). API process sends start/stop commands via a separate `multiprocessing.Queue` command channel; CV worker writes session rows. API process only reads from SQLite.

### Frontend (React 19 + Vite 6 + TypeScript)

SPA with two routes: Dashboard (live monitoring) and History (past sessions). Uses shadcn/ui + Tailwind v4 for UI, Recharts for charts, Zustand for state, TanStack Query for API, ky for HTTP.

### Docker Compose

Two services: `backend` (Python 3.12) and `frontend` (Node 22 / nginx). OrbStack-compatible domains. Models pre-downloaded at build time.

## 2. CV Pipeline Design

```
MP4 (looping via OpenCV) → YOLO26n (person detection, every frame)
  → ByteTrack (tracking, via ultralytics model.track())
  → InsightFace SCRFD + genderage.onnx (every 3rd frame, face crops only)
  → Policy layer (age < 13 = child, configurable)
  → supervision annotators (BoundingBox + Label, color-coded)
  → JPEG encode → push to mp.Queue
  → persist track lifecycle to SQLite
```

**Key decisions:**
- YOLO26n default, YOLOv11n as pinned fallback
- Ultralytics built-in ByteTrack (not supervision's tracker) — fewer integration points
- Supervision used only for annotation drawing
- Frame-skip classification (every 3rd frame), labels interpolated between
- "Unknown" category for persons without visible face — counted in totals, excluded from gender/age breakdown
- Confidence score in bounding box labels = gender classification confidence from genderage.onnx (not YOLO detection confidence or face detection confidence)

## 3. Data Model

Three tables: `channels` (static MP4 registry), `sessions` (start/stop lifecycle), `tracks` (one row per tracked person per session, updated on last_seen/classification change). Plus `session_snapshots` (aggregated counts every 5s for charts).

**Not per-frame rows.** Track lifecycle approach keeps SQLite lean.

Raw attributes stored (`age_estimate`, `gender_estimate`). Classification derived by policy layer.

## 4. API Design

REST (GET/POST only) + MJPEG stream + SSE events. See PRD Section 8 for full endpoint list.

Key streaming endpoints:
- `GET /api/stream` → `multipart/x-mixed-replace` MJPEG
- `GET /api/events` → SSE with stats payload every ~1s

**Frontend URL resolution:** The frontend runs in the browser, not inside Docker. `VITE_API_URL` must point to the browser-accessible backend URL. In OrbStack: `https://backend.live-monitor.orb.local`. For non-OrbStack: `http://localhost:8000`. This is set at build time via Vite env vars.

**Stream reconnection:** Browser `EventSource` auto-reconnects SSE. MJPEG via `<img>` does not — the frontend must detect stale frames (no new data for >3s) and re-set the `src` attribute. A connection status indicator (green/red dot) should be visible near the preview.

## 5. Frontend Design System

### Theme: Dark Mode (OLED)

| Role | Hex | Tailwind |
|------|-----|----------|
| Background | `#020617` | `slate-950` |
| Surface/Cards | `#0F172A` | `slate-900` |
| Surface Hover | `#1E293B` | `slate-800` |
| CTA/Accent | `#22C55E` | `green-500` |
| Text Primary | `#F8FAFC` | `slate-50` |
| Text Muted | `#94A3B8` | `slate-400` |

### Typography: Fira Code / Fira Sans

- **Headings:** Fira Code (monospace, technical feel)
- **Body:** Fira Sans (readable, pairs with Fira Code)
- **Mood:** Dashboard, data, analytics, technical, precise

### Classification Colors (bounding boxes + stats)

| Class | Color | Hex |
|-------|-------|-----|
| Man | Blue | `#3B82F6` |
| Woman | Pink | `#EC4899` |
| Child | Green | `#22C55E` |
| Unknown | Gray | `#6B7280` |

### Chart Style

- **Type:** Streaming Area Chart (stacked)
- **Library:** Recharts
- **Colors:** Classification colors above with 20% opacity fills
- **Grid:** Dark (`#1E293B`)
- **Animation:** Smooth transitions, respect `prefers-reduced-motion`

### Icons

Lucide React (consistent with shadcn/ui). No emojis.

### Pages

**Dashboard** — Full-width. Top bar with channel selector + start/stop. Left 2/3: MJPEG live preview. Right 1/3: Stats panel (in-frame + session totals). Bottom: stacked area chart of people over time.

**History** — Table of past sessions using shadcn DataTable. Click row → session detail view with summary stats + time-series chart replay.

## 6. Configuration

All tunable via environment variables (see PRD Section 12). Key ones:
- `DETECTION_MODEL` (yolo26n / yolo11n)
- `CHILD_AGE_THRESHOLD` (default 13)
- `CLASSIFICATION_INTERVAL` (default 3)
- `JPEG_QUALITY` (default 70)

## 7. Known Limitations (PoC)

- No GPU acceleration
- No re-entry re-identification (person gets new ID if they leave and return)
- Only one channel analyzed at a time
- "Unknown" persons when face not visible
- Child classification approximate (age MAE ~4yr)
- MJPEG bandwidth ~1-3 Mbps (local only)
