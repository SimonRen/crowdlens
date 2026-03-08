# Research: Live Feed Monitor PoC

**Date:** 2026-03-08
**Type:** Greenfield — no existing codebase to deep-read

---

## 1. CV Pipeline Integration Points

### YOLO Detection + ByteTrack Tracking

```python
from ultralytics import YOLO
model = YOLO("yolo11n.pt")  # or yolo26n.pt
results = model.track(frame, persist=True, tracker="bytetrack.yaml", classes=[0], conf=0.5)
result = results[0]

# CRITICAL: boxes.id is None when no tracks assigned (first frame, low confidence)
if result.boxes.id is not None:
    track_ids = result.boxes.id.int().cpu().tolist()
    boxes_xyxy = result.boxes.xyxy.cpu().numpy()
    confidences = result.boxes.conf.cpu().numpy()
```

**Gotchas:**
- `persist=True` mandatory for frame-by-frame loops
- `boxes.id` can be `None` — always guard
- On video loop restart: must call `model.predictor.trackers[0].reset()` manually
- `STrack._count` is a class variable — reset affects all tracker instances in process

### InsightFace Face Analysis

```python
from insightface.app import FaceAnalysis
face_app = FaceAnalysis(
    name='buffalo_l',
    allowed_modules=['detection', 'genderage'],  # skip recognition
    providers=['CPUExecutionProvider'],
)
face_app.prepare(ctx_id=0, det_thresh=0.5, det_size=(640, 640))

faces = face_app.get(person_crop, max_num=1)
# face.sex = 'M' or 'F' (string, not int)
# face.age = int
# face.det_score = float
# face.bbox = ndarray [x1,y1,x2,y2]
```

**Gotchas:**
- `buffalo_l` is 326MB — must pre-download in Docker build
- `face.sex` returns `'M'`/`'F'` string (not 0/1)
- Tiny crops (< 20px) silently return empty list
- `storage.insightface.ai` CDN unreliable — use GitHub releases URL

### Supervision Annotation

```python
import supervision as sv
detections = sv.Detections.from_ultralytics(result)
# detections.tracker_id auto-populated from ultralytics

box_annotator = sv.BoundingBoxAnnotator(thickness=2, color_lookup=sv.ColorLookup.TRACK)
label_annotator = sv.LabelAnnotator(text_scale=0.5, color_lookup=sv.ColorLookup.TRACK)

# labels list MUST match len(detections) exactly
annotated = box_annotator.annotate(scene=frame.copy(), detections=detections)
annotated = label_annotator.annotate(scene=annotated, detections=detections, labels=labels)
```

## 2. FastAPI Backend Patterns

### MJPEG Streaming

```python
from fastapi.responses import StreamingResponse

async def mjpeg_generator(frame_queue):
    while True:
        try:
            frame_bytes = frame_queue.get_nowait()
        except Exception:
            await anyio.sleep(0.01)  # MUST have await for cancellation
            continue
        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")

@app.get("/api/stream")
async def video_feed():
    return StreamingResponse(mjpeg_generator(q), media_type="multipart/x-mixed-replace; boundary=frame")
```

**Key**: Every async generator MUST contain an `await` point — without it, client disconnect cannot be processed.

### SSE (Native FastAPI)

FastAPI >= 0.135.0 has built-in `EventSourceResponse` — no need for `sse-starlette`. Auto-handles keep-alive pings, `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

```python
from fastapi.sse import EventSourceResponse, ServerSentEvent

@app.get("/api/events", response_class=EventSourceResponse)
async def stream_stats() -> AsyncIterable[ServerSentEvent]:
    while True:
        stats = get_latest_stats()
        yield ServerSentEvent(data=stats, event="stats_update")
        await anyio.sleep(1.0)
```

### Multiprocessing with Lifespan

**Use `mp.get_context("spawn")`, not fork.** Fork inherits uvicorn signal handlers → child exit kills parent.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = mp.get_context("spawn")
    frame_queue = ctx.Queue(maxsize=2)
    cmd_queue = ctx.Queue(maxsize=10)
    stop_event = ctx.Event()

    worker = ctx.Process(target=cv_worker, args=(...), daemon=True)
    worker.start()
    app.state.frame_queue = frame_queue
    yield
    stop_event.set()
    worker.join(timeout=5)
    if worker.is_alive():
        worker.terminate()
    # Drain queues before close to prevent BrokenPipeError
    for q in (frame_queue, cmd_queue):
        while not q.empty():
            try: q.get_nowait()
            except: break
        q.close(); q.join_thread()
```

### Bounded Queue Drop-Oldest

```python
import queue
def put_drop_oldest(q, item):
    try:
        q.put_nowait(item)
    except queue.Full:
        try: q.get_nowait()
        except queue.Empty: pass
        try: q.put_nowait(item)
        except queue.Full: pass  # race condition safe
```

## 3. Docker Setup

### CRITICAL: Use Python 3.11, not 3.12

InsightFace has build failures on Python 3.12+ (Cython/ONNX wheel compilation). Ultralytics' own Dockerfile uses `python:3.11.10-slim-bookworm`. **This overrides the PRD's Python 3.12 spec.**

### Backend Dockerfile Pattern

- **Multi-stage build**: builder stage for C extensions (insightface needs gcc), runtime stage slim
- **Use `opencv-python-headless`**, not `opencv-python` — avoids libGL/X11 deps
- **Pin `numpy<2.0`** — InsightFace incompatible with NumPy 2.x
- **System deps needed**: `libglib2.0-0 libgl1 libsm6 libxext6 libxrender1 ffmpeg`
- **Pre-download models in Docker layer**:
  - YOLO: `ADD https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt`
  - InsightFace: `wget https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip`
- Place model downloads AFTER pip install, BEFORE `COPY . .` for layer caching

### Frontend Dockerfile Pattern

- Multi-stage: `node:22-slim` build → `nginx:stable-alpine` serve (~25MB final image)
- nginx.conf with SPA fallback (`try_files $uri $uri/ /index.html`)
- **Proxy `/api/` to backend** via nginx — solves the VITE_API_URL problem entirely
- Static asset caching: `expires 1y` for js/css/images

### YOLO26n Note

YOLO26n `.pt` URL not yet confirmed on GitHub releases. If unavailable at build time, fall back to `yolo11n.pt` which is at `https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt`. Can try YOLO26n at runtime via ultralytics auto-download.

### Multiprocessing in Docker

Use `spawn` — same as bare metal. `fork` can deadlock when ONNX Runtime has threads.

## 4. Reference Implementations

No directly matching open-source project found that combines all components (YOLO + ByteTrack + InsightFace + FastAPI MJPEG + React dashboard). However, the individual patterns are well-documented:

- **Ultralytics tracking**: Official docs + multiple tutorials
- **FastAPI MJPEG**: GitHub discussions #9803 (YOLOv8 streaming pattern)
- **InsightFace face analysis**: Official GitHub examples + DeepWiki docs
- **Supervision annotation**: Official Roboflow guides

## 5. E2E Readiness

**E2E infra does not exist** — greenfield project.

**E2E approach for PoC:**
- **Backend API**: `curl` / `httpx` tests against running backend container
- **Frontend**: Not critical for PoC — manual browser testing acceptable
- **Integration**: Docker Compose health checks + a simple smoke test script that:
  1. Starts docker compose
  2. Checks `/api/health` returns 200
  3. Starts a session via `POST /api/sessions/start`
  4. Verifies MJPEG stream returns frames (check Content-Type header)
  5. Verifies SSE stream returns stats events
  6. Stops session via `POST /api/sessions/stop`
  7. Queries `GET /api/sessions` and verifies the session appears

**Recommendation:** Add a simple `test_smoke.py` using `httpx` as the last implementation task. No browser automation needed for PoC.

## 6. Key Constraints & Corrections to PRD

| PRD Spec | Correction | Reason |
|----------|-----------|--------|
| Python 3.12 | **Python 3.11** | InsightFace build failures on 3.12+ |
| `VITE_API_URL=http://backend:8000` | **nginx proxy `/api/` → backend** | Browser can't resolve Docker DNS |
| YOLO26n as default | **YOLO11n as safe default**, YOLO26n as opt-in | YOLO26n .pt URL not confirmed on releases |
| `sse-starlette` implied | **Native FastAPI SSE** | Built-in since FastAPI 0.135.0 |
| `opencv-python` | **`opencv-python-headless`** | Avoids X11/GUI deps in Docker |
