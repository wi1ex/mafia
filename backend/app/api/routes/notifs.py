from __future__ import annotations
from contextlib import suppress
from fastapi import APIRouter, Depends
from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route, rate_limited
from ...models.notif import Notif, NotifInboxState
from ...realtime.sio import sio
from ...schemas.common import Identity, Ok
from ...schemas.notif import ClearNotifsOut, NotifsListOut, MarkReadIn, NotifOut

router = APIRouter()


def _select_inbox_cutoff(uid: int):
    return select(NotifInboxState.cleared_through_id).where(NotifInboxState.user_id == uid)


@router.get("", response_model=NotifsListOut)
@log_route("notifs.list_notifs")
@rate_limited(lambda ident, **_: f"rl:notif:list:{ident['id']}", limit=10, window_s=1)
async def list_notifs(
    limit: int = 50,
    before_id: int | None = None,
    ident: Identity = Depends(get_identity),
    db: AsyncSession = Depends(get_session),
):
    uid = int(ident["id"])
    lim = max(1, min(200, limit))

    cutoff = int(await db.scalar(_select_inbox_cutoff(uid)) or 0)
    visible = (Notif.user_id == uid, Notif.id > cutoff)
    stmt = select(Notif).where(*visible)
    if before_id and before_id > 0:
        stmt = stmt.where(Notif.id < before_id)

    q = await db.execute(stmt.order_by(Notif.id.desc()).limit(lim + 1))
    rows = q.scalars().all()
    has_more = len(rows) > lim
    page = rows[:lim]

    items: list[NotifOut] = []
    for n in page:
        items.append(NotifOut(
            id=n.id,
            title=n.title or "Уведомление",
            text=(n.text or None),
            date=n.created_at,
            read=(n.read_at is not None),
        ))

    next_before_id = int(page[-1].id) if has_more and page else None
    total_unread = await db.scalar(
        select(func.count()).select_from(Notif).where(*visible, Notif.read_at.is_(None))
    )

    return NotifsListOut(
        items=items,
        unread_count=int(total_unread or 0),
        has_more=has_more,
        next_before_id=next_before_id,
        cleared_through_id=cutoff,
    )


@router.post("/mark_read", response_model=Ok)
@log_route("notifs.mark_read")
@rate_limited(lambda ident, **_: f"rl:notif:mark:{ident['id']}", limit=20, window_s=1)
async def mark_read(payload: MarkReadIn, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    stmt = update(Notif).where(
        Notif.user_id == uid,
        Notif.id > func.coalesce(_select_inbox_cutoff(uid).scalar_subquery(), 0),
        Notif.read_at.is_(None),
    ).values(read_at=func.now())
    if payload.all_before_id:
        await db.execute(stmt.where(Notif.id <= payload.all_before_id))
    elif payload.ids:
        await db.execute(stmt.where(Notif.id.in_(payload.ids)))
    await db.commit()

    return Ok()


@router.post("/clear", response_model=ClearNotifsOut)
@log_route("notifs.clear")
@rate_limited(lambda ident, **_: f"rl:notif:clear:{ident['id']}", limit=5, window_s=5)
async def clear_notifs(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> ClearNotifsOut:
    uid = int(ident["id"])
    latest_id = select(func.coalesce(func.max(Notif.id), 0)).where(Notif.user_id == uid).scalar_subquery()
    stmt = insert(NotifInboxState).values(user_id=uid, cleared_through_id=latest_id)
    stmt = stmt.on_conflict_do_update(
        index_elements=[NotifInboxState.user_id],
        set_={"cleared_through_id": func.greatest(
            NotifInboxState.cleared_through_id, stmt.excluded.cleared_through_id,
        )},
    ).returning(NotifInboxState.cleared_through_id)
    cutoff = int(await db.scalar(stmt) or 0)
    await db.commit()

    with suppress(Exception):
        await sio.emit("notif_clear", {"through_id": cutoff}, room=f"user:{uid}", namespace="/auth")

    return ClearNotifsOut(through_id=cutoff)
