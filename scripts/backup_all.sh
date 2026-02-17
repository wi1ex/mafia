#!/usr/bin/env bash
set -euo pipefail
# chmod +x scripts/backup_all.sh
# scripts/backup_all.sh

# === 0) Блокировка и трапы ===
LOCKFILE="/var/lock/backup_all.lock"
exec 200>"$LOCKFILE"
flock -n 200 || { echo "$(date '+%F %T') [ERROR] Backup already running"; exit 1; }

cleanup() {
  rc=$?
  flock -u 200
  rm -f "$LOCKFILE"
  if [ $rc -ne 0 ]; then
    echo "$(date '+%F %T') [ERROR] Backup failed (rc=$rc)"
  fi
  exit $rc
}
trap cleanup EXIT

log(){ echo "$(date '+%F %T') [INFO] $*"; }
error(){ echo "$(date '+%F %T') [ERROR] $*" >&2; }

# === 1) Подготовка ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
[ -f "$PROJECT_ROOT/.env" ] || { error ".env not found"; exit 1; }
source "$PROJECT_ROOT/.env"

TIMESTAMP="$(date +'%Y%m%d_%H%M')"
BACKUP_ROOT="$PROJECT_ROOT/backups"
mkdir -p \
  "$BACKUP_ROOT/postgres" \
  "$BACKUP_ROOT/redis" \
  "$BACKUP_ROOT/minio"

: "${COMPOSE_PROJECT_NAME:=$(basename "$PROJECT_ROOT")}"
: "${DB_NAME:?DB_NAME not set}"
: "${DB_USER:?DB_USER not set}"
: "${DB_PASSWORD:?DB_PASSWORD not set}"
: "${REDIS_PASSWORD:?REDIS_PASSWORD not set}"
: "${MINIO_BUCKET:?MINIO_BUCKET not set}"

# === 2) PostgreSQL ===
log "PostgreSQL: dump + checksum + archive"
PG_CONTAINER=$(docker-compose ps -q db)
[ -n "$PG_CONTAINER" ] || { error "Postgres container not found"; exit 1; }

# временная рабочая директория
TMP=$(mktemp -d)
PG_DUMP="$TMP/${DB_NAME}.dump"
docker exec "$PG_CONTAINER" \
  sh -c "export PGPASSWORD='$DB_PASSWORD' && pg_dump -U '$DB_USER' -F c '$DB_NAME'" \
  > "$PG_DUMP"

# checksum
sha256sum "$PG_DUMP" > "$TMP/${DB_NAME}.sha256"

# единый архив
PG_ARCHIVE="$BACKUP_ROOT/postgres/${DB_NAME}_${TIMESTAMP}.tar.gz"
tar czf "$PG_ARCHIVE" -C "$TMP" "${DB_NAME}.dump" "${DB_NAME}.sha256"
log "→ $PG_ARCHIVE"

rm -rf "$TMP"

# === 3) Redis ===
log "Redis: dump + checksum + archive"
REDIS_CONTAINER=$(docker-compose ps -q redis)
[ -n "$REDIS_CONTAINER" ] || { error "Redis container not found"; exit 1; }

TMP=$(mktemp -d)
REDIS_DUMP="$TMP/dump.rdb"
docker exec "$REDIS_CONTAINER" \
  sh -c "redis-cli --no-auth-warning -a '$REDIS_PASSWORD' SAVE"
docker exec "$REDIS_CONTAINER" \
  cat /data/dump.rdb > "$REDIS_DUMP"

sha256sum "$REDIS_DUMP" > "$TMP/dump.sha256"

REDIS_ARCHIVE="$BACKUP_ROOT/redis/redis_${TIMESTAMP}.tar.gz"
tar czf "$REDIS_ARCHIVE" -C "$TMP" "dump.rdb" "dump.sha256"
log "→ $REDIS_ARCHIVE"

rm -rf "$TMP"

# === 4) MinIO ===
log "MinIO: bucket + checksum + archive"
MINIO_CONTAINER=$(docker-compose ps -q minio)
[ -n "$MINIO_CONTAINER" ] || { error "MinIO container not found"; exit 1; }

TMP=$(mktemp -d)
# скопировать бакет на хост
docker cp "$MINIO_CONTAINER:/data/$MINIO_BUCKET" "$TMP/"

# checksum для каталога (рекурсивно)
tar czf - -C "$TMP" "$MINIO_BUCKET" | tee "$TMP/${MINIO_BUCKET}.tar" \
  | sha256sum > "$TMP/${MINIO_BUCKET}.sha256"

# итоговый архив включает уже готовый tar-байтстрим и sha
MINIO_ARCHIVE="$BACKUP_ROOT/minio/${MINIO_BUCKET}_${TIMESTAMP}.tar.gz"
tar czf "$MINIO_ARCHIVE" -C "$TMP" \
  "${MINIO_BUCKET}.tar" "${MINIO_BUCKET}.sha256"
log "→ $MINIO_ARCHIVE"

rm -rf "$TMP"

# === 5) Ротация ===
log "Cleaning backups older than 7 days"
find "$BACKUP_ROOT" -type f -mtime +7 -delete

log "Backup completed successfully"
