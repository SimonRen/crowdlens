import queue
import threading
from collections import deque

import anyio


class StreamHub:
    """Consumes from multiprocessing.Queue and caches latest frame/stats.
    Multiple HTTP clients poll the latest data via version counters (fan-out).

    Match events use a dedicated queue with a deque buffer to avoid being
    overwritten by the latest-value sampling pattern used for stats.
    """

    def __init__(self, frame_queue, stats_queue, match_queue=None):
        self._frame_queue = frame_queue
        self._stats_queue = stats_queue
        self._match_queue = match_queue
        self.latest_frame: bytes | None = None
        self.latest_stats: dict | None = None
        self._match_buffer: deque[dict] = deque(maxlen=16)
        self._frame_version = 0
        self._stats_version = 0
        self._match_version = 0
        self._match_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._drain_loop, daemon=True)
        self._thread.start()

    def _drain_loop(self):
        """Background thread: drain queues, update latest values."""
        while not self._stop.is_set():
            got_something = False
            try:
                self.latest_frame = self._frame_queue.get_nowait()
                self._frame_version += 1
                got_something = True
            except queue.Empty:
                pass
            try:
                self.latest_stats = self._stats_queue.get_nowait()
                self._stats_version += 1
                got_something = True
            except queue.Empty:
                pass
            if self._match_queue is not None:
                try:
                    match = self._match_queue.get_nowait()
                    with self._match_lock:
                        self._match_buffer.append(match)
                    self._match_version += 1
                    got_something = True
                except queue.Empty:
                    pass
            if not got_something:
                self._stop.wait(timeout=0.01)

    async def wait_frame(self) -> bytes | None:
        """Wait for a new frame via version polling. Returns None if timeout."""
        version = self._frame_version
        deadline = 5.0  # max wait seconds
        waited = 0.0
        while self._frame_version == version:
            if self._stop.is_set() or waited >= deadline:
                return self.latest_frame  # may be None if no frames yet
            await anyio.sleep(0.02)
            waited += 0.02
        return self.latest_frame

    async def wait_stats(self) -> dict | None:
        """Wait for new stats via version polling. Returns None if timeout."""
        version = self._stats_version
        deadline = 5.0
        waited = 0.0
        while self._stats_version == version:
            if self._stop.is_set() or waited >= deadline:
                return self.latest_stats
            await anyio.sleep(0.05)
            waited += 0.05
        return self.latest_stats

    async def wait_match(self) -> dict | None:
        """Wait for a new match event. Returns None if timeout (no match).

        Uses a deque buffer so match events are never lost, even with
        multiple SSE clients or rapid arrivals.
        """
        # Drain any buffered events first — they may have arrived while
        # we were blocked in wait_stats() on the previous loop iteration.
        with self._match_lock:
            if self._match_buffer:
                return self._match_buffer.popleft()

        version = self._match_version
        deadline = 1.0  # short poll — match events are rare
        waited = 0.0
        while self._match_version == version:
            if self._stop.is_set() or waited >= deadline:
                return None  # no match — return None, not stale data
            await anyio.sleep(0.05)
            waited += 0.05
        with self._match_lock:
            if self._match_buffer:
                return self._match_buffer.popleft()
        return None

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
