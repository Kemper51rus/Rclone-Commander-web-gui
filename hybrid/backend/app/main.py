from __future__ import annotations

import configparser
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import threading
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .config import Settings, load_settings
from .domain import (
    BackupOptions,
    CloudSettings,
    GotifySettings,
    JobCatalog,
    JobDefinition,
    JobNotificationSettings,
    QueueSettings,
    RetentionSettings,
    ScheduleDefinition,
)
from .gotify import GotifyClient
from .jobs_loader import build_profiles, load_catalog, save_catalog
from .orchestrator import Orchestrator
from .runner import CommandRunner
from .storage import Storage


settings: Settings = load_settings()
catalog = load_catalog(
    settings.jobs_file,
    standard_interval_minutes=settings.standard_interval_minutes,
    heavy_hour=settings.heavy_hour,
)
catalog_lock = threading.RLock()
storage = Storage(settings.db_path)
runner = CommandRunner(
    dry_run=settings.dry_run,
    output_tail_chars=settings.output_tail_chars,
)
gotify = GotifyClient()
orchestrator = Orchestrator(
    settings=settings,
    storage=storage,
    catalog=catalog,
    runner=runner,
    gotify=gotify,
)
DASHBOARD_HTML = Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")
FS_ROOTS = ["/media", "/srv", "/home", "/root", "/mnt", "/tmp"]


@asynccontextmanager
async def lifespan(_: FastAPI):
    storage.initialize()
    orchestrator.start()
    try:
        yield
    finally:
        orchestrator.stop()


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    lifespan=lifespan,
)


def _get_bearer_token(header_value: str | None) -> str | None:
    if not header_value:
        return None
    parts = header_value.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


def require_write_access(request: Request) -> None:
    return


class RunCreateRequest(BaseModel):
    profile: str = Field(default="standard")
    source: str = Field(default="api")
    requested_by: str = Field(default="api")
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventTriggerRequest(BaseModel):
    event_type: str = Field(default="filesystem")
    path: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class SchedulePayload(BaseModel):
    enabled: bool = False
    mode: str = "manual"
    interval_minutes: int = 60
    hour: int = 3
    minute: int = 0
    weekdays: list[int] = Field(default_factory=list)


class BackupOptionsPayload(BaseModel):
    max_age: str | None = None
    min_age: str | None = None
    exclude: list[str] = Field(default_factory=list)
    extra_args: list[str] = Field(default_factory=list)


class JobNotificationPayload(BaseModel):
    on_success: bool = False
    on_failure: bool = True
    priority: int | None = None
    custom_title: str | None = None


class RetentionPayload(BaseModel):
    enabled: bool = False
    min_age: str | None = None
    exclude: list[str] = Field(default_factory=list)
    extra_args: list[str] = Field(default_factory=list)


class BackupJobPayload(BaseModel):
    key: str
    description: str | None = None
    title: str | None = None
    profile: str = "standard"
    enabled: bool = True
    timeout_seconds: int = 1800
    continue_on_error: bool = True
    source_path: str
    cloud_key: str | None = None
    destination_subpath: str | None = None
    destination_path: str
    transfer_mode: str = "copy"
    schedule: SchedulePayload = Field(default_factory=SchedulePayload)
    options: BackupOptionsPayload = Field(default_factory=BackupOptionsPayload)
    retention: RetentionPayload = Field(default_factory=RetentionPayload)
    notifications: JobNotificationPayload = Field(default_factory=JobNotificationPayload)
    order: int = 10


class JobPayload(BaseModel):
    key: str
    description: str | None = None
    title: str | None = None
    kind: str = "backup"
    profile: str = "standard"
    enabled: bool = True
    timeout_seconds: int = 1800
    continue_on_error: bool = True
    source_path: str | None = None
    cloud_key: str | None = None
    destination_subpath: str | None = None
    destination_path: str | None = None
    transfer_mode: str = "copy"
    command: list[str] = Field(default_factory=list)
    schedule: SchedulePayload = Field(default_factory=SchedulePayload)
    options: BackupOptionsPayload = Field(default_factory=BackupOptionsPayload)
    retention: RetentionPayload = Field(default_factory=RetentionPayload)
    notifications: JobNotificationPayload = Field(default_factory=JobNotificationPayload)
    order: int = 10


class JobCatalogPayload(BaseModel):
    jobs: list[JobPayload] = Field(default_factory=list)


class BackupCatalogPayload(BaseModel):
    jobs: list[BackupJobPayload] = Field(default_factory=list)


class GotifyPayload(BaseModel):
    enabled: bool = False
    url: str | None = None
    token: str | None = None
    default_priority: int = 5


class QueueSettingsPayload(BaseModel):
    allow_parallel_profiles: bool = False
    allow_scheduler_queueing: bool = False
    allow_event_queueing: bool = False


class CloudPayload(BaseModel):
    key: str
    title: str
    provider: str = "generic"
    remote_name: str | None = None
    username: str | None = None
    token: str | None = None
    endpoint: str | None = None
    root_path: str | None = None
    notes: str | None = None
    extra_config: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class CloudCatalogPayload(BaseModel):
    clouds: list[CloudPayload] = Field(default_factory=list)


class CloudTestPayload(BaseModel):
    provider: str = "generic"
    remote_name: str | None = None
    username: str | None = None
    token: str | None = None
    endpoint: str | None = None
    root_path: str | None = None


def _slug_cloud_key(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "cloud"


def _import_clouds_from_rclone_config(
    config_path: Path,
    existing_clouds: list[CloudSettings],
) -> list[CloudSettings]:
    if not config_path.exists():
        raise FileNotFoundError(f"rclone config not found: {config_path}")

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(config_path, encoding="utf-8")

    clouds_by_key = {cloud.key: cloud for cloud in existing_clouds}
    key_by_remote = {
        cloud.remote_name: cloud.key
        for cloud in existing_clouds
        if cloud.remote_name
    }
    known_option_names = {
        "type",
        "vendor",
        "user",
        "username",
        "login",
        "email",
        "token",
        "access_token",
        "bearer_token",
        "password",
        "pass",
        "endpoint",
        "url",
        "server",
        "hostname",
        "root_path",
        "root_folder",
        "root_folder_id",
        "directory",
    }

    for section in parser.sections():
        remote_name = section.strip()
        if not remote_name:
            continue
        values = parser[section]
        provider = (
            values.get("vendor")
            or values.get("type")
            or "generic"
        ).strip().lower()
        username = (
            values.get("user")
            or values.get("username")
            or values.get("login")
            or values.get("email")
        )
        token = (
            values.get("token")
            or values.get("access_token")
            or values.get("bearer_token")
            or values.get("password")
            or values.get("pass")
        )
        endpoint = (
            values.get("endpoint")
            or values.get("url")
            or values.get("server")
            or values.get("hostname")
        )
        root_path = (
            values.get("root_path")
            or values.get("root_folder")
            or values.get("root_folder_id")
            or values.get("directory")
        )
        extra_config = {
            option_key: option_value
            for option_key, option_value in values.items()
            if option_key not in known_option_names and str(option_value).strip()
        }
        existing_key = key_by_remote.get(remote_name)
        existing = clouds_by_key.get(existing_key) if existing_key else None
        key = existing.key if existing else _slug_cloud_key(remote_name)
        while key in clouds_by_key and clouds_by_key[key].remote_name != remote_name:
            key = _slug_cloud_key(f"{remote_name}_{len(clouds_by_key) + 1}")
        title = existing.title if existing and existing.title else remote_name
        notes = existing.notes if existing and existing.notes else f"Imported from {config_path.name}"
        clouds_by_key[key] = CloudSettings(
            key=key,
            title=title,
            provider=provider,
            remote_name=remote_name,
            username=(username if username not in (None, "") else (existing.username if existing else None)),
            token=(token if token not in (None, "") else (existing.token if existing else None)),
            endpoint=(endpoint if endpoint not in (None, "") else (existing.endpoint if existing else None)),
            root_path=(root_path if root_path not in (None, "") else (existing.root_path if existing else None)),
            notes=notes,
            extra_config=(extra_config or (existing.extra_config if existing else {})),
            enabled=existing.enabled if existing else True,
        ).normalized()
        key_by_remote[remote_name] = key

    return sorted(clouds_by_key.values(), key=lambda cloud: (cloud.title, cloud.key))


def _import_single_cloud_from_rclone_config(
    config_path: Path,
    remote_name: str,
    existing_clouds: list[CloudSettings],
) -> CloudSettings:
    imported_clouds = _import_clouds_from_rclone_config(config_path, existing_clouds)
    for cloud in imported_clouds:
        if (cloud.remote_name or "").strip() == remote_name.strip():
            return cloud
    raise FileNotFoundError(f"remote not found in rclone config: {remote_name}")


def _compose_cloud_destination(cloud: CloudSettings | None, destination_subpath: str | None) -> str | None:
    if not cloud or not cloud.remote_name:
        return None
    root_path = (cloud.root_path or "").strip().strip("/")
    subpath = (destination_subpath or "").strip().strip("/")
    segments = [segment for segment in [root_path, subpath] if segment]
    if not segments:
        return f"{cloud.remote_name}:"
    return f"{cloud.remote_name}:/{'/'.join(segments)}"


def _cloud_test_target(remote_name: str, root_path: str | None) -> str:
    root = (root_path or "").strip().strip("/")
    if not root:
        return f"{remote_name}:"
    return f"{remote_name}:/{root}"


def _write_temp_rclone_config(cloud: CloudSettings) -> tuple[tempfile.NamedTemporaryFile, str]:
    handle = tempfile.NamedTemporaryFile("w+", suffix=".conf", encoding="utf-8", delete=False)
    remote_name = (cloud.remote_name or "cloudtest").strip() or "cloudtest"
    config_lines = [f"[{remote_name}]", f"type = {cloud.provider or 'generic'}"]
    if cloud.username:
        config_lines.extend([f"user = {cloud.username}", f"username = {cloud.username}"])
    if cloud.token:
        config_lines.extend(
            [
                f"token = {cloud.token}",
                f"access_token = {cloud.token}",
                f"bearer_token = {cloud.token}",
                f"password = {cloud.token}",
            ]
        )
    if cloud.endpoint:
        config_lines.extend([f"endpoint = {cloud.endpoint}", f"url = {cloud.endpoint}"])
    for option_key, option_value in cloud.extra_config.items():
        config_lines.append(f"{option_key} = {option_value}")
    handle.write("\n".join(config_lines) + "\n")
    handle.flush()
    return handle, remote_name


def _build_rclone_section(cloud: CloudSettings) -> dict[str, str]:
    section: dict[str, str] = {"type": cloud.provider or "generic"}
    if cloud.username:
        section["username"] = cloud.username
    if cloud.token:
        section["token"] = cloud.token
    if cloud.endpoint:
        section["endpoint"] = cloud.endpoint
    for option_key, option_value in cloud.extra_config.items():
        if option_key in {"type", "username", "token", "endpoint"}:
            continue
        section[option_key] = option_value
    return section


def _sync_clouds_to_rclone_config(
    config_path: Path,
    previous_clouds: list[CloudSettings],
    clouds: list[CloudSettings],
) -> None:
    parser = configparser.ConfigParser(interpolation=None)
    if config_path.exists():
        parser.read(config_path, encoding="utf-8")

    previous_remote_names = {
        (cloud.remote_name or "").strip()
        for cloud in previous_clouds
        if (cloud.remote_name or "").strip()
    }
    current_remote_names = {
        (cloud.remote_name or "").strip()
        for cloud in clouds
        if (cloud.remote_name or "").strip()
    }

    for removed_remote in sorted(previous_remote_names - current_remote_names):
        if parser.has_section(removed_remote):
            parser.remove_section(removed_remote)

    for cloud in clouds:
        remote_name = (cloud.remote_name or "").strip()
        if not remote_name:
            continue
        if parser.has_section(remote_name):
            parser.remove_section(remote_name)
        parser[remote_name] = _build_rclone_section(cloud)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        parser.write(handle)


def _run_rclone_cloud_test(target: str, config_path: Path | None = None) -> dict[str, Any]:
    command = ["rclone", "lsf", target, "--max-depth", "1"]
    if config_path is not None:
        command.extend(["--config", str(config_path)])
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=25,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("connection test timed out") from exc

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if result.returncode != 0:
        detail = stderr or stdout or f"rclone exited with code {result.returncode}"
        raise RuntimeError(detail)
    return {
        "ok": True,
        "target": target,
        "output_preview": "\n".join(stdout.splitlines()[:10]),
    }


def _rclone_remote_exists(config_path: Path, remote_name: str) -> bool:
    if not config_path.exists():
        return False
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(config_path, encoding="utf-8")
    return parser.has_section(remote_name)


def _test_cloud_connection(payload: CloudTestPayload, config_path: Path) -> dict[str, Any]:
    cloud = CloudSettings(
        key="cloud_test",
        title="cloud_test",
        provider=payload.provider,
        remote_name=payload.remote_name,
        username=payload.username,
        token=payload.token,
        endpoint=payload.endpoint,
        root_path=payload.root_path,
        notes=None,
        enabled=True,
    ).normalized()
    if not cloud.provider:
        raise RuntimeError("provider is required")
    if not cloud.remote_name:
        raise RuntimeError("remote name is required")

    if _rclone_remote_exists(config_path, cloud.remote_name):
        target = _cloud_test_target(cloud.remote_name, cloud.root_path)
        result = _run_rclone_cloud_test(target, config_path=config_path)
        result["used_existing_remote"] = True
        return result

    temp_config, remote_name = _write_temp_rclone_config(cloud)
    try:
        target = _cloud_test_target(remote_name, cloud.root_path)
        result = _run_rclone_cloud_test(target, config_path=Path(temp_config.name))
    finally:
        temp_config.close()
        Path(temp_config.name).unlink(missing_ok=True)

    result["used_existing_remote"] = False
    return result


def _list_rclone_providers() -> list[dict[str, str]]:
    try:
        result = subprocess.run(
            ["rclone", "config", "providers"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("rclone is not installed") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(stderr or "failed to query rclone providers") from exc

    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("rclone returned invalid providers json") from exc

    providers: list[dict[str, str]] = []
    for item in raw:
        name = str(item.get("Name") or "").strip()
        if not name:
            continue
        providers.append(
            {
                "name": name,
                "description": str(item.get("Description") or "").strip(),
                "prefix": str(item.get("Prefix") or name).strip(),
            }
        )
    return sorted(providers, key=lambda item: item["name"])


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD_HTML


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "utc_time": datetime.now(timezone.utc).isoformat(),
        "app": settings.app_name,
    }


@app.get("/api/state")
def state() -> dict[str, Any]:
    snapshot = orchestrator.snapshot()
    snapshot["token_required"] = bool(settings.api_token)
    snapshot["latest_runs"] = storage.list_runs(limit=15)
    snapshot["backup_jobs"] = catalog.list_backup_jobs()
    return snapshot


@app.get("/api/jobs")
def jobs() -> dict[str, Any]:
    return {
        "profiles": catalog.profiles,
        "gotify": catalog.gotify.to_dict(),
        "queues": catalog.queues.to_dict(),
        "clouds": catalog.list_clouds(),
        "jobs": catalog.list_jobs(),
        "backup_jobs": catalog.list_backup_jobs(),
        "command_jobs": catalog.list_command_jobs(),
    }


@app.get("/api/gotify")
def get_gotify_settings() -> dict[str, Any]:
    return {"gotify": catalog.gotify.to_dict()}


@app.get("/api/queues")
def get_queue_settings() -> dict[str, Any]:
    return {"queues": catalog.queues.to_dict()}


@app.get("/api/clouds")
def get_cloud_settings() -> dict[str, Any]:
    return {"clouds": catalog.list_clouds()}


@app.get("/api/rclone/providers")
def get_rclone_providers() -> dict[str, Any]:
    try:
        providers = _list_rclone_providers()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"providers": providers}


@app.put("/api/gotify", dependencies=[Depends(require_write_access)])
def update_gotify_settings(payload: GotifyPayload) -> dict[str, Any]:
    gotify = GotifySettings(**payload.model_dump()).normalized()
    with catalog_lock:
        updated_catalog = JobCatalog(
            jobs=catalog.raw_jobs(),
            profiles=build_profiles(catalog.raw_jobs()),
            gotify=gotify,
            queues=catalog.queues,
            clouds=catalog.raw_clouds(),
        )
        save_catalog(settings.jobs_file, updated_catalog)
        catalog.replace(
            updated_catalog.raw_jobs(),
            updated_catalog.profiles,
            gotify=updated_catalog.gotify,
            queues=updated_catalog.queues,
            clouds=updated_catalog.raw_clouds(),
        )
    return {"saved": True, "gotify": catalog.gotify.to_dict()}


@app.put("/api/queues", dependencies=[Depends(require_write_access)])
def update_queue_settings(payload: QueueSettingsPayload) -> dict[str, Any]:
    queues = QueueSettings(**payload.model_dump()).normalized()
    with catalog_lock:
        updated_catalog = JobCatalog(
            jobs=catalog.raw_jobs(),
            profiles=build_profiles(catalog.raw_jobs()),
            gotify=catalog.gotify,
            queues=queues,
            clouds=catalog.raw_clouds(),
        )
        save_catalog(settings.jobs_file, updated_catalog)
        catalog.replace(
            updated_catalog.raw_jobs(),
            updated_catalog.profiles,
            gotify=updated_catalog.gotify,
            queues=updated_catalog.queues,
            clouds=updated_catalog.raw_clouds(),
        )
    return {"saved": True, "queues": catalog.queues.to_dict()}


@app.put("/api/clouds", dependencies=[Depends(require_write_access)])
def update_cloud_settings(payload: CloudCatalogPayload) -> dict[str, Any]:
    clouds: list[CloudSettings] = []
    seen_keys: set[str] = set()
    for item in payload.clouds:
        key = item.key.strip()
        if not key:
            raise HTTPException(status_code=400, detail="cloud key is required")
        if key in seen_keys:
            raise HTTPException(status_code=400, detail=f"duplicate cloud key '{key}'")
        seen_keys.add(key)
        clouds.append(CloudSettings(**item.model_dump()).normalized())

    with catalog_lock:
        previous_clouds = catalog.raw_clouds()
        try:
            _sync_clouds_to_rclone_config(settings.rclone_config_file, previous_clouds, clouds)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"failed to sync rclone config: {exc}") from exc
        updated_catalog = JobCatalog(
            jobs=catalog.raw_jobs(),
            profiles=build_profiles(catalog.raw_jobs()),
            gotify=catalog.gotify,
            queues=catalog.queues,
            clouds=clouds,
        )
        save_catalog(settings.jobs_file, updated_catalog)
        catalog.replace(
            updated_catalog.raw_jobs(),
            updated_catalog.profiles,
            gotify=updated_catalog.gotify,
            queues=updated_catalog.queues,
            clouds=updated_catalog.raw_clouds(),
        )
    return {"saved": True, "clouds": catalog.list_clouds()}


@app.post("/api/clouds/import-rclone", dependencies=[Depends(require_write_access)])
def import_cloud_settings_from_rclone() -> dict[str, Any]:
    try:
        imported_clouds = _import_clouds_from_rclone_config(
            settings.rclone_config_file,
            catalog.raw_clouds(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to import rclone config: {exc}") from exc

    with catalog_lock:
        updated_catalog = JobCatalog(
            jobs=catalog.raw_jobs(),
            profiles=build_profiles(catalog.raw_jobs()),
            gotify=catalog.gotify,
            queues=catalog.queues,
            clouds=imported_clouds,
        )
        save_catalog(settings.jobs_file, updated_catalog)
        catalog.replace(
            updated_catalog.raw_jobs(),
            updated_catalog.profiles,
            gotify=updated_catalog.gotify,
            queues=updated_catalog.queues,
            clouds=updated_catalog.raw_clouds(),
        )
    return {"saved": True, "clouds": catalog.list_clouds()}


@app.post("/api/clouds/import-rclone-remote", dependencies=[Depends(require_write_access)])
def import_single_cloud_settings_from_rclone(remote_name: str = Query(..., min_length=1)) -> dict[str, Any]:
    try:
        cloud = _import_single_cloud_from_rclone_config(
            settings.rclone_config_file,
            remote_name,
            catalog.raw_clouds(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to import rclone remote: {exc}") from exc
    return {"cloud": cloud.to_dict()}


@app.post("/api/clouds/test", dependencies=[Depends(require_write_access)])
def test_cloud_settings(payload: CloudTestPayload) -> dict[str, Any]:
    try:
        result = _test_cloud_connection(payload, settings.rclone_config_file)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.post("/api/gotify/test", dependencies=[Depends(require_write_access)])
def test_gotify_settings(payload: GotifyPayload) -> dict[str, Any]:
    gotify_settings = GotifySettings(**payload.model_dump()).normalized()
    if not gotify_settings.is_configured():
        raise HTTPException(status_code=400, detail="gotify is not fully configured")
    sent = gotify.send(
        gotify_settings,
        title="Rclone Hybrid Test",
        message=(
            f"Тестовое уведомление из {settings.app_name}\n"
            f"time={datetime.now(timezone.utc).isoformat()}"
        ),
        priority=gotify_settings.default_priority,
    )
    if not sent:
        raise HTTPException(status_code=502, detail="failed to send gotify notification")
    return {"sent": True}


@app.put("/api/backups", dependencies=[Depends(require_write_access)])
def update_backups(payload: BackupCatalogPayload) -> dict[str, Any]:
    backup_jobs: list[JobDefinition] = []
    seen_keys: set[str] = set()

    for item in payload.jobs:
        key = item.key.strip()
        if not key:
            raise HTTPException(status_code=400, detail="backup key is required")
        if key in seen_keys:
            raise HTTPException(status_code=400, detail=f"duplicate backup key '{key}'")
        if item.retention.enabled and not (item.retention.min_age or "").strip():
            raise HTTPException(status_code=400, detail=f"backup '{key}' retention requires min_age")
        seen_keys.add(key)
        cloud = catalog.get_cloud(item.cloud_key) if item.cloud_key else None
        destination_path = _compose_cloud_destination(cloud, item.destination_subpath) or item.destination_path
        backup_jobs.append(
            JobDefinition(
                key=key,
                order=item.order,
                description=item.description or item.title or key,
                title=item.title,
                timeout_seconds=item.timeout_seconds,
                enabled=item.enabled,
                continue_on_error=item.continue_on_error,
                kind="backup",
                profile=item.profile,
                schedule=ScheduleDefinition(**item.schedule.model_dump()),
                source_path=item.source_path,
                cloud_key=item.cloud_key,
                destination_subpath=item.destination_subpath,
                destination_path=destination_path,
                transfer_mode=item.transfer_mode,
                options=BackupOptions(**item.options.model_dump()),
                retention=RetentionSettings(**item.retention.model_dump()),
                notifications=JobNotificationSettings(**item.notifications.model_dump()),
            ).validate()
        )

    with catalog_lock:
        command_jobs = [job for job in catalog.raw_jobs() if job.kind == "command"]
        merged_jobs = sorted(command_jobs + backup_jobs, key=lambda job: (job.order, job.key))
        updated_catalog = JobCatalog(
            jobs=merged_jobs,
            profiles=build_profiles(merged_jobs),
            gotify=catalog.gotify,
            queues=catalog.queues,
            clouds=catalog.raw_clouds(),
        )
        save_catalog(settings.jobs_file, updated_catalog)
        catalog.replace(
            updated_catalog.raw_jobs(),
            updated_catalog.profiles,
            gotify=updated_catalog.gotify,
            queues=updated_catalog.queues,
            clouds=updated_catalog.raw_clouds(),
        )

    return {
        "saved": True,
        "backup_jobs": catalog.list_backup_jobs(),
        "profiles": catalog.profiles,
        "gotify": catalog.gotify.to_dict(),
        "queues": catalog.queues.to_dict(),
        "clouds": catalog.list_clouds(),
    }


@app.put("/api/jobs", dependencies=[Depends(require_write_access)])
def update_jobs(payload: JobCatalogPayload) -> dict[str, Any]:
    jobs_to_save: list[JobDefinition] = []
    seen_keys: set[str] = set()

    for item in payload.jobs:
        key = item.key.strip()
        if not key:
            raise HTTPException(status_code=400, detail="job key is required")
        if key in seen_keys:
            raise HTTPException(status_code=400, detail=f"duplicate job key '{key}'")
        seen_keys.add(key)
        if item.kind == "backup" and item.retention.enabled and not (item.retention.min_age or "").strip():
            raise HTTPException(status_code=400, detail=f"backup '{key}' retention requires min_age")

        common_kwargs = dict(
            key=key,
            order=item.order,
            description=item.description or item.title or key,
            title=item.title,
            timeout_seconds=item.timeout_seconds,
            enabled=item.enabled,
            continue_on_error=item.continue_on_error,
            kind=item.kind,
            profile=item.profile,
            schedule=ScheduleDefinition(**item.schedule.model_dump()),
            notifications=JobNotificationSettings(**item.notifications.model_dump()),
        )
        if item.kind == "command":
            jobs_to_save.append(
                JobDefinition(
                    **common_kwargs,
                    command=[part for part in item.command if str(part).strip()],
                ).validate()
            )
        else:
            cloud = catalog.get_cloud(item.cloud_key) if item.cloud_key else None
            destination_path = _compose_cloud_destination(cloud, item.destination_subpath) or item.destination_path
            jobs_to_save.append(
                JobDefinition(
                    **common_kwargs,
                    source_path=item.source_path,
                    cloud_key=item.cloud_key,
                    destination_subpath=item.destination_subpath,
                    destination_path=destination_path,
                    transfer_mode=item.transfer_mode,
                    options=BackupOptions(**item.options.model_dump()),
                    retention=RetentionSettings(**item.retention.model_dump()),
                ).validate()
            )

    with catalog_lock:
        updated_catalog = JobCatalog(
            jobs=sorted(jobs_to_save, key=lambda job: (job.order, job.key)),
            profiles=build_profiles(jobs_to_save),
            gotify=catalog.gotify,
            queues=catalog.queues,
            clouds=catalog.raw_clouds(),
        )
        save_catalog(settings.jobs_file, updated_catalog)
        catalog.replace(
            updated_catalog.raw_jobs(),
            updated_catalog.profiles,
            gotify=updated_catalog.gotify,
            queues=updated_catalog.queues,
            clouds=updated_catalog.raw_clouds(),
        )

    return {
        "saved": True,
        "jobs": catalog.list_jobs(),
        "backup_jobs": catalog.list_backup_jobs(),
        "command_jobs": catalog.list_command_jobs(),
        "profiles": catalog.profiles,
        "gotify": catalog.gotify.to_dict(),
        "queues": catalog.queues.to_dict(),
        "clouds": catalog.list_clouds(),
    }


@app.get("/api/fs/browse")
def browse_directories(path: str | None = None) -> dict[str, Any]:
    if not path:
        roots = []
        for root in FS_ROOTS:
            root_path = Path(root)
            if root_path.exists() and root_path.is_dir():
                roots.append(
                    {
                        "name": root_path.name or root_path.as_posix(),
                        "path": root_path.as_posix(),
                    }
                )
        return {"path": None, "parent": None, "directories": roots}

    target = Path(path).expanduser()
    if not target.is_absolute():
        raise HTTPException(status_code=400, detail="path must be absolute")
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="directory not found")

    directories: list[dict[str, str]] = []
    try:
        for child in sorted(target.iterdir(), key=lambda item: item.name.lower()):
            if child.is_dir():
                directories.append({"name": child.name, "path": child.as_posix()})
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=f"permission denied: {exc}") from exc

    parent = target.parent.as_posix() if target.parent != target else None
    return {
        "path": target.as_posix(),
        "parent": parent,
        "directories": directories,
    }


@app.get("/api/runs")
def list_runs(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
    return {"runs": storage.list_runs(limit=limit)}


@app.get("/api/runs/{run_id}")
def run_details(run_id: int) -> dict[str, Any]:
    run = storage.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {
        "run": run,
        "steps": storage.list_run_steps(run_id),
    }


@app.post("/api/runs", dependencies=[Depends(require_write_access)])
def create_run(payload: RunCreateRequest) -> dict[str, Any]:
    if payload.profile not in catalog.profiles:
        raise HTTPException(
            status_code=400,
            detail=f"unknown profile '{payload.profile}'",
        )
    try:
        run_id = orchestrator.enqueue_run(
            profile=payload.profile,
            trigger_type="manual",
            source=payload.source,
            requested_by=payload.requested_by,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"accepted": True, "run_id": run_id}


@app.post("/api/runs/job/{job_key}", dependencies=[Depends(require_write_access)])
def create_job_run(job_key: str) -> dict[str, Any]:
    try:
        run_id = orchestrator.enqueue_job(
            job_key=job_key,
            trigger_type="manual",
            source="dashboard",
            requested_by="dashboard",
            metadata={"job_key": job_key},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"accepted": True, "run_id": run_id}


@app.post("/api/triggers/event", dependencies=[Depends(require_write_access)])
def trigger_event(payload: EventTriggerRequest) -> dict[str, Any]:
    data = payload.model_dump()
    return orchestrator.enqueue_event(data)
