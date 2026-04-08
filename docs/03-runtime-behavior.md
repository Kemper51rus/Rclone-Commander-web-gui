# ⚙️ Runtime Behavior

Этот документ описывает, как создаются, ставятся в очередь, исполняются и наблюдаются запуски.

---

## 🧭 Источники запусков

Запуск может быть создан из трёх источников:

1. Scheduler
2. Dashboard или API
3. Filesystem watcher

---

## 👀 Event-Driven Flow

Watcher используется для реакции на изменения в файловой системе почти в реальном времени.

### Последовательность

1. `scripts/rclone-watch-hybrid.sh` отслеживает директории через `inotifywait`
2. Watcher отправляет `POST /api/triggers/event`
3. API сохраняет событие
4. Debounce логика отсекает шумные серии событий
5. При разрешённой queue policy создаётся run профиля `standard`
6. Worker исполняет соответствующие jobs

---

## 🕒 Scheduled Flow

Scheduler работает внутри web-сервиса.

### Последовательность

1. Scheduler проверяет jobs каждую минуту
2. При наступлении schedule slot создаётся run
3. Run направляется в нужную очередь
4. Worker исполняет его шаги

---

## 🧵 Профили и очереди

| Профиль | Назначение |
| --- | --- |
| `standard` | Частые и короткие задачи |
| `heavy` | Долгие и ресурсоёмкие задачи |
| `all` | Агрегированный профиль для UI и полного запуска |

Поведение очередей определяется секцией `queues` в runtime catalog:

- `allow_parallel_profiles`
- `allow_scheduler_queueing`
- `allow_event_queueing`

---

## 💾 Runtime State

### Runtime Catalog

- `hybrid/backend/app/jobs/default_jobs.json`

### SQLite Database

- путь задаётся через `HYBRID_DB_PATH`
- значение по умолчанию зависит от deployment mode

В базе хранятся:

- runs
- step execution history
- events
- scheduler key-value state

---

## 📊 Наблюдаемость

### UI

- Dashboard доступен по `/`

### API

- `GET /api/health`
- `GET /api/state`
- `GET /api/jobs`
- `GET /api/runs`
- `GET /api/runs/{run_id}`

### Что сохраняется по каждому шагу

- status
- exit code
- duration
- stdout tail
- stderr tail

---

## 🔐 Security Notes

- Для write endpoints используйте `HYBRID_API_TOKEN`, если сервис доступен не только локально
- Для внешнего доступа предпочтителен reverse proxy с сетевыми ограничениями
- Runtime catalogs и credentials не должны храниться в Git
