#!/usr/bin/env bash
set -euo pipefail
# chmod +x scripts/restore_all.sh
# scripts/restore_all.sh

# === 0) Блокировка и трапы ===
LOCKFILE="/var/lock/restore_all.lock"
exec 200>"$LOCKFILE"
flock -n 200 || { echo "$(date '+%F %T') [ERROR] Restore already running"; exit 1; }
trap 'rc=$?; flock -u 200; rm -f "$LOCKFILE"; [ $rc -ne 0 ] && echo "$(date "+%F %T") [ERROR] Restore failed (rc=$rc)"; exit $rc' EXIT

log(){ echo "$(date '+%F %T') [INFO] $*"; }
error(){ echo "$(date '+%F %T') [ERROR] $*" >&2; }

# === 1) Подготовка ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
[ -f "$PROJECT_ROOT/.env" ] || { error ".env not found"; exit 1; }
# shellcheck disable=SC1091
source "$PROJECT_ROOT/.env"

: "${DB_NAME:?DB_NAME not set}"
: "${DB_USER:?DB_USER not set}"
: "${DB_PASSWORD:?DB_PASSWORD not set}"
: "${REDIS_PASSWORD:?REDIS_PASSWORD not set}"
: "${MINIO_BUCKET:?MINIO_BUCKET not set}"

BACKUP_ROOT="$PROJECT_ROOT/backups"
latest() { ls -1t "$1"/*.tar.gz 2>/dev/null | head -n1; }

# === 2) Остановить пишущие сервисы (но НЕ БД) ===
log "[0/6] Stopping writers: backend frontend bot (если есть)"
docker-compose stop backend frontend bot 2>/dev/null || true

# === 3) PostgreSQL ===
log "[1/6] Restoring PostgreSQL"
docker-compose up -d db

# дождаться готовности БД
for i in {1..30}; do
  if docker-compose exec -T db bash -lc "export PGPASSWORD='$DB_PASSWORD'; pg_isready -U '$DB_USER' -d '$DB_NAME' >/dev/null 2>&1"; then
    break
  fi
  sleep 1
done

PG_ARCHIVE="$(latest "$BACKUP_ROOT/postgres")"; [ -f "$PG_ARCHIVE" ] || { error "Postgres archive not found"; exit 1; }
TMP="$(mktemp -d)"
tar xzf "$PG_ARCHIVE" -C "$TMP"

# твой бэкап пишет в .sha256 абсолютный путь → проверяем хэш вручную
exp_pg_hash="$(awk '{print $1}' "$TMP/${DB_NAME}.sha256")"
act_pg_hash="$(sha256sum "$TMP/${DB_NAME}.dump" | awk '{print $1}')"
[ "$exp_pg_hash" = "$act_pg_hash" ] || { error "Postgres dump checksum mismatch"; exit 1; }

docker-compose exec -T db bash -lc "export PGPASSWORD='$DB_PASSWORD'; createdb -U '$DB_USER' '$DB_NAME' 2>/dev/null || true"
docker-compose exec -T db bash -lc "export PGPASSWORD='$DB_PASSWORD'; pg_restore -U '$DB_USER' -d '$DB_NAME' --clean --no-owner --if-exists" < "$TMP/${DB_NAME}.dump"
rm -rf "$TMP"
log "→ PostgreSQL restored from $(basename "$PG_ARCHIVE")"

# === 4) Redis ===
log "[2/6] Restoring Redis (RDB)"
REDIS_ARCHIVE="$(latest "$BACKUP_ROOT/redis")"; [ -f "$REDIS_ARCHIVE" ] || { error "Redis archive not found"; exit 1; }
TMP="$(mktemp -d)"
tar xzf "$REDIS_ARCHIVE" -C "$TMP"

# .sha256 у тебя содержит абсолютный путь → сверяем только хэш
exp_rdb_hash="$(awk '{print $1}' "$TMP/dump.sha256")"
act_rdb_hash="$(sha256sum "$TMP/dump.rdb" | awk '{print $1}')"
[ "$exp_rdb_hash" = "$act_rdb_hash" ] || { error "Redis RDB checksum mismatch"; exit 1; }

# найдём путь маунта /data у контейнера redis и заменим содержимое
docker-compose up -d redis
REDIS_CID="$(docker-compose ps -q redis)"; [ -n "$REDIS_CID" ] || { error "Redis container not found"; exit 1; }
REDIS_MNT="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Source}}{{end}}{{end}}' "$REDIS_CID")"
[ -d "$REDIS_MNT" ] || { error "Redis /data mountpoint not found"; exit 1; }

docker-compose stop redis
rm -f "$REDIS_MNT"/appendonly.aof* || true
rm -f "$REDIS_MNT"/dump.rdb || true
cp "$TMP/dump.rdb" "$REDIS_MNT/dump.rdb"
rm -rf "$TMP"
docker-compose up -d redis
log "→ Redis restored from $(basename "$REDIS_ARCHIVE")"

# === 5) MinIO ===
log "[3/6] Restoring MinIO bucket"
MINIO_ARCHIVE="$(latest "$BACKUP_ROOT/minio")"; [ -f "$MINIO_ARCHIVE" ] || { error "MinIO archive not found"; exit 1; }
TMP="$(mktemp -d)"
tar xzf "$MINIO_ARCHIVE" -C "$TMP"

# у тебя .sha256 содержит HASH и имя '-' (stdin). Сравним хэши вручную.
exp_minio_hash="$(awk '{print $1}' "$TMP/${MINIO_BUCKET}.sha256")"
act_minio_hash="$(sha256sum "$TMP/${MINIO_BUCKET}.tar" | awk '{print $1}')"
[ "$exp_minio_hash" = "$act_minio_hash" ] || { error "MinIO bucket checksum mismatch"; exit 1; }

docker-compose up -d minio
MINIO_CID="$(docker-compose ps -q minio)"; [ -n "$MINIO_CID" ] || { error "MinIO container not found"; exit 1; }
MINIO_MNT="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Source}}{{end}}{{end}}' "$MINIO_CID")"
[ -d "$MINIO_MNT" ] || { error "MinIO /data mountpoint not found"; exit 1; }

docker-compose stop minio
rm -rf "$MINIO_MNT/$MINIO_BUCKET"
# ВНУТРЕННИЙ файл — это gz-тар, хоть и называется .tar → распаковываем с -z
tar xzf "$TMP/${MINIO_BUCKET}.tar" -C "$MINIO_MNT"
rm -rf "$TMP"
docker-compose up -d minio
log "→ MinIO bucket '$MINIO_BUCKET' restored from $(basename "$MINIO_ARCHIVE")"

# === 6) Поднимаем приложение ===
log "[5/6] Starting services: backend bot frontend"
docker-compose up -d backend bot frontend

log "Restore completed successfully"
