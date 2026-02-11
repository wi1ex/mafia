from __future__ import annotations
import asyncio
import logging
import aiohttp
from aiogram import types
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, Tuple, TypeVar
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

T = TypeVar("T")


def normalize_webhook_path(path: str) -> str:
    if not path:
        return "/bot/webhook"

    return path if path.startswith("/") else f"/{path}"


def keyboard_verify_only() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Верификация")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def keyboard_reset_only() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Сбросить пароль")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def reset_confirm_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="Подтвердить", callback_data="reset_confirm"),
            InlineKeyboardButton(text="Отмена", callback_data="reset_cancel"),
        ]]
    )


def _is_transient_telegram_error(exc: TelegramAPIError) -> bool:
    text = str(exc).lower()
    transient_markers = (
        "timeout",
        "temporarily unavailable",
        "bad gateway",
        "gateway",
        "try again later",
        "restart",
    )

    return any(marker in text for marker in transient_markers)


async def safe_telegram_call(action: str, call: Callable[[], Awaitable[T]], *, retries: int = 3, logger: logging.Logger | None = None) -> T | None:
    log = logger or logging.getLogger("bot")
    for attempt in range(1, retries + 1):
        try:
            return await call()

        except TelegramRetryAfter as exc:
            retry_after = float(getattr(exc, "retry_after", 1.0) or 1.0)
            wait_s = max(retry_after, 0.5)
            log.warning("bot.telegram.retry_after", extra={"action": action, "attempt": attempt, "wait_s": wait_s})

        except TelegramNetworkError:
            wait_s = 0.5 * attempt
            log.warning("bot.telegram.network_error", extra={"action": action, "attempt": attempt, "wait_s": wait_s}, exc_info=True)

        except TelegramAPIError as exc:
            if attempt < retries and _is_transient_telegram_error(exc):
                wait_s = 0.5 * attempt
                log.warning("bot.telegram.api_transient", extra={"action": action, "attempt": attempt, "wait_s": wait_s}, exc_info=True)
            else:
                log.error("bot.telegram.api_error", extra={"action": action, "attempt": attempt}, exc_info=True)
                return None

        except Exception:
            wait_s = 0.5 * attempt
            log.error("bot.telegram.unexpected_error", extra={"action": action, "attempt": attempt}, exc_info=True)
            if attempt >= retries:
                return None

        if attempt < retries:
            await asyncio.sleep(wait_s)

    return None


async def safe_message_answer(message: types.Message, text: str, **kwargs: Any) -> types.Message | None:
    return await safe_telegram_call("message.answer", lambda: message.answer(text, **kwargs))


async def safe_message_edit_text(message: types.Message, text: str, **kwargs: Any) -> types.Message | None:
    return await safe_telegram_call("message.edit_text", lambda: message.edit_text(text, **kwargs))


async def safe_message_delete(message: types.Message) -> bool:
    res = await safe_telegram_call("message.delete", message.delete)
    return bool(res)


async def safe_callback_answer(callback: types.CallbackQuery, **kwargs: Any) -> bool:
    res = await safe_telegram_call("callback.answer", lambda: callback.answer(**kwargs))
    return bool(res)


async def backend_request(session: aiohttp.ClientSession, path: str, payload: Dict[str, Any], *, backend_url: str, bot_api_token: str, request_timeout: int = 10, retry_attempts: int = 3, logger: logging.Logger | None = None) -> Tuple[int | None, Dict[str, Any] | None]:
    log = logger or logging.getLogger("bot")
    if not bot_api_token:
        return None, None

    url = f"{backend_url}{path}"
    headers = {"X-Bot-Token": bot_api_token}
    last_status: int | None = None
    for attempt in range(1, retry_attempts + 1):
        try:
            async with session.post(url, json=payload, headers=headers, timeout=request_timeout) as resp:
                last_status = resp.status
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = {}
                return resp.status, data if isinstance(data, dict) else {}

        except aiohttp.ClientResponseError as e:
            last_status = e.status
            log.warning(
                "bot.backend.client_response_error",
                extra={"path": path, "attempt": attempt, "status": e.status},
                exc_info=True,
            )
        except Exception:
            last_status = None
            log.warning(
                "bot.backend.request_error",
                extra={"path": path, "attempt": attempt},
                exc_info=True,
            )
        if attempt < retry_attempts:
            await asyncio.sleep(0.5 * attempt)

    return last_status, None


def map_verify_error(detail: str | None, status_code: int | None) -> str:
    if status_code == 404 or detail == "user_not_found":
        return "Аккаунт не найден."

    if detail == "invalid_credentials":
        return "Неверный никнейм или пароль."

    if detail == "password_not_set":
        return "Пароль не установлен. Сначала восстановите пароль."

    if detail == "telegram_in_use":
        return "Этот Telegram уже привязан к другому аккаунту."

    if detail == "telegram_already_linked":
        return "К аккаунту уже привязан другой Telegram."

    if detail == "user_deleted":
        return "Аккаунт удален."

    return "Не удалось пройти верификацию."


def map_reset_error(detail: str | None, status_code: int | None) -> str:
    if status_code == 404 or detail == "user_not_found":
        return "Аккаунт не найден."

    if detail == "not_verified":
        return "Сначала пройдите верификацию."

    if detail == "telegram_mismatch":
        return "Этот Telegram не привязан к аккаунту."

    if detail == "user_deleted":
        return "Аккаунт удален."

    return "Не удалось сбросить пароль."


def guarded_handler(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)

        except Exception:
            log = logging.getLogger("bot")
            log.exception("bot.handler.unhandled_error", extra={"handler": func.__name__})

            event = args[0] if args else None
            if isinstance(event, types.CallbackQuery):
                await safe_callback_answer(
                    event,
                    text="Временная ошибка. Попробуйте еще раз через минуту.",
                    show_alert=True,
                )
                if event.message:
                    await safe_message_answer(event.message, "Не удалось обработать запрос. Повторите позже.")
                return None

            if isinstance(event, types.Message):
                await safe_message_answer(event, "Не удалось обработать запрос. Повторите позже.")
                return None

            return None

    return wrapper
