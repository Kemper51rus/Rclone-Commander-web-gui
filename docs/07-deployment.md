# 📦 Deployment

Проект поддерживает два production deployment mode:

- `docker`
- `systemd`

---

## 🐳 Docker Deployment

Docker mode запускает два сервиса:

- `hybrid-web`
- `hybrid-watch`

### Требования

- Docker с Compose
- Доступные host bind mounts:
  - `/media`
  - `/srv`
  - `/root/.config/rclone`

### Подготовка

```bash
cd hybrid
cp .env.docker.example .env.docker
```

Проверьте:

- `HYBRID_RCLONE_CONFIG`
- `APP_TIMEZONE`
- `HYBRID_API_TOKEN`

### Запуск

```bash
docker compose --env-file .env.docker up -d --build
```

### Installer Script

```bash
./scripts/install-hybrid-docker.sh /opt/rclone-hybrid
```

---

## 🖥️ Systemd Deployment

Systemd mode запускает web service и watcher напрямую на хосте.

### Требования

- `python3`
- `python3-venv`
- `rclone`
- `curl`
- `inotifywait`
- `systemd`

### Подготовка

```bash
cp hybrid/.env.systemd.example hybrid/.env
```

Проверьте:

- `HYBRID_DB_PATH`
- `HYBRID_JOBS_FILE`
- `HYBRID_RCLONE_CONFIG`
- `HYBRID_API_URL`

### Установка

```bash
./scripts/install-hybrid-systemd.sh /opt/rclone-hybrid
```

### Включение сервисов

```bash
systemctl enable --now rclone-hybrid-web.service
systemctl enable --now rclone-watch-hybrid.service
```

---

## ✅ Post-Deployment Checklist

Проверьте:

- `GET /api/health`
- `GET /api/state`
- ручное создание run
- создание SQLite database
- bootstrap runtime catalog при чистом старте

---

## 🆚 Выбор режима

| Режим | Когда подходит лучше |
| --- | --- |
| `docker` | Нужен self-contained deployment bundle |
| `systemd` | Нужен нативный host runtime и прямая системная интеграция |
