#!/usr/bin/env bash
set -euo pipefail

API_URL="${HYBRID_API_URL:-http://127.0.0.1:8080}"
API_TOKEN="${HYBRID_API_TOKEN:-}"

WATCH=(
  /media/photo/immich_library/upload
  /media/photo/immich_library/library
  /media/downloads/BACKUPS/dump
  /media/cloud/frigate
  /srv/homepage
)

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/ }"
  printf '%s' "$value"
}

post_event() {
  local raw="$1"
  local path="$2"
  local event="$3"

  local payload
  payload=$(printf '{"event_type":"filesystem","path":"%s","details":{"event":"%s","raw":"%s"}}' \
    "$(json_escape "$path")" \
    "$(json_escape "$event")" \
    "$(json_escape "$raw")")

  local headers=(-H "Content-Type: application/json")
  if [[ -n "$API_TOKEN" ]]; then
    headers+=(-H "Authorization: Bearer $API_TOKEN")
  fi

  curl -fsS -m 5 \
    -X POST \
    "${headers[@]}" \
    -d "$payload" \
    "${API_URL}/api/triggers/event" >/dev/null || true
}

inotifywait -m -r \
  -e create -e close_write -e moved_to -e delete -e delete_self -e move_self \
  --format "%w%f %e" "${WATCH[@]}" | while read -r line; do
    path="${line% *}"
    event="${line##* }"
    post_event "$line" "$path" "$event"
done
