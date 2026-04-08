# ⚙️ Configuration

Этот документ описывает runtime catalog, env-переменные и рекомендуемую модель работы с секретами.

---

## 📄 Jobs Catalog

### Файлы

| Файл | Роль |
| --- | --- |
| `hybrid/backend/app/jobs/default_jobs.example.json` | Безопасный шаблон, хранится в Git |
| `hybrid/backend/app/jobs/default_jobs.json` | Runtime catalog, создаётся из шаблона |

### Основные секции

Catalog содержит:

- `profiles`
- `gotify`
- `queues`
- `clouds`
- `jobs`

---

## 🛠️ Что настраивается

### Jobs

- key и порядок выполнения
- source path
- destination path
- cloud binding
- transfer mode: `copy` или `sync`
- timeout
- schedule
- notifications
- retention policy

### Queues

- параллельное выполнение профилей
- queueing для scheduler
- queueing для watcher

### Clouds

- remote metadata
- provider
- remote name
- endpoint
- root path
- optional extra config

---

## 🚀 Bootstrap Behavior

Если runtime catalog отсутствует, приложение автоматически создаёт его по схеме:

```text
default_jobs.example.json -> default_jobs.json
```

Это позволяет не хранить environment-specific runtime данные в репозитории.

---

## 🌍 Environment Variables

| Переменная | Назначение |
| --- | --- |
| `HYBRID_APP_NAME` | Публичное имя приложения |
| `APP_ROOT` | Корневой runtime path |
| `HYBRID_DB_PATH` | Путь к SQLite |
| `HYBRID_JOBS_FILE` | Путь к runtime catalog |
| `HYBRID_RCLONE_CONFIG` | Путь к `rclone.conf` |
| `APP_TIMEZONE` | Таймзона приложения |
| `HYBRID_ENABLE_SCHEDULER` | Включение scheduler |
| `HYBRID_STANDARD_INTERVAL_MINUTES` | Интервал стандартных задач |
| `HYBRID_HEAVY_HOUR` | Час heavy-задач |
| `HYBRID_EVENT_DEBOUNCE_SECONDS` | Debounce окно для событий |
| `HYBRID_DEFAULT_TIMEOUT_SECONDS` | Таймаут команд по умолчанию |
| `HYBRID_OUTPUT_TAIL_CHARS` | Размер сохраняемого tail вывода |
| `HYBRID_DRY_RUN` | Dry-run режим |
| `HYBRID_API_TOKEN` | Токен для write access |
| `HYBRID_API_URL` | URL API для watcher |

---

## 🔄 Что сделать после bootstrap

1. Проверить сгенерированный `default_jobs.json`
2. Импортировать или настроить cloud settings из `rclone.conf`
3. Проверить destination paths и schedules
4. Проверить retention policies
5. Включить защиту API при необходимости

---

## 🔐 Secret Management

Рекомендуемый подход:

- хранить `default_jobs.example.json` в Git
- не хранить `default_jobs.json` в Git
- не хранить `hybrid/.env` в Git
- хранить cloud credentials в `rclone.conf` или другом внешнем secret source
- не коммитить access tokens, refresh tokens и runtime cloud metadata
