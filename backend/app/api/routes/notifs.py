from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route, rate_limited
from ...models.notif import Notif
from ...schemas.common import Identity, Ok
from ...schemas.notif import NotifsListOut, MarkReadIn, NotifOut

router = APIRouter()


@log_route("notifs.list_notifs")
@rate_limited(lambda ident, **_: f"rl:notif:list:{ident['id']}", limit=10, window_s=1)
@router.get("", response_model=NotifsListOut)
async def list_notifs(
    limit: int = 50,
    before_id: int | None = None,
    ident: Identity = Depends(get_identity),
    db: AsyncSession = Depends(get_session),
):
    uid = int(ident["id"])
    lim = max(1, min(200, limit))

    stmt = select(Notif).where(Notif.user_id == uid)
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
        select(func.count()).select_from(Notif).where(Notif.user_id == uid, Notif.read_at.is_(None))
    )

    return NotifsListOut(
        items=items,
        unread_count=int(total_unread or 0),
        has_more=has_more,
        next_before_id=next_before_id,
    )


@log_route("notifs.mark_read")
@rate_limited(lambda ident, **_: f"rl:notif:mark:{ident['id']}", limit=20, window_s=1)
@router.post("/mark_read", response_model=Ok)
async def mark_read(payload: MarkReadIn, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    now = func.now()
    if payload.all_before_id:
        await db.execute(update(Notif).where(Notif.user_id == uid, Notif.id <= payload.all_before_id, Notif.read_at.is_(None)).values(read_at=now))
    elif payload.ids:
        await db.execute(update(Notif).where(Notif.user_id == uid, Notif.id.in_(payload.ids), Notif.read_at.is_(None)).values(read_at=now))
    await db.commit()

    return Ok()
