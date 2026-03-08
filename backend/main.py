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


app = FastAPI(title="CrowdLens", lifespan=lifespan)

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
