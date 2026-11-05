from __future__ import annotations
import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any
from uuid import uuid4
from .clients import get_redis

__all__ = ["run_shared_job"]

_LEASE_TTL_SECONDS = 60
_LEASE_RENEW_SECONDS = 15
_CLEANUP_TIMEOUT_SECONDS = 5
_MAX_EXACT_SLOT = 2**53 - 1

_READ_COMPLETED_LUA = """
local completed = redis.call('GET', KEYS[2])
local last = nil
if completed then
    if not string.match(completed, '^%-?%d+$') then
        return redis.error_reply('invalid background job completed slot')
    end
    last = tonumber(completed)
    if not last or math.abs(last) > 9007199254740991 then
        return redis.error_reply('invalid background job completed slot')
    end
end
local slot = tonumber(ARGV[2])
"""

_CLAIM_LUA = _READ_COMPLETED_LUA + """
if last and last >= slot then
    return 2
end
if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[3]) then
    return 1
end
return 0
"""

_RENEW_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return 0
"""

_COMPLETE_LUA = _READ_COMPLETED_LUA + """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then
    return 0
end
if not last or last < slot then
    if tonumber(ARGV[3]) > 0 then
        redis.call('SET', KEYS[2], ARGV[2], 'EX', ARGV[3])
    else
        redis.call('SET', KEYS[2], ARGV[2])
    end
end
redis.call('DEL', KEYS[1])
return 1
"""

_RELEASE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


def _consume_task_result(task: asyncio.Task[Any]) -> None:
    with suppress(asyncio.CancelledError, Exception):
        task.exception()


async def _cleanup_job(
    redis: Any,
    lease_key: str,
    token: str,
    tasks: tuple[asyncio.Task[Any], ...],
    *,
    release: bool,
) -> None:
    deadline = asyncio.get_running_loop().time() + _CLEANUP_TIMEOUT_SECONDS
    for task in tasks:
        task.add_done_callback(_consume_task_result)
        if not task.done():
            task.cancel()
    _, pending = await asyncio.wait(tasks, timeout=_CLEANUP_TIMEOUT_SECONDS)
    if pending or not release:
        return

    remaining = deadline - asyncio.get_running_loop().time()
    if remaining > 0:
        with suppress(Exception):
            await asyncio.wait_for(
                redis.eval(_RELEASE_LUA, 1, lease_key, token), timeout=remaining
            )


async def run_shared_job(
    name: str,
    slot: int,
    callback: Callable[[], Awaitable[Any]],
    *,
    completion_ttl: int | None = None,
) -> bool:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Background job name must not be empty")

    if type(slot) is not int or abs(slot) > _MAX_EXACT_SLOT:
        raise ValueError("Background job slot must be an exact integer")

    if completion_ttl is not None and (
        type(completion_ttl) is not int or completion_ttl <= 0
    ):
        raise ValueError("Background job completion TTL must be positive")

    redis = get_redis()
    lease_key = f"background:job:{name}:lease"
    done_key = f"background:job:{name}:done"
    token = uuid4().hex
    claimed = int(await redis.eval(
        _CLAIM_LUA, 2, lease_key, done_key, token, slot, _LEASE_TTL_SECONDS
    ))
    if claimed == 2:
        return True

    if claimed == 0:
        return False

    if claimed != 1:
        raise RuntimeError("Invalid background job claim result")

    async def execute() -> Any:
        return await callback()

    async def renew() -> None:
        while True:
            await asyncio.sleep(_LEASE_RENEW_SECONDS)
            renewed = await redis.eval(
                _RENEW_LUA, 1, lease_key, token, _LEASE_TTL_SECONDS
            )
            if int(renewed) != 1:
                raise RuntimeError(f"Background job lease lost: {name}")

    body = asyncio.create_task(execute())
    renewal = asyncio.create_task(renew())
    completed = False
    try:
        finished, _ = await asyncio.wait(
            (body, renewal), return_when=asyncio.FIRST_COMPLETED
        )
        if renewal in finished:
            await renewal
            raise RuntimeError(f"Background job renewal stopped: {name}")

        await body
        renewal.cancel()
        renewal_result = (await asyncio.gather(renewal, return_exceptions=True))[0]
        if isinstance(renewal_result, BaseException) and not isinstance(
            renewal_result, asyncio.CancelledError
        ):
            raise renewal_result

        saved = await redis.eval(
            _COMPLETE_LUA, 2, lease_key, done_key, token, slot, completion_ttl or 0
        )
        if int(saved) != 1:
            raise RuntimeError(f"Background job lease lost: {name}")

        completed = True
        return True

    finally:
        cleanup = asyncio.create_task(_cleanup_job(
            redis, lease_key, token, (body, renewal), release=not completed
        ))
        cleanup.add_done_callback(_consume_task_result)
        await asyncio.shield(cleanup)
