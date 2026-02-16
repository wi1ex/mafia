from __future__ import annotations
import asyncio
import logging
import os
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from utils import (
    backend_request,
    guarded_handler,
    keyboard_reset_only,
    keyboard_verify_only,
    map_reset_error,
    map_verify_error,
    normalize_webhook_path,
    reset_confirm_buttons,
    safe_callback_answer,
    safe_message_answer,
    safe_message_delete,
    safe_message_edit_text,
    safe_telegram_call,
)

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

BACKEND_REQUEST_KWARGS = {
    "backend_url": BACKEND_URL,
    "bot_api_token": BOT_API_TOKEN,
    "request_timeout": REQUEST_TIMEOUT,
    "retry_attempts": RETRY_ATTEMPTS,
    "logger": log,
}


class VerifyState(StatesGroup):
    username = State()
    password = State()


class ResetState(StatesGroup):
    confirm = State()


router = Router()


@router.message(Command("start"))
@guarded_handler
async def start_cmd(message: types.Message, session: aiohttp.ClientSession) -> None:
    tg_id = message.from_user.id if message.from_user else 0
    status_code, payload = await backend_request(
        session,
        "/bot/status",
        {"telegram_id": tg_id},
        **BACKEND_REQUEST_KWARGS,
    )
    verified = bool((payload or {}).get("verified")) if status_code == 200 else False
    kb = keyboard_reset_only() if verified else keyboard_verify_only()
    await safe_message_answer(message, "Выберите действие:", reply_markup=kb)


@router.message(Command("cancel"))
@guarded_handler
async def cancel_cmd(message: types.Message, state: FSMContext) -> None:
    await do_cancel(state, message)


async def do_cancel(state: FSMContext, message: types.Message | None) -> None:
    await state.clear()
    if message:
        await safe_message_answer(message, "Действие отменено.")


@router.message(Command("verify"))
@router.message(F.text == "Верификация")
@guarded_handler
async def verify_start(message: types.Message, state: FSMContext, session: aiohttp.ClientSession) -> None:
    tg_id = message.from_user.id if message.from_user else 0
    status_code, payload = await backend_request(
        session,
        "/bot/status",
        {"telegram_id": tg_id},
        **BACKEND_REQUEST_KWARGS,
    )
    verified = bool((payload or {}).get("verified")) if status_code == 200 else False
    if verified:
        await state.clear()
        await safe_message_answer(message, "Этот Telegram уже привязан. Доступен Сброс пароля.", reply_markup=keyboard_reset_only())
        return

    await state.clear()
    await state.set_state(VerifyState.username)
    await safe_message_answer(message, "Введите никнейм:")


@router.message(VerifyState.username, F.text)
@guarded_handler
async def verify_username(message: types.Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    parts = [p for p in text.split() if p]
    if len(parts) != 1:
        await safe_message_answer(message, "Введите никнейм без пробелов.")
        return

    username = parts[0]
    await state.update_data(username=username)
    await state.set_state(VerifyState.password)
    await safe_message_answer(message, "Введите пароль:")


@router.message(VerifyState.password, F.text)
@guarded_handler
async def verify_password(message: types.Message, state: FSMContext, session: aiohttp.ClientSession) -> None:
    password = (message.text or "").strip()
    await safe_message_delete(message)

    if not password:
        await safe_message_answer(message, "Введите пароль.")
        return

    data = await state.get_data()
    username = str((data or {}).get("username") or "").strip()
    if not username:
        await state.clear()
        await state.set_state(VerifyState.username)
        await safe_message_answer(message, "Сессия верификации истекла. Введите никнейм:")
        return

    tg_id = message.from_user.id if message.from_user else 0
    status_code, payload = await backend_request(
        session,
        "/bot/verify",
        {"username": username, "password": password, "telegram_id": tg_id},
        **BACKEND_REQUEST_KWARGS,
    )

    await state.clear()
    if status_code == 200:
        await safe_message_answer(message, "Верификация прошла успешно. Доступ к комнатам открыт.", reply_markup=keyboard_reset_only())
        return

    detail = (payload or {}).get("detail")
    await state.set_state(VerifyState.username)
    await safe_message_answer(
        message,
        f"{map_verify_error(detail, status_code)}\nВведите никнейм:",
        reply_markup=keyboard_verify_only(),
    )


@router.message(Command("reset"))
@router.message(F.text == "Сбросить пароль")
@guarded_handler
async def reset_start(message: types.Message, state: FSMContext, session: aiohttp.ClientSession) -> None:
    tg_id = message.from_user.id if message.from_user else 0
    status_code, payload = await backend_request(
        session,
        "/bot/status",
        {"telegram_id": tg_id},
        **BACKEND_REQUEST_KWARGS,
    )
    verified = bool((payload or {}).get("verified")) if status_code == 200 else False
    if not verified:
        await state.clear()
        await safe_message_answer(message, "Сначала пройдите верификацию.", reply_markup=keyboard_verify_only())
        return

    await state.clear()
    await state.set_state(ResetState.confirm)
    await safe_message_answer(
        message,
        "Вы уверены, что хотите сбросить пароль?",
        reply_markup=reset_confirm_buttons(),
    )


@router.callback_query(F.data == "reset_confirm")
@guarded_handler
async def reset_confirm(callback: types.CallbackQuery, state: FSMContext, session: aiohttp.ClientSession) -> None:
    await safe_callback_answer(callback)
    tg_id = callback.from_user.id if callback.from_user else 0
    status_code, payload = await backend_request(
        session,
        "/bot/reset_password",
        {"telegram_id": tg_id},
        **BACKEND_REQUEST_KWARGS,
    )
    if status_code == 200:
        temp = (payload or {}).get("temp_password")
        username = (payload or {}).get("username") or "не указан"
        await state.clear()
        if message := callback.message:
            await safe_message_edit_text(
                message,
                f"Пароль успешно сброшен!\n"
                f"Прежний никнейм: {username}\n"
                f"Временный пароль: {temp}\n"
                f"После входа обязательно измените пароль в Личном кабинете.",
            )
            await safe_message_answer(message, "Выберите действие:", reply_markup=keyboard_reset_only())
        return

    detail = (payload or {}).get("detail")
    if message := callback.message:
        await safe_message_edit_text(message, map_reset_error(detail, status_code))


@router.callback_query(F.data == "reset_cancel")
@guarded_handler
async def reset_cancel(callback: types.CallbackQuery, state: FSMContext) -> None:
    await safe_callback_answer(callback)
    await do_cancel(state, callback.message)


async def on_startup(app: web.Application) -> None:
    bot: Bot = app["bot"]
    dp: Dispatcher = app["dp"]
    await safe_telegram_call(
        "bot.set_my_commands",
        lambda: bot.set_my_commands(
            [
                types.BotCommand(command="start", description="Показать меню"),
                types.BotCommand(command="verify", description="Пройти верификацию"),
                types.BotCommand(command="reset", description="Сбросить пароль"),
                types.BotCommand(command="cancel", description="Отмена текущего действия"),
            ]
        ),
        retries=RETRY_ATTEMPTS,
        logger=log,
    )
    await safe_telegram_call(
        "bot.delete_webhook",
        lambda: bot.delete_webhook(drop_pending_updates=False),
        retries=RETRY_ATTEMPTS,
        logger=log,
    )
    webhook_path = normalize_webhook_path(WEBHOOK_PATH)
    await safe_telegram_call(
        "bot.set_webhook",
        lambda: bot.set_webhook(
            f"{WEBHOOK_HOST}{webhook_path}",
            secret_token=WEBHOOK_SECRET,
            allowed_updates=dp.resolve_used_update_types(),
        ),
        retries=RETRY_ATTEMPTS,
        logger=log,
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

    webhook_path = normalize_webhook_path(WEBHOOK_PATH)
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
