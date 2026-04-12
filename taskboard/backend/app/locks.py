from __future__ import annotations

from contextlib import contextmanager
import fcntl
from pathlib import Path
import time
from typing import Callable, Iterator


@contextmanager
def file_lock(
    path: Path,
    *,
    poll_interval_seconds: float = 0.5,
    should_abort: Callable[[], bool] | None = None,
) -> Iterator[Path]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if should_abort and should_abort():
                    raise InterruptedError(f"lock wait aborted for {path.name}")
                time.sleep(max(0.1, poll_interval_seconds))
        try:
            yield path
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
