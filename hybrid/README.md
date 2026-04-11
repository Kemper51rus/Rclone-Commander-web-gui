# 📦 Hybrid Runtime

Каталог `hybrid/` содержит приложение, шаблоны окружения и файлы для развертывания.

---

## 📁 Содержимое

| Путь | Назначение |
| --- | --- |
| `backend/app/main.py` | FastAPI entrypoint |
| `backend/app/orchestrator.py` | Scheduler, queues, workers |
| `backend/app/storage.py` | SQLite persistence |
| `backend/app/jobs/default_jobs.example.json` | Шаблон рабочего каталога |
| `.env.docker.example` | Шаблон env для Docker |
| `.env.systemd.example` | Шаблон env для systemd |
| `docker-compose.yml` | Docker-стек |

---

## 🚀 Bootstrap

При чистом старте приложение создаёт:

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
- `HYBRID_WATCHER_DEBOUNCE_SECONDS`
- `HYBRID_COPY_STARTUP_DELAY_SECONDS`
- `HYBRID_COPY_MIN_START_INTERVAL_SECONDS`
- `HYBRID_ENABLE_SCHEDULER`
- `HYBRID_STANDARD_INTERVAL_MINUTES`
- `HYBRID_HEAVY_HOUR`

---

## 🧩 Runtime Features

- structured `rclone`-опции у backup и retention задач:
  `transfers`, `checkers`, `tpslimit`, `tpslimit_burst`, `retries`, `low_level_retries`,
  `retries_sleep`, `fast_list`, `no_traverse`, `debug_dump`, `extra_args`
- `Mail.ru safe preset` в редакторе backup-задач
- сериализация запусков для Mail.ru remote на вкладке `Облака`
- ручное и автоматическое step-логирование `rclone`

---

## 📖 API Surface

Полное описание вынесено в `docs/04-api-reference.md`. Ниже приведён краткий обзор текущего API без сокращений и устаревших endpoints.

---

## 📘 Связанные документы

- [Руководство по развертыванию](/root/projects/rclone-web-ui/rclone/docs/07-deployment.md)
- [Служебные заметки для разработки](/root/projects/rclone-web-ui/rclone/docs/08-development-notes.md)
- [Архивные материалы по legacy](/root/projects/rclone-web-ui/rclone/legacy/README.md)
