import asyncio

from fastapi import APIRouter, HTTPException, Request
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
