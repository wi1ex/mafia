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
#   - Запускать только при четком понимании последствий.
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
# sed -i 's/\r$//' .env
# grep -n $'\r' .env
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
#   3) Выбирает последний полный набор PostgreSQL/Redis/MinIO с общим
#      timestamp и до остановки приложений проверяет архивы/checksum.
#   4) Восстанавливает PostgreSQL из выбранного набора:
#      - проверяет sha256
#      - выполняет pg_restore --clean --if-exists
#   5) Если ENABLE_REDIS_BACKUP=1: восстанавливает Redis из того же
#      набора (удаляет AOF, заменяет /data/dump.rdb и исправляет права).
#   6) Восстанавливает MinIO из того же набора:
#      - проверяет sha256
#      - принимает текущий внутренний .tar.gz и исторический .tar
#      - заменяет каталог /data/$MINIO_BUCKET и исправляет права
#   7) Поднимает только те прикладные сервисы, которые работали до restore.
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
umask 077

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
[[ "$DB_NAME" =~ ^[A-Za-z_][A-Za-z0-9_.-]{0,62}$ ]] || { error "Invalid PostgreSQL database name"; exit 1; }
[[ "$DB_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]{0,62}$ ]] || { error "Invalid PostgreSQL user name"; exit 1; }
if [[ ! "$MINIO_BUCKET" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]] ||
   [[ "$MINIO_BUCKET" == *..* ]]; then
  error "Invalid MinIO bucket name"
  exit 1
fi
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

RESTORE_STAGE=""
WRITER_SERVICES=()
WRITERS_STOPPED=0
DATA_MUTATION_STARTED=0
cleanup() {
  local rc=$?
  if [ "$rc" -ne 0 ] && [ "$WRITERS_STOPPED" -eq 1 ] && [ "${#WRITER_SERVICES[@]}" -gt 0 ]; then
    if [ "$DATA_MUTATION_STARTED" -eq 0 ]; then
      log "Restore failed before data mutation; starting previously running application services"
      compose up -d "${WRITER_SERVICES[@]}" >/dev/null || error "Failed to restart application services"
    else
      error "Restore failed after data mutation started; application services remain stopped to avoid serving a mixed-store state"
      compose stop "${WRITER_SERVICES[@]}" >/dev/null \
        || error "Failed to stop one or more application services after restore failure"
      error "Inspect PostgreSQL, Redis and MinIO, then rerun the same snapshot or perform a verified rollback before starting writers"
    fi
  fi
  if [ -n "${RESTORE_STAGE:-}" ] && [ -d "$RESTORE_STAGE" ]; then
    rm -rf -- "$RESTORE_STAGE" || true
  fi
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

snapshot_timestamp_from_archive() {
  local base="${1##*/}"
  if [[ "$base" =~ _([0-9]{8}_[0-9]{4})\.tar\.gz$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return 0
  fi
  return 1
}

latest_complete_snapshot_timestamp() {
  local archive timestamp
  local -a candidates=()

  # Historical backup scripts already used the same timestamp suffix for all
  # stores, so this also selects old sets without requiring a new manifest.
  for archive in "$BACKUP_ROOT/postgres/${DB_NAME}"_*.tar.gz; do
    [ -f "$archive" ] || continue
    timestamp="$(snapshot_timestamp_from_archive "$archive")" || continue
    candidates+=("$timestamp")
  done

  [ "${#candidates[@]}" -gt 0 ] || return 1
  while IFS= read -r timestamp; do
    [ -n "$timestamp" ] || continue
    [ -f "$BACKUP_ROOT/postgres/${DB_NAME}_${timestamp}.tar.gz" ] || continue
    [ -f "$BACKUP_ROOT/minio/${MINIO_BUCKET}_${timestamp}.tar.gz" ] || continue
    if [ "$ENABLE_REDIS_BACKUP" = "1" ]; then
      [ -f "$BACKUP_ROOT/redis/redis_${timestamp}.tar.gz" ] || continue
    fi
    printf '%s\n' "$timestamp"
    return 0
  done < <(printf '%s\n' "${candidates[@]}" | sort -ru)

  return 1
}

validate_tar_archive() {
  local archive="$1"
  local entry
  while IFS= read -r entry; do
    case "$entry" in
      /*|../*|*/../*|*/..)
        error "Unsafe path in archive $(basename "$archive"): $entry"
        return 1
        ;;
    esac
  done < <(tar tzf "$archive")
}

log "Preflight: selecting and verifying restore archives"
RESTORE_STAGE="$(mktemp -d)"

REQUIRED_SNAPSHOT_STORES="PostgreSQL/MinIO"
if [ "$ENABLE_REDIS_BACKUP" = "1" ]; then
  REQUIRED_SNAPSHOT_STORES="$REQUIRED_SNAPSHOT_STORES/Redis"
fi
SNAPSHOT_TIMESTAMP="$(latest_complete_snapshot_timestamp)" \
  || { error "No complete $REQUIRED_SNAPSHOT_STORES snapshot set with a common timestamp was found"; exit 1; }
PG_ARCHIVE="$BACKUP_ROOT/postgres/${DB_NAME}_${SNAPSHOT_TIMESTAMP}.tar.gz"
MINIO_ARCHIVE="$BACKUP_ROOT/minio/${MINIO_BUCKET}_${SNAPSHOT_TIMESTAMP}.tar.gz"
REDIS_ARCHIVE=""
if [ "$ENABLE_REDIS_BACKUP" = "1" ]; then
  REDIS_ARCHIVE="$BACKUP_ROOT/redis/redis_${SNAPSHOT_TIMESTAMP}.tar.gz"
fi
log "Selected snapshot timestamp: $SNAPSHOT_TIMESTAMP"

validate_tar_archive "$PG_ARCHIVE"
PG_STAGE="$RESTORE_STAGE/postgres"
mkdir -p "$PG_STAGE"
tar xzf "$PG_ARCHIVE" -C "$PG_STAGE"
[ -f "$PG_STAGE/${DB_NAME}.dump" ] || { error "Dump file not found in archive: ${DB_NAME}.dump"; exit 1; }
[ -f "$PG_STAGE/${DB_NAME}.sha256" ] || { error "Checksum file not found in archive: ${DB_NAME}.sha256"; exit 1; }
exp_pg_hash="$(awk '{print $1}' "$PG_STAGE/${DB_NAME}.sha256")"
act_pg_hash="$(sha256sum "$PG_STAGE/${DB_NAME}.dump" | awk '{print $1}')"
[ "$exp_pg_hash" = "$act_pg_hash" ] || { error "Postgres dump checksum mismatch"; exit 1; }

REDIS_STAGE=""
if [ "$ENABLE_REDIS_BACKUP" = "1" ]; then
  validate_tar_archive "$REDIS_ARCHIVE"
  REDIS_STAGE="$RESTORE_STAGE/redis"
  mkdir -p "$REDIS_STAGE"
  tar xzf "$REDIS_ARCHIVE" -C "$REDIS_STAGE"
  [ -f "$REDIS_STAGE/dump.rdb" ] || { error "Redis dump not found in archive"; exit 1; }
  [ -f "$REDIS_STAGE/dump.sha256" ] || { error "Redis checksum file not found in archive"; exit 1; }
  exp_rdb_hash="$(awk '{print $1}' "$REDIS_STAGE/dump.sha256")"
  act_rdb_hash="$(sha256sum "$REDIS_STAGE/dump.rdb" | awk '{print $1}')"
  [ "$exp_rdb_hash" = "$act_rdb_hash" ] || { error "Redis dump checksum mismatch"; exit 1; }
fi

validate_tar_archive "$MINIO_ARCHIVE"
MINIO_STAGE="$RESTORE_STAGE/minio"
MINIO_ARCHIVE_STAGE="$MINIO_STAGE/archive"
MINIO_CONTENT_STAGE="$MINIO_STAGE/content"
mkdir -p "$MINIO_ARCHIVE_STAGE" "$MINIO_CONTENT_STAGE"
tar xzf "$MINIO_ARCHIVE" -C "$MINIO_ARCHIVE_STAGE"
[ -f "$MINIO_ARCHIVE_STAGE/${MINIO_BUCKET}.sha256" ] || { error "MinIO checksum file not found in archive"; exit 1; }
if [ -f "$MINIO_ARCHIVE_STAGE/${MINIO_BUCKET}.tar.gz" ]; then
  MINIO_BUCKET_ARCHIVE="$MINIO_ARCHIVE_STAGE/${MINIO_BUCKET}.tar.gz"
elif [ -f "$MINIO_ARCHIVE_STAGE/${MINIO_BUCKET}.tar" ]; then
  # Legacy project backups used a gzip-compressed tar stream with a .tar suffix.
  MINIO_BUCKET_ARCHIVE="$MINIO_ARCHIVE_STAGE/${MINIO_BUCKET}.tar"
else
  error "MinIO bucket tar not found in archive (.tar.gz or legacy .tar)"
  exit 1
fi
exp_minio_hash="$(awk '{print $1}' "$MINIO_ARCHIVE_STAGE/${MINIO_BUCKET}.sha256")"
act_minio_hash="$(sha256sum "$MINIO_BUCKET_ARCHIVE" | awk '{print $1}')"
[ "$exp_minio_hash" = "$act_minio_hash" ] || { error "MinIO bucket checksum mismatch"; exit 1; }
validate_tar_archive "$MINIO_BUCKET_ARCHIVE"
tar xzf "$MINIO_BUCKET_ARCHIVE" -C "$MINIO_CONTENT_STAGE"
[ -d "$MINIO_CONTENT_STAGE/$MINIO_BUCKET" ] || { error "MinIO bucket directory not found after unpack"; exit 1; }
log "Preflight completed successfully"

if ! COMPOSE_SERVICES_RAW="$(compose config --services 2>/dev/null)"; then
  error "Docker Compose configuration is invalid; refusing to restore while writer state is unknown"
  exit 1
fi
[ -n "$COMPOSE_SERVICES_RAW" ] \
  || { error "Docker Compose returned no services; refusing to restore"; exit 1; }
mapfile -t COMPOSE_SERVICES <<< "$COMPOSE_SERVICES_RAW"
service_exists() {
  local needle="$1"
  local svc
  for svc in "${COMPOSE_SERVICES[@]}"; do
    [ "$svc" = "$needle" ] && return 0
  done
  return 1
}

service_is_running() {
  local service="$1"
  local cid cid_output state
  if ! cid_output="$(compose ps -q "$service" 2>/dev/null)"; then
    return 2
  fi
  cid="${cid_output%%$'\n'*}"
  [ -n "$cid" ] || return 1
  if ! state="$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null)"; then
    return 2
  fi
  case "$state" in
    true) return 0 ;;
    false) return 1 ;;
    *) return 2 ;;
  esac
}

for candidate in backend bot nginx frontend; do
  if service_exists "$candidate"; then
    if service_is_running "$candidate"; then
      WRITER_SERVICES+=("$candidate")
    else
      running_check_rc=$?
      if [ "$running_check_rc" -ne 1 ]; then
        error "Could not determine whether writer service '$candidate' is running"
        exit 1
      fi
    fi
  fi
done

if [ "${#WRITER_SERVICES[@]}" -gt 0 ]; then
  log "Stopping writers: ${WRITER_SERVICES[*]}"
  WRITERS_STOPPED=1
  compose stop "${WRITER_SERVICES[@]}" >/dev/null
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

# From this point onward a failure may leave stores at different restore steps.
# The EXIT trap therefore keeps writers stopped until a verified rerun/rollback.
DATA_MUTATION_STARTED=1
compose exec -e PGPASSWORD="$DB_PASSWORD" -T db sh -lc "createdb -U '$DB_USER' '$DB_NAME' 2>/dev/null || true"
compose exec -e PGPASSWORD="$DB_PASSWORD" -T db sh -lc "pg_restore -U '$DB_USER' -d '$DB_NAME' --clean --no-owner --if-exists --exit-on-error --single-transaction" < "$PG_STAGE/${DB_NAME}.dump"
log "-> PostgreSQL restored from $(basename "$PG_ARCHIVE")"

if [ "$ENABLE_REDIS_BACKUP" = "1" ]; then
  log "Restoring Redis (RDB)"
  compose up -d redis >/dev/null
  REDIS_CID="$(compose ps -q redis)"
  [ -n "$REDIS_CID" ] || { error "Redis container not found"; exit 1; }
  compose stop redis >/dev/null

  REDIS_IMAGE="$(docker inspect -f '{{.Config.Image}}' "$REDIS_CID")"
  REDIS_DATA_OWNER="$(docker run --rm --user 0:0 --volumes-from "$REDIS_CID" --entrypoint sh "$REDIS_IMAGE" \
    -c 'stat -c "%u:%g" /data')"
  [[ "$REDIS_DATA_OWNER" =~ ^[0-9]+:[0-9]+$ ]] \
    || { error "Could not determine numeric Redis /data owner"; exit 1; }
  docker run --rm --user 0:0 --volumes-from "$REDIS_CID" --entrypoint sh "$REDIS_IMAGE" \
    -c 'rm -rf -- /data/appendonlydir /data/appendonly.aof /data/appendonly.aof.* /data/dump.rdb'
  docker cp "$REDIS_STAGE/dump.rdb" "$REDIS_CID:/data/dump.rdb"
  docker run --rm --user 0:0 --volumes-from "$REDIS_CID" --entrypoint sh "$REDIS_IMAGE" \
    -c "chown '$REDIS_DATA_OWNER' /data/dump.rdb && chmod 600 /data/dump.rdb"
  compose up -d redis >/dev/null
  log "-> Redis restored from $(basename "$REDIS_ARCHIVE")"
else
  log "Redis restore skipped (ENABLE_REDIS_BACKUP=0)"
fi

log "Restoring MinIO bucket"
compose up -d minio >/dev/null
MINIO_CID="$(compose ps -q minio)"
[ -n "$MINIO_CID" ] || { error "MinIO container not found"; exit 1; }
compose stop minio >/dev/null

MINIO_IMAGE="$(docker inspect -f '{{.Config.Image}}' "$MINIO_CID")"
MINIO_DATA_OWNER="$(docker run --rm --user 0:0 --volumes-from "$MINIO_CID" --entrypoint sh "$MINIO_IMAGE" \
  -c 'stat -c "%u:%g" /data')"
[[ "$MINIO_DATA_OWNER" =~ ^[0-9]+:[0-9]+$ ]] \
  || { error "Could not determine numeric MinIO /data owner"; exit 1; }
docker run --rm --user 0:0 --volumes-from "$MINIO_CID" --entrypoint sh "$MINIO_IMAGE" \
  -c "rm -rf '/data/$MINIO_BUCKET'"
docker cp "$MINIO_CONTENT_STAGE/$MINIO_BUCKET" "$MINIO_CID:/data/"
docker run --rm --user 0:0 --volumes-from "$MINIO_CID" --entrypoint sh "$MINIO_IMAGE" \
  -c "chown -R '$MINIO_DATA_OWNER' '/data/$MINIO_BUCKET' && chmod -R u+rwX,go-rwx '/data/$MINIO_BUCKET'"
compose up -d minio >/dev/null
log "-> MinIO bucket '$MINIO_BUCKET' restored from $(basename "$MINIO_ARCHIVE")"

if [ "${#WRITER_SERVICES[@]}" -gt 0 ]; then
  log "Starting services: ${WRITER_SERVICES[*]}"
  compose up -d "${WRITER_SERVICES[@]}" >/dev/null
  WRITERS_STOPPED=0
fi

log "Restore completed successfully"
