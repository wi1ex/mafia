#!/usr/bin/env bash
#
# backup_all.sh
# ------------------------------------------------------------
# Назначение:
#   Создаёт резервные копии PostgreSQL, Redis и MinIO (бакет),
#   складывает их в каталог ./backups и удаляет старые бэкапы
#   по политике хранения.
#
# Что нужно перед запуском:
#   1) Запущенный Docker и контейнеры проекта (db, redis, minio).
#   2) Файл .env в корне проекта.
#   3) Утилиты: docker, tar, sha256sum, flock, mktemp.
#   4) Права на запись в каталоги ./backups и ./.locks.
#
# Какие переменные использует скрипт:
#   - POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD
#     (если их нет, пробует DB_NAME / DB_USER / DB_PASSWORD).
#   - ENABLE_REDIS_BACKUP (опционально, по умолчанию 0)
#     0 = Redis НЕ бэкапится, 1 = Redis бэкапится
#   - REDIS_PASSWORD (обязателен только если ENABLE_REDIS_BACKUP=1)
#   - MINIO_BUCKET
#   - BACKUP_RETENTION_DAYS (опционально, по умолчанию 30)
#
# Быстрый запуск:
#   chmod +x scripts/backup_all.sh
#   ./scripts/backup_all.sh
#
# Запуск с кастомной глубиной хранения:
#   BACKUP_RETENTION_DAYS=45 ./scripts/backup_all.sh
#
# Куда складываются бэкапы:
#   ./backups/postgres/*.tar.gz
#   ./backups/redis/*.tar.gz
#   ./backups/minio/*.tar.gz
#
# Что делает скрипт по шагам:
#   1) Ставит lock-файл (./.locks/backup_all.lock), чтобы не было
#      параллельных запусков.
#   2) Делает pg_dump PostgreSQL + sha256 и архивирует.
#   3) Если ENABLE_REDIS_BACKUP=1: делает SAVE в Redis, копирует
#      dump.rdb + sha256 и архивирует.
#   4) Копирует бакет MinIO, делает tar.gz + sha256 и архивирует.
#   5) Удаляет файлы бэкапов старше BACKUP_RETENTION_DAYS дней.
#
# Пример cron (ежедневно в 03:10):
#   10 3 * * * cd /path/to/mafia && BACKUP_RETENTION_DAYS=30 ./scripts/backup_all.sh >> /var/log/mafia-backup.log 2>&1
#
# Рекомендации:
#   - Периодически проверяйте, что новые архивы действительно
#     появляются в ./backups.
#   - Храните копии архивов также вне сервера (offsite), чтобы
#     пережить потерю диска/инстанса.
#
set -euo pipefail

log() { echo "$(date '+%F %T') [INFO] $*"; }
error() { echo "$(date '+%F %T') [ERROR] $*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"

[ -f "$ENV_FILE" ] || { error ".env not found: $ENV_FILE"; exit 1; }
# shellcheck disable=SC1090
source "$ENV_FILE"

DB_NAME="${POSTGRES_DB:-${DB_NAME:-}}"
DB_USER="${POSTGRES_USER:-${DB_USER:-}}"
DB_PASSWORD="${POSTGRES_PASSWORD:-${DB_PASSWORD:-}}"
ENABLE_REDIS_BACKUP="${ENABLE_REDIS_BACKUP:-0}"

case "${ENABLE_REDIS_BACKUP,,}" in
  1|true|yes|on) ENABLE_REDIS_BACKUP="1" ;;
  0|false|no|off|'') ENABLE_REDIS_BACKUP="0" ;;
  *)
    error "ENABLE_REDIS_BACKUP must be one of: 0/1/true/false/yes/no/on/off"
    exit 1
    ;;
esac

: "${DB_NAME:?POSTGRES_DB (or DB_NAME) not set}"
: "${DB_USER:?POSTGRES_USER (or DB_USER) not set}"
: "${DB_PASSWORD:?POSTGRES_PASSWORD (or DB_PASSWORD) not set}"
: "${MINIO_BUCKET:?MINIO_BUCKET not set}"
if [ "$ENABLE_REDIS_BACKUP" = "1" ]; then
  : "${REDIS_PASSWORD:?REDIS_PASSWORD not set (required when ENABLE_REDIS_BACKUP=1)}"
fi

BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
case "$BACKUP_RETENTION_DAYS" in
  ''|*[!0-9]*)
    error "BACKUP_RETENTION_DAYS must be a non-negative integer"
    exit 1
    ;;
esac

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  error "Neither 'docker compose' nor 'docker-compose' was found"
  exit 1
fi
compose() { "${COMPOSE[@]}" "$@"; }

command -v flock >/dev/null 2>&1 || { error "flock is required"; exit 1; }

LOCK_DIR="$PROJECT_ROOT/.locks"
mkdir -p "$LOCK_DIR"
LOCKFILE="$LOCK_DIR/backup_all.lock"
exec 200>"$LOCKFILE"
flock -n 200 || { error "Backup already running"; exit 1; }

cleanup() {
  local rc=$?
  flock -u 200 || true
  rm -f "$LOCKFILE" || true
  if [ "$rc" -ne 0 ]; then
    error "Backup failed (rc=$rc)"
  fi
  exit "$rc"
}
trap cleanup EXIT

TIMESTAMP="$(date +'%Y%m%d_%H%M')"
BACKUP_ROOT="$PROJECT_ROOT/backups"
mkdir -p \
  "$BACKUP_ROOT/postgres" \
  "$BACKUP_ROOT/redis" \
  "$BACKUP_ROOT/minio"

log "PostgreSQL: dump + checksum + archive"
PG_CONTAINER="$(compose ps -q db)"
[ -n "$PG_CONTAINER" ] || { error "Postgres container is not running"; exit 1; }

TMP="$(mktemp -d)"
PG_DUMP="$TMP/${DB_NAME}.dump"
docker exec "$PG_CONTAINER" \
  sh -c "export PGPASSWORD='$DB_PASSWORD'; pg_dump -U '$DB_USER' -F c '$DB_NAME'" \
  > "$PG_DUMP"
(cd "$TMP" && sha256sum "${DB_NAME}.dump" > "${DB_NAME}.sha256")

PG_ARCHIVE="$BACKUP_ROOT/postgres/${DB_NAME}_${TIMESTAMP}.tar.gz"
tar czf "$PG_ARCHIVE" -C "$TMP" "${DB_NAME}.dump" "${DB_NAME}.sha256"
log "-> $PG_ARCHIVE"
rm -rf "$TMP"

if [ "$ENABLE_REDIS_BACKUP" = "1" ]; then
  log "Redis: dump + checksum + archive"
  REDIS_CONTAINER="$(compose ps -q redis)"
  [ -n "$REDIS_CONTAINER" ] || { error "Redis container is not running"; exit 1; }

  TMP="$(mktemp -d)"
  REDIS_DUMP="$TMP/dump.rdb"
  docker exec "$REDIS_CONTAINER" \
    sh -c "redis-cli --no-auth-warning -a '$REDIS_PASSWORD' SAVE >/dev/null"
  docker exec "$REDIS_CONTAINER" cat /data/dump.rdb > "$REDIS_DUMP"
  (cd "$TMP" && sha256sum "dump.rdb" > "dump.sha256")

  REDIS_ARCHIVE="$BACKUP_ROOT/redis/redis_${TIMESTAMP}.tar.gz"
  tar czf "$REDIS_ARCHIVE" -C "$TMP" "dump.rdb" "dump.sha256"
  log "-> $REDIS_ARCHIVE"
  rm -rf "$TMP"
else
  log "Redis backup skipped (ENABLE_REDIS_BACKUP=0)"
fi

log "MinIO: bucket + checksum + archive"
MINIO_CONTAINER="$(compose ps -q minio)"
[ -n "$MINIO_CONTAINER" ] || { error "MinIO container is not running"; exit 1; }

TMP="$(mktemp -d)"
docker cp "$MINIO_CONTAINER:/data/$MINIO_BUCKET" "$TMP/"

MINIO_TAR="$TMP/${MINIO_BUCKET}.tar.gz"
tar czf "$MINIO_TAR" -C "$TMP" "$MINIO_BUCKET"
(cd "$TMP" && sha256sum "${MINIO_BUCKET}.tar.gz" > "${MINIO_BUCKET}.sha256")

MINIO_ARCHIVE="$BACKUP_ROOT/minio/${MINIO_BUCKET}_${TIMESTAMP}.tar.gz"
tar czf "$MINIO_ARCHIVE" -C "$TMP" "${MINIO_BUCKET}.tar.gz" "${MINIO_BUCKET}.sha256"
log "-> $MINIO_ARCHIVE"
rm -rf "$TMP"

log "Cleaning backups older than $BACKUP_RETENTION_DAYS days"
find "$BACKUP_ROOT" -type f -mtime +"$BACKUP_RETENTION_DAYS" -delete

log "Backup completed successfully"
