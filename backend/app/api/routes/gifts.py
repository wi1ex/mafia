from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...core.roles import ROLE_ADMIN, ROLE_MODER, normalize_user_role
from ...models.user import User
from ...schemas.common import Identity, Ok
from ...schemas.gifts import (
    GiftMoveIn, GiftOut, GiftPurchaseIn, GiftPurchaseOut, GiftRemovalOut, GiftRemovalQuoteOut,
    ProfileGiftIconIn, ProfileGiftIconOut, UserGiftOut, UserGiftsOut,
)
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route
from ...services.blacklist import blacklist_relation
from ...services.gifts import (
    buy_gift, dismiss_gift_toast, gift_catalog, gift_removal_quote, move_user_gift,
    pending_gift_toasts, remove_user_gift, set_profile_gift_icon, user_gift_purchase, user_gifts,
)
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


@router.patch("/me/order", response_model=Ok)
@log_route("gifts.move_purchase")
async def move_purchase(
    payload: GiftMoveIn,
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> Ok:
    owner_id = int(ident["id"])
    await ensure_verification_allowed(session, owner_id)
    await move_user_gift(session, owner_id=owner_id, payload=payload)
    return Ok()


@router.patch("/me/profile-icon", response_model=ProfileGiftIconOut)
@log_route("gifts.profile_icon")
async def update_profile_icon(
    payload: ProfileGiftIconIn,
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> ProfileGiftIconOut:
    owner_id = int(ident["id"])
    await ensure_verification_allowed(session, owner_id)
    return await set_profile_gift_icon(session, owner_id=owner_id, acquisition_id=payload.acquisition_id)


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

    reveal_private_senders = viewer_role == ROLE_ADMIN and not grouped
    if reveal_private_senders:
        response.headers["Cache-Control"] = "private, no-store"
    return await user_gifts(
        session, user_id, grouped=grouped, limit=limit, offset=offset,
        reveal_private_senders=reveal_private_senders,
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


@router.get("/purchases/{acquisition_id}/removal", response_model=GiftRemovalQuoteOut)
@log_route("gifts.removal_quote")
async def removal_quote(
    response: Response,
    acquisition_id: int = Path(gt=0, le=2**31 - 1),
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> GiftRemovalQuoteOut:
    owner_id = int(ident["id"])
    await ensure_verification_allowed(session, owner_id)
    response.headers["Cache-Control"] = "private, no-store"
    return await gift_removal_quote(session, acquisition_id, owner_id=owner_id)


@router.delete("/purchases/{acquisition_id}", response_model=GiftRemovalOut)
@log_route("gifts.remove_purchase")
async def remove_purchase(
    acquisition_id: int = Path(gt=0, le=2**31 - 1),
    max_cost_dc: int = Query(default=0, ge=0, le=2**63 - 1),
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> GiftRemovalOut:
    owner_id = int(ident["id"])
    await ensure_verification_allowed(session, owner_id)
    return await remove_user_gift(session, acquisition_id, owner_id=owner_id, max_cost_dc=max_cost_dc)
