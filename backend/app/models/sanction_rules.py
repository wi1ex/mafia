from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, Integer, JSON, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base


class SanctionRulesConfig(Base):
    __tablename__ = "sanction_rules_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


async def get_sanction_rules(session: AsyncSession) -> SanctionRulesConfig | None:
    return await session.get(SanctionRulesConfig, 1)


def build_default_sanction_rules_sections() -> list[dict[str, Any]]:
    return [{
        "id": "general",
        "title": "1. Принятие правил и персональные данные",
        "rules": [{"text": f"1.{number}. {text}", "badges": []} for number, text in enumerate((
            "Использование платформы deceit.games регулируется Пользовательским соглашением, настоящими Правилами и Политикой обработки персональных данных.",
            "Новая редакция публикуется на сайте и применяется с даты публикации (или иной указанной даты). Продолжение использования платформы означает согласие с изменениями.",
            "Для использования функционала платформы требуется верификация через Telegram-бота. Верификация не является подтверждением личности или возраста пользователя.",
            "Вопросы об обработке персональных данных, удалении аккаунта, оплате и возвратах направляются на support@deceit.games. Порядок удаления данных и сроки их хранения определяются Политикой обработки персональных данных. Условия подписки, порядок оплаты и возвратов определяются Пользовательским соглашением.",
            "Платформа не записывает звук, видео и демонстрацию экрана в лобби (игровых комнатах), не создаёт архивов этих трансляций и не запрашивает паспортные данные или копии документов для проверки возраста.",
            "При применении санкций доступ к платформе может быть ограничен/заблокирован для соответствующего аккаунта пользователя на основе аккаунта, привязанного к Telegram.",
        ), start=1)],
    }]


async def ensure_sanction_rules(session: AsyncSession) -> SanctionRulesConfig:
    row = await get_sanction_rules(session)
    if row is None:
        row = SanctionRulesConfig(id=1, sections=build_default_sanction_rules_sections())
        session.add(row)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            row = await get_sanction_rules(session)
            if row is None:
                raise
        else:
            await session.refresh(row)

    return row
