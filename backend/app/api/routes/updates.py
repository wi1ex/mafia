from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...models.update import SiteUpdate, UpdateRead
from ...schemas.common import Identity, Ok
from ...schemas.updates import UpdatesListOut, UpdateOut, MarkUpdatesReadIn
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route, rate_limited

router = APIRouter()


@log_route("updates.list")
@rate_limited(lambda ident, **_: f"rl:updates:list:{ident['id']}", limit=5, window_s=1)
@router.get("", response_model=UpdatesListOut)
async def list_updates(limit: int = 50, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UpdatesListOut:
    uid = int(ident["id"])
    lim = max(1, min(200, limit))
    q = await db.execute(
        select(SiteUpdate, UpdateRead.read_at)
        .outerjoin(UpdateRead, (UpdateRead.update_id == SiteUpdate.id) & (UpdateRead.user_id == uid))
        .order_by(SiteUpdate.update_date.desc(), SiteUpdate.id.desc())
        .limit(lim)
    )
    items: list[UpdateOut] = []
    for upd, read_at in q.all():
        items.append(UpdateOut(
            id=upd.id,
            version=upd.version,
            date=upd.update_date,
            description=upd.description,
            read=read_at is not None,
        ))

    total_unread = await db.scalar(
        select(func.count(SiteUpdate.id))
        .select_from(SiteUpdate)
        .outerjoin(UpdateRead, (UpdateRead.update_id == SiteUpdate.id) & (UpdateRead.user_id == uid))
        .where(UpdateRead.update_id.is_(None))
    )

    return UpdatesListOut(items=items, unread_count=int(total_unread or 0))


@log_route("updates.mark_read")
@rate_limited(lambda ident, **_: f"rl:updates:mark:{ident['id']}", limit=10, window_s=1)
@router.post("/mark_read", response_model=Ok)
async def mark_read(payload: MarkUpdatesReadIn, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    ids: list[int] = []
    if payload.all:
        rows = await db.execute(select(SiteUpdate.id).outerjoin(UpdateRead, (UpdateRead.update_id == SiteUpdate.id) & (UpdateRead.user_id == uid)).where(UpdateRead.update_id.is_(None)))
        ids = [int(r[0]) for r in rows.all() if r and r[0] is not None]
    elif payload.ids:
        ids = [int(v) for v in payload.ids if int(v) > 0]

    if not ids:
        return Ok()

    existing_rows = await db.execute(select(UpdateRead.update_id).where(UpdateRead.user_id == uid, UpdateRead.update_id.in_(ids)))
    existing = {int(r[0]) for r in existing_rows.all() if r and r[0] is not None}
    now = datetime.utcnow()
    for upd_id in ids:
        if upd_id in existing:
            continue
        db.add(UpdateRead(user_id=uid, update_id=upd_id, read_at=now))
    await db.commit()

    return Ok()
