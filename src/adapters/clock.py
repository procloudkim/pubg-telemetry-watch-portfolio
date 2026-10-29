"""Wall time and monotonic durations have separate meanings."""

from datetime import datetime, timezone
import time


class SystemClock:
    def now(self, *, timespec="microseconds"):
        return datetime.now(timezone.utc).isoformat(timespec=timespec)

    def perf_counter(self):
        return time.perf_counter()

    def monotonic(self):
        return time.monotonic()

    def sleep(self, seconds):
        time.sleep(seconds)
