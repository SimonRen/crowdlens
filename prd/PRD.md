# PRD: Live Feed Monitor & Analyzer (PoC)

**Version:** 1.0
**Date:** 2026-03-08
**Status:** Draft

---

## 1. Overview

A software system that monitors live video feeds, detects and classifies people (man/woman/child), tracks individuals to avoid double-counting, and presents real-time statistics on a web dashboard. For the PoC, live feeds are simulated using MP4 files. The system runs entirely on CPU — no GPU required.

## 2. Goals & Non-Goals

### Goals

- Detect people in video feeds at ≥10 FPS on a modern CPU
- Classify detected persons as man, woman, or child using face analysis
- Track individuals frame-to-frame to maintain unique person counts
- Display annotated live preview with color-coded bounding boxes and labels
- Provide a dashboard with real-time counters and time-series charts
- Support session-based monitoring (start/stop) with historical review
- Run via `docker compose up` with zero manual setup

### Non-Goals

- GPU acceleration (out of scope for PoC)
- Re-entry re-identification (person leaves and re-enters frame)
- Multiple channels analyzed simultaneously
- Production-grade scalability or high availability
- Audio analysis
- Real RTSP/camera input (MP4 simulation only)

## 3. User Stories

1. **As an operator**, I want to select a video channel from the dashboard and start monitoring, so I can begin analyzing a feed.
2. **As an operator**, I want to see a live preview with bounding boxes around people, labeled by classification, so I can visually verify detections.
3. **As an operator**, I want to see real-time counters (men/women/children/unknown in frame + session totals), so I can monitor crowd composition.
4. **As an operator**, I want to view time-series charts of people counts over a session, so I can see trends.
5. **As an operator**, I want to stop a session and review its summary statistics, so I can compare sessions.
6. **As an operator**, I want to browse past sessions and view their stats, so I can review historical data.

## 4. Architecture

### 4.1 High-Level Diagram

```
┌──────────────────┐                          ┌─────────────────────────────┐
│                  │    MJPEG /api/stream      │  Backend (Python FastAPI)   │
│  React Frontend  │◄─────────────────────────│                             │
│                  │    SSE /api/events        │  ┌───────────────────────┐  │
│  - Channel       │◄─────────────────────────│  │  API Process          │  │
│    selector      │    REST /api/*            │  │  (FastAPI + Uvicorn)  │  │
│  - Start/Stop    │◄─────────────────────────│  │  Reads from queue     │  │
│  - Live preview  │                          │  └───────────┬───────────┘  │
│  - Stats charts  │                          │              │ mp.Queue     │
│  - Session list  │                          │  ┌───────────▼───────────┐  │
│                  │                          │  │  CV Worker Process    │  │
└──────────────────┘                          │  │  YOLO26n detection    │  │
                                              │  │  ByteTrack tracking   │  │
                                              │  │  InsightFace gender   │  │
                                              │  │  Frame annotation     │  │
                                              │  └───────────┬───────────┘  │
                                              │              │              │
                                              │  ┌───────────▼───────────┐  │
                                              │  │  SQLite (WAL mode)    │  │
                                              │  │  sessions + tracks +  │  │
                                              │  │  snapshots            │  │
                                              │  └───────────────────────┘  │
                                              └─────────────────────────────┘
```

### 4.2 Process Isolation

The backend uses two OS-level processes to avoid Python's GIL bottleneck:

| Process | Responsibility | Communication |
|---------|---------------|---------------|
| **API process** | FastAPI server: REST endpoints, MJPEG stream, SSE events | Reads annotated frames + stats from `multiprocessing.Queue` |
| **CV worker process** | Video decode, YOLO detection, ByteTrack tracking, InsightFace classification, frame annotation, persistence | Writes to queue + SQLite |

This ensures CPU-intensive inference never blocks API response latency.

### 4.3 CV Pipeline (per frame)

```
MP4 File (looping)
    │
    ▼
OpenCV VideoCapture (decode)
    │
    ▼
YOLO26n Detection (person class only)
    │
    ▼
Ultralytics ByteTrack (assign persistent track IDs)
    │
    ▼
Every Nth frame: InsightFace SCRFD face detection
    on each person crop → genderage.onnx
    │
    ▼
Policy Layer: derive man/woman/child/unknown
    from raw age_estimate + gender_estimate
    │
    ▼
Supervision Annotators (bounding boxes + labels)
    │
    ▼
JPEG encode → push to shared queue
    │
    ▼
Persist track lifecycle events to SQLite
```

**Frame-skipping strategy:**
- Person detection + tracking: every frame
- Face detection + classification: every 3rd frame (interpolate labels between)
- This balances CPU load and classification responsiveness

## 5. Tech Stack

### 5.1 Backend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Web framework | FastAPI + Uvicorn | REST API, MJPEG stream, SSE |
| Detection model | YOLO26n (ONNX) | Person detection, ~38.9ms/frame at 640px on CPU |
| Fallback model | YOLOv11n (ONNX) | If YOLO26n is unstable, ~56.1ms/frame |
| Tracking | Ultralytics built-in ByteTrack | Frame-to-frame person tracking via `model.track()` |
| Face analysis | InsightFace SCRFD + genderage.onnx | Face detection + age/gender estimation |
| Inference runtime | ONNX Runtime (CPU) | Model execution |
| Annotation | Supervision (BoundingBoxAnnotator, LabelAnnotator) | Drawing overlays on frames |
| Video I/O | OpenCV (cv2) | Frame decoding, JPEG encoding |
| Database | SQLite (WAL mode) | Session and track storage |
| Process model | multiprocessing | CV worker isolation from API |
| Language | Python 3.12 | |

**Pinned dependency:** `ultralytics` version pinned in requirements.txt to ensure YOLO26n stability.

### 5.2 Frontend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | React 19 + TypeScript | UI |
| Build tool | Vite 6 | Dev server + build |
| UI components | shadcn/ui + Tailwind CSS v4 | Polished component library |
| Charts | Recharts | Time-series visualization |
| State management | Zustand | Client state |
| Data fetching | TanStack Query | API integration + cache |
| Routing | TanStack Router | Page navigation |
| HTTP client | ky | REST calls |

### 5.3 Infrastructure

| Component | Technology |
|-----------|-----------|
| Containerization | Docker Compose |
| Local HTTPS | OrbStack |
| Frontend domain | `https://frontend.live-monitor.orb.local` |
| Backend domain | `https://backend.live-monitor.orb.local` |

## 6. Data Model (SQLite)

### 6.1 Tables

```sql
-- Video channels (MP4 files)
CREATE TABLE channels (
    id          TEXT PRIMARY KEY,       -- e.g., "street-scene"
    filename    TEXT NOT NULL,          -- e.g., "street-scene.mp4"
    label       TEXT NOT NULL           -- display name
);

-- Monitoring sessions
CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,       -- UUID
    channel_id  TEXT NOT NULL REFERENCES channels(id),
    started_at  TEXT NOT NULL,          -- ISO 8601
    stopped_at  TEXT,                   -- NULL if active
    status      TEXT NOT NULL DEFAULT 'active'  -- active | stopped
);

-- Track lifecycle events (NOT per-frame rows)
CREATE TABLE tracks (
    id              TEXT PRIMARY KEY,   -- UUID
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    track_id        INTEGER NOT NULL,   -- ByteTrack assigned ID
    classification  TEXT,               -- man | woman | child | unknown
    age_estimate    REAL,               -- raw model output
    gender_estimate TEXT,               -- raw: male | female | null
    confidence      REAL,               -- classification confidence
    first_seen_at   TEXT NOT NULL,      -- ISO 8601
    last_seen_at    TEXT NOT NULL,      -- ISO 8601
    UNIQUE(session_id, track_id)
);

-- Periodic aggregated snapshots (every ~5 seconds)
CREATE TABLE session_snapshots (
    id              TEXT PRIMARY KEY,   -- UUID
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    timestamp       TEXT NOT NULL,      -- ISO 8601
    men_in_frame    INTEGER NOT NULL DEFAULT 0,
    women_in_frame  INTEGER NOT NULL DEFAULT 0,
    children_in_frame INTEGER NOT NULL DEFAULT 0,
    unknown_in_frame INTEGER NOT NULL DEFAULT 0,
    total_unique_men    INTEGER NOT NULL DEFAULT 0,
    total_unique_women  INTEGER NOT NULL DEFAULT 0,
    total_unique_children INTEGER NOT NULL DEFAULT 0,
    total_unique_unknown INTEGER NOT NULL DEFAULT 0
);
```

### 6.2 Key Design Decisions

- **Track lifecycle, not per-frame events.** Each tracked person gets one row in `tracks`, updated on last_seen and classification changes. This prevents table bloat (vs. 75+ rows/sec with per-frame logging).
- **Raw attributes stored.** `age_estimate` and `gender_estimate` are raw model outputs. The `classification` field is derived by a policy layer.
- **Periodic snapshots for charts.** The `session_snapshots` table stores aggregated counts every ~5 seconds, providing time-series data without querying raw tracks.

## 7. Classification Policy

Age/gender classification is derived from InsightFace model outputs, not treated as ground truth.

| Classification | Rule | Notes |
|---------------|------|-------|
| **child** | `age_estimate < 13` | Configurable threshold via env var `CHILD_AGE_THRESHOLD` |
| **man** | `age_estimate >= 13` AND `gender_estimate = male` | |
| **woman** | `age_estimate >= 13` AND `gender_estimate = female` | |
| **unknown** | No face detected OR low confidence | Counted in total persons but excluded from gender/age stats |

**Known limitations:**
- People facing away from camera will be classified as "unknown"
- Age estimation has ~4 year MAE — borderline ages (11-15) may misclassify
- The threshold is a product rule, not a model property — tune based on demo footage

## 8. API Endpoints

All endpoints use **GET and POST only** (company convention).

### 8.1 REST

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/channels` | List available video channels |
| POST | `/api/sessions/start` | Start monitoring a channel. Body: `{ "channel_id": "..." }` |
| POST | `/api/sessions/stop` | Stop the active session. Body: `{ "session_id": "..." }` |
| GET | `/api/sessions` | List all sessions (most recent first) |
| GET | `/api/sessions/{id}/stats` | Get stats for a session (snapshot time-series + track summary) |
| GET | `/api/health` | Health check (model loaded, worker alive) |

### 8.2 Streaming

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream` | MJPEG stream of annotated frames. Returns `multipart/x-mixed-replace` |
| GET | `/api/events` | SSE stream of real-time stats. Pushes every ~1 second |

### 8.3 SSE Event Format

```json
{
    "type": "stats",
    "data": {
        "in_frame": { "men": 3, "women": 2, "children": 1, "unknown": 0 },
        "session_total": { "men": 15, "women": 12, "children": 4, "unknown": 3 },
        "fps": 18.5,
        "session_id": "abc-123",
        "timestamp": "2026-03-08T14:30:00Z"
    }
}
```

## 9. Frontend Pages

### 9.1 Dashboard (Main Page)

```
┌─────────────────────────────────────────────────────────────┐
│  Live Feed Monitor                          [Channel ▼] [▶ Start]  │
├─────────────────────────────────┬───────────────────────────┤
│                                 │  In Frame Now             │
│                                 │  👤 Men:      3           │
│    Live Preview                 │  👤 Women:    2           │
│    (MJPEG Stream)               │  👤 Children: 1           │
│    with bounding boxes          │  👤 Unknown:  0           │
│    & classification labels      │                           │
│                                 │  Session Total            │
│                                 │  👤 Men:      15          │
│                                 │  👤 Women:    12          │
│                                 │  👤 Children: 4           │
│                                 │  👤 Unknown:  3           │
├─────────────────────────────────┴───────────────────────────┤
│  People Over Time (Area Chart)                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  ▄▄▄                                                  │  │
│  │ ████▄▄   ▄▄▄                                          │  │
│  │ ████████████▄▄                                        │  │
│  └───────────────────────────────────────────────────────┘  │
│  [men] [women] [children] [unknown]                         │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 Session History Page

| Column | Description |
|--------|-------------|
| Channel | Which video feed |
| Started | Session start time |
| Duration | How long the session ran |
| Total People | Unique persons detected |
| Men / Women / Children | Breakdown |
| Actions | View details → navigates to session detail with charts |

## 10. Bounding Box Annotation

Using Supervision library annotators with color coding:

| Classification | Box Color | Label Format |
|---------------|-----------|-------------|
| man | Blue (#3B82F6) | `Man #14 (0.92)` |
| woman | Pink (#EC4899) | `Woman #7 (0.88)` |
| child | Green (#22C55E) | `Child #3 (0.75)` |
| unknown | Gray (#6B7280) | `Person #21` |

Label shows: classification + track ID + confidence score.

## 11. Docker Compose Setup

```yaml
# docker-compose.yml structure
services:
  backend:
    build: ./backend
    volumes:
      - ./videos:/app/videos        # MP4 files
      - ./data:/app/data             # SQLite database
    environment:
      - CHILD_AGE_THRESHOLD=13
      - JPEG_QUALITY=70
      - DETECTION_MODEL=yolo26n      # or yolo11n
      - CLASSIFICATION_INTERVAL=3    # classify every Nth frame
    ports:
      - "8000:8000"

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://backend:8000
```

### 11.1 Model Pre-loading

Models are downloaded during `docker build` (not at runtime) to ensure fast startup:

- YOLO26n ONNX weights (~6MB)
- InsightFace SCRFD face detector (~3MB)
- InsightFace genderage.onnx (~1MB)

A `/api/health` endpoint confirms all models are loaded before accepting sessions.

### 11.2 Sample Videos

Ship 2-3 royalty-free crowd/street scene MP4 files in `./videos/`:
- Source: Pexels or Pixabay (CC0 / royalty-free license)
- Requirements: visible faces, mix of people, 30-60 seconds each
- MP4 files loop seamlessly when they reach the end

## 12. Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `DETECTION_MODEL` | `yolo26n` | Detection model (`yolo26n` or `yolo11n`) |
| `CHILD_AGE_THRESHOLD` | `13` | Age below which a person is classified as "child" |
| `CLASSIFICATION_INTERVAL` | `3` | Classify faces every Nth frame |
| `JPEG_QUALITY` | `70` | MJPEG stream JPEG quality (1-100) |
| `SNAPSHOT_INTERVAL` | `5` | Seconds between session snapshot aggregations |
| `INPUT_RESOLUTION` | `640` | YOLO input resolution (lower = faster) |
| `DATABASE_PATH` | `/app/data/monitor.db` | SQLite database file path |

## 13. Performance Expectations (CPU-Only)

| Metric | Expected | Notes |
|--------|----------|-------|
| Detection FPS | 15-25 | YOLO26n at 640px, depends on CPU |
| End-to-end FPS | 10-18 | Including tracking, classification, annotation, encoding |
| Face classification | ~10ms/face | InsightFace genderage.onnx |
| Startup time | < 10s | Models pre-loaded in Docker image |
| Memory usage | ~500MB-1GB | Models + OpenCV buffers |

**Tested on:** Modern laptop CPU (Apple M-series or Intel i7+). Older CPUs may see lower FPS.

## 14. Project Structure

```
live-monitor/
├── prd/
│   └── PRD.md                  # This document
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                 # FastAPI app, startup, health check
│   ├── api/
│   │   ├── routes.py           # REST endpoints
│   │   ├── stream.py           # MJPEG streaming endpoint
│   │   └── events.py           # SSE endpoint
│   ├── cv/
│   │   ├── worker.py           # CV worker process entry point
│   │   ├── detector.py         # YOLO detection + tracking
│   │   ├── classifier.py       # InsightFace face analysis
│   │   └── policy.py           # Classification policy (age threshold)
│   ├── db/
│   │   ├── database.py         # SQLite connection, WAL setup
│   │   ├── models.py           # Table definitions
│   │   └── queries.py          # Read queries for stats
│   └── config.py               # Environment variable loading
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── src/
│   │   ├── main.tsx
│   │   ├── routes/
│   │   │   ├── dashboard.tsx   # Main monitoring page
│   │   │   └── history.tsx     # Session history page
│   │   ├── components/
│   │   │   ├── live-preview.tsx
│   │   │   ├── stats-panel.tsx
│   │   │   ├── time-chart.tsx
│   │   │   ├── channel-selector.tsx
│   │   │   └── session-table.tsx
│   │   ├── hooks/
│   │   │   ├── use-sse.ts      # SSE connection hook
│   │   │   └── use-session.ts  # Session management
│   │   ├── stores/
│   │   │   └── monitor.ts      # Zustand store
│   │   └── lib/
│   │       └── api.ts          # ky API client
├── videos/                     # Sample MP4 files
│   ├── street-scene.mp4
│   ├── mall-crowd.mp4
│   └── park-walk.mp4
├── data/                       # SQLite DB (gitignored)
├── docker-compose.yml
└── .gitignore
```

## 15. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| YOLO26n not stable in pinned ultralytics version | Low | Medium | Fallback to YOLOv11n, documented in config |
| Low FPS on older CPUs | Medium | Medium | Reduce input resolution, increase classification interval |
| Poor child classification accuracy | High | Low (PoC) | Configurable threshold, raw attributes stored, "unknown" category |
| InsightFace model download fails in Docker build | Low | High | Pin model URLs, cache in Docker layer |
| SQLite write contention under load | Low | Low | WAL mode, track-lifecycle storage (not per-frame) |
| Sample MP4s lack visible faces | Medium | Medium | Curate videos with front-facing people; test before demo |

## 16. Future Enhancements (Post-PoC)

- **GPU acceleration** — ONNX Runtime CUDA/TensorRT provider
- **Re-entry re-identification** — Re-ID embeddings (osnet_x0_25) for cross-gap dedup
- **Multi-channel concurrent analysis** — multiple CV worker processes
- **Real camera input** — RTSP/WebRTC source support
- **WebRTC streaming** — lower latency, better bandwidth efficiency
- **PostgreSQL** — replace SQLite for production workloads
- **Alerting** — threshold-based notifications (e.g., crowd exceeds N)
- **Full-body classification** — fallback classifier for people without visible faces
