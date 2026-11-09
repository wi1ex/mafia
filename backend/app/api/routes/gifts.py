from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...core.roles import ROLE_ADMIN, ROLE_MODER, normalize_user_role
from ...models.user import User
from ...schemas.common import Identity, Ok
from ...schemas.gifts import GiftOut, GiftPurchaseIn, GiftPurchaseOut, MyGiftsOut, UserGiftOut, UserGiftsOut
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route
from ...services.blacklist import blacklist_relation
from ...services.gifts import buy_gift, dismiss_gift_toast, gift_catalog, my_gifts, pending_gift_toasts, remove_user_gift, user_gift_purchase, user_gifts
from ..utils import ensure_verification_allowed

router = APIRouter()


@router.get("/catalog", response_model=list[GiftOut], dependencies=[Depends(get_identity)])
@log_route("gifts.catalog")
async def catalog(session: AsyncSession = Depends(get_session)):
    return await gift_catalog(session)


@router.post("/purchases", response_model=GiftPurchaseOut)
@log_route("gifts.purchase")
async def purchase(
    payload: GiftPurchaseIn,
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> GiftPurchaseOut:
    return await buy_gift(session, payer_id=int(ident["id"]), payload=payload)


@router.get("/me", response_model=MyGiftsOut)
@log_route("gifts.my_collection")
async def my_collection(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=2**31 - 1),
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> MyGiftsOut:
    user_id = int(ident["id"])
    await ensure_verification_allowed(session, user_id)
    return await my_gifts(session, user_id, limit=limit, offset=offset)


@router.get("/pending-toasts")
@log_route("gifts.pending_toasts")
async def pending_toasts(
    after_id: int = Query(default=0, ge=0, le=2**31 - 1),
    limit: int = Query(default=20, ge=1, le=20),
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await pending_gift_toasts(session, owner_id=int(ident["id"]), after_id=after_id, limit=limit)


@router.get("/users/{user_id}", response_model=UserGiftsOut)
@log_route("gifts.user_collection")
async def user_collection(
    response: Response,
    user_id: int = Path(gt=0, le=2**63 - 1),
    grouped: bool = True,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=2**31 - 1),
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> UserGiftsOut:
    viewer_id = int(ident["id"])
    await ensure_verification_allowed(session, viewer_id)
    viewer_role = normalize_user_role(ident["role"])
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(404, detail="user_not_found")

    if normalize_user_role(user.role) == ROLE_ADMIN and viewer_role != ROLE_ADMIN:
        raise HTTPException(404, detail="user_not_found")

    if user_id != viewer_id and viewer_role not in {ROLE_ADMIN, ROLE_MODER}:
        relation = await blacklist_relation(session, viewer_id, user_id)
        if relation["b_blocks_a"]:
            raise HTTPException(403, detail="requester_blacklisted_by_target")

    reveal_anonymous_sender = viewer_role == ROLE_ADMIN and not grouped
    if reveal_anonymous_sender:
        response.headers["Cache-Control"] = "private, no-store"
    return await user_gifts(
        session, user_id, grouped=grouped, limit=limit, offset=offset,
        reveal_anonymous_sender=reveal_anonymous_sender,
    )


@router.get("/purchases/{acquisition_id}", response_model=UserGiftOut)
@log_route("gifts.user_purchase")
async def purchase_details(
    acquisition_id: int = Path(gt=0, le=2**31 - 1),
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> UserGiftOut:
    return await user_gift_purchase(session, acquisition_id, owner_id=int(ident["id"]))


@router.post("/purchases/{acquisition_id}/dismiss-toast", response_model=Ok)
@log_route("gifts.dismiss_toast")
async def dismiss_toast(
    acquisition_id: int = Path(gt=0, le=2**31 - 1),
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> Ok:
    await dismiss_gift_toast(session, acquisition_id, owner_id=int(ident["id"]))
    return Ok()


@router.delete("/purchases/{acquisition_id}", response_model=Ok)
@log_route("gifts.remove_purchase")
async def remove_purchase(
    acquisition_id: int = Path(gt=0, le=2**31 - 1),
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> Ok:
    owner_id = int(ident["id"])
    await ensure_verification_allowed(session, owner_id)
    await remove_user_gift(session, acquisition_id, owner_id=owner_id)
    return Ok()
