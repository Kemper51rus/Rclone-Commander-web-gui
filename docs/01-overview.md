# 📘 Обзор проекта

`Rclone Commander Web GUI` это self-hosted слой управления для backup-процессов на базе `rclone`. Проект заменяет shell-driven orchestration на структурированный runtime с API, dashboard, scheduler и queue-based workers.

---

## 🎯 Цели проекта

- Централизовать управление backup-задачами
- Разделить orchestration и фактический перенос данных
- Поддержать schedule-driven и event-driven сценарии
- Сделать runs и step history наблюдаемыми
- Подготовить единый production runtime для `docker` и `systemd`

---

## 🧱 Основные блоки

| Блок | Ответственность |
| --- | --- |
| FastAPI app | API, dashboard, конфигурация |
| Scheduler | Создание плановых запусков |
| Worker queues | Исполнение профилей `standard` и `heavy` |
| Watcher | Передача filesystem events в API |
| SQLite | Хранение runs, steps, events и state |

---

## 🧭 Модель исполнения

Проект использует hybrid-модель:

- orchestration находится в приложении
- `rclone` остаётся execution engine
- jobs описываются в runtime catalog
- watcher больше не запускает systemd units напрямую

---

## 📁 Ключевые пути

| Путь | Назначение |
| --- | --- |
| `hybrid/backend/app/` | Исходный код backend |
| `hybrid/backend/app/jobs/default_jobs.example.json` | Безопасный шаблон catalog |
| `hybrid/backend/app/jobs/default_jobs.json` | Runtime catalog |
| `hybrid/docker-compose.yml` | Docker deployment |
| `systemd/` | Host deployment units |
| `scripts/` | Install и migration scripts |

---

## ✅ Что даёт проект

- Dashboard для operational control
- Ручной запуск профилей и отдельных job-ов
- Историю запусков с деталями шагов
- Event-driven и schedule-driven автоматизацию
- Runtime configuration через catalog и API

---

## 🔐 Источник правды

Активный runtime catalog:

`hybrid/backend/app/jobs/default_jobs.json`

Он создаётся из шаблона:

`hybrid/backend/app/jobs/default_jobs.example.json`

Шаблон безопасно хранить в Git. Runtime-файл должен оставаться вне version control.
