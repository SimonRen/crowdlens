import asyncio
from collections.abc import AsyncIterable

import anyio
from fastapi import APIRouter, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

router = APIRouter()


@router.get("/api/events", response_class=EventSourceResponse)
async def stats_stream(request: Request) -> AsyncIterable[ServerSentEvent]:
    hub = request.app.state.hub

    async def stats_generator():
        while True:
            stats = await hub.wait_stats()
            if stats is not None:
                yield stats

    async def match_generator():
        while True:
            match = await hub.wait_match()
            if match is not None:
                yield match

    # Merge stats and match streams into a single SSE connection
    stats_iter = stats_generator().__aiter__()
    match_iter = match_generator().__aiter__()

    while True:
        # Use gather to poll both concurrently; whichever yields first wins
        stats_task = asyncio.ensure_future(stats_iter.__anext__())
        match_task = asyncio.ensure_future(match_iter.__anext__())

        done, pending = await asyncio.wait(
            {stats_task, match_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        for task in done:
            result = task.result()
            if "type" in result and result["type"] == "match":
                yield ServerSentEvent(data=result, event="match")
            else:
                yield ServerSentEvent(data=result, event="stats")
