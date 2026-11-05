from __future__ import annotations
from sqlalchemy import String, cast, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.coin_purchase import CoinPurchase
from ..models.subscription_purchase import SubscriptionPurchase
from ..schemas.user import UserOperationHistoryOut, UserOperationOut
from .wallet import money_text


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


async def operation_history(session: AsyncSession, user_id: int, *, page: int = 1, per_page: int = 20) -> UserOperationHistoryOut:
    page, per_page = max(1, page), max(1, min(100, per_page))
    coin = select(
        literal("coin").label("journal"), CoinPurchase.id.label("operation_id"),
        CoinPurchase.processed_at.label("date"), CoinPurchase.source.label("source"),
        CoinPurchase.quantity.label("quantity"), CoinPurchase.amount.label("amount"),
        CoinPurchase.currency.label("currency"), literal(0).label("days"),
        literal(0).label("months"), literal(0).label("dc_cost"),
    ).where(CoinPurchase.user_id == user_id, CoinPurchase.status == "processed",
            CoinPurchase.processed_at.is_not(None), CoinPurchase.source != "provider_event")
    subscription = select(
        literal("subscription").label("journal"), SubscriptionPurchase.id.label("operation_id"),
        SubscriptionPurchase.processed_at.label("date"), SubscriptionPurchase.source.label("source"),
        literal(0).label("quantity"), literal(None).label("amount"), literal(None).label("currency"),
        SubscriptionPurchase.days.label("days"), SubscriptionPurchase.months.label("months"),
        SubscriptionPurchase.dc_cost.label("dc_cost"),
    ).where(SubscriptionPurchase.user_id == user_id, SubscriptionPurchase.status == "processed",
            SubscriptionPurchase.processed_at.is_not(None))
    combined = union_all(coin, subscription).subquery()
    total = int(await session.scalar(select(func.count()).select_from(combined)) or 0)
    rows = (await session.execute(select(combined).order_by(
        combined.c.date.desc(), combined.c.journal.desc(), combined.c.operation_id.desc(),
    ).offset((page - 1) * per_page).limit(per_page))).mappings().all()
    items: list[UserOperationOut] = []
    for row in rows:
        source = row["source"]
        if row["journal"] == "coin":
            quantity = int(row["quantity"])
            operation_type = {
                "lava": "Покупка монет", "admin_grant": "Выдача монет",
                "admin_remove": "Снятие монет", "game_reward": "Награда за проведение игр",
            }.get(source, "Начисление монет")
            received = "—" if source == "admin_remove" else f"{quantity} DC"
            spent = money_text(row["amount"], row["currency"]) if source == "lava" else f"{quantity} DC" if source == "admin_remove" else "Бесплатно"
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
