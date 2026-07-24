from __future__ import annotations
import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from time import time
from typing import Any
from sqlalchemy import select
from ..api.utils import (
    delete_stale_unverified_accounts,
    emit_auth_profile_sync,
    emit_expired_timed_sanctions_chat_notices,
    fetch_online_user_ids,
    notify_expiring_profile_subscriptions,
    sync_expired_profile_subscriptions,
)
from ..models.user import User
from ..security.parameters import refresh_app_settings
from ..services.minio import delete_stale_pending_chat_images_async, ensure_bucket
from ..services.nickname_limits import reset_monthly_nickname_change_limits
from ..services.telegram import get_telegram_nickname
from .clients import get_redis
from .db import SessionLocal

__all__ = ["LifespanBackgroundTasks", "verify_runtime_dependencies"]

EMPTY_ROOM_MARKER_TTL_SECONDS = 30 * 24 * 60 * 60
EMPTY_ROOM_GC_SCAN_INTERVAL_SECONDS = 60
TELEGRAM_NICKNAME_SYNC_INTERVAL_SECONDS = 1.0


def _next_local_daily_run_at(*, hour: int, minute: int = 0) -> datetime:
    now = datetime.now().astimezone()
    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return next_run


def _next_monday_utc_run_at(*, hour: int, minute: int = 0) -> datetime:
    now = datetime.now(timezone.utc)
    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    next_run += timedelta(days=(0 - next_run.weekday()) % 7)
    if next_run <= now:
        next_run += timedelta(days=7)
    return next_run


async def verify_runtime_dependencies() -> None:
    await asyncio.gather(get_redis().ping(), asyncio.to_thread(ensure_bucket))


class LifespanBackgroundTasks:
    def __init__(self, log: Any) -> None:
        self._log = log
        self._settings_task: asyncio.Task[None] | None = None
        self._expired_sanctions_chat_task: asyncio.Task[None] | None = None
        self._expired_subscriptions_task: asyncio.Task[None] | None = None
        self._stale_unverified_accounts_task: asyncio.Task[None] | None = None
        self._empty_rooms_gc_task: asyncio.Task[None] | None = None
        self._stale_chat_uploads_task: asyncio.Task[None] | None = None
        self._telegram_nickname_sync_task: asyncio.Task[None] | None = None
        self._empty_room_gc_tasks: dict[int, asyncio.Task[None]] = {}

    def start(self) -> None:
        self._settings_task = asyncio.create_task(self.settings_pubsub_loop())
        self._expired_sanctions_chat_task = asyncio.create_task(self.expired_sanctions_chat_loop())
        self._expired_subscriptions_task = asyncio.create_task(self.expired_profile_subscriptions_loop())
        self._stale_unverified_accounts_task = asyncio.create_task(self.stale_unverified_accounts_loop())
        self._empty_rooms_gc_task = asyncio.create_task(self.empty_rooms_gc_loop())
        self._stale_chat_uploads_task = asyncio.create_task(self.stale_chat_uploads_loop())
        self._telegram_nickname_sync_task = asyncio.create_task(self.telegram_nickname_sync_loop())

    async def stop(self) -> None:
        try:
            managed_tasks = (
                self._settings_task,
                self._expired_sanctions_chat_task,
                self._expired_subscriptions_task,
                self._stale_unverified_accounts_task,
                self._empty_rooms_gc_task,
                self._stale_chat_uploads_task,
                self._telegram_nickname_sync_task,
            )
            for managed_task in managed_tasks:
                await self._cancel_and_wait(managed_task)
            for gc_task in tuple(self._empty_room_gc_tasks.values()):
                await self._cancel_and_wait(gc_task)
            self._empty_room_gc_tasks.clear()
        except Exception:
            self._log.warning("app.shutdown.settings_task_failed")

    @staticmethod
    async def _cancel_and_wait(background_task: asyncio.Task[None] | None) -> None:
        if background_task is None:
            return
        background_task.cancel()
        with suppress(asyncio.CancelledError):
            await background_task

    def schedule_empty_room_gc(self, room_id: int) -> None:
        rid = int(room_id)
        existing = self._empty_room_gc_tasks.get(rid)
        if existing and not existing.done():
            return

        async def _runner() -> None:
            try:
                from ..realtime.utils import gc_empty_room
                await gc_empty_room(rid)
            except asyncio.CancelledError:
                raise
            except Exception:
                self._log.exception("app.rooms.empty_gc.recovery_failed", rid=rid)
            finally:
                current = self._empty_room_gc_tasks.get(rid)
                if current is asyncio.current_task():
                    del self._empty_room_gc_tasks[rid]

        self._empty_room_gc_tasks[rid] = asyncio.create_task(_runner())

    async def recover_empty_rooms_gc(self) -> None:
        r = get_redis()
        try:
            raw_ids = await r.zrange("rooms:index", 0, -1)
        except Exception:
            self._log.exception("app.rooms.empty_gc.index_load_failed")
            return

        room_ids: list[int] = []
        for raw_id in raw_ids or []:
            try:
                rid = int(raw_id)
            except Exception:
                continue
            if rid > 0:
                room_ids.append(rid)

        if not room_ids:
            return

        try:
            async with r.pipeline() as p:
                for rid in room_ids:
                    await p.scard(f"room:{rid}:members")
                    await p.hget(f"room:{rid}:game_state", "phase")
                    await p.get(f"room:{rid}:empty_since")
                rows = await p.execute()
        except Exception:
            self._log.exception("app.rooms.empty_gc.state_load_failed")
            return

        now_ts = str(int(time()))
        for index, rid in enumerate(room_ids):
            raw_occupancy, raw_phase, raw_empty_since = rows[index * 3: index * 3 + 3]
            try:
                occupancy = int(raw_occupancy or 0)
            except Exception:
                continue

            phase = str(raw_phase or "idle")
            if occupancy != 0 or phase != "idle":
                continue

            empty_since = str(raw_empty_since or "")
            try:
                int(empty_since)
            except (TypeError, ValueError):
                try:
                    if int(await r.scard(f"room:{rid}:members") or 0) != 0:
                        continue
                    marker_key = f"room:{rid}:empty_since"
                    if empty_since:
                        await r.set(marker_key, now_ts, xx=True, ex=EMPTY_ROOM_MARKER_TTL_SECONDS)
                    else:
                        await r.set(marker_key, now_ts, nx=True, ex=EMPTY_ROOM_MARKER_TTL_SECONDS)
                except Exception:
                    self._log.exception("app.rooms.empty_gc.empty_since_restore_failed", rid=rid)
                    continue

            self.schedule_empty_room_gc(rid)

    async def empty_rooms_gc_loop(self) -> None:
        try:
            while True:
                try:
                    await self.recover_empty_rooms_gc()
                except Exception:
                    self._log.exception("app.rooms.empty_gc.recovery_loop_failed")
                await asyncio.sleep(EMPTY_ROOM_GC_SCAN_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            pass

    async def stale_chat_uploads_loop(self) -> None:
        try:
            while True:
                next_run = _next_local_daily_run_at(hour=3, minute=0)
                delay_s = max(0.0, (next_run - datetime.now(next_run.tzinfo)).total_seconds())
                await asyncio.sleep(delay_s)
                try:
                    deleted = await delete_stale_pending_chat_images_async()
                    if deleted:
                        self._log.info("app.chat.pending_uploads_cleaned", deleted=deleted)
                except Exception:
                    self._log.exception("app.chat.pending_upload_cleanup_failed")
        except asyncio.CancelledError:
            pass

    async def telegram_nickname_sync_loop(self) -> None:
        try:
            while True:
                next_run = _next_monday_utc_run_at(hour=4)
                delay_s = max(0.0, (next_run - datetime.now(timezone.utc)).total_seconds())
                self._log.info(
                    "app.telegram_nicknames.sync_scheduled",
                    run_at=next_run.isoformat(),
                    delay_s=int(delay_s),
                )
                await asyncio.sleep(delay_s)
                try:
                    await self.sync_telegram_nicknames()
                except Exception:
                    self._log.exception("app.telegram_nicknames.sync_failed")
        except asyncio.CancelledError:
            pass

    async def sync_telegram_nicknames(self) -> None:
        async with SessionLocal() as session:
            rows = await session.execute(
                select(User.id, User.telegram_id)
                .where(User.telegram_id.is_not(None))
                .order_by(User.id.asc())
            )
            verified_users = [
                (int(user_id), int(telegram_id))
                for user_id, telegram_id in rows.all()
                if telegram_id is not None
            ]

        updated = 0
        unchanged = 0
        missing_nickname = 0
        failed = 0
        skipped = 0

        for user_id, telegram_id in verified_users:
            wait_s = TELEGRAM_NICKNAME_SYNC_INTERVAL_SECONDS
            try:
                result = await get_telegram_nickname(chat_id=telegram_id)
                wait_s = max(wait_s, result.retry_after_seconds)
                if not result.ok:
                    failed += 1
                    continue

                if not result.nickname:
                    missing_nickname += 1
                    continue

                async with SessionLocal() as session:
                    user = await session.get(User, user_id)
                    if user is None or int(user.telegram_id or 0) != telegram_id:
                        skipped += 1
                        continue

                    if user.telegram_nickname == result.nickname:
                        unchanged += 1
                        continue

                    user.telegram_nickname = result.nickname
                    await session.commit()
                    updated += 1
            except asyncio.CancelledError:
                raise
            except Exception:
                failed += 1
                self._log.exception(
                    "app.telegram_nicknames.user_sync_failed",
                    user_id=user_id,
                    telegram_id=telegram_id,
                )
            finally:
                await asyncio.sleep(wait_s)

        self._log.info(
            "app.telegram_nicknames.sync_done",
            total=len(verified_users),
            updated=updated,
            unchanged=unchanged,
            missing_nickname=missing_nickname,
            failed=failed,
            skipped=skipped,
        )

    async def settings_pubsub_loop(self) -> None:
        r = get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe("settings:update")
        try:
            async for message in pubsub.listen():
                if not message or message.get("type") != "message":
                    continue
                try:
                    async with SessionLocal() as session:
                        await refresh_app_settings(session)
                except Exception:
                    self._log.warning("app.settings.refresh_failed")
        except asyncio.CancelledError:
            pass
        finally:
            with suppress(Exception):
                await pubsub.unsubscribe("settings:update")
            with suppress(Exception):
                await pubsub.close()

    async def expired_sanctions_chat_loop(self) -> None:
        try:
            while True:
                try:
                    await emit_expired_timed_sanctions_chat_notices()
                except Exception:
                    self._log.exception("app.sanctions.expired_chat_loop_failed")
                await asyncio.sleep(15)
        except asyncio.CancelledError:
            pass

    async def stale_unverified_accounts_loop(self) -> None:
        try:
            while True:
                try:
                    deleted = await delete_stale_unverified_accounts()
                    if deleted > 0:
                        self._log.info("app.users.auto_delete_unverified.done", deleted=deleted)
                except Exception:
                    self._log.exception("app.users.auto_delete_unverified.failed")
                await asyncio.sleep(15 * 60)
        except asyncio.CancelledError:
            pass

    async def expired_profile_subscriptions_loop(self) -> None:
        try:
            while True:
                next_run = _next_local_daily_run_at(hour=3, minute=0)
                delay_s = max(0.0, (next_run - datetime.now(next_run.tzinfo)).total_seconds())
                self._log.info(
                    "app.subscriptions.maintenance.scheduled",
                    run_at=next_run.isoformat(),
                    delay_s=int(delay_s),
                )
                await asyncio.sleep(delay_s)
                try:
                    reset_users = await reset_monthly_nickname_change_limits()
                    if reset_users > 0:
                        synced_online_profiles = await self.sync_online_profiles_after_nickname_limit_reset()
                        self._log.info(
                            "app.users.nickname_changes_monthly_reset.done",
                            reset_users=reset_users,
                            synced_online_profiles=synced_online_profiles,
                            scheduled_at=next_run.isoformat(),
                        )
                except Exception:
                    self._log.exception("app.users.nickname_changes_monthly_reset.failed")
                try:
                    synced = await sync_expired_profile_subscriptions()
                    self._log.info(
                        "app.subscriptions.expired_sync.done",
                        synced=synced,
                        scheduled_at=next_run.isoformat(),
                    )
                except Exception:
                    self._log.exception("app.subscriptions.expired_sync.failed")
                try:
                    notified = await notify_expiring_profile_subscriptions()
                    self._log.info(
                        "app.subscriptions.expiring_soon.done",
                        notified=notified,
                        scheduled_at=next_run.isoformat(),
                    )
                except Exception:
                    self._log.exception("app.subscriptions.expiring_soon.failed")
        except asyncio.CancelledError:
            pass

    async def sync_online_profiles_after_nickname_limit_reset(self) -> int:
        try:
            online_user_ids = await fetch_online_user_ids(get_redis())
        except Exception:
            self._log.warning("app.users.nickname_changes_monthly_reset.online_lookup_failed")
            return 0

        synced = 0
        for uid in online_user_ids:
            with suppress(Exception):
                await emit_auth_profile_sync(uid)
                synced += 1
        return synced
