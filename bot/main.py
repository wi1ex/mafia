from __future__ import annotations
import asyncio
import logging
import os
from typing import Any, Dict, Tuple
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000/api").rstrip("/")
BOT_API_TOKEN = os.getenv("BOT_API_TOKEN", "").strip()

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "").rstrip("/")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/bot/webhook").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8081"))

REQUEST_TIMEOUT = 10
RETRY_ATTEMPTS = 3

REDIS_URL = os.getenv("REDIS_URL", "").strip()
if not REDIS_URL:
    r_host = os.getenv("REDIS_HOST", "redis").strip()
    r_port = os.getenv("REDIS_PORT", "6379").strip()
    r_pass = os.getenv("REDIS_PASSWORD", "").strip()
    auth = f":{r_pass}@" if r_pass else ""
    REDIS_URL = f"redis://{auth}{r_host}:{r_port}/1"


class VerifyState(StatesGroup):
    login = State()


class ResetState(StatesGroup):
    confirm = State()


router = Router()


def _normalize_webhook_path(path: str) -> str:
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
        keyboard=[[KeyboardButton(text="Восстановить пароль")]],
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


async def backend_request(session: aiohttp.ClientSession, path: str, payload: Dict[str, Any]) -> Tuple[int | None, Dict[str, Any] | None]:
    if not BOT_API_TOKEN:
        return None, None

    url = f"{BACKEND_URL}{path}"
    headers = {"X-Bot-Token": BOT_API_TOKEN}
    last_status: int | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            async with session.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT) as resp:
                last_status = resp.status
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = {}
                return resp.status, data if isinstance(data, dict) else {}

        except aiohttp.ClientResponseError as e:
            last_status = e.status
        except Exception:
            last_status = None
        if attempt < RETRY_ATTEMPTS:
            await asyncio.sleep(0.5 * attempt)

    return last_status, None


def map_verify_error(detail: str | None, status_code: int | None) -> str:
    if status_code == 404 or detail == "user_not_found":
        return "Аккаунт не найден."

    if detail == "invalid_credentials":
        return "Неверный логин или пароль."

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

    return "Не удалось восстановить пароль."


@router.message(Command("start"))
async def start_cmd(message: types.Message, session: aiohttp.ClientSession) -> None:
    tg_id = message.from_user.id if message.from_user else 0
    status_code, payload = await backend_request(
        session,
        "/bot/status",
        {"telegram_id": tg_id},
    )
    verified = bool((payload or {}).get("verified")) if status_code == 200 else False
    kb = keyboard_reset_only() if verified else keyboard_verify_only()
    await message.answer("Выберите действие:", reply_markup=kb)


@router.message(Command("cancel"))
async def cancel_cmd(message: types.Message, state: FSMContext) -> None:
    await do_cancel(state, message)


async def do_cancel(state: FSMContext, message: types.Message | None) -> None:
    await state.clear()
    if message:
        await message.answer("Действие отменено.")


@router.message(Command("verify"))
@router.message(F.text == "Верификация")
async def verify_start(message: types.Message, state: FSMContext, session: aiohttp.ClientSession) -> None:
    tg_id = message.from_user.id if message.from_user else 0
    status_code, payload = await backend_request(
        session,
        "/bot/status",
        {"telegram_id": tg_id},
    )
    verified = bool((payload or {}).get("verified")) if status_code == 200 else False
    if verified:
        await state.clear()
        await message.answer("Этот Telegram уже привязан. Доступно восстановление пароля.", reply_markup=keyboard_reset_only())
        return

    await state.clear()
    await state.set_state(VerifyState.login)
    await message.answer("Введите логин и пароль через пробел (например: login password):")


@router.message(VerifyState.login, F.text)
async def verify_credentials(message: types.Message, state: FSMContext, session: aiohttp.ClientSession) -> None:
    text = (message.text or "").strip()
    parts = [p for p in text.split() if p]
    try:
        await message.delete()
    except Exception:
        pass

    if len(parts) < 2:
        await message.answer("Необходимо ввести логин и пароль через пробел (например: login password).")
        return

    username = parts[0]
    password = " ".join(parts[1:])

    tg_id = message.from_user.id if message.from_user else 0
    status_code, payload = await backend_request(
        session,
        "/bot/verify",
        {"username": username, "password": password, "telegram_id": tg_id},
    )

    await state.clear()
    if status_code == 200:
        await message.answer("Верификация прошла успешно. Доступ к комнатам открыт.", reply_markup=keyboard_reset_only())
        return

    detail = (payload or {}).get("detail")
    await state.set_state(VerifyState.login)
    await message.answer(f"{map_verify_error(detail, status_code)}\nВведите логин и пароль через пробел (например: login password):", reply_markup=keyboard_verify_only())

@router.message(Command("reset"))
@router.message(F.text == "Восстановить пароль")
async def reset_start(message: types.Message, state: FSMContext, session: aiohttp.ClientSession) -> None:
    tg_id = message.from_user.id if message.from_user else 0
    status_code, payload = await backend_request(
        session,
        "/bot/status",
        {"telegram_id": tg_id},
    )
    verified = bool((payload or {}).get("verified")) if status_code == 200 else False
    if not verified:
        await state.clear()
        await message.answer("Сначала пройдите верификацию.", reply_markup=keyboard_verify_only())
        return

    await state.clear()
    await state.set_state(ResetState.confirm)
    await message.answer(
        "Вы уверены, что хотите восстановить пароль?",
        reply_markup=reset_confirm_buttons(),
    )


@router.callback_query(F.data == "reset_confirm")
async def reset_confirm(callback: types.CallbackQuery, state: FSMContext, session: aiohttp.ClientSession) -> None:
    await callback.answer()
    tg_id = callback.from_user.id if callback.from_user else 0
    status_code, payload = await backend_request(
        session,
        "/bot/reset_password",
        {"telegram_id": tg_id},
    )
    if status_code == 200:
        temp = (payload or {}).get("temp_password")
        await state.clear()
        if message := callback.message:
            await message.edit_text(
                f"Временный пароль: {temp}\nПосле входа обязательно измените пароль в личном кабинете."
            )
            await message.answer("Доступные действия:", reply_markup=keyboard_reset_only())
        return

    detail = (payload or {}).get("detail")
    if message := callback.message:
        await message.edit_text(map_reset_error(detail, status_code))


@router.callback_query(F.data == "reset_cancel")
async def reset_cancel(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await do_cancel(state, callback.message)


async def on_startup(app: web.Application) -> None:
    bot: Bot = app["bot"]
    dp: Dispatcher = app["dp"]
    await bot.set_my_commands(
        [
            types.BotCommand(command="start", description="Показать меню"),
            types.BotCommand(command="verify", description="Пройти верификацию"),
            types.BotCommand(command="reset", description="Восстановить пароль"),
            types.BotCommand(command="cancel", description="Отмена текущего действия"),
        ]
    )
    await bot.delete_webhook(drop_pending_updates=False)
    webhook_path = _normalize_webhook_path(WEBHOOK_PATH)
    await bot.set_webhook(
        f"{WEBHOOK_HOST}{webhook_path}",
        secret_token=WEBHOOK_SECRET,
        allowed_updates=dp.resolve_used_update_types(),
    )


async def on_shutdown(app: web.Application) -> None:
    bot: Bot = app["bot"]
    session: aiohttp.ClientSession = app["session"]
    storage: RedisStorage = app["storage"]
    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        pass
    await session.close()
    await storage.close()
    await bot.session.close()


async def main() -> None:
    if not TG_BOT_TOKEN:
        raise RuntimeError("TG_BOT_TOKEN is required")

    if not BOT_API_TOKEN:
        raise RuntimeError("BOT_API_TOKEN is required")

    if not WEBHOOK_HOST:
        raise RuntimeError("WEBHOOK_HOST is required")

    if not WEBHOOK_SECRET:
        raise RuntimeError("WEBHOOK_SECRET is required")

    webhook_path = _normalize_webhook_path(WEBHOOK_PATH)

    bot = Bot(token=TG_BOT_TOKEN)
    storage = RedisStorage.from_url(REDIS_URL)
    dp = Dispatcher(storage=storage)

    session = aiohttp.ClientSession()
    dp["session"] = session
    dp.include_router(router)

    app = web.Application()
    app["bot"] = bot
    app["dp"] = dp
    app["session"] = session
    app["storage"] = storage

    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET).register(app, path=webhook_path)
    setup_application(app, dp, bot=bot)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=WEBHOOK_PORT)
    await site.start()

    log.info("bot.webhook.ready", extra={"path": webhook_path, "port": WEBHOOK_PORT})
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
