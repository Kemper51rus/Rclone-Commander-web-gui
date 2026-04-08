#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
TARGET_ROOT="${1:-/opt/rclone-hybrid}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

require_cmd docker
require_cmd install

install -d "$TARGET_ROOT" "$TARGET_ROOT/hybrid" "$TARGET_ROOT/hybrid/backend" \
  "$TARGET_ROOT/hybrid/backend/app" "$TARGET_ROOT/hybrid/data" "$TARGET_ROOT/scripts"

cp -a "$REPO_ROOT/hybrid/backend/app/." "$TARGET_ROOT/hybrid/backend/app/"
find "$TARGET_ROOT/hybrid/backend/app" \( -type d -name __pycache__ -o -type f -name '*.pyc' \) -exec rm -rf {} +
install -m 0644 "$REPO_ROOT/hybrid/backend/requirements.txt" "$TARGET_ROOT/hybrid/backend/requirements.txt"
install -m 0644 "$REPO_ROOT/hybrid/backend/Dockerfile" "$TARGET_ROOT/hybrid/backend/Dockerfile"
install -m 0644 "$REPO_ROOT/hybrid/backend/app/jobs/default_jobs.example.json" "$TARGET_ROOT/hybrid/backend/app/jobs/default_jobs.example.json"
install -m 0644 "$REPO_ROOT/hybrid/docker-compose.yml" "$TARGET_ROOT/hybrid/docker-compose.yml"
install -m 0755 "$REPO_ROOT/scripts/rclone-watch-hybrid.sh" "$TARGET_ROOT/scripts/rclone-watch-hybrid.sh"
install -m 0644 "$REPO_ROOT/hybrid/.env.docker.example" "$TARGET_ROOT/hybrid/.env.docker.example"

if [[ ! -f "$TARGET_ROOT/hybrid/.env.docker" ]]; then
  install -m 0644 "$REPO_ROOT/hybrid/.env.docker.example" "$TARGET_ROOT/hybrid/.env.docker"
fi

if [[ ! -f "$TARGET_ROOT/hybrid/backend/app/jobs/default_jobs.json" ]]; then
  install -m 0644 \
    "$REPO_ROOT/hybrid/backend/app/jobs/default_jobs.example.json" \
    "$TARGET_ROOT/hybrid/backend/app/jobs/default_jobs.json"
fi

(
  cd "$TARGET_ROOT/hybrid"
  docker compose --env-file .env.docker up -d --build
)

cat <<EOF
docker deployment bundle installed into: $TARGET_ROOT

Active files:
  - $TARGET_ROOT/hybrid/docker-compose.yml
  - $TARGET_ROOT/hybrid/.env.docker

Update command:
  cd $TARGET_ROOT/hybrid && docker compose --env-file .env.docker up -d --build
EOF
