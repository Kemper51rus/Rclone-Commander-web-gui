# 📦 Hybrid Runtime

Каталог `hybrid/` содержит приложение, deployment templates и packaging assets.

---

## 📁 Содержимое

| Путь | Назначение |
| --- | --- |
| `backend/app/main.py` | FastAPI entrypoint |
| `backend/app/orchestrator.py` | Scheduler, queues, workers |
| `backend/app/storage.py` | SQLite persistence |
| `backend/app/jobs/default_jobs.example.json` | Безопасный шаблон runtime catalog |
| `.env.docker.example` | Docker env template |
| `.env.systemd.example` | Systemd env template |
| `docker-compose.yml` | Docker deployment stack |

---

## 🚀 Bootstrap

При чистом старте runtime создаёт:

```text
backend/app/jobs/default_jobs.json
```

из шаблона:

```text
backend/app/jobs/default_jobs.example.json
```

---

## ⚙️ Важные переменные

- `HYBRID_APP_NAME`
- `HYBRID_DB_PATH`
- `HYBRID_JOBS_FILE`
- `HYBRID_RCLONE_CONFIG`
- `HYBRID_API_TOKEN`
- `HYBRID_API_URL`
- `HYBRID_ENABLE_SCHEDULER`
- `HYBRID_STANDARD_INTERVAL_MINUTES`
- `HYBRID_HEAVY_HOUR`

---

## 📖 API Surface

- `GET /api/health`
- `GET /api/state`
- `GET /api/jobs`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `POST /api/runs`
- `POST /api/runs/job/{job_key}`
- `POST /api/triggers/event`
- `PUT /api/backups`

---

## 📘 Связанные документы

- [Руководство по развертыванию](/root/projects/rclone-web-ui/rclone/docs/07-deployment.md)
- [Руководство по миграции с legacy](/root/projects/rclone-web-ui/rclone/docs/08-legacy-migration.md)
