from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.decorators import log_route
from ...db import get_session
from ...core.security import get_identity
from ...core.decorators import rate_limited
from ...schemas import NotifsListOut, NotifOut, MarkReadIn, Ok, Identity
from ...models.notif import Notif

router = APIRouter()


@log_route("notifs.list_notifs")
@rate_limited(lambda ident, **_: f"rl:notif:list:{ident['id']}", limit=5, window_s=1)
@router.get("", response_model=NotifsListOut)
async def list_notifs(limit: int = 50, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)):
    uid = int(ident["id"])
    lim = max(1, min(200, limit))
    q = await db.execute(select(Notif).where(Notif.user_id == uid).order_by(Notif.id.desc()).limit(lim))
    items = [NotifOut(id=n.id, text=n.text, created_at=n.created_at.isoformat(), read=(n.read_at is not None)) for n in q.scalars().all()]
    total_unread = await db.scalar(select(func.count()).select_from(Notif).where(Notif.user_id == uid, Notif.read_at.is_(None)))

    return NotifsListOut(items=items, unread_count=int(total_unread or 0))


@log_route("notifs.mark_read")
@rate_limited(lambda ident, **_: f"rl:notif:mark:{ident['id']}", limit=5, window_s=1)
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
