import queue
import threading

import anyio


class StreamHub:
    """Consumes from multiprocessing.Queue and caches latest frame/stats.
    Multiple HTTP clients poll the latest data via version counters (fan-out).
    """

    def __init__(self, frame_queue, stats_queue):
        self._frame_queue = frame_queue
        self._stats_queue = stats_queue
        self.latest_frame: bytes | None = None
        self.latest_stats: dict | None = None
        self._frame_version = 0
        self._stats_version = 0
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

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
