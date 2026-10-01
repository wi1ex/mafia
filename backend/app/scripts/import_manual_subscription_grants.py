"""Restore grant history from admin logs; defaults to a read-only preview.

History is imported automatically by lifespan after creating the schema.
Optional manual preview/import from the project root:
    docker compose exec backend python -m app.scripts.import_manual_subscription_grants
    docker compose exec backend python -m app.scripts.import_manual_subscription_grants --apply

Only grant history is written. Subscriptions and notifications are untouched.
"""
from __future__ import annotations

import argparse
import asyncio
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ManualGrant:
    user_id: int
    months: int
    days: int


def parse_manual_grant(details: str) -> ManualGrant:
    # The log's user_id column identifies the administrator; the recipient is
    # stored in details. Match complete tokens, never nickname substrings.
    values = {}
    for key in ("user_id", "months", "days"):
        matches = re.findall(rf"(?:^|\s){key}=([^\s]+)", details)
        if len(matches) != 1 or not re.fullmatch(r"[0-9]+", matches[0]):
            raise ValueError(f"missing or invalid {key}")
        values[key] = int(matches[0])
    if values["user_id"] <= 0 or values["user_id"] > 2**63 - 1:
        raise ValueError("invalid user_id")
    if max(values["months"], values["days"]) > 2**31 - 1:
        raise ValueError("duration exceeds database integer range")
    if values["months"] == 0 and values["days"] == 0:
        raise ValueError("empty duration")
    return ManualGrant(**values)


def already_recorded_by_admin(details: str) -> bool:
    return re.search(r"(?:^|\s)subscription_grant_id=[1-9][0-9]*(?:\s|$)", details) is not None


async def import_manual_grants(session, *, apply: bool = True, verbose: bool = False) -> dict[str, int]:
    """Import original event dates; the caller owns the transaction and engine."""
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert
    from ..models.log import AppLog
    from ..models.subscription import SubscriptionGrant

    counts = dict(found=0, pending=0, inserted=0, existing=0, invalid=0)
    imported_ids = set(await session.scalars(
        select(SubscriptionGrant.source_log_id).where(SubscriptionGrant.source_log_id.is_not(None))
    ))
    rows = await session.stream_scalars(
        select(AppLog).where(AppLog.action == "admin_subscription_upsert")
        .order_by(AppLog.created_at, AppLog.id)
        .execution_options(yield_per=500)
    )
    async for log in rows:
        counts["found"] += 1
        if log.id in imported_ids or already_recorded_by_admin(log.details):
            counts["existing"] += 1
            continue
        try:
            grant = parse_manual_grant(log.details)
        except ValueError as exc:
            counts["invalid"] += 1
            if verbose:
                print(f"SKIP log={log.id}: {exc}")
            else:
                import structlog
                structlog.get_logger().warning("subscription.manual_history.invalid_log", log_id=log.id, error=str(exc))
            continue
        counts["pending"] += 1
        if verbose:
            print(f"log={log.id} user={grant.user_id} date={log.created_at.isoformat()} reason=Донат months={grant.months} days={grant.days}")
        if apply:
            inserted_id = await session.scalar(
                insert(SubscriptionGrant).values(
                    user_id=grant.user_id, issued_at=log.created_at, reason="Донат",
                    months=grant.months, days=grant.days, source_log_id=log.id,
                ).on_conflict_do_nothing(index_elements=[SubscriptionGrant.source_log_id])
                .returning(SubscriptionGrant.id)
            )
            if inserted_id is not None:
                counts["inserted"] += 1
            else:
                counts["existing"] += 1
    return counts


async def import_history(*, apply: bool) -> None:
    from ..core.db import SessionLocal, engine

    try:
        async with SessionLocal() as session:
            counts = await import_manual_grants(session, apply=apply, verbose=True)
            if apply:
                await session.commit()
            else:
                await session.rollback()
        print(("IMPORT" if apply else "PREVIEW") + " " + " ".join(f"{key}={value}" for key, value in counts.items()))
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Write the previewed grant history; default is read-only")
    args = parser.parse_args()
    asyncio.run(import_history(apply=args.apply))


if __name__ == "__main__":
    main()
