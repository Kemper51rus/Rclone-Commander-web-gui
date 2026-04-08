# 🚀 Rclone Commander Web GUI

Современная web-панель управления для backup-автоматизации на базе `rclone`.

`Rclone Commander Web GUI` переносит orchestration, планирование, наблюдаемость и управление заданиями из shell-скриптов в единое приложение с API, dashboard, очередями и историей запусков. При этом `rclone` остаётся основным механизмом передачи данных.

---

## 📚 Table of Contents

- [✨ Возможности](#-возможности)
- [🏗️ Архитектура](#️-архитектура)
- [📂 Структура проекта](#-структура-проекта)
- [📦 Installation](#-installation)
- [🚀 Usage](#-usage)
- [⚙️ Configuration](#️-configuration)
- [📖 API](#-api)
- [🧪 Examples](#-examples)
- [🔐 Безопасность](#-безопасность)
- [🔄 Миграция с legacy](#-миграция-с-legacy)
- [❓ FAQ](#-faq)
- [📘 Документация](#-документация)

---

## ✨ Возможности

- Web dashboard для ручного управления и мониторинга
- API для запуска, просмотра и настройки backup-задач
- Отдельные очереди для профилей `standard` и `heavy`
- Встроенный scheduler для периодических запусков
- Event-driven запуск через `inotifywait`
- SQLite-хранилище истории запусков и шагов
- Редактируемый runtime catalog заданий
- Поддержка двух режимов развертывания: `docker` и `systemd`
- Автоматический bootstrap конфигурации при чистом запуске

---

## 🏗️ Архитектура

Проект использует hybrid-подход:

- orchestration выполняет приложение
- фактический перенос данных выполняет `rclone`
- watcher отправляет события в API
- scheduler создаёт плановые запуски
- worker-потоки исполняют задания из очередей
- SQLite хранит operational state и историю

### Основные компоненты

| Компонент | Назначение |
| --- | --- |
| FastAPI app | API, dashboard, точки управления |
| Scheduler | Плановые запуски по расписанию |
| Workers | Исполнение queued runs |
| Watcher | Отправка filesystem events в API |
| SQLite | История запусков, шагов, событий и state |

### Поток выполнения

1. Запуск создаётся scheduler, API, dashboard или watcher.
2. Профиль помещается в соответствующую очередь.
3. Worker загружает активные jobs из runtime catalog.
4. Каждый шаг выполняет `rclone`-команду или другой action.
5. Результаты сохраняются в SQLite и становятся доступны через API и dashboard.

---

## 📂 Структура проекта

```text
.
├── docs/
├── hybrid/
│   ├── backend/
│   │   ├── app/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── .env.docker.example
│   ├── .env.systemd.example
│   └── docker-compose.yml
├── scripts/
├── systemd/
└── README.md
```

### Ключевые пути

| Путь | Назначение |
| --- | --- |
| `hybrid/backend/app/` | Исходный код backend-приложения |
| `hybrid/backend/app/jobs/default_jobs.example.json` | Безопасный шаблон catalog |
| `hybrid/backend/app/jobs/default_jobs.json` | Runtime catalog, создаётся при первом запуске |
| `hybrid/docker-compose.yml` | Docker stack |
| `systemd/` | Unit-файлы для host deployment |
| `scripts/` | Install и migration scripts |

---

## 📦 Installation

Поддерживаются два production-режима развертывания.

### 🐳 Docker

Используйте этот режим, если нужен self-contained deployment bundle.

#### Требования

- Docker с поддержкой Compose
- Доступ хоста к:
  - `/media`
  - `/srv`
  - `/root/.config/rclone`

#### Быстрый старт

```bash
cd hybrid
cp .env.docker.example .env.docker
docker compose --env-file .env.docker up -d --build
```

#### Что запускается

- `hybrid-web` — API, dashboard, scheduler, workers
- `hybrid-watch` — watcher, который отправляет события в API

### 🖥️ Systemd

Используйте этот режим, если нужен нативный runtime без контейнеров.

#### Требования

- `python3`
- `python3-venv`
- `rclone`
- `curl`
- `inotifywait`
- `systemd`

#### Быстрый старт

```bash
cp hybrid/.env.systemd.example hybrid/.env
./scripts/install-hybrid-systemd.sh /opt/rclone-hybrid
systemctl enable --now rclone-hybrid-web.service
systemctl enable --now rclone-watch-hybrid.service
```

---

## 🚀 Usage

После запуска доступны:

- Dashboard: `http://<host>:8080/`
- Health check: `GET /api/health`
- Runtime state: `GET /api/state`

### Базовый сценарий работы

1. Поднять приложение через `docker` или `systemd`
2. Открыть dashboard
3. Проверить состояние worker-ов и scheduler
4. Запустить профиль или отдельный job вручную
5. Просмотреть историю запусков и результаты шагов

### Профили

| Профиль | Назначение |
| --- | --- |
| `standard` | Короткие и частые задачи |
| `heavy` | Длинные и ресурсоёмкие задачи |
| `all` | Агрегированный профиль для полного запуска |

---

## ⚙️ Configuration

Проект использует runtime catalog и env-конфигурацию.

### Jobs Catalog

| Файл | Назначение |
| --- | --- |
| `default_jobs.example.json` | Безопасный шаблон, хранится в Git |
| `default_jobs.json` | Runtime catalog, создаётся при первом запуске |

### Что хранится в catalog

- `profiles`
- `queues`
- `gotify`
- `clouds`
- `jobs`

### Что можно настроить

- порядок и состав jobs
- `copy` или `sync`
- расписание
- timeout
- retention
- cloud settings
- queue behavior
- notification settings

### Bootstrap-поведение

Если `default_jobs.json` отсутствует, приложение автоматически создаёт его из шаблона:

```text
default_jobs.example.json -> default_jobs.json
```

Это позволяет хранить репозиторий без environment-specific runtime данных.

### Основные env-переменные

| Переменная | Назначение |
| --- | --- |
| `HYBRID_APP_NAME` | Имя приложения |
| `APP_ROOT` | Корневой runtime path |
| `HYBRID_DB_PATH` | Путь к SQLite |
| `HYBRID_JOBS_FILE` | Путь к runtime catalog |
| `HYBRID_RCLONE_CONFIG` | Путь к `rclone.conf` |
| `APP_TIMEZONE` | Таймзона приложения |
| `HYBRID_ENABLE_SCHEDULER` | Включение scheduler |
| `HYBRID_STANDARD_INTERVAL_MINUTES` | Интервал стандартных задач |
| `HYBRID_HEAVY_HOUR` | Час запуска heavy-задач |
| `HYBRID_EVENT_DEBOUNCE_SECONDS` | Debounce для watcher events |
| `HYBRID_DEFAULT_TIMEOUT_SECONDS` | Таймаут команд по умолчанию |
| `HYBRID_OUTPUT_TAIL_CHARS` | Размер сохраняемого tail вывода |
| `HYBRID_DRY_RUN` | Dry-run режим |
| `HYBRID_API_TOKEN` | Токен для write endpoints |
| `HYBRID_API_URL` | URL API для watcher |

---

## 📖 API

### Основные endpoints

| Method | Endpoint | Назначение |
| --- | --- | --- |
| `GET` | `/api/health` | Проверка доступности сервиса |
| `GET` | `/api/state` | Состояние runtime, очередей и worker-ов |
| `GET` | `/api/jobs` | Полный runtime catalog |
| `GET` | `/api/runs` | Список запусков |
| `GET` | `/api/runs/{run_id}` | Детали запуска и шагов |
| `POST` | `/api/runs` | Запуск профиля |
| `POST` | `/api/runs/job/{job_key}` | Запуск отдельного job |
| `POST` | `/api/triggers/event` | Приём событий от watcher |
| `PUT` | `/api/backups` | Обновление backup jobs |
| `PUT` | `/api/jobs` | Обновление полного каталога |
| `PUT` | `/api/clouds` | Обновление cloud settings |
| `PUT` | `/api/gotify` | Обновление Gotify settings |
| `PUT` | `/api/queues` | Обновление queue settings |

### Что хранится по каждому шагу

- status
- exit code
- duration
- stdout tail
- stderr tail

---

## 🧪 Examples

### Запуск профиля `standard`

```bash
curl -X POST http://127.0.0.1:8080/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"profile":"standard","source":"api","requested_by":"operator"}'
```

### Просмотр состояния runtime

```bash
curl http://127.0.0.1:8080/api/state
```

### Отправка filesystem event вручную

```bash
curl -X POST http://127.0.0.1:8080/api/triggers/event \
  -H 'Content-Type: application/json' \
  -d '{"event_type":"filesystem","path":"/media/photo/immich_library/upload","details":{"event":"close_write"}}'
```

### Развертывание через installer script

```bash
./scripts/install-hybrid-docker.sh /opt/rclone-hybrid
```

```bash
./scripts/install-hybrid-systemd.sh /opt/rclone-hybrid
```

---

## 🔐 Безопасность

### Рекомендуемые практики

- Не хранить `hybrid/.env` в Git
- Не хранить runtime `default_jobs.json` в Git
- Не хранить `rclone.conf` внутри репозитория
- Использовать `HYBRID_API_TOKEN`, если API доступен не только локально
- Публиковать сервис наружу только через reverse proxy и сетевые ограничения

### Рекомендуемая модель хранения секретов

- `default_jobs.example.json` — в Git
- `default_jobs.json` — только runtime
- `hybrid/.env` — только runtime
- cloud credentials — в `rclone.conf`, env или внешнем secret store

---

## 🔄 Миграция с legacy

Legacy runtime обычно включал:

- `rclone-backup.service`
- `rclone-backup.timer`
- `rclone-watch.service`
- `rclone-web.service`
- shell scripts в `/usr/local/bin`

Для миграции используется:

```bash
./scripts/migrate-legacy-to-hybrid.sh <systemd|docker> [target-root]
```

### Что делает migration script

1. Сохраняет snapshot legacy-окружения
2. Экспортирует unit definitions и status output
3. Копирует legacy runtime artifacts в backup directory
4. Останавливает и отключает старые unit-ы
5. Устанавливает hybrid runtime в выбранном режиме

### Что попадает в backup snapshot

- `systemctl cat` для legacy units
- `systemctl status` для legacy units
- `/usr/local/bin/rclone-backup.sh`
- `/usr/local/bin/rclone-backup-status.sh`
- `/usr/local/bin/rclone-watch.sh`
- `/etc/rclone-backup.gotify`
- `/var/lib/rclone-backup`
- `/var/log/rclone-backup.log`

### Примеры

#### Миграция в systemd

```bash
sudo ./scripts/migrate-legacy-to-hybrid.sh systemd /opt/rclone-hybrid
```

#### Миграция в docker

```bash
sudo ./scripts/migrate-legacy-to-hybrid.sh docker /opt/rclone-hybrid
```

---

## ❓ FAQ

### Пройдёт ли чистый запуск без `default_jobs.json`?

Да. При первом запуске runtime создаёт `default_jobs.json` из `default_jobs.example.json`.

### Где должны храниться cloud credentials?

В `rclone.conf`, env-переменных или внешнем secret storage. Их не следует коммитить в репозиторий.

### Что выбрать: `docker` или `systemd`?

| Режим | Когда использовать |
| --- | --- |
| `docker` | Если нужен self-contained deployment |
| `systemd` | Если нужен нативный host runtime |

### Что проверять после развертывания?

- `GET /api/health`
- `GET /api/state`
- создание SQLite database
- создание `default_jobs.json`
- успешный ручной запуск job-а или профиля

---

## 📘 Документация

- `docs/01-overview.md` — обзор проекта
- `docs/03-runtime-behavior.md` — runtime behavior
- `docs/06-hybrid-mvp.md` — configuration
- `docs/07-deployment.md` — deployment guide
- `docs/08-legacy-migration.md` — legacy migration guide
- `hybrid/README.md` — заметки по runtime-каталогу `hybrid/`
