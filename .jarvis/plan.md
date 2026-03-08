# Live Feed Monitor PoC — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a working live video feed monitor that detects, classifies, and tracks people via YOLO + InsightFace, showing results on a React dashboard — all CPU-only, deployed via Docker Compose.

**Architecture:** Two-process Python backend (FastAPI API + CV worker via multiprocessing) serving MJPEG + SSE to a React SPA. SQLite for persistence. Docker Compose for deployment.

**Tech Stack:** Python 3.11 / FastAPI / ultralytics / InsightFace / supervision / SQLite | React 19 / Vite 6 / shadcn/ui / Tailwind v4 / Recharts / Zustand / TanStack

---

## Task Dependency Graph

```
T1 (backend scaffold) ──┐
T2 (config)             ├── T4 (CV worker) ──┐
T3 (database)           ┘                    ├── T6 (API endpoints) ──┐
T5 (channel scanner)  ──────────────────────┘                        ├── T9 (Docker) ── T10 (smoke test)
T7 (frontend scaffold) ── T8 (dashboard + history) ──────────────────┘
```

**Parallelizable groups:**
- T1, T2, T3, T5 can run in parallel (no dependencies between them)
- T7 can start once T6's API contract is known (after T6 API types defined)
- T6 depends on T1-T5 (backend scaffold, config, database, CV worker, channel scanner)
- T9 depends on both backend (T1-T6) and frontend (T7-T8) being complete

---

## Task 1: Backend Project Scaffold

**Files:**
- Create: `backend/main.py`
- Create: `backend/requirements.txt`
- Create: `backend/__init__.py`
- Create: `backend/api/__init__.py`
- Create: `backend/cv/__init__.py`
- Create: `backend/db/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p backend/api backend/cv backend/db backend/tests
touch backend/__init__.py backend/api/__init__.py backend/cv/__init__.py backend/db/__init__.py
```

Also create `backend/pyproject.toml` for pytest path resolution:

```toml
# backend/pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

**Step 2: Write requirements.txt**

```
# backend/requirements.txt
fastapi>=0.135.0
uvicorn[standard]>=0.32.0
ultralytics>=8.3.0
onnxruntime>=1.18.0
opencv-python-headless>=4.9.0
numpy<2.0
insightface>=0.7.3
supervision>=0.24.0
pydantic>=2.0.0
```

**Step 3: Write minimal main.py with health check**

```python
# backend/main.py
import multiprocessing as mp
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Will be populated in Task 4 (CV worker) and Task 6 (API)
    yield


app = FastAPI(title="Live Feed Monitor", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

**Step 4: Verify it runs**

```bash
cd backend && pip install -r requirements.txt && python main.py
# Expected: Uvicorn running on http://0.0.0.0:8000
# curl http://localhost:8000/api/health → {"status":"ok"}
```

**Step 5: Commit**

```bash
git add backend/
git commit -m "feat: backend scaffold with FastAPI health check"
```

---

## Task 2: Configuration Module

**Files:**
- Create: `backend/config.py`
- Create: `backend/tests/test_config.py`

**Step 1: Write test**

```python
# backend/tests/test_config.py
import os
import pytest


def test_default_config():
    # Unset any env vars that might interfere
    for key in ["DETECTION_MODEL", "CHILD_AGE_THRESHOLD", "CLASSIFICATION_INTERVAL",
                "JPEG_QUALITY", "SNAPSHOT_INTERVAL", "INPUT_RESOLUTION", "DATABASE_PATH"]:
        os.environ.pop(key, None)

    # Re-import to get fresh defaults
    import importlib
    import config
    importlib.reload(config)
    settings = config.get_settings()

    assert settings.detection_model == "yolo11n"
    assert settings.child_age_threshold == 13
    assert settings.classification_interval == 3
    assert settings.jpeg_quality == 70
    assert settings.snapshot_interval == 5
    assert settings.input_resolution == 640
    assert settings.database_path == "/app/data/monitor.db"


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("DETECTION_MODEL", "yolo26n")
    monkeypatch.setenv("CHILD_AGE_THRESHOLD", "10")
    monkeypatch.setenv("JPEG_QUALITY", "85")

    import importlib
    import config
    importlib.reload(config)
    settings = config.get_settings()

    assert settings.detection_model == "yolo26n"
    assert settings.child_age_threshold == 10
    assert settings.jpeg_quality == 85
```

**Step 2: Write implementation**

```python
# backend/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    detection_model: str = "yolo11n"
    child_age_threshold: int = 13
    classification_interval: int = 3
    jpeg_quality: int = 70
    snapshot_interval: int = 5
    input_resolution: int = 640
    database_path: str = "/app/data/monitor.db"
    videos_dir: str = "/app/videos"

    model_config = {"env_prefix": ""}


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Note: also add `pydantic-settings` to `requirements.txt`.

**Step 3: Run tests**

```bash
cd backend && pip install pydantic-settings pytest
pytest tests/test_config.py -v
# Expected: 2 passed
```

**Step 4: Commit**

```bash
git add backend/config.py backend/tests/test_config.py backend/requirements.txt
git commit -m "feat: configuration module with env var support"
```

---

## Task 3: Database Layer

**Files:**
- Create: `backend/db/database.py`
- Create: `backend/db/models.py`
- Create: `backend/db/queries.py`
- Create: `backend/tests/test_database.py`

**Step 1: Write tests**

```python
# backend/tests/test_database.py
import os
import tempfile
import pytest
from db.database import init_db, get_connection
from db.models import create_tables
from db import queries


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def db(db_path):
    conn = init_db(db_path)
    create_tables(conn)
    return conn


def test_create_tables(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "channels" in tables
    assert "sessions" in tables
    assert "tracks" in tables
    assert "session_snapshots" in tables


def test_insert_and_query_channel(db):
    queries.upsert_channel(db, "test-ch", "test.mp4", "Test Channel")
    channels = queries.list_channels(db)
    assert len(channels) == 1
    assert channels[0]["id"] == "test-ch"


def test_session_lifecycle(db):
    queries.upsert_channel(db, "ch1", "vid.mp4", "Channel 1")
    session_id = queries.create_session(db, "ch1")
    assert session_id is not None

    sessions = queries.list_sessions(db)
    assert len(sessions) == 1
    assert sessions[0]["status"] == "active"

    queries.stop_session(db, session_id)
    sessions = queries.list_sessions(db)
    assert sessions[0]["status"] == "stopped"
    assert sessions[0]["stopped_at"] is not None


def test_track_upsert(db):
    queries.upsert_channel(db, "ch1", "vid.mp4", "Channel 1")
    sid = queries.create_session(db, "ch1")

    queries.upsert_track(db, sid, track_id=1, classification="man",
                         age_estimate=30.0, gender_estimate="male", confidence=0.95)
    queries.upsert_track(db, sid, track_id=1, classification="man",
                         age_estimate=30.0, gender_estimate="male", confidence=0.95)

    tracks = queries.get_session_tracks(db, sid)
    assert len(tracks) == 1  # upsert, not duplicate


def test_snapshot_insert_and_query(db):
    queries.upsert_channel(db, "ch1", "vid.mp4", "Channel 1")
    sid = queries.create_session(db, "ch1")

    queries.insert_snapshot(db, sid, men_in_frame=3, women_in_frame=2,
                            children_in_frame=1, unknown_in_frame=0,
                            total_unique_men=5, total_unique_women=4,
                            total_unique_children=2, total_unique_unknown=1)

    snapshots = queries.get_session_snapshots(db, sid)
    assert len(snapshots) == 1
    assert snapshots[0]["men_in_frame"] == 3
```

**Step 2: Write database.py**

```python
# backend/db/database.py
import sqlite3


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def get_connection(db_path: str) -> sqlite3.Connection:
    return init_db(db_path)
```

**Step 3: Write models.py**

```python
# backend/db/models.py
import sqlite3


def create_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS channels (
            id          TEXT PRIMARY KEY,
            filename    TEXT NOT NULL,
            label       TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            channel_id  TEXT NOT NULL REFERENCES channels(id),
            started_at  TEXT NOT NULL,
            stopped_at  TEXT,
            status      TEXT NOT NULL DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS tracks (
            id              TEXT PRIMARY KEY,
            session_id      TEXT NOT NULL REFERENCES sessions(id),
            track_id        INTEGER NOT NULL,
            classification  TEXT,
            age_estimate    REAL,
            gender_estimate TEXT,
            confidence      REAL,
            first_seen_at   TEXT NOT NULL,
            last_seen_at    TEXT NOT NULL,
            UNIQUE(session_id, track_id)
        );

        CREATE TABLE IF NOT EXISTS session_snapshots (
            id                      TEXT PRIMARY KEY,
            session_id              TEXT NOT NULL REFERENCES sessions(id),
            timestamp               TEXT NOT NULL,
            men_in_frame            INTEGER NOT NULL DEFAULT 0,
            women_in_frame          INTEGER NOT NULL DEFAULT 0,
            children_in_frame       INTEGER NOT NULL DEFAULT 0,
            unknown_in_frame        INTEGER NOT NULL DEFAULT 0,
            total_unique_men        INTEGER NOT NULL DEFAULT 0,
            total_unique_women      INTEGER NOT NULL DEFAULT 0,
            total_unique_children   INTEGER NOT NULL DEFAULT 0,
            total_unique_unknown    INTEGER NOT NULL DEFAULT 0
        );
    """)
    conn.commit()
```

**Step 4: Write queries.py**

```python
# backend/db/queries.py
import sqlite3
import uuid
from datetime import datetime, timezone


def upsert_channel(conn: sqlite3.Connection, channel_id: str, filename: str, label: str):
    conn.execute(
        "INSERT OR REPLACE INTO channels (id, filename, label) VALUES (?, ?, ?)",
        (channel_id, filename, label),
    )
    conn.commit()


def list_channels(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM channels").fetchall()
    return [dict(r) for r in rows]


def create_session(conn: sqlite3.Connection, channel_id: str) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO sessions (id, channel_id, started_at, status) VALUES (?, ?, ?, 'active')",
        (session_id, channel_id, now),
    )
    conn.commit()
    return session_id


def stop_session(conn: sqlite3.Connection, session_id: str):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE sessions SET stopped_at = ?, status = 'stopped' WHERE id = ?",
        (now, session_id),
    )
    conn.commit()


def list_sessions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM sessions ORDER BY started_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_session(conn: sqlite3.Connection, session_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else None


def upsert_track(conn: sqlite3.Connection, session_id: str, track_id: int,
                 classification: str | None, age_estimate: float | None,
                 gender_estimate: str | None, confidence: float | None):
    row_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO tracks (id, session_id, track_id, classification, age_estimate,
                            gender_estimate, confidence, first_seen_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id, track_id) DO UPDATE SET
            classification = COALESCE(excluded.classification, classification),
            age_estimate = COALESCE(excluded.age_estimate, age_estimate),
            gender_estimate = COALESCE(excluded.gender_estimate, gender_estimate),
            confidence = COALESCE(excluded.confidence, confidence),
            last_seen_at = excluded.last_seen_at
    """, (row_id, session_id, track_id, classification, age_estimate,
          gender_estimate, confidence, now, now))
    conn.commit()


def get_session_tracks(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM tracks WHERE session_id = ?", (session_id,)).fetchall()
    return [dict(r) for r in rows]


def insert_snapshot(conn: sqlite3.Connection, session_id: str, **counts):
    snap_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO session_snapshots (id, session_id, timestamp,
            men_in_frame, women_in_frame, children_in_frame, unknown_in_frame,
            total_unique_men, total_unique_women, total_unique_children, total_unique_unknown)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (snap_id, session_id, now,
          counts.get("men_in_frame", 0), counts.get("women_in_frame", 0),
          counts.get("children_in_frame", 0), counts.get("unknown_in_frame", 0),
          counts.get("total_unique_men", 0), counts.get("total_unique_women", 0),
          counts.get("total_unique_children", 0), counts.get("total_unique_unknown", 0)))
    conn.commit()


def get_session_snapshots(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM session_snapshots WHERE session_id = ? ORDER BY timestamp",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_session_stats(conn: sqlite3.Connection, session_id: str) -> dict:
    """Get summary stats for a session: track counts by classification + snapshots."""
    tracks = get_session_tracks(conn, session_id)
    summary = {"men": 0, "women": 0, "children": 0, "unknown": 0, "total": len(tracks)}
    for t in tracks:
        cls = t.get("classification", "unknown") or "unknown"
        if cls == "man":
            summary["men"] += 1
        elif cls == "woman":
            summary["women"] += 1
        elif cls == "child":
            summary["children"] += 1
        else:
            summary["unknown"] += 1

    snapshots = get_session_snapshots(conn, session_id)
    return {"summary": summary, "snapshots": snapshots}
```

**Step 5: Run tests**

```bash
cd backend && pytest tests/test_database.py -v
# Expected: 5 passed
```

**Step 6: Commit**

```bash
git add backend/db/ backend/tests/test_database.py
git commit -m "feat: SQLite database layer with WAL mode, track lifecycle storage"
```

---

## Task 4: CV Worker Process

This is the core — the computer vision pipeline running in a separate process.

**Files:**
- Create: `backend/cv/worker.py`
- Create: `backend/cv/detector.py`
- Create: `backend/cv/classifier.py`
- Create: `backend/cv/policy.py`
- Create: `backend/cv/annotator.py`
- Create: `backend/tests/test_policy.py`

**Depends on:** T2 (config), T3 (database), T5 (policy)

**Step 1: Write and test classification policy (pure logic, no ML deps)**

```python
# backend/tests/test_policy.py
from cv.policy import classify_person


def test_classify_man():
    result = classify_person(age=30, gender="M", det_score=0.9, threshold=13)
    assert result["classification"] == "man"


def test_classify_woman():
    result = classify_person(age=25, gender="F", det_score=0.85, threshold=13)
    assert result["classification"] == "woman"


def test_classify_child_male():
    result = classify_person(age=8, gender="M", det_score=0.8, threshold=13)
    assert result["classification"] == "child"


def test_classify_child_female():
    result = classify_person(age=10, gender="F", det_score=0.7, threshold=13)
    assert result["classification"] == "child"


def test_classify_unknown_no_face():
    result = classify_person(age=None, gender=None, det_score=None, threshold=13)
    assert result["classification"] == "unknown"


def test_classify_custom_threshold():
    result = classify_person(age=14, gender="M", det_score=0.9, threshold=16)
    assert result["classification"] == "child"
    result2 = classify_person(age=14, gender="M", det_score=0.9, threshold=13)
    assert result2["classification"] == "man"
```

**Step 2: Write policy.py**

```python
# backend/cv/policy.py


def classify_person(
    age: int | None,
    gender: str | None,
    det_score: float | None,
    threshold: int = 13,
) -> dict:
    """Derive classification from raw InsightFace outputs.

    Returns dict with classification, age_estimate, gender_estimate, confidence.
    """
    if age is None or gender is None or det_score is None:
        return {
            "classification": "unknown",
            "age_estimate": None,
            "gender_estimate": None,
            "confidence": None,
        }

    gender_mapped = "male" if gender == "M" else "female"

    if age < threshold:
        classification = "child"
    elif gender == "M":
        classification = "man"
    else:
        classification = "woman"

    return {
        "classification": classification,
        "age_estimate": float(age),
        "gender_estimate": gender_mapped,
        "confidence": float(det_score),
    }
```

**Step 3: Run policy tests**

```bash
pytest tests/test_policy.py -v
# Expected: 6 passed
```

**Step 4: Write detector.py (YOLO + ByteTrack wrapper)**

```python
# backend/cv/detector.py
import numpy as np

class PersonDetector:
    def __init__(self, model_name: str = "yolo11n.pt", input_size: int = 640):
        from ultralytics import YOLO
        self.model = YOLO(model_name)
        self.input_size = input_size

    def detect_and_track(self, frame: np.ndarray) -> dict:
        """Run detection + tracking on a frame.

        Returns dict with keys: boxes_xyxy, track_ids, confidences, result (raw).
        """
        results = self.model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            classes=[0],  # person only
            conf=0.5,
            iou=0.7,
            imgsz=self.input_size,
            verbose=False,
        )
        result = results[0]

        if result.boxes.id is None:
            return {
                "boxes_xyxy": np.empty((0, 4)),
                "track_ids": [],
                "confidences": np.empty(0),
                "result": result,
            }

        return {
            "boxes_xyxy": result.boxes.xyxy.cpu().numpy(),
            "track_ids": result.boxes.id.int().cpu().tolist(),
            "confidences": result.boxes.conf.cpu().numpy(),
            "result": result,
        }

    def reset_tracker(self):
        """Reset ByteTrack state (call on video loop restart)."""
        if hasattr(self.model, "predictor") and self.model.predictor is not None:
            for tracker in self.model.predictor.trackers:
                tracker.reset()
```

**Step 5: Write classifier.py (InsightFace wrapper)**

```python
# backend/cv/classifier.py
import numpy as np


class FaceClassifier:
    def __init__(self, det_size: tuple[int, int] = (640, 640), det_thresh: float = 0.5):
        from insightface.app import FaceAnalysis
        self.app = FaceAnalysis(
            name="buffalo_l",
            allowed_modules=["detection", "genderage"],
            providers=["CPUExecutionProvider"],
        )
        self.app.prepare(ctx_id=0, det_thresh=det_thresh, det_size=det_size)

    def analyze_crop(self, crop: np.ndarray) -> dict | None:
        """Run face analysis on a person crop.

        Returns dict with age, gender, det_score or None if no face found.
        """
        if crop.shape[0] < 20 or crop.shape[1] < 20:
            return None

        faces = self.app.get(crop, max_num=1)
        if not faces:
            return None

        face = faces[0]
        return {
            "age": face.age,
            "gender": face.sex,  # 'M' or 'F'
            "det_score": float(face.det_score),
        }
```

**Step 6: Write annotator.py (supervision wrapper)**

```python
# backend/cv/annotator.py
import numpy as np
import supervision as sv

# Classification -> color mapping
CLASS_COLORS = {
    "man": sv.Color.from_hex("#3B82F6"),
    "woman": sv.Color.from_hex("#EC4899"),
    "child": sv.Color.from_hex("#22C55E"),
    "unknown": sv.Color.from_hex("#6B7280"),
}


CLASS_TO_ID = {"man": 0, "woman": 1, "child": 2, "unknown": 3}
PALETTE = sv.ColorPalette([
    sv.Color.from_hex("#3B82F6"),  # man = blue
    sv.Color.from_hex("#EC4899"),  # woman = pink
    sv.Color.from_hex("#22C55E"),  # child = green
    sv.Color.from_hex("#6B7280"),  # unknown = gray
])


class FrameAnnotator:
    def __init__(self):
        self.box_annotator = sv.BoundingBoxAnnotator(
            thickness=2, color=PALETTE, color_lookup=sv.ColorLookup.CLASS,
        )
        self.label_annotator = sv.LabelAnnotator(
            text_scale=0.5, text_padding=5, text_color=sv.Color.WHITE,
            color=PALETTE, color_lookup=sv.ColorLookup.CLASS,
        )

    def annotate(
        self,
        frame: np.ndarray,
        detections: sv.Detections,
        classifications: dict[int, dict],
    ) -> np.ndarray:
        """Draw bounding boxes and labels on frame.

        Args:
            frame: BGR frame
            detections: supervision Detections from ultralytics result
            classifications: mapping of track_id -> {classification, confidence}
        """
        if len(detections) == 0:
            return frame

        # Override class_id to map classification -> palette index
        # (YOLO returns class_id=0 for all persons; we remap based on gender/age)
        labels = []
        new_class_ids = []
        for i in range(len(detections)):
            tid = detections.tracker_id[i] if detections.tracker_id is not None else i
            info = classifications.get(tid, {})
            cls = info.get("classification", "unknown")
            conf = info.get("confidence")

            new_class_ids.append(CLASS_TO_ID.get(cls, 3))

            if cls == "unknown":
                labels.append(f"Person #{tid}")
            else:
                conf_str = f" ({conf:.2f})" if conf is not None else ""
                labels.append(f"{cls.capitalize()} #{tid}{conf_str}")

        detections.class_id = np.array(new_class_ids)

        annotated = self.box_annotator.annotate(scene=frame.copy(), detections=detections)
        annotated = self.label_annotator.annotate(scene=annotated, detections=detections, labels=labels)
        return annotated
```

**Step 7: Write worker.py (main CV loop)**

```python
# backend/cv/worker.py
import multiprocessing as mp
import queue
import signal
import time
from datetime import datetime, timezone

import cv2
import numpy as np
import supervision as sv

from config import Settings
from cv.detector import PersonDetector
from cv.classifier import FaceClassifier
from cv.policy import classify_person
from cv.annotator import FrameAnnotator
from db.database import init_db
from db.models import create_tables
from db import queries


def put_drop_oldest(q: mp.Queue, item):
    """Put item into bounded queue, dropping oldest if full."""
    try:
        q.put_nowait(item)
    except queue.Full:
        try:
            q.get_nowait()
        except queue.Empty:
            pass
        try:
            q.put_nowait(item)
        except queue.Full:
            pass


def cv_worker(
    frame_queue: mp.Queue,
    stats_queue: mp.Queue,
    cmd_queue: mp.Queue,
    stop_event: mp.Event,
    settings_dict: dict,
):
    """Main CV worker process. Runs detection + tracking + classification loop."""
    # Reset signal handlers (safety for spawn)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    settings = Settings(**settings_dict)

    # Initialize components
    detector = PersonDetector(
        model_name=f"{settings.detection_model}.pt",
        input_size=settings.input_resolution,
    )
    classifier = FaceClassifier(det_size=(640, 640))
    annotator = FrameAnnotator()

    # Initialize DB (own connection for this process)
    conn = init_db(settings.database_path)
    create_tables(conn)

    # State
    cap = None
    session_id = None
    frame_count = 0
    classifications: dict[int, dict] = {}  # track_id -> classification info
    last_snapshot_time = 0.0
    fps_counter = 0
    fps_time = time.time()
    current_fps = 0.0

    try:
        while not stop_event.is_set():
            # Check for commands
            try:
                cmd = cmd_queue.get_nowait()
                if cmd["type"] == "start":
                    channel = cmd["channel"]
                    video_path = f"{settings.videos_dir}/{channel['filename']}"
                    cap = cv2.VideoCapture(video_path)
                    session_id = cmd["session_id"]
                    frame_count = 0
                    classifications.clear()
                    last_snapshot_time = time.time()
                    detector.reset_tracker()
                elif cmd["type"] == "stop":
                    if cap is not None:
                        cap.release()
                        cap = None
                    session_id = None
                    classifications.clear()
            except queue.Empty:
                pass

            # If no active session, sleep briefly and continue
            if cap is None or session_id is None:
                time.sleep(0.05)
                continue

            ret, frame = cap.read()
            if not ret:
                # Loop the video
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                detector.reset_tracker()
                classifications.clear()
                continue

            frame_count += 1

            # FPS tracking
            fps_counter += 1
            elapsed = time.time() - fps_time
            if elapsed >= 1.0:
                current_fps = fps_counter / elapsed
                fps_counter = 0
                fps_time = time.time()

            # 1. Detect + track
            det = detector.detect_and_track(frame)
            track_ids = det["track_ids"]
            boxes = det["boxes_xyxy"]

            # 2. Classify faces (every Nth frame)
            if frame_count % settings.classification_interval == 0:
                for tid, box in zip(track_ids, boxes):
                    x1, y1, x2, y2 = box.astype(int)
                    crop = frame[y1:y2, x1:x2]
                    face_result = classifier.analyze_crop(crop)

                    if face_result is not None:
                        cls_result = classify_person(
                            age=face_result["age"],
                            gender=face_result["gender"],
                            det_score=face_result["det_score"],
                            threshold=settings.child_age_threshold,
                        )
                        classifications[tid] = cls_result

                        # Persist track
                        queries.upsert_track(
                            conn, session_id, tid,
                            classification=cls_result["classification"],
                            age_estimate=cls_result["age_estimate"],
                            gender_estimate=cls_result["gender_estimate"],
                            confidence=cls_result["confidence"],
                        )
                    elif tid not in classifications:
                        classifications[tid] = classify_person(None, None, None)
                        queries.upsert_track(
                            conn, session_id, tid,
                            classification="unknown",
                            age_estimate=None,
                            gender_estimate=None,
                            confidence=None,
                        )

            # 3. Annotate frame
            detections = sv.Detections.from_ultralytics(det["result"])
            annotated = annotator.annotate(frame, detections, classifications)

            # 4. Encode JPEG and push to frame queue
            _, jpeg = cv2.imencode(".jpg", annotated,
                                    [cv2.IMWRITE_JPEG_QUALITY, settings.jpeg_quality])
            put_drop_oldest(frame_queue, jpeg.tobytes())

            # 5. Compute current stats and push
            in_frame = {"men": 0, "women": 0, "children": 0, "unknown": 0}
            for tid in track_ids:
                cls = classifications.get(tid, {}).get("classification", "unknown")
                if cls == "man":
                    in_frame["men"] += 1
                elif cls == "woman":
                    in_frame["women"] += 1
                elif cls == "child":
                    in_frame["children"] += 1
                else:
                    in_frame["unknown"] += 1

            # Session totals from in-memory classifications (no per-frame DB query)
            session_total = {"men": 0, "women": 0, "children": 0, "unknown": 0}
            for cls_info in classifications.values():
                c = cls_info.get("classification", "unknown")
                if c == "man":
                    session_total["men"] += 1
                elif c == "woman":
                    session_total["women"] += 1
                elif c == "child":
                    session_total["children"] += 1
                else:
                    session_total["unknown"] += 1

            stats = {
                "in_frame": in_frame,
                "session_total": session_total,
                "fps": round(current_fps, 1),
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            put_drop_oldest(stats_queue, stats)

            # 6. Periodic snapshot
            now = time.time()
            if now - last_snapshot_time >= settings.snapshot_interval:
                queries.insert_snapshot(
                    conn, session_id,
                    men_in_frame=in_frame["men"],
                    women_in_frame=in_frame["women"],
                    children_in_frame=in_frame["children"],
                    unknown_in_frame=in_frame["unknown"],
                    total_unique_men=session_total["men"],
                    total_unique_women=session_total["women"],
                    total_unique_children=session_total["children"],
                    total_unique_unknown=session_total["unknown"],
                )
                last_snapshot_time = now

    finally:
        if cap is not None:
            cap.release()
        conn.close()
```

**Step 8: Commit**

```bash
git add backend/cv/ backend/tests/test_policy.py
git commit -m "feat: CV worker with YOLO detection, ByteTrack tracking, InsightFace classification"
```

---

## Task 5: Channel Registration

**Files:**
- Create: `backend/cv/channels.py`
- Create: `backend/tests/test_channels.py`

**Step 1: Write test**

```python
# backend/tests/test_channels.py
import os
import tempfile
import pytest
from cv.channels import scan_videos_dir


def test_scan_empty_dir():
    with tempfile.TemporaryDirectory() as d:
        channels = scan_videos_dir(d)
        assert channels == []


def test_scan_with_mp4_files():
    with tempfile.TemporaryDirectory() as d:
        # Create fake mp4 files
        for name in ["street-scene.mp4", "mall-crowd.mp4", "readme.txt"]:
            open(os.path.join(d, name), "w").close()
        channels = scan_videos_dir(d)
        assert len(channels) == 2
        ids = [c["id"] for c in channels]
        assert "street-scene" in ids
        assert "mall-crowd" in ids
```

**Step 2: Write implementation**

```python
# backend/cv/channels.py
import os
from pathlib import Path


def scan_videos_dir(videos_dir: str) -> list[dict]:
    """Scan directory for MP4 files and return channel list."""
    channels = []
    path = Path(videos_dir)
    if not path.exists():
        return channels

    for f in sorted(path.glob("*.mp4")):
        channel_id = f.stem  # filename without extension
        channels.append({
            "id": channel_id,
            "filename": f.name,
            "label": channel_id.replace("-", " ").replace("_", " ").title(),
        })
    return channels
```

**Step 3: Run tests, commit**

```bash
pytest tests/test_channels.py -v
git add backend/cv/channels.py backend/tests/test_channels.py
git commit -m "feat: video channel scanner from mp4 directory"
```

---

## Task 6: API Endpoints (REST + MJPEG + SSE)

**Files:**
- Create: `backend/api/routes.py`
- Create: `backend/api/stream.py`
- Create: `backend/api/events.py`
- Modify: `backend/main.py` (wire up lifespan + routers)

**Depends on:** T1, T2, T3, T4, T5

**Step 1: Write routes.py (REST endpoints)**

```python
# backend/api/routes.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import get_settings
from cv.channels import scan_videos_dir
from db import queries

router = APIRouter(prefix="/api")


class StartSessionRequest(BaseModel):
    channel_id: str


class StopSessionRequest(BaseModel):
    session_id: str


@router.get("/channels")
async def list_channels():
    settings = get_settings()
    return scan_videos_dir(settings.videos_dir)


@router.post("/sessions/start")
async def start_session(req: StartSessionRequest, request: Request):
    db = request.app.state.db
    cmd_queue = request.app.state.cmd_queue

    channels = scan_videos_dir(get_settings().videos_dir)
    channel = next((c for c in channels if c["id"] == req.channel_id), None)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Register channel in DB if not exists
    queries.upsert_channel(db, channel["id"], channel["filename"], channel["label"])

    # Create session
    session_id = queries.create_session(db, req.channel_id)

    # Send start command to CV worker
    cmd_queue.put({"type": "start", "channel": channel, "session_id": session_id})

    return {"session_id": session_id, "status": "started"}


@router.post("/sessions/stop")
async def stop_session(req: StopSessionRequest, request: Request):
    db = request.app.state.db
    cmd_queue = request.app.state.cmd_queue

    session = queries.get_session(db, req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    queries.stop_session(db, req.session_id)
    cmd_queue.put({"type": "stop"})

    return {"session_id": req.session_id, "status": "stopped"}


@router.get("/sessions")
async def list_sessions(request: Request):
    return queries.list_sessions(request.app.state.db)


@router.get("/sessions/{session_id}/stats")
async def session_stats(session_id: str, request: Request):
    session = queries.get_session(request.app.state.db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    stats = queries.get_session_stats(request.app.state.db, session_id)
    return {**session, **stats}
```

**Step 2: Write stream_hub.py (latest-frame cache for multi-client fan-out)**

```python
# backend/api/stream_hub.py
import asyncio
import queue
import threading

import anyio


class StreamHub:
    """Consumes from multiprocessing.Queue and caches latest frame/stats.
    Multiple HTTP clients read copies of the latest data (fan-out).
    Runs a background thread to drain the mp.Queue.
    """

    def __init__(self, frame_queue, stats_queue):
        self._frame_queue = frame_queue
        self._stats_queue = stats_queue
        self.latest_frame: bytes | None = None
        self.latest_stats: dict | None = None
        self._frame_event = asyncio.Event()
        self._stats_event = asyncio.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._drain_loop, daemon=True)
        self._thread.start()

    def _drain_loop(self):
        """Background thread: drain queues, update latest values."""
        while not self._stop.is_set():
            got_something = False
            try:
                self.latest_frame = self._frame_queue.get_nowait()
                self._frame_event.set()
                got_something = True
            except queue.Empty:
                pass
            try:
                self.latest_stats = self._stats_queue.get_nowait()
                self._stats_event.set()
                got_something = True
            except queue.Empty:
                pass
            if not got_something:
                self._stop.wait(timeout=0.01)

    async def wait_frame(self) -> bytes:
        """Wait for a new frame (async, multiple callers OK)."""
        self._frame_event.clear()
        while self.latest_frame is None:
            await anyio.sleep(0.01)
        await asyncio.wait_for(self._frame_event.wait(), timeout=1.0)
        self._frame_event.clear()
        return self.latest_frame

    async def wait_stats(self) -> dict:
        """Wait for new stats (async, multiple callers OK)."""
        self._stats_event.clear()
        while self.latest_stats is None:
            await anyio.sleep(0.1)
        await asyncio.wait_for(self._stats_event.wait(), timeout=2.0)
        self._stats_event.clear()
        return self.latest_stats

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
```

**Step 3: Write stream.py (MJPEG)**

```python
# backend/api/stream.py
import anyio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()


async def mjpeg_generator(hub):
    """Yield latest MJPEG frames from StreamHub. Multi-client safe."""
    while True:
        try:
            frame_bytes = await hub.wait_frame()
        except Exception:
            await anyio.sleep(0.01)
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame_bytes
            + b"\r\n"
        )


@router.get("/api/stream")
async def video_stream(request: Request):
    return StreamingResponse(
        mjpeg_generator(request.app.state.hub),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
```

**Step 4: Write events.py (SSE)**

```python
# backend/api/events.py
import json
from collections.abc import AsyncIterable

import anyio
from fastapi import APIRouter, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

router = APIRouter()


@router.get("/api/events", response_class=EventSourceResponse)
async def stats_stream(request: Request) -> AsyncIterable[ServerSentEvent]:
    hub = request.app.state.hub
    while True:
        try:
            stats = await hub.wait_stats()
            yield ServerSentEvent(data=json.dumps(stats), event="stats")
        except Exception:
            await anyio.sleep(0.1)
```

**Step 4: Update main.py with full lifespan and router wiring**

```python
# backend/main.py
import multiprocessing as mp
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from cv.channels import scan_videos_dir
from cv.worker import cv_worker
from db.database import init_db
from db.models import create_tables
from db import queries


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Ensure data directory exists
    os.makedirs(os.path.dirname(settings.database_path), exist_ok=True)

    # Init DB for API process (read-only usage)
    db = init_db(settings.database_path)
    create_tables(db)
    app.state.db = db

    # Register channels
    channels = scan_videos_dir(settings.videos_dir)
    for ch in channels:
        queries.upsert_channel(db, ch["id"], ch["filename"], ch["label"])

    # Start CV worker process
    ctx = mp.get_context("spawn")
    frame_queue = ctx.Queue(maxsize=2)
    stats_queue = ctx.Queue(maxsize=4)
    cmd_queue = ctx.Queue(maxsize=10)
    stop_event = ctx.Event()

    worker = ctx.Process(
        target=cv_worker,
        args=(frame_queue, stats_queue, cmd_queue, stop_event, settings.model_dump()),
        daemon=True,
    )
    worker.start()

    app.state.frame_queue = frame_queue
    app.state.stats_queue = stats_queue
    app.state.cmd_queue = cmd_queue
    app.state.worker = worker
    app.state.stop_event = stop_event

    # StreamHub: caches latest frame/stats, fans out to multiple HTTP clients
    from api.stream_hub import StreamHub
    hub = StreamHub(frame_queue, stats_queue)
    app.state.hub = hub

    yield

    # Shutdown
    hub.stop()
    stop_event.set()
    worker.join(timeout=5)
    if worker.is_alive():
        worker.terminate()
        worker.join(timeout=2)

    for q in (frame_queue, stats_queue, cmd_queue):
        while not q.empty():
            try:
                q.get_nowait()
            except Exception:
                break
        q.close()
        q.join_thread()

    db.close()


app = FastAPI(title="Live Feed Monitor", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from api.routes import router as api_router
from api.stream import router as stream_router
from api.events import router as events_router

app.include_router(api_router)
app.include_router(stream_router)
app.include_router(events_router)


@app.get("/api/health")
async def health():
    worker_alive = hasattr(app.state, "worker") and app.state.worker.is_alive()
    return {"status": "ok", "worker_alive": worker_alive}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
```

**Step 5: Commit**

```bash
git add backend/api/ backend/main.py
git commit -m "feat: API endpoints - REST, MJPEG stream, SSE events with multiprocessing lifespan"
```

---

## Task 7: Frontend Scaffold

**Files:**
- Create: `frontend/` (entire Vite + React + shadcn setup)

**Step 1: Scaffold Vite + React + TypeScript**

```bash
cd /Users/simonren/Developer/tes/live-monitor
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

**Step 2: Install dependencies**

```bash
npm install ky zustand recharts @tanstack/react-query @tanstack/react-router lucide-react dayjs
npm install -D tailwindcss @tailwindcss/vite
```

**Step 3: Set up Tailwind v4**

Add Tailwind plugin to `vite.config.ts`:

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

Add to `src/index.css`:

```css
@import "tailwindcss";
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');

@theme {
  --font-heading: 'Fira Code', monospace;
  --font-body: 'Fira Sans', sans-serif;
  --color-bg: #020617;
  --color-surface: #0F172A;
  --color-surface-hover: #1E293B;
  --color-accent: #22C55E;
  --color-text: #F8FAFC;
  --color-muted: #94A3B8;
  --color-border: #1E293B;
  --color-man: #3B82F6;
  --color-woman: #EC4899;
  --color-child: #22C55E;
  --color-unknown: #6B7280;
}
```

**Step 4: Initialize shadcn/ui**

```bash
npx shadcn@latest init
# Select: New York style, Slate color, CSS variables
npx shadcn@latest add button card select table badge
```

**Step 5: Write API client**

```typescript
// frontend/src/lib/api.ts
import ky from 'ky'

const api = ky.create({ prefixUrl: '/api' })

export interface Channel {
  id: string
  filename: string
  label: string
}

export interface Session {
  id: string
  channel_id: string
  started_at: string
  stopped_at: string | null
  status: 'active' | 'stopped'
}

export interface StatsEvent {
  in_frame: { men: number; women: number; children: number; unknown: number }
  session_total: { men: number; women: number; children: number; unknown: number }
  fps: number
  session_id: string
  timestamp: string
}

export interface SessionStats extends Session {
  summary: { men: number; women: number; children: number; unknown: number; total: number }
  snapshots: Array<{
    timestamp: string
    men_in_frame: number
    women_in_frame: number
    children_in_frame: number
    unknown_in_frame: number
  }>
}

export const fetchChannels = () => api.get('channels').json<Channel[]>()
export const fetchSessions = () => api.get('sessions').json<Session[]>()
export const fetchSessionStats = (id: string) => api.get(`sessions/${id}/stats`).json<SessionStats>()
export const startSession = (channel_id: string) =>
  api.post('sessions/start', { json: { channel_id } }).json<{ session_id: string }>()
export const stopSession = (session_id: string) =>
  api.post('sessions/stop', { json: { session_id } }).json<{ session_id: string }>()
```

**Step 6: Write Zustand store**

```typescript
// frontend/src/stores/monitor.ts
import { create } from 'zustand'
import type { StatsEvent } from '../lib/api'

interface MonitorState {
  sessionId: string | null
  stats: StatsEvent | null
  chartData: Array<StatsEvent & { time: string }>
  isConnected: boolean
  setSessionId: (id: string | null) => void
  setStats: (stats: StatsEvent) => void
  setConnected: (connected: boolean) => void
  clearChart: () => void
}

export const useMonitorStore = create<MonitorState>((set) => ({
  sessionId: null,
  stats: null,
  chartData: [],
  isConnected: false,
  setSessionId: (id) => set({ sessionId: id }),
  setStats: (stats) =>
    set((state) => ({
      stats,
      chartData: [
        ...state.chartData.slice(-60),  // keep last 60 data points (~5 min at 5s interval)
        { ...stats, time: new Date(stats.timestamp).toLocaleTimeString() },
      ],
    })),
  setConnected: (connected) => set({ isConnected: connected }),
  clearChart: () => set({ chartData: [], stats: null }),
}))
```

**Step 7: Write SSE hook**

```typescript
// frontend/src/hooks/use-sse.ts
import { useEffect, useRef } from 'react'
import { useMonitorStore } from '../stores/monitor'
import type { StatsEvent } from '../lib/api'

export function useSSE() {
  const { setStats, setConnected } = useMonitorStore()
  const eventSourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource('/api/events')
    eventSourceRef.current = es

    es.addEventListener('stats', (e) => {
      const data: StatsEvent = JSON.parse(e.data)
      setStats(data)
      setConnected(true)
    })

    es.onerror = () => {
      setConnected(false)
    }

    es.onopen = () => {
      setConnected(true)
    }

    return () => {
      es.close()
      eventSourceRef.current = null
    }
  }, [setStats, setConnected])
}
```

**Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: frontend scaffold with Vite, React, shadcn/ui, Tailwind, API client, Zustand store"
```

---

## Task 8: Frontend Dashboard & History Pages

**Files:**
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/components/live-preview.tsx`
- Create: `frontend/src/components/stats-panel.tsx`
- Create: `frontend/src/components/time-chart.tsx`
- Create: `frontend/src/components/channel-selector.tsx`
- Create: `frontend/src/components/session-table.tsx`
- Create: `frontend/src/routes/dashboard.tsx`
- Create: `frontend/src/routes/history.tsx`

**Depends on:** T7

This task builds all UI components and pages per the design system at `.jarvis/design-system/`. Key reference:
- Dashboard: `.jarvis/design-system/pages/dashboard.md`
- History: `.jarvis/design-system/pages/history.md`
- Global: `.jarvis/design-system/MASTER.md`

**Components to implement (in order):**

1. **`channel-selector.tsx`** — shadcn Select dropdown listing channels from `GET /api/channels`
2. **`live-preview.tsx`** — `<img>` tag pointing at `/api/stream` with connection status dot, MJPEG reconnection logic (re-set `src` if stale >3s)
3. **`stats-panel.tsx`** — Real-time counters (in-frame + session totals) with classification colors
4. **`time-chart.tsx`** — Recharts stacked AreaChart of people over time from Zustand chartData
5. **`session-table.tsx`** — shadcn DataTable of past sessions with duration formatting
6. **`dashboard.tsx`** — Full page composing channel-selector, start/stop button, live-preview, stats-panel, time-chart
7. **`history.tsx`** — Session list page with table, click-to-view session detail with charts
8. **`App.tsx`** — Top-level routing between Dashboard and History, dark theme wrapper

**Design tokens to use:**
- Background: `bg-[#020617]`
- Surface: `bg-[#0F172A]`
- Border: `border-[#1E293B]`
- Text: `text-[#F8FAFC]`
- Muted: `text-[#94A3B8]`
- Classification colors: man=`#3B82F6`, woman=`#EC4899`, child=`#22C55E`, unknown=`#6B7280`
- Font heading: `font-heading` (Fira Code)
- Font body: `font-body` (Fira Sans)
- Chart grid: `#1E293B`, fills at 20% opacity

**Commit after each major component group (preview+stats, chart, pages).**

---

## Task 9: Docker Compose Setup

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Create: `docker-compose.yml`
- Create: `.gitignore`
- Create: `videos/` (with download script for sample videos)

**Depends on:** T6 (backend complete), T8 (frontend complete)

**Step 1: Write backend Dockerfile**

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim-bookworm AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential gcc g++ python3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /tmp/requirements.txt

FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 ORT_LOG_LEVEL=ERROR

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libglib2.0-0 libgl1 libsm6 libxext6 libxrender1 ffmpeg wget unzip curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

# Pre-download YOLO model
ADD https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt /models/yolo11n.pt

# Pre-download InsightFace models
RUN mkdir -p /root/.insightface/models && \
    wget -q https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip \
        -O /tmp/buffalo_l.zip && \
    unzip -q /tmp/buffalo_l.zip -d /root/.insightface/models/ && \
    rm /tmp/buffalo_l.zip

WORKDIR /app
COPY . .

EXPOSE 8000
CMD ["python", "main.py"]
```

**Step 2: Write frontend Dockerfile + nginx.conf**

```dockerfile
# frontend/Dockerfile
FROM node:22-slim AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:stable-alpine
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

```nginx
# frontend/nginx.conf
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
    }
}
```

**Step 3: Write docker-compose.yml**

```yaml
# docker-compose.yml
services:
  backend:
    build: ./backend
    volumes:
      - ./videos:/app/videos
      - ./data:/app/data
    environment:
      - DETECTION_MODEL=yolo11n
      - CHILD_AGE_THRESHOLD=13
      - CLASSIFICATION_INTERVAL=3
      - JPEG_QUALITY=70
      - SNAPSHOT_INTERVAL=5
      - INPUT_RESOLUTION=640
      - DATABASE_PATH=/app/data/monitor.db
      - VIDEOS_DIR=/app/videos
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend
    restart: unless-stopped
```

**Step 4: Write .gitignore**

```
# .gitignore
data/
__pycache__/
*.pyc
.pytest_cache/
node_modules/
frontend/dist/
*.egg-info/
.env
```

**Step 5: Create sample video download script**

```bash
# download_samples.sh
#!/bin/bash
mkdir -p videos
echo "Download 2-3 royalty-free crowd videos from Pexels and place them in ./videos/"
echo "Example: https://www.pexels.com/search/videos/crowd%20walking/"
echo ""
echo "For quick testing, you can use any MP4 file:"
echo "  cp /path/to/any/video.mp4 videos/street-scene.mp4"
```

**Step 6: Test Docker build**

```bash
docker compose build
docker compose up
# Verify: http://localhost:3000 loads frontend
# Verify: http://localhost:3000/api/health returns {"status":"ok","worker_alive":true}
```

**Step 7: Commit**

```bash
git add backend/Dockerfile frontend/Dockerfile frontend/nginx.conf docker-compose.yml .gitignore download_samples.sh
git commit -m "feat: Docker Compose setup with multi-stage builds, model pre-download, nginx proxy"
```

---

## Task 10: Smoke Test

**Files:**
- Create: `tests/test_smoke.py`

**Depends on:** T9 (Docker Compose working)

**Step 1: Write smoke test using httpx**

```python
# tests/test_smoke.py
"""
Smoke test for the Live Feed Monitor.
Requires: docker compose up running + at least one MP4 in ./videos/

Run: python tests/test_smoke.py
"""
import sys
import time
import httpx

BASE_URL = "http://localhost:3000"  # through nginx proxy


def test_health():
    r = httpx.get(f"{BASE_URL}/api/health", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["worker_alive"] is True
    print("✓ Health check passed")


def test_channels():
    r = httpx.get(f"{BASE_URL}/api/channels", timeout=10)
    assert r.status_code == 200
    channels = r.json()
    assert len(channels) > 0, "No channels found — add MP4 files to ./videos/"
    print(f"✓ Found {len(channels)} channel(s): {[c['id'] for c in channels]}")
    return channels


def test_session_lifecycle(channel_id: str):
    # Start session
    r = httpx.post(f"{BASE_URL}/api/sessions/start",
                   json={"channel_id": channel_id}, timeout=10)
    assert r.status_code == 200
    session_id = r.json()["session_id"]
    print(f"✓ Session started: {session_id}")

    # Wait for processing
    time.sleep(3)

    # Check MJPEG stream
    with httpx.stream("GET", f"{BASE_URL}/api/stream", timeout=10) as resp:
        assert resp.status_code == 200
        assert "multipart/x-mixed-replace" in resp.headers.get("content-type", "")
        # Read a few bytes to confirm data is flowing
        chunk = next(resp.iter_bytes(chunk_size=1024))
        assert len(chunk) > 0
    print("✓ MJPEG stream is active")

    # Check SSE stream
    with httpx.stream("GET", f"{BASE_URL}/api/events", timeout=10) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if line.startswith("data:"):
                print("✓ SSE stats event received")
                break

    # Stop session
    r = httpx.post(f"{BASE_URL}/api/sessions/stop",
                   json={"session_id": session_id}, timeout=10)
    assert r.status_code == 200
    print(f"✓ Session stopped")

    # Check session appears in history
    r = httpx.get(f"{BASE_URL}/api/sessions", timeout=10)
    sessions = r.json()
    assert any(s["id"] == session_id for s in sessions)
    print("✓ Session appears in history")

    # Check session stats
    r = httpx.get(f"{BASE_URL}/api/sessions/{session_id}/stats", timeout=10)
    assert r.status_code == 200
    stats = r.json()
    print(f"✓ Session stats: {stats['summary']}")


def main():
    print("=== Live Feed Monitor Smoke Test ===\n")
    try:
        test_health()
        channels = test_channels()
        test_session_lifecycle(channels[0]["id"])
        print("\n=== ALL SMOKE TESTS PASSED ===")
    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 2: Run**

```bash
pip install httpx
python tests/test_smoke.py
# Expected: ALL SMOKE TESTS PASSED
```

**Step 3: Commit**

```bash
git add tests/test_smoke.py
git commit -m "feat: smoke test for end-to-end session lifecycle"
```

---

## Summary

| Task | Description | Depends On | Est. Complexity |
|------|-------------|-----------|-----------------|
| T1 | Backend scaffold (FastAPI + health check) | — | Low |
| T2 | Config module (pydantic-settings) | — | Low |
| T3 | Database layer (SQLite + queries) | — | Medium |
| T4 | CV worker (YOLO + ByteTrack + InsightFace + annotation) | T2, T3, T5 | High |
| T5 | Channel scanner (MP4 directory scan) | — | Low |
| T6 | API endpoints (REST + MJPEG + SSE + lifespan) | T1-T5 | High |
| T7 | Frontend scaffold (Vite + React + shadcn + stores) | — | Medium |
| T8 | Frontend pages (Dashboard + History) | T7 | High |
| T9 | Docker Compose (Dockerfiles + nginx + compose) | T6, T8 | Medium |
| T10 | Smoke test (httpx E2E) | T9 | Low |
