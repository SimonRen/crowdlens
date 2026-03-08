from collections.abc import AsyncIterable

import anyio
from fastapi import APIRouter, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

router = APIRouter()


@router.get("/api/events", response_class=EventSourceResponse)
async def stats_stream(request: Request) -> AsyncIterable[ServerSentEvent]:
    hub = request.app.state.hub
    while True:
        stats = await hub.wait_stats()
        if stats is None:
            # Send keepalive comment to prevent proxy timeout
            yield ServerSentEvent(comment="keepalive")
            continue
        # Pass dict directly — ServerSentEvent handles JSON serialization
        yield ServerSentEvent(data=stats, event="stats")
