import asyncio
import os

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import get_settings
from cv.channels import scan_videos_dir
from cv.face_matcher import FaceMatcher
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

    # NOTE: PoC dual-writer — API process writes session/channel rows,
    # CV worker writes track/snapshot rows. Both use SQLite WAL mode with
    # busy_timeout=5000 to handle write contention safely.
    queries.upsert_channel(db, channel["id"], channel["filename"], channel["label"])
    session_id = queries.create_session(db, req.channel_id)

    # Non-blocking put to avoid stalling the event loop
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, cmd_queue.put, {"type": "start", "channel": channel, "session_id": session_id}
    )

    return {"session_id": session_id, "status": "started"}


@router.post("/sessions/stop")
async def stop_session(req: StopSessionRequest, request: Request):
    db = request.app.state.db
    cmd_queue = request.app.state.cmd_queue

    session = queries.get_session(db, req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    queries.stop_session(db, req.session_id)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, cmd_queue.put, {"type": "stop"})

    return {"session_id": req.session_id, "status": "stopped"}


@router.post("/reset")
async def reset_system(request: Request):
    """Stop any active session and reset the CV worker to idle."""
    db = request.app.state.db
    cmd_queue = request.app.state.cmd_queue

    # Stop all active sessions in DB
    active = queries.list_active_sessions(db)
    for s in active:
        queries.stop_session(db, s["id"])

    # Tell CV worker to stop processing
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, cmd_queue.put, {"type": "stop"})

    return {"status": "reset", "stopped_sessions": len(active)}


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


# ---------------------------------------------------------------------------
# Target person search
# ---------------------------------------------------------------------------

# Lazy-loaded FaceMatcher (API process — used only for upload embedding extraction)
_face_matcher: FaceMatcher | None = None


def _get_face_matcher() -> FaceMatcher:
    global _face_matcher
    if _face_matcher is None:
        settings = get_settings()
        _face_matcher = FaceMatcher(model_name=settings.face_model_name)
    return _face_matcher


def _target_dir() -> str:
    settings = get_settings()
    return os.path.join(os.path.dirname(settings.database_path), "target")


class ThresholdRequest(BaseModel):
    threshold: float


@router.post("/target/upload")
async def upload_target(
    request: Request,
    file: UploadFile = File(...),
    threshold: float = Form(0.5),
):
    """Upload a target photo. Extracts face embedding and notifies the worker."""
    contents = await file.read()
    arr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    matcher = _get_face_matcher()
    embedding = matcher.extract_embedding(image)
    if embedding is None:
        raise HTTPException(status_code=400, detail="No face detected in uploaded photo")

    # Save photo thumbnail for frontend
    target_dir = _target_dir()
    thumb_path = os.path.join(target_dir, "target.jpg")
    cv2.imwrite(thumb_path, image)

    # Send embedding to worker via cmd_queue (embedding is ~2KB as list)
    cmd_queue = request.app.state.cmd_queue
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, cmd_queue.put, {
        "type": "set_target",
        "embedding": embedding.tolist(),
        "threshold": threshold,
    })

    request.app.state.target_active = True
    request.app.state.target_threshold = threshold

    return {"status": "active", "threshold": threshold, "has_face": True}


@router.get("/target")
async def get_target(request: Request):
    """Get current target search status."""
    active = getattr(request.app.state, "target_active", False)
    threshold = getattr(request.app.state, "target_threshold", 0.5)
    thumb_path = os.path.join(_target_dir(), "target.jpg")
    has_thumbnail = os.path.exists(thumb_path)
    return {
        "active": active,
        "threshold": threshold,
        "thumbnail_url": "/api/target/thumbnail" if has_thumbnail else None,
    }


@router.post("/target/clear")
async def clear_target(request: Request):
    """Clear the target and stop searching."""
    cmd_queue = request.app.state.cmd_queue
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, cmd_queue.put, {"type": "clear_target"})

    request.app.state.target_active = False

    # Delete stored photo
    thumb_path = os.path.join(_target_dir(), "target.jpg")
    if os.path.exists(thumb_path):
        os.remove(thumb_path)

    return {"status": "cleared"}


@router.post("/target/resume")
async def resume_after_match(request: Request):
    """Resume monitoring after a match pause."""
    cmd_queue = request.app.state.cmd_queue
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, cmd_queue.put, {"type": "resume"})
    return {"status": "resumed"}


@router.post("/target/threshold")
async def update_threshold(req: ThresholdRequest, request: Request):
    """Update match threshold live."""
    cmd_queue = request.app.state.cmd_queue
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, cmd_queue.put, {
        "type": "update_threshold",
        "threshold": req.threshold,
    })

    request.app.state.target_threshold = req.threshold

    return {"status": "updated", "threshold": req.threshold}


@router.get("/target/thumbnail")
async def get_target_thumbnail():
    """Serve the stored target photo."""
    thumb_path = os.path.join(_target_dir(), "target.jpg")
    if not os.path.exists(thumb_path):
        raise HTTPException(status_code=404, detail="No target photo")
    return FileResponse(thumb_path, media_type="image/jpeg")
