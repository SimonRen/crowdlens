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
