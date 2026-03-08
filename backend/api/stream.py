import anyio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()


async def mjpeg_generator(hub):
    """Yield latest MJPEG frames from StreamHub. Multi-client safe."""
    while True:
        frame_bytes = await hub.wait_frame()
        if frame_bytes is None:
            await anyio.sleep(0.1)
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
