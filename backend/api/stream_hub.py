import asyncio
import queue
import threading

import anyio


class StreamHub:
    """Consumes from multiprocessing.Queue and caches latest frame/stats.
    Multiple HTTP clients read copies of the latest data (fan-out).
    Runs a background thread to drain the mp.Queue.

    Thread-safety: uses loop.call_soon_threadsafe + asyncio.Condition
    so that the drain thread can safely notify async waiters.
    """

    def __init__(self, frame_queue, stats_queue):
        self._frame_queue = frame_queue
        self._stats_queue = stats_queue
        self.latest_frame: bytes | None = None
        self.latest_stats: dict | None = None
        self._frame_version = 0
        self._stats_version = 0
        self._frame_cond = asyncio.Condition()
        self._stats_cond = asyncio.Condition()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._drain_loop, daemon=True)
        self._thread.start()

    def bind_loop(self, loop: asyncio.AbstractEventLoop):
        """Bind to the running event loop. Must be called from the async context."""
        self._loop = loop

    def _notify_frame(self):
        """Called via call_soon_threadsafe to notify all frame waiters."""
        asyncio.ensure_future(self._do_notify_frame())

    async def _do_notify_frame(self):
        async with self._frame_cond:
            self._frame_cond.notify_all()

    def _notify_stats(self):
        """Called via call_soon_threadsafe to notify all stats waiters."""
        asyncio.ensure_future(self._do_notify_stats())

    async def _do_notify_stats(self):
        async with self._stats_cond:
            self._stats_cond.notify_all()

    def _drain_loop(self):
        """Background thread: drain queues, update latest values."""
        while not self._stop.is_set():
            got_something = False
            try:
                self.latest_frame = self._frame_queue.get_nowait()
                self._frame_version += 1
                got_something = True
                if self._loop is not None:
                    self._loop.call_soon_threadsafe(self._notify_frame)
            except queue.Empty:
                pass
            try:
                self.latest_stats = self._stats_queue.get_nowait()
                self._stats_version += 1
                got_something = True
                if self._loop is not None:
                    self._loop.call_soon_threadsafe(self._notify_stats)
            except queue.Empty:
                pass
            if not got_something:
                self._stop.wait(timeout=0.01)

    async def wait_frame(self) -> bytes:
        """Wait for a new frame. Multiple concurrent callers each get notified."""
        version = self._frame_version
        while self.latest_frame is None:
            await anyio.sleep(0.01)
        async with self._frame_cond:
            # Wait until a new frame arrives (version changes)
            while self._frame_version == version:
                try:
                    await asyncio.wait_for(self._frame_cond.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    break
        return self.latest_frame

    async def wait_stats(self) -> dict:
        """Wait for new stats. Multiple concurrent callers each get notified."""
        version = self._stats_version
        while self.latest_stats is None:
            await anyio.sleep(0.1)
        async with self._stats_cond:
            while self._stats_version == version:
                try:
                    await asyncio.wait_for(self._stats_cond.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    break
        return self.latest_stats

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
