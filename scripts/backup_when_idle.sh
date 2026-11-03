#!/usr/bin/env bash

# scripts/systemd/deceit-backup.service	to /etc/systemd/system/deceit-backup.service
# scripts/systemd/deceit-backup.timer	to /etc/systemd/system/deceit-backup.timer

: << 'COMMENT'
bash <<'BASH'
set -euo pipefail

# Выбираем каталог проекта.
if [[ -d /root/deceit ]]; then
  PROJECT_DIR=/root/deceit
elif [[ -d /root/mafia ]]; then
  PROJECT_DIR=/root/mafia
else
  echo "Не найдены /root/deceit и /root/mafia" >&2
  exit 1
fi

cd "$PROJECT_DIR"
echo "Каталог проекта: $PROJECT_DIR"

# Проверяем наличие файлов.
for file in \
  .env \
  scripts/backup_all.sh \
  scripts/backup_when_idle.sh \
  /etc/systemd/system/deceit-backup.service \
  /etc/systemd/system/deceit-backup.timer
do
  [[ -f "$file" ]] || {
    echo "Не найден файл: $file" >&2
    exit 1
  }
done

# Исправляем переносы строк после Windows.
sed -i 's/\r$//' \
  .env \
  scripts/backup_all.sh \
  scripts/backup_when_idle.sh \
  /etc/systemd/system/deceit-backup.service \
  /etc/systemd/system/deceit-backup.timer

# Выставляем права.
chmod +x scripts/backup_all.sh scripts/backup_when_idle.sh
chmod 644 \
  /etc/systemd/system/deceit-backup.service \
  /etc/systemd/system/deceit-backup.timer

# Проверяем конфигурацию.
bash -n scripts/backup_all.sh
bash -n scripts/backup_when_idle.sh
systemd-analyze verify \
  /etc/systemd/system/deceit-backup.service \
  /etc/systemd/system/deceit-backup.timer

# Включаем таймер и автозапуск после перезагрузки.
systemctl daemon-reload
systemctl enable --now deceit-backup.timer
systemctl list-timers --all deceit-backup.timer
BASH
COMMENT

# Called by deceit-backup.timer; one successful backup per Moscow calendar day.
# The service selects /root/deceit first, then /root/mafia if deceit is absent.
set -euo pipefail
umask 077
export TZ=Europe/Moscow

log() { echo "$(date '+%F %T %Z') [INFO] $*"; }
error() { echo "$(date '+%F %T %Z') [ERROR] $*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
STATE_DIR="${STATE_DIRECTORY:-/var/lib/deceit-backup}"
SUCCESS_FILE="$STATE_DIR/last-success-date"

# Check the window here as well: Persistent timers may fire after 08:00 on boot.
read -r ATTEMPT_DATE ATTEMPT_HOUR <<< "$(date '+%F %H')"
if (( 10#$ATTEMPT_HOUR < 3 || 10#$ATTEMPT_HOUR >= 8 )); then
  log "Outside 03:00-08:00 Europe/Moscow; waiting for the next scheduled check"
  exit 0
fi

for tool in flock timeout docker; do
  command -v "$tool" >/dev/null 2>&1 || { error "$tool is required"; exit 1; }
done

mkdir -p "$STATE_DIR"
exec 201>"$STATE_DIR/scheduler.lock"
if ! flock -n 201; then
  log "Another scheduled backup is already running"
  exit 0
fi
# Keep scheduler.lock on disk so every invocation locks the same inode.

if [[ -f "$SUCCESS_FILE" ]] && [[ "$(cat "$SUCCESS_FILE")" == "$ATTEMPT_DATE" ]]; then
  log "Backup already completed for $ATTEMPT_DATE; waiting for the next day"
  exit 0
fi

cd "$PROJECT_ROOT"
[[ -f .env ]] || { error ".env not found in $PROJECT_ROOT"; exit 1; }
if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  error "Docker Compose is required"
  exit 1
fi

# Query the same Redis DB and full rooms:index used by the backend. The guest
# room list hides anonymous rooms, so an empty public response is insufficient.
# Use the backend's own settings without printing secrets or sourcing .env here.
if ! ROOM_COUNT="$(timeout 30s "${COMPOSE[@]}" exec -T backend python -c '
import redis
from app.core.settings import settings

client = redis.Redis.from_url(
    settings.redis_url,
    socket_connect_timeout=5,
    socket_timeout=5,
)
try:
    print(client.zcard("rooms:index"))
finally:
    client.close()
')"; then
  error "Could not check rooms; backup skipped, timer will retry"
  exit 1
fi
ROOM_COUNT="${ROOM_COUNT//$'\r'/}"
if [[ ! "$ROOM_COUNT" =~ ^[0-9]+$ ]]; then
  error "Invalid room count; backup skipped, timer will retry"
  exit 1
fi
if [[ "$ROOM_COUNT" != "0" ]]; then
  log "Rooms exist ($ROOM_COUNT); waiting for the next scheduled check"
  exit 0
fi

# Recheck the time after the query so a delayed check cannot start after 08:00.
read -r CURRENT_DATE CURRENT_HOUR <<< "$(date '+%F %H')"
if [[ "$CURRENT_DATE" != "$ATTEMPT_DATE" ]] || (( 10#$CURRENT_HOUR < 3 || 10#$CURRENT_HOUR >= 8 )); then
  log "Backup window has ended; waiting for the next day"
  exit 0
fi

log "No rooms exist; starting backup for $ATTEMPT_DATE"
sed -i 's/\r$//' .env
# grep -n would print .env secrets and returns 1 when no CR characters remain.
if LC_ALL=C grep -q $'\r' .env; then
  error ".env still contains CR characters"
  exit 1
fi
chmod +x scripts/backup_all.sh
./scripts/backup_all.sh

# Record success only after the whole backup script exits successfully.
SUCCESS_TMP="$(mktemp "$STATE_DIR/.last-success.XXXXXX")"
trap 'rm -f -- "$SUCCESS_TMP"' EXIT
printf '%s\n' "$ATTEMPT_DATE" > "$SUCCESS_TMP"
mv -f -- "$SUCCESS_TMP" "$SUCCESS_FILE"
log "Backup completed for $ATTEMPT_DATE; no more backups today"
