from collections.abc import AsyncIterable

from fastapi import APIRouter, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

router = APIRouter()


@router.get("/api/events", response_class=EventSourceResponse)
async def stats_stream(request: Request) -> AsyncIterable[ServerSentEvent]:
    hub = request.app.state.hub
    while True:
        # Check for match events first (rare but critical — must not be lost)
        match = await hub.wait_match()
        if match is not None:
            yield ServerSentEvent(data=match, event="match")
            continue

        # Then check for stats (frequent)
        stats = await hub.wait_stats()
        if stats is not None:
            yield ServerSentEvent(data=stats, event="stats")
            continue

        # Neither produced data — send keepalive to prevent proxy timeout
        yield ServerSentEvent(comment="keepalive")
