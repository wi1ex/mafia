from __future__ import annotations
from sqlalchemy import and_, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.coin_purchase import CoinPurchase
from ..models.gift import UserGift
from ..models.subscription_purchase import SubscriptionPurchase
from ..models.user import User
from ..schemas.user import UserOperationHistoryOut, UserOperationOut
from .wallet import money_text, subscription_gift_is_anonymous


def _word(value: int, one: str, few: str, many: str) -> str:
    if 11 <= value % 100 <= 14:
        return many

    return one if value % 10 == 1 else few if 2 <= value % 10 <= 4 else many


def subscription_term(months: int, days: int) -> str:
    parts: list[str] = []
    years, remainder = divmod(int(months), 12)
    if years:
        parts.append(f"{years} {_word(years, 'год', 'года', 'лет')}")
    if remainder:
        parts.append(f"{remainder} {_word(remainder, 'месяц', 'месяца', 'месяцев')}")
    if days:
        parts.append(f"{days} {_word(days, 'день', 'дня', 'дней')}")
    return " ".join(parts) + " подписки" if parts else "Подписка"


def _gift_user_label(snapshot: object, party: str, fallback_id: int | None) -> str:
    data = snapshot if isinstance(snapshot, dict) else {}
    username = data.get(f"{party}_username")
    if isinstance(username, str) and username.strip():
        return username.strip()

    try:
        user_id = int(data.get(f"{party}_id") or fallback_id or 0)
    except (TypeError, ValueError, OverflowError):
        user_id = int(fallback_id or 0)
    return f"пользователя #{user_id}" if user_id > 0 else "пользователя"


async def operation_history(session: AsyncSession, user_id: int, *, page: int = 1, per_page: int = 20,
                            reveal_anonymous_subscription_sender: bool = False) -> UserOperationHistoryOut:
    page, per_page = max(1, page), max(1, min(100, per_page))
    coin = select(
        literal("coin").label("journal"), CoinPurchase.id.label("operation_id"),
        CoinPurchase.processed_at.label("date"), CoinPurchase.source.label("source"),
        CoinPurchase.quantity.label("quantity"), CoinPurchase.amount.label("amount"),
        CoinPurchase.currency.label("currency"), literal(0).label("days"),
        literal(0).label("months"), literal(0).label("dc_cost"),
        CoinPurchase.user_id.label("user_id"), CoinPurchase.actor_id.label("actor_id"),
    ).where(CoinPurchase.user_id == user_id, CoinPurchase.status == "processed",
            CoinPurchase.processed_at.is_not(None), CoinPurchase.source != "provider_event")
    subscription = select(
        literal("subscription").label("journal"), SubscriptionPurchase.id.label("operation_id"),
        SubscriptionPurchase.processed_at.label("date"), SubscriptionPurchase.source.label("source"),
        literal(0).label("quantity"), literal(None).label("amount"), literal(None).label("currency"),
        SubscriptionPurchase.days.label("days"), SubscriptionPurchase.months.label("months"),
        SubscriptionPurchase.dc_cost.label("dc_cost"),
        SubscriptionPurchase.user_id.label("user_id"), SubscriptionPurchase.actor_id.label("actor_id"),
    ).where(or_(SubscriptionPurchase.user_id == user_id,
                and_(SubscriptionPurchase.source == "gift", SubscriptionPurchase.actor_id == user_id)),
            SubscriptionPurchase.status == "processed",
            SubscriptionPurchase.processed_at.is_not(None))
    def gift_operations(journal, date):
        return select(
            literal(journal), UserGift.id, date, literal("gift"),
            UserGift.gift_id, literal(None), literal(None),
            literal(0), literal(0), UserGift.dc_cost,
            UserGift.owner_id, UserGift.payer_id,
        )

    gift_participant = or_(UserGift.owner_id == user_id, UserGift.payer_id == user_id)
    gift = gift_operations("gift", UserGift.acquired_at).where(gift_participant)
    refund = gift_operations("gift_refund", UserGift.refunded_at).where(
        gift_participant,
        UserGift.refunded_at.is_not(None),
        func.coalesce(UserGift.refund_recipient_id, UserGift.payer_id) == user_id,
    )
    combined = union_all(coin, subscription, gift, refund).subquery()
    total = int(await session.scalar(select(func.count()).select_from(combined)) or 0)
    rows = (await session.execute(select(combined).order_by(
        combined.c.date.desc(), combined.c.journal.desc(), combined.c.operation_id.desc(),
    ).offset((page - 1) * per_page).limit(per_page))).mappings().all()
    gift_ids = [int(row["operation_id"]) for row in rows
                if row["journal"] == "subscription" and row["source"] == "gift"]
    gift_metadata = dict((await session.execute(
        select(SubscriptionPurchase.id, SubscriptionPurchase.result)
        .where(SubscriptionPurchase.id.in_(gift_ids))
    )).all()) if gift_ids else {}
    sender_usernames: dict[int, str] = {}
    if reveal_anonymous_subscription_sender:
        sender_ids = {
            row["actor_id"] for row in rows
            if row["journal"] == "subscription" and row["source"] == "gift"
            and row["user_id"] == user_id and row["actor_id"] not in (None, user_id)
            and subscription_gift_is_anonymous(gift_metadata.get(row["operation_id"]))
        }
        if sender_ids:
            sender_usernames = dict((await session.execute(
                select(User.id, User.username).where(User.id.in_(sender_ids), User.deleted_at.is_(None))
            )).all())
    gift_purchase_ids = [int(row["operation_id"]) for row in rows if row["journal"] == "gift"]
    gift_purchases = {
        int(item.id): item for item in (await session.scalars(
            select(UserGift).where(UserGift.id.in_(gift_purchase_ids))
        )).all()
    } if gift_purchase_ids else {}
    items: list[UserOperationOut] = []
    for row in rows:
        source = row["source"]
        if row["journal"] == "coin":
            quantity = int(row["quantity"])
            operation_type = {
                "lava": "Покупка монет", "admin_grant": "Выдача монет",
                "admin_remove": "Снятие монет", "game_reward": "Награда за проведение игр",
                "gift_removal": "Удаление подарка",
            }.get(source, "Начисление монет")
            is_debit = source in {"admin_remove", "gift_removal"}
            received = "—" if is_debit else f"{quantity} DC"
            if source == "lava":
                spent = money_text(row["amount"], row["currency"])
            else:
                spent = f"{quantity} DC" if is_debit else "Бесплатно"
        elif row["journal"] == "gift_refund":
            operation_type = f"Возврат за подарок №{row['quantity']}"
            received = f"{int(row['dc_cost'])} DC"
            spent = "—"
        elif row["journal"] == "gift":
            purchase = gift_purchases[int(row["operation_id"])]
            gift_label = f"Подарок №{purchase.gift_id}"
            if purchase.payer_id == purchase.owner_id:
                operation_type = "Покупка подарка"
                received = gift_label
                spent = f"{purchase.dc_cost} DC"
            elif purchase.payer_id == user_id:
                recipient = purchase.owner_username or f"пользователя #{purchase.owner_id}"
                operation_type = f"{gift_label} для {recipient}"
                received = "—"
                spent = f"{purchase.dc_cost} DC"
            else:
                sender = purchase.payer_username or f"пользователя #{purchase.payer_id}"
                operation_type = "Анонимный подарок" if purchase.anonymous else f"Подарок от {sender}"
                received = gift_label
                spent = "Бесплатно"
        elif source == "gift":
            snapshot = gift_metadata.get(row["operation_id"])
            anonymous = subscription_gift_is_anonymous(snapshot)
            if row["actor_id"] == user_id:
                recipient = _gift_user_label(snapshot, "recipient", row["user_id"])
                gift_label = "Анонимный подарок подписки" if anonymous else "Подарок подписки"
                operation_type = f"{gift_label} для {recipient}"
                received = "—"
                spent = f"{int(row['dc_cost'])} DC"
            else:
                if anonymous:
                    operation_type = "Анонимный подарок подписки"
                    if sender_username := sender_usernames.get(row["actor_id"]):
                        operation_type += f" ({sender_username})"
                else:
                    sender = _gift_user_label(snapshot, "sender", row["actor_id"])
                    operation_type = f"Подарок подписки от {sender}"
                received = subscription_term(int(row["months"] or 0), int(row["days"] or 0))
                spent = "Бесплатно"
        else:
            operation_type = {
                "admin": "Выдача подписки",
                "compensation": "Компенсация подписки",
            }.get(source, "Покупка подписки")
            received = subscription_term(int(row["months"] or 0), int(row["days"] or 0))
            cost = row["dc_cost"]
            spent = f"{int(cost)} DC" if cost else "Бесплатно"
        items.append(UserOperationOut(id=f"{row['journal']}:{row['operation_id']}", date=row["date"],
                                      type=operation_type, received=received, spent=spent))
    return UserOperationHistoryOut(items=items, total=total, page=page, per_page=per_page,
                                   pages=(total + per_page - 1) // per_page)
