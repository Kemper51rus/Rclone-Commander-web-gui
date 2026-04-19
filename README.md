<p align="center">
   <img src="https://raw.githubusercontent.com/Kemper51rus/Rclone-taskboard/main/docs/readme-wordmark.svg" alt="Rclone taskboard" width="620">
</p>

RCLONE TASKBOARD — собирает запуск задач, расписание, очереди, историю и интерфейс управления в одном приложении. Сам перенос данных по-прежнему выполняет `rclone`, а приложение отвечает за координацию, хранение состояния и работу API.

---

## Quick Start

```bash
bash <(curl -Ls https://raw.githubusercontent.com/Kemper51rus/Rclone-taskboard/main/install.sh)
```

---

## ✨ Возможности

- web dashboard для ручного управления задачами и наблюдения за состоянием сервиса
- HTTP API для запуска, просмотра истории и изменения настроек
- настраиваемые очереди с собственным числом workers и ограничениями скорости
- встроенный scheduler для периодических запусков
- встроенный watcher для запуска задач по изменениям в файловой системе
- SQLite для хранения запусков, шагов, событий и служебного состояния
- диагностика размера SQLite-базы, WAL, fd и памяти backend
- редактирование каталога задач через UI и API
- поддержка развертывания через `docker` и `systemd`
- автоматическое создание рабочего каталога задач при первом старте

---

## 🏠 Homepage widget

Для Homepage/customapi используйте лёгкий endpoint `GET /api/homepage`, а не полный `/api/state`.
Скорость, открытые запуски и очереди обновляются на каждый запрос, поэтому при `refreshInterval: 500` скорость будет почти real-time.
Размер БД, WAL и количество задач кэшируются на стороне taskboard на `slow_cache_seconds`, чтобы частый polling не нагружал SQLite-диагностику.

Пример:

```yaml
widget:
  type: customapi
  url: http://100.100.0.243:8080/api/homepage
  refreshInterval: 500
  mappings:
    - field: total_copy_speed_megabits_per_second
      label: Speed
      format: float
      suffix: " Mbps"
    - field: open_runs_total
      label: Open Runs
      format: number
    - field: database_total_size_bytes
      label: DB
      format: bytes
```

---

## 📘 Документация

- [Обзор проекта](docs/01-overview.md)
- [Руководство по работе](docs/02-user-guide.md)
- [Runtime behavior](docs/03-runtime-behavior.md)
- [API reference](docs/04-api-reference.md)
- [Configuration](docs/06-taskboard-mvp.md)
- [Deployment](docs/07-deployment.md)
- [Development notes](docs/08-development-notes.md)
- [Legacy migration](docs/09-legacy-migration.md)
- [Runtime-каталог](docs/10-taskboard-runtime.md)
