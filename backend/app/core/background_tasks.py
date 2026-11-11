from __future__ import annotations
import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from time import time
from typing import Any
from zoneinfo import ZoneInfo
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
from ..services.nickname import reset_monthly_nickname_change_limits
from ..services.telegram import get_telegram_nickname
from .clients import get_redis
from .background_jobs import run_shared_job
from .db import SessionLocal

__all__ = ["LifespanBackgroundTasks", "verify_runtime_dependencies"]

EMPTY_ROOM_MARKER_TTL_SECONDS = 30 * 24 * 60 * 60
EMPTY_ROOM_GC_SCAN_INTERVAL_SECONDS = 60
TELEGRAM_NICKNAME_SYNC_INTERVAL_SECONDS = 1.0
MOSCOW = ZoneInfo("Europe/Moscow")


def _moscow_run_at(*, hour: int, minute: int = 0, monthly: bool = False, now: datetime | None = None, after: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local_now = current.astimezone(MOSCOW)
    run_at = local_now.replace(day=1 if monthly else local_now.day, hour=hour, minute=minute, second=0, microsecond=0)
    if after is None or run_at > after:
        return run_at

    if not monthly:
        return run_at + timedelta(days=1)

    if run_at.month == 12:
        return run_at.replace(year=run_at.year + 1, month=1)

    return run_at.replace(month=run_at.month + 1)


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
        self._coin_reconciliation_task: asyncio.Task[None] | None = None
        self._nomination_rewards_task: asyncio.Task[None] | None = None
        self._empty_room_gc_tasks: dict[int, asyncio.Task[None]] = {}

    def start(self, *, backfill_nomination_rewards: bool = False) -> None:
        self._settings_task = asyncio.create_task(self.settings_pubsub_loop())
        self._expired_sanctions_chat_task = asyncio.create_task(self.expired_sanctions_chat_loop())
        self._expired_subscriptions_task = asyncio.create_task(self.expired_profile_subscriptions_loop())
        self._stale_unverified_accounts_task = asyncio.create_task(self.stale_unverified_accounts_loop())
        self._empty_rooms_gc_task = asyncio.create_task(self.empty_rooms_gc_loop())
        self._stale_chat_uploads_task = asyncio.create_task(self.stale_chat_uploads_loop())
        self._telegram_nickname_sync_task = asyncio.create_task(self.telegram_nickname_sync_loop())
        self._coin_reconciliation_task = asyncio.create_task(self.coin_reconciliation_loop())
        self._nomination_rewards_task = asyncio.create_task(self.nomination_rewards_loop(backfill=backfill_nomination_rewards))

    async def stop(self) -> None:
        managed_tasks = (
            self._settings_task,
            self._expired_sanctions_chat_task,
            self._expired_subscriptions_task,
            self._stale_unverified_accounts_task,
            self._empty_rooms_gc_task,
            self._stale_chat_uploads_task,
            self._telegram_nickname_sync_task,
            self._coin_reconciliation_task,
            self._nomination_rewards_task,
            *tuple(self._empty_room_gc_tasks.values()),
        )
        tasks = [task for task in managed_tasks if task is not None]
        for task in tasks:
            task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                self._log.warning("app.shutdown.background_task_failed", error=type(result).__name__)
        self._empty_room_gc_tasks.clear()

    async def _periodic_job_loop(self, name: str, interval: int,
                                 callback: Callable[[], Awaitable[Any]]) -> None:
        try:
            while True:
                slot = int(time() // interval) * interval
                try:
                    completed = await run_shared_job(name, slot, callback)
                except Exception:
                    self._log.exception("app.background.job_failed", job=name)
                    completed = False
                remaining = max(0.1, slot + interval - time())
                await asyncio.sleep(remaining if completed else min(5.0, remaining))
        except asyncio.CancelledError:
            pass

    async def _scheduled_job_loop(self, name: str, *, hour: int,
                                  callback: Callable[[datetime], Awaitable[Any]],
                                  monthly: bool = False, catch_up_on_start: bool = True) -> None:
        now = datetime.now(timezone.utc)
        scheduled_at = _moscow_run_at(hour=hour, monthly=monthly, now=now)
        if not catch_up_on_start and scheduled_at < now:
            scheduled_at = _moscow_run_at(hour=hour, monthly=monthly, now=now, after=scheduled_at)
        try:
            while True:
                now = datetime.now(timezone.utc)
                current_slot = _moscow_run_at(hour=hour, monthly=monthly, now=now)
                scheduled_at = max(scheduled_at, current_slot)
                delay = (scheduled_at - now).total_seconds()
                if delay > 0:
                    await asyncio.sleep(min(delay, 60.0))
                    continue
                try:
                    completed = await run_shared_job(
                        name, int(scheduled_at.timestamp()), lambda: callback(scheduled_at),
                    )
                except Exception:
                    self._log.exception("app.background.job_failed", job=name)
                    completed = False
                if completed:
                    scheduled_at = _moscow_run_at(hour=hour, monthly=monthly, after=scheduled_at)
                else:
                    await asyncio.sleep(15)
        except asyncio.CancelledError:
            pass

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
        await self._periodic_job_loop(
            "empty_rooms_scan", EMPTY_ROOM_GC_SCAN_INTERVAL_SECONDS, self.recover_empty_rooms_gc,
        )

    async def stale_chat_uploads_loop(self) -> None:
        async def clean_uploads(scheduled_at: datetime) -> None:
            deleted = await delete_stale_pending_chat_images_async()
            self._log.info("app.chat.pending_uploads_cleaned", deleted=deleted,
                           scheduled_at=scheduled_at.isoformat())
        await self._scheduled_job_loop("chat_pending_uploads", hour=6, callback=clean_uploads)

    async def telegram_nickname_sync_loop(self) -> None:
        async def sync_nicknames(_scheduled_at: datetime) -> None:
            await self.sync_telegram_nicknames()
        await self._scheduled_job_loop(
            "telegram_nicknames", hour=7, monthly=True, callback=sync_nicknames,
        )

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
        loop = asyncio.get_running_loop()
        pubsub = None
        next_refresh = 0.0
        next_subscription_warning = 0.0

        async def refresh_settings() -> None:
            nonlocal next_refresh
            next_refresh = loop.time() + 30
            try:
                async with SessionLocal() as session:
                    await refresh_app_settings(session)
            except Exception:
                self._log.warning("app.settings.refresh_failed")

        async def close_subscription() -> None:
            nonlocal pubsub
            current, pubsub = pubsub, None
            if current is not None:
                with suppress(Exception):
                    await asyncio.wait_for(current.unsubscribe("settings:update"), timeout=1)
                with suppress(Exception):
                    await asyncio.wait_for(current.close(), timeout=1)

        try:
            while True:
                try:
                    if pubsub is None:
                        pubsub = get_redis().pubsub()
                        await pubsub.subscribe("settings:update")
                        await refresh_settings()
                    elif loop.time() >= next_refresh:
                        await refresh_settings()

                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
                    if message and message.get("type") == "message":
                        await refresh_settings()
                except Exception:
                    if loop.time() >= next_subscription_warning:
                        self._log.warning("app.settings.subscription_failed")
                        next_subscription_warning = loop.time() + 30
                    await close_subscription()
                    if loop.time() >= next_refresh:
                        await refresh_settings()
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await close_subscription()

    async def expired_sanctions_chat_loop(self) -> None:
        await self._periodic_job_loop(
            "expired_sanctions", 15, emit_expired_timed_sanctions_chat_notices,
        )

    async def stale_unverified_accounts_loop(self) -> None:
        async def delete_unverified() -> None:
            deleted = await delete_stale_unverified_accounts()
            if deleted > 0:
                self._log.info("app.users.auto_delete_unverified.done", deleted=deleted)
        await self._periodic_job_loop("unverified_accounts", 15 * 60, delete_unverified)

    async def coin_reconciliation_loop(self) -> None:
        from ..services.payments import reconcile_coin_invoices
        async def reconcile() -> None:
            async with SessionLocal() as session:
                await reconcile_coin_invoices(session, limit=50)
        await self._periodic_job_loop("coin_reconciliation", 60, reconcile)

    async def nomination_rewards_loop(self, *, backfill: bool) -> None:
        from ..services.nomination_rewards import grant_nomination_rewards

        async def backfill_rewards() -> None:
            granted = await grant_nomination_rewards()
            self._log.info("app.nominations.backfill.done", rewarded_users=granted)

        async def daily_rewards(scheduled_at: datetime) -> None:
            granted = await grant_nomination_rewards(scheduled_at)
            self._log.info("app.nominations.daily.done", rewarded_users=granted, scheduled_at=scheduled_at.isoformat())

        while backfill:
            try:
                if await run_shared_job("nomination_rewards_backfill", 1, backfill_rewards):
                    break
            except Exception:
                self._log.exception("app.background.job_failed", job="nomination_rewards_backfill")
            await asyncio.sleep(15)

        await self._scheduled_job_loop("nomination_rewards", hour=8, callback=daily_rewards, catch_up_on_start=False)

    async def expired_profile_subscriptions_loop(self) -> None:
        async def maintain_subscriptions(scheduled_at: datetime) -> None:
            async def reset_nickname_limits() -> None:
                reset_users = await reset_monthly_nickname_change_limits()
                if reset_users > 0:
                    synced_profiles = await self.sync_online_profiles_after_nickname_limit_reset()
                    self._log.info("app.users.nickname_changes_monthly_reset.done",
                                   reset_users=reset_users, synced_online_profiles=synced_profiles,
                                   scheduled_at=scheduled_at.isoformat())

            local_now = datetime.now(MOSCOW)
            if scheduled_at.day == 1 and local_now.date() == scheduled_at.date():
                month_slot = int(scheduled_at.timestamp())
                if not await run_shared_job("monthly_nickname_limits", month_slot, reset_nickname_limits):
                    raise RuntimeError("Monthly nickname limit reset is already running")
            synced = await sync_expired_profile_subscriptions()
            self._log.info("app.subscriptions.expired_sync.done", synced=synced,
                           scheduled_at=scheduled_at.isoformat())
            notified = await notify_expiring_profile_subscriptions()
            self._log.info("app.subscriptions.expiring_soon.done", notified=notified,
                           scheduled_at=scheduled_at.isoformat())

        await self._scheduled_job_loop("subscription_maintenance", hour=5, callback=maintain_subscriptions)

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
