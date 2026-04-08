from __future__ import annotations

from dataclasses import dataclass
import subprocess
import time


@dataclass(frozen=True)
class CommandResult:
    status: str
    exit_code: int | None
    stdout_tail: str
    stderr_tail: str
    duration_seconds: float


class CommandRunner:
    def __init__(self, dry_run: bool = False, output_tail_chars: int = 8000) -> None:
        self.dry_run = dry_run
        self.output_tail_chars = max(512, output_tail_chars)

    def run(self, command: list[str], timeout_seconds: int) -> CommandResult:
        started = time.perf_counter()

        if self.dry_run:
            duration = time.perf_counter() - started
            return CommandResult(
                status="succeeded",
                exit_code=0,
                stdout_tail=f"dry-run: {' '.join(command)}",
                stderr_tail="",
                duration_seconds=duration,
            )

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
            duration = time.perf_counter() - started
            status = "succeeded" if completed.returncode == 0 else "failed"
            return CommandResult(
                status=status,
                exit_code=completed.returncode,
                stdout_tail=self._tail(completed.stdout or ""),
                stderr_tail=self._tail(completed.stderr or ""),
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.perf_counter() - started
            stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            stderr_msg = f"command timed out after {timeout_seconds}s"
            if stderr:
                stderr_msg = f"{stderr_msg}\n{stderr}"
            return CommandResult(
                status="failed",
                exit_code=None,
                stdout_tail=self._tail(stdout),
                stderr_tail=self._tail(stderr_msg),
                duration_seconds=duration,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            duration = time.perf_counter() - started
            return CommandResult(
                status="failed",
                exit_code=None,
                stdout_tail="",
                stderr_tail=self._tail(f"runner exception: {exc}"),
                duration_seconds=duration,
            )

    def _tail(self, value: str) -> str:
        if len(value) <= self.output_tail_chars:
            return value
        return value[-self.output_tail_chars :]
