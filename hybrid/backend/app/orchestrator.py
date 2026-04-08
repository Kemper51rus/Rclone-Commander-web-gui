from __future__ import annotations

from datetime import datetime, timezone
import logging
import queue
import threading
from typing import Any
from zoneinfo import ZoneInfo

from .config import Settings
from .domain import JobCatalog, JobDefinition, RunStepDefinition
from .gotify import GotifyClient
from .runner import CommandRunner
from .storage import Storage


logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        storage: Storage,
        catalog: JobCatalog,
        runner: CommandRunner,
        gotify: GotifyClient,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.catalog = catalog
        self.runner = runner
        self.gotify = gotify

        self._standard_queue: queue.Queue[int | None] = queue.Queue()
        self._heavy_queue: queue.Queue[int | None] = queue.Queue()
        self._stop_event = threading.Event()

        self._standard_worker_thread: threading.Thread | None = None
        self._heavy_worker_thread: threading.Thread | None = None
        self._scheduler_thread: threading.Thread | None = None

    def start(self) -> None:
        if self._standard_worker_thread and self._standard_worker_thread.is_alive():
            return

        self._stop_event.clear()

        self._standard_worker_thread = threading.Thread(
            target=self._worker_loop,
            args=("standard", self._standard_queue),
            name="hybrid-worker-standard",
            daemon=True,
        )
        self._standard_worker_thread.start()

        self._heavy_worker_thread = threading.Thread(
            target=self._worker_loop,
            args=("heavy", self._heavy_queue),
            name="hybrid-worker-heavy",
            daemon=True,
        )
        self._heavy_worker_thread.start()

        if self.settings.enable_scheduler:
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                name="hybrid-scheduler",
                daemon=True,
            )
            self._scheduler_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._standard_queue.put(None)
        self._heavy_queue.put(None)

        if self._standard_worker_thread:
            self._standard_worker_thread.join(timeout=5)
        if self._heavy_worker_thread:
            self._heavy_worker_thread.join(timeout=5)
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)

    def enqueue_run(
        self,
        profile: str,
        trigger_type: str,
        source: str,
        requested_by: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        steps = self.catalog.steps_for_profile(profile)
        if not steps:
            raise ValueError(f"profile '{profile}' has no enabled steps")

        return self._enqueue_steps(
            queue_profile="heavy" if profile == "heavy" else "standard",
            run_profile=profile,
            steps=steps,
            trigger_type=trigger_type,
            source=source,
            requested_by=requested_by,
            metadata=metadata,
        )

    def enqueue_job(
        self,
        job_key: str,
        trigger_type: str,
        source: str,
        requested_by: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        job = self.catalog.get_job(job_key)
        if not job:
            raise ValueError(f"unknown job '{job_key}'")
        if not job.enabled:
            raise ValueError(f"job '{job_key}' is disabled")
        return self._enqueue_steps(
            queue_profile=job.profile,
            run_profile=job.profile,
            steps=[job],
            trigger_type=trigger_type,
            source=source,
            requested_by=requested_by,
            metadata={**(metadata or {}), "job_key": job_key, "scheduled": True},
        )

    def _enqueue_steps(
        self,
        queue_profile: str,
        run_profile: str,
        steps: list[JobDefinition],
        trigger_type: str,
        source: str,
        requested_by: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        if not steps:
            raise ValueError("no steps to enqueue")
        expanded_steps = self._expand_steps(steps)
        if not expanded_steps:
            raise ValueError("no runnable steps to enqueue")

        run_id = self.storage.create_run(
            profile=run_profile,
            trigger_type=trigger_type,
            source=source,
            requested_by=requested_by,
            metadata=metadata or {},
        )
        self.storage.insert_run_steps(run_id, expanded_steps)

        target_queue = self._queue_for_profile(queue_profile)
        target_queue.put(run_id)
        return run_id

    def enqueue_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.storage.append_event("filesystem", payload)

        now = datetime.now(timezone.utc)
        last_ts_raw = self.storage.get_state("event_last_enqueued_at")
        if last_ts_raw:
            try:
                last_ts = datetime.fromisoformat(last_ts_raw)
                elapsed = (now - last_ts).total_seconds()
                if elapsed < self.settings.event_debounce_seconds:
                    return {
                        "accepted": False,
                        "reason": "debounced",
                        "retry_after_seconds": int(self.settings.event_debounce_seconds - elapsed),
                    }
            except ValueError:
                pass

        if self._event_enqueue_blocked():
            return {
                "accepted": False,
                "reason": "standard_run_in_progress",
            }

        run_id = self.enqueue_run(
            profile="standard",
            trigger_type="event",
            source="watcher",
            requested_by="watcher",
            metadata=payload,
        )
        self.storage.set_state("event_last_enqueued_at", now.isoformat())
        return {
            "accepted": True,
            "run_id": run_id,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "standard_queue_size": self._standard_queue.qsize(),
            "heavy_queue_size": self._heavy_queue.qsize(),
            "standard_worker_alive": bool(
                self._standard_worker_thread and self._standard_worker_thread.is_alive()
            ),
            "heavy_worker_alive": bool(
                self._heavy_worker_thread and self._heavy_worker_thread.is_alive()
            ),
            "scheduler_alive": bool(
                self._scheduler_thread and self._scheduler_thread.is_alive()
            ),
            "open_runs_total": self.storage.open_run_count(),
            "open_runs_standard": self.storage.open_run_count("standard"),
            "open_runs_heavy": self.storage.open_run_count("heavy"),
            "last_standard_tick": self.storage.get_state("scheduler_last_standard_tick"),
            "last_heavy_day": self.storage.get_state("scheduler_last_heavy_day"),
            "last_event_enqueued_at": self.storage.get_state("event_last_enqueued_at"),
        }

    def _queue_for_profile(self, profile: str) -> queue.Queue[int | None]:
        if profile == "heavy":
            return self._heavy_queue
        return self._standard_queue

    def _queue_busy(self, profile: str) -> bool:
        if self.storage.open_run_count(profile) > 0:
            return True
        if not self.catalog.queues.allow_parallel_profiles and self.storage.open_run_count() > 0:
            return True
        return False

    def _scheduler_enqueue_blocked(self, profile: str) -> bool:
        if self.catalog.queues.allow_scheduler_queueing:
            return False
        return self._queue_busy(profile)

    def _event_enqueue_blocked(self) -> bool:
        if self.catalog.queues.allow_event_queueing:
            return False
        return self._queue_busy("standard")

    def _worker_loop(self, queue_name: str, run_queue: queue.Queue[int | None]) -> None:
        while not self._stop_event.is_set():
            try:
                item = run_queue.get(timeout=1)
            except queue.Empty:
                continue

            if item is None:
                break

            try:
                self._process_run(item)
            except Exception:
                logger.exception("run %s failed in %s queue", item, queue_name)

    def _process_run(self, run_id: int) -> None:
        run = self.storage.get_run(run_id)
        if not run:
            return

        self.storage.mark_run_running(run_id)
        steps = self.storage.list_run_steps(run_id)
        total_steps = len(steps)
        completed_steps = 0
        error_count = 0
        failed_jobs: list[str] = []

        for step in steps:
            step_id = int(step["id"])
            self.storage.mark_step_running(step_id)

            command = list(step.get("command", []))
            timeout_seconds = int(step.get("timeout_seconds") or self.settings.default_timeout_seconds)
            result = self.runner.run(command=command, timeout_seconds=timeout_seconds)

            self.storage.mark_step_finished(
                step_id=step_id,
                status=result.status,
                duration_seconds=result.duration_seconds,
                exit_code=result.exit_code,
                stdout_tail=result.stdout_tail,
                stderr_tail=result.stderr_tail,
            )
            self._notify_for_step(run=run, step=step, result=result)

            completed_steps += 1
            if result.status != "succeeded":
                error_count += 1
                failed_jobs.append(str(step.get("job_key", "unknown")))
                if not bool(step.get("continue_on_error", 0)):
                    self.storage.skip_pending_steps(
                        run_id=run_id,
                        after_step_order=int(step["step_order"]),
                    )
                    break

        status = "succeeded" if error_count == 0 else "failed"
        summary = f"completed={completed_steps}/{total_steps}; errors={error_count}"
        if failed_jobs:
            summary = f"{summary}; failed_jobs={','.join(failed_jobs)}"
        self.storage.mark_run_finished(
            run_id=run_id,
            status=status,
            summary=summary,
            error_count=error_count,
        )

    def _notify_for_step(self, run: dict[str, Any], step: dict[str, Any], result: Any) -> None:
        if step.get("step_kind") != "job":
            return
        job = self.catalog.get_job(str(step.get("job_key", "")))
        if not job:
            return
        notifications = job.notifications.normalized()
        if result.status == "succeeded" and not notifications.on_success:
            return
        if result.status != "succeeded" and not notifications.on_failure:
            return

        priority = notifications.priority or self.catalog.gotify.default_priority
        title_prefix = notifications.custom_title or job.title or job.description or job.key
        title = f"{title_prefix}: {'OK' if result.status == 'succeeded' else 'FAILED'}"
        message = "\n".join(
            [
                f"job={job.key}",
                f"profile={run.get('profile', job.profile)}",
                f"status={result.status}",
                f"trigger={run.get('trigger_type', 'manual')}",
                f"requested_by={run.get('requested_by', 'dashboard')}",
                f"duration={result.duration_seconds:.2f}s",
                f"exit_code={result.exit_code if result.exit_code is not None else 'n/a'}",
            ]
        )
        if result.stderr_tail:
            message = f"{message}\n\nstderr_tail:\n{result.stderr_tail[-1200:]}"
        self.gotify.send(
            self.catalog.gotify,
            title=title,
            message=message,
            priority=priority,
        )

    def _expand_steps(self, jobs: list[JobDefinition]) -> list[RunStepDefinition]:
        expanded: list[RunStepDefinition] = []
        for job in jobs:
            expanded.append(
                RunStepDefinition(
                    job_key=job.key,
                    step_kind="job",
                    description=job.description,
                    command=list(job.command),
                    timeout_seconds=job.timeout_seconds,
                    continue_on_error=job.continue_on_error,
                )
            )
            retention = job.retention.normalized()
            if (
                job.kind == "backup"
                and retention.enabled
                and job.destination_path
            ):
                expanded.append(
                    RunStepDefinition(
                        job_key=job.key,
                        step_kind="retention",
                        description=f"{job.description} / retention",
                        command=JobDefinition.build_retention_command(
                            destination_path=job.destination_path,
                            retention=retention,
                        ),
                        timeout_seconds=job.timeout_seconds,
                        continue_on_error=False,
                    )
                )
        return expanded

    def _scheduler_loop(self) -> None:
        timezone = ZoneInfo(self.settings.timezone)
        while not self._stop_event.is_set():
            now_local = datetime.now(timezone)
            try:
                self._maybe_schedule_jobs(now_local)
            except Exception:
                logger.exception("scheduler tick failed")
            self._stop_event.wait(5)

    def _maybe_schedule_jobs(self, now_local: datetime) -> None:
        jobs = self.catalog.raw_jobs()
        for job in jobs:
            schedule_slot = job.schedule.due_slot(now_local)
            if schedule_slot is None:
                continue

            state_key = f"job_schedule_last_slot:{job.key}"
            if self.storage.get_state(state_key) == schedule_slot:
                continue

            if self._scheduler_enqueue_blocked(job.profile):
                continue

            run_id = self.enqueue_job(
                job_key=job.key,
                trigger_type="schedule",
                source="scheduler",
                requested_by="scheduler",
                metadata={"slot": schedule_slot, "schedule_mode": job.schedule.mode},
            )
            self.storage.set_state(state_key, schedule_slot)
            if job.profile == "standard":
                self.storage.set_state("scheduler_last_standard_tick", schedule_slot)
            if job.profile == "heavy":
                self.storage.set_state("scheduler_last_heavy_day", schedule_slot)
            logger.info("scheduled job %s: %s", job.key, run_id)
