# 🔄 Legacy Migration

Этот документ описывает переход со старой связки shell-скриптов и systemd на текущий taskboard runtime приложения.

---

## 🧱 Legacy Components

Legacy stack обычно включал:

- `rclone-backup.service`
- `rclone-backup.timer`
- `rclone-watch.service`
- shell scripts в `/usr/local/bin`

---

## 🛠️ Migration Command

```bash
sudo ./install.sh migrate-legacy
```

### Полная установка с migration

Для установки/обновления и migration в одном процессе запустите:

```bash
sudo ./install.sh
```

---

## 📦 Что делает скрипт

1. Создаёт snapshot legacy-окружения
2. Экспортирует unit definitions и status output
3. Копирует legacy runtime artifacts в backup directory
4. Останавливает и отключает legacy services
5. Удаляет legacy-скрипты и unit'ы после backup

---

## 🗂️ Содержимое backup snapshot

В snapshot могут попасть:

- `systemctl cat` для legacy units
- `systemctl status` для legacy units
- `/usr/local/bin/rclone-backup.sh`
- `/usr/local/bin/rclone-backup-status.sh`
- `/usr/local/bin/rclone-watch.sh`
- `/usr/local/bin/rclone-backup.sh.bak.*`

---

## 🧪 Examples

### Миграция в Systemd

```bash
sudo ./install.sh migrate-legacy
```

### Миграция в Docker

```bash
sudo ./install.sh
```

---

## ✅ Validation Checklist

После миграции проверьте:

- новые сервисы или Compose stack действительно запущены
- `GET /api/health` возвращает успешный ответ
- `GET /api/state` показывает живые scheduler и workers
- `default_jobs.json` создан при необходимости
- ручной запуск job-а или профиля проходит успешно
