#!/usr/bin/env bash
#
# restore_all.sh
# ------------------------------------------------------------
# Назначение:
#   Восстанавливает PostgreSQL, Redis и MinIO из последних архивов
#   в каталоге ./backups.
#
# ВАЖНО:
#   - Скрипт останавливает прикладные сервисы на время восстановления.
#   - Текущие данные в PostgreSQL/Redis/MinIO будут заменены.
#   - Запускать только при чётком понимании последствий.
#
# Что нужно перед запуском:
#   1) Запущенный Docker.
#   2) Файл .env в корне проекта.
#   3) Подготовленные архивы в:
#      ./backups/postgres
#      ./backups/redis
#      ./backups/minio
#   4) Утилиты: docker, tar, sha256sum, flock, mktemp.
#
# Какие переменные использует скрипт:
#   - POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD
#     (если их нет, пробует DB_NAME / DB_USER / DB_PASSWORD).
#   - ENABLE_REDIS_BACKUP (опционально, по умолчанию 0)
#     0 = Redis НЕ восстанавливается, 1 = Redis восстанавливается
#   - REDIS_PASSWORD (обязателен только если ENABLE_REDIS_BACKUP=1)
#   - MINIO_BUCKET
#
# Быстрый запуск:
#   chmod +x scripts/restore_all.sh
#   ./scripts/restore_all.sh
#
# Что делает скрипт по шагам:
#   1) Ставит lock-файл (./.locks/restore_all.lock), чтобы не было
#      параллельных запусков.
#   2) Останавливает пишущие сервисы (backend/bot/nginx/frontend,
#      если они есть в compose), чтобы не получить рассинхронизацию.
#   3) Восстанавливает PostgreSQL из последнего архива:
#      - проверяет sha256
#      - выполняет pg_restore --clean --if-exists
#   4) Если ENABLE_REDIS_BACKUP=1: восстанавливает Redis из
#      последнего архива (проверяет sha256 и заменяет /data/dump.rdb).
#   5) Восстанавливает MinIO из последнего архива:
#      - проверяет sha256
#      - заменяет каталог /data/$MINIO_BUCKET
#   6) Поднимает остановленные ранее прикладные сервисы обратно.
#
# Практические рекомендации:
#   - Сначала выполните тестовое восстановление на staging, а не сразу
#     в production.
#   - После восстановления проверьте ключевые сценарии приложения
#     (вход, список комнат, загрузка/чтение файлов из MinIO и т.д.).
#   - Перед боевым restore желательно сделать свежий backup, чтобы
#     иметь точку отката.
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
LOCKFILE="$LOCK_DIR/restore_all.lock"
exec 200>"$LOCKFILE"
flock -n 200 || { error "Restore already running"; exit 1; }

cleanup() {
  local rc=$?
  flock -u 200 || true
  rm -f "$LOCKFILE" || true
  if [ "$rc" -ne 0 ]; then
    error "Restore failed (rc=$rc)"
  fi
  exit "$rc"
}
trap cleanup EXIT

BACKUP_ROOT="$PROJECT_ROOT/backups"
[ -d "$BACKUP_ROOT" ] || { error "Backups folder not found: $BACKUP_ROOT"; exit 1; }

latest_archive() {
  local dir="$1"
  ls -1t "$dir"/*.tar.gz 2>/dev/null | head -n1 || true
}

mapfile -t COMPOSE_SERVICES < <(compose config --services 2>/dev/null || true)
service_exists() {
  local needle="$1"
  local svc
  for svc in "${COMPOSE_SERVICES[@]}"; do
    [ "$svc" = "$needle" ] && return 0
  done
  return 1
}

WRITER_SERVICES=()
for candidate in backend bot nginx frontend; do
  if service_exists "$candidate"; then
    WRITER_SERVICES+=("$candidate")
  fi
done

if [ "${#WRITER_SERVICES[@]}" -gt 0 ]; then
  log "Stopping writers: ${WRITER_SERVICES[*]}"
  compose stop "${WRITER_SERVICES[@]}" >/dev/null || true
fi

log "Restoring PostgreSQL"
compose up -d db >/dev/null

ready=0
for _ in {1..60}; do
  if compose exec -e PGPASSWORD="$DB_PASSWORD" -T db sh -lc "pg_isready -U '$DB_USER' -d '$DB_NAME' >/dev/null 2>&1"; then
    ready=1
    break
  fi
  sleep 1
done
[ "$ready" -eq 1 ] || { error "PostgreSQL is not ready"; exit 1; }

PG_ARCHIVE="$(latest_archive "$BACKUP_ROOT/postgres")"
[ -n "$PG_ARCHIVE" ] || { error "Postgres archive not found"; exit 1; }
TMP="$(mktemp -d)"
tar xzf "$PG_ARCHIVE" -C "$TMP"
[ -f "$TMP/${DB_NAME}.dump" ] || { error "Dump file not found in archive: ${DB_NAME}.dump"; exit 1; }
[ -f "$TMP/${DB_NAME}.sha256" ] || { error "Checksum file not found in archive: ${DB_NAME}.sha256"; exit 1; }

exp_pg_hash="$(awk '{print $1}' "$TMP/${DB_NAME}.sha256")"
act_pg_hash="$(sha256sum "$TMP/${DB_NAME}.dump" | awk '{print $1}')"
[ "$exp_pg_hash" = "$act_pg_hash" ] || { error "Postgres dump checksum mismatch"; exit 1; }

compose exec -e PGPASSWORD="$DB_PASSWORD" -T db sh -lc "createdb -U '$DB_USER' '$DB_NAME' 2>/dev/null || true"
compose exec -e PGPASSWORD="$DB_PASSWORD" -T db sh -lc "pg_restore -U '$DB_USER' -d '$DB_NAME' --clean --no-owner --if-exists" < "$TMP/${DB_NAME}.dump"
rm -rf "$TMP"
log "-> PostgreSQL restored from $(basename "$PG_ARCHIVE")"

if [ "$ENABLE_REDIS_BACKUP" = "1" ]; then
  log "Restoring Redis (RDB)"
  REDIS_ARCHIVE="$(latest_archive "$BACKUP_ROOT/redis")"
  [ -n "$REDIS_ARCHIVE" ] || { error "Redis archive not found"; exit 1; }
  TMP="$(mktemp -d)"
  tar xzf "$REDIS_ARCHIVE" -C "$TMP"
  [ -f "$TMP/dump.rdb" ] || { error "Redis dump not found in archive"; exit 1; }
  [ -f "$TMP/dump.sha256" ] || { error "Redis checksum file not found in archive"; exit 1; }

  exp_rdb_hash="$(awk '{print $1}' "$TMP/dump.sha256")"
  act_rdb_hash="$(sha256sum "$TMP/dump.rdb" | awk '{print $1}')"
  [ "$exp_rdb_hash" = "$act_rdb_hash" ] || { error "Redis dump checksum mismatch"; exit 1; }

  compose up -d redis >/dev/null
  REDIS_CID="$(compose ps -q redis)"
  [ -n "$REDIS_CID" ] || { error "Redis container not found"; exit 1; }
  compose stop redis >/dev/null

  REDIS_IMAGE="$(docker inspect -f '{{.Config.Image}}' "$REDIS_CID")"
  docker run --rm --volumes-from "$REDIS_CID" --entrypoint sh "$REDIS_IMAGE" \
    -c 'rm -f /data/appendonly.aof* /data/dump.rdb'
  docker cp "$TMP/dump.rdb" "$REDIS_CID:/data/dump.rdb"
  rm -rf "$TMP"
  compose up -d redis >/dev/null
  log "-> Redis restored from $(basename "$REDIS_ARCHIVE")"
else
  log "Redis restore skipped (ENABLE_REDIS_BACKUP=0)"
fi

log "Restoring MinIO bucket"
MINIO_ARCHIVE="$(latest_archive "$BACKUP_ROOT/minio")"
[ -n "$MINIO_ARCHIVE" ] || { error "MinIO archive not found"; exit 1; }
TMP="$(mktemp -d)"
tar xzf "$MINIO_ARCHIVE" -C "$TMP"
[ -f "$TMP/${MINIO_BUCKET}.tar.gz" ] || { error "MinIO bucket tar not found in archive"; exit 1; }
[ -f "$TMP/${MINIO_BUCKET}.sha256" ] || { error "MinIO checksum file not found in archive"; exit 1; }

exp_minio_hash="$(awk '{print $1}' "$TMP/${MINIO_BUCKET}.sha256")"
act_minio_hash="$(sha256sum "$TMP/${MINIO_BUCKET}.tar.gz" | awk '{print $1}')"
[ "$exp_minio_hash" = "$act_minio_hash" ] || { error "MinIO bucket checksum mismatch"; exit 1; }

tar xzf "$TMP/${MINIO_BUCKET}.tar.gz" -C "$TMP"
[ -d "$TMP/$MINIO_BUCKET" ] || { error "MinIO bucket directory not found after unpack"; exit 1; }

compose up -d minio >/dev/null
MINIO_CID="$(compose ps -q minio)"
[ -n "$MINIO_CID" ] || { error "MinIO container not found"; exit 1; }
compose stop minio >/dev/null

MINIO_IMAGE="$(docker inspect -f '{{.Config.Image}}' "$MINIO_CID")"
docker run --rm --volumes-from "$MINIO_CID" --entrypoint sh "$MINIO_IMAGE" \
  -c "rm -rf '/data/$MINIO_BUCKET'"
docker cp "$TMP/$MINIO_BUCKET" "$MINIO_CID:/data/"
rm -rf "$TMP"
compose up -d minio >/dev/null
log "-> MinIO bucket '$MINIO_BUCKET' restored from $(basename "$MINIO_ARCHIVE")"

if [ "${#WRITER_SERVICES[@]}" -gt 0 ]; then
  log "Starting services: ${WRITER_SERVICES[*]}"
  compose up -d "${WRITER_SERVICES[@]}" >/dev/null
fi

log "Restore completed successfully"
