from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_root: Path
    db_path: Path
    jobs_file: Path
    rclone_config_file: Path
    timezone: str
    enable_scheduler: bool
    standard_interval_minutes: int
    heavy_hour: int
    event_debounce_seconds: int
    default_timeout_seconds: int
    output_tail_chars: int
    dry_run: bool
    api_token: str | None


def load_settings() -> Settings:
    app_root_raw = os.getenv("APP_ROOT")
    if app_root_raw:
        app_root = Path(app_root_raw).expanduser().resolve()
    else:
        app_root = Path(__file__).resolve().parents[1]

    db_path = Path(os.getenv("HYBRID_DB_PATH", app_root / "data" / "hybrid.db")).expanduser()
    jobs_file = Path(
        os.getenv("HYBRID_JOBS_FILE", app_root / "app" / "jobs" / "default_jobs.json")
    ).expanduser()
    rclone_config_file = Path(
        os.getenv("HYBRID_RCLONE_CONFIG", Path.home() / ".config" / "rclone" / "rclone.conf")
    ).expanduser()

    standard_interval = max(1, _read_int("HYBRID_STANDARD_INTERVAL_MINUTES", 1))
    heavy_hour = _read_int("HYBRID_HEAVY_HOUR", 3)
    if heavy_hour < 0:
        heavy_hour = 0
    if heavy_hour > 23:
        heavy_hour = 23

    return Settings(
        app_name=os.getenv("HYBRID_APP_NAME", "rclone-hybrid"),
        app_root=app_root,
        db_path=db_path.resolve(),
        jobs_file=jobs_file.resolve(),
        rclone_config_file=rclone_config_file.resolve(),
        timezone=os.getenv("APP_TIMEZONE", "Europe/Moscow"),
        enable_scheduler=_read_bool("HYBRID_ENABLE_SCHEDULER", True),
        standard_interval_minutes=standard_interval,
        heavy_hour=heavy_hour,
        event_debounce_seconds=max(1, _read_int("HYBRID_EVENT_DEBOUNCE_SECONDS", 45)),
        default_timeout_seconds=max(1, _read_int("HYBRID_DEFAULT_TIMEOUT_SECONDS", 3600)),
        output_tail_chars=max(512, _read_int("HYBRID_OUTPUT_TAIL_CHARS", 8000)),
        dry_run=_read_bool("HYBRID_DRY_RUN", False),
        api_token=os.getenv("HYBRID_API_TOKEN"),
    )
