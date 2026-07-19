from __future__ import annotations
import asyncio
from contextlib import suppress
from time import time
from typing import Any, Mapping
import structlog
from ..core.clients import get_redis
from ..core.roles import normalize_user_role
from ..core.settings import settings
from ..security.admin_guard import normalize_protected_admin_role
from ..services.user_cache import read_user_profile_cache
from .sio import sio

log = structlog.get_logger()

AUTHENTICATED_NAMESPACES = ("/auth", "/chat", "/room", "/rooms")
_REGISTRY_TTL_SECONDS = max(86400, int(settings.REFRESH_EXP_DAY) * 86400 + 3600)
_SESSION_WATCHDOG_SECONDS = 30
_watchdog_tasks: dict[tuple[str, str], asyncio.Task[None]] = {}


class _SocketSessionRejected(Exception):
    def __init__(self, reason: str, *, emit_force_logout: bool = True) -> None:
        super().__init__(reason)
        self.reason = reason
        self.emit_force_logout = emit_force_logout


def _stop_session_watchdog(socket_sid: str, namespace: str) -> None:
    task = _watchdog_tasks.pop((namespace, socket_sid), None)
    current = asyncio.current_task()
    if task and task is not current and not task.done():
        task.cancel()


async def _session_watchdog(socket_sid: str, namespace: str) -> None:
    try:
        while True:
            await asyncio.sleep(_SESSION_WATCHDOG_SECONDS)
            if await validate_socket_session(socket_sid, namespace=namespace) is None:
                return

    except asyncio.CancelledError:
        raise

    except Exception:
        log.exception(
            "sio.session.watchdog_failed",
            namespace=namespace,
        )
        await _disconnect_socket(
            user_id=0,
            socket_sid=socket_sid,
            namespace=namespace,
            reason="auth_service_unavailable",
            emit_force_logout=False,
        )
    finally:
        current = asyncio.current_task()
        watchdog_key = (namespace, socket_sid)
        if _watchdog_tasks.get(watchdog_key) is current:
            del _watchdog_tasks[watchdog_key]


def _start_session_watchdog(socket_sid: str, namespace: str) -> None:
    _stop_session_watchdog(socket_sid, namespace)
    _watchdog_tasks[(namespace, socket_sid)] = asyncio.create_task(
        _session_watchdog(socket_sid, namespace),
        name=f"sio-auth-watchdog:{namespace}:{socket_sid}",
    )


def _registry_key(user_id: int, namespace: str) -> str:
    normalized = namespace.strip("/") or "root"
    if namespace not in AUTHENTICATED_NAMESPACES:
        raise ValueError("unsupported Socket.IO namespace")

    return f"sio:user:{int(user_id)}:{normalized}"


async def register_user_socket(
    *,
    user_id: int,
    socket_sid: str,
    namespace: str,
    auth_sid: str,
) -> None:
    uid = int(user_id)
    if uid <= 0 or not socket_sid or not auth_sid:
        raise ValueError("authenticated socket registration requires uid and session ids")

    r = get_redis()
    key = _registry_key(uid, namespace)
    async with r.pipeline() as p:
        await p.hset(key, mapping={socket_sid: auth_sid})
        await p.expire(key, _REGISTRY_TTL_SECONDS)
        await p.execute()
    _start_session_watchdog(socket_sid, namespace)


async def unregister_user_socket(*, user_id: int, socket_sid: str, namespace: str) -> None:
    _stop_session_watchdog(socket_sid, namespace)
    uid = int(user_id)
    if uid <= 0 or not socket_sid:
        return

    with suppress(Exception):
        await get_redis().hdel(_registry_key(uid, namespace), socket_sid)


async def _disconnect_socket(
    *,
    user_id: int,
    socket_sid: str,
    namespace: str,
    reason: str,
    emit_force_logout: bool = True,
) -> None:
    if emit_force_logout:
        with suppress(Exception):
            await sio.emit(
                "force_logout",
                {"reason": reason},
                to=socket_sid,
                namespace=namespace,
            )
    try:
        await sio.disconnect(socket_sid, namespace=namespace)
    except Exception:
        log.warning(
            "sio.session.disconnect_failed",
            user_id=int(user_id),
            namespace=namespace,
        )


async def disconnect_user_sockets(
    user_id: int,
    *,
    reason: str,
    only_auth_sid: str | None = None,
) -> int:
    uid = int(user_id)
    if uid <= 0:
        return 0

    r = get_redis()
    disconnected = 0
    for namespace in AUTHENTICATED_NAMESPACES:
        key = _registry_key(uid, namespace)
        try:
            registered = await r.hgetall(key)
        except Exception:
            log.exception(
                "sio.session.registry_read_failed",
                user_id=uid,
                namespace=namespace,
            )
            continue

        for socket_sid, registered_auth_sid in (registered or {}).items():
            if only_auth_sid and str(registered_auth_sid) != str(only_auth_sid):
                continue
            await _disconnect_socket(
                user_id=uid,
                socket_sid=str(socket_sid),
                namespace=namespace,
                reason=reason,
            )
            disconnected += 1
            with suppress(Exception):
                await r.hdel(key, socket_sid)

    return disconnected


async def revoke_user_session(
    user_id: int,
    *,
    reason: str,
    expected_auth_sid: str | None = None,
) -> bool:
    uid = int(user_id)
    if uid <= 0:
        return False

    r = get_redis()
    expected = str(expected_auth_sid or "")
    revoke_script = """
    local current_sid = redis.call('GET', KEYS[1])
    local expected_sid = ARGV[1]
    if expected_sid ~= '' then
        redis.call('DEL', 'session:' .. expected_sid .. ':rjti')
        if current_sid and current_sid == expected_sid then
            redis.call('DEL', KEYS[1])
            return expected_sid
        end
        return ''
    end
    if current_sid then
        redis.call('DEL', 'session:' .. current_sid .. ':rjti')
        redis.call('DEL', KEYS[1])
        return current_sid
    end
    return ''
    """
    removed_current_sid = str(await r.eval(
        revoke_script,
        1,
        f"user:{uid}:sid",
        expected,
    ) or "")

    target_auth_sid = expected or removed_current_sid
    if target_auth_sid:
        await disconnect_user_sockets(
            uid,
            reason=reason,
            only_auth_sid=target_auth_sid,
        )
    return bool(removed_current_sid)


async def validate_socket_session(
    socket_sid: str,
    *,
    namespace: str,
    auth_optional: bool = False,
) -> Mapping[str, Any] | None:
    try:
        session = await sio.get_session(socket_sid, namespace=namespace)
        if not isinstance(session, Mapping):
            raise _SocketSessionRejected("session_expired")

        try:
            uid = int(session.get("uid") or 0)
        except (TypeError, ValueError):
            raise _SocketSessionRejected("session_expired") from None

        if uid <= 0 and auth_optional:
            return session

        if uid <= 0:
            raise _SocketSessionRejected("session_expired")

        auth_sid = str(session.get("auth_sid") or "")
        if not auth_sid:
            raise _SocketSessionRejected("session_expired")

        try:
            auth_expires_at = int(session.get("auth_expires_at") or 0)
        except (TypeError, ValueError):
            auth_expires_at = 0
        if auth_expires_at <= int(time()):
            raise _SocketSessionRejected(
                "access_token_expired",
                emit_force_logout=False,
            )

        r = get_redis()
        async with r.pipeline() as p:
            await p.get(f"user:{uid}:sid")
            await p.exists(f"session:{auth_sid}:rjti")
            current_auth_sid_raw, refresh_family_exists = await p.execute()
        current_auth_sid = str(current_auth_sid_raw or "")
        if not current_auth_sid or current_auth_sid != auth_sid:
            raise _SocketSessionRejected("session_revoked")

        if not refresh_family_exists:
            raise _SocketSessionRejected("session_expired")

        profile = await read_user_profile_cache(uid, redis_client=r)
        if not profile:
            raise _SocketSessionRejected("profile_unavailable", emit_force_logout=False)

        if profile.get("deleted_at"):
            raise _SocketSessionRejected("account_deleted")

        session_role = str(session.get("base_role") or session.get("role") or "user")
        profile_role = normalize_protected_admin_role(
            uid,
            str(profile.get("role") or "user"),
            fallback_role="user",
        )
        if normalize_user_role(session_role) != normalize_user_role(profile_role):
            raise _SocketSessionRejected("role_changed")

        return session

    except _SocketSessionRejected as exc:
        log.warning(
            "sio.session.rejected",
            namespace=namespace,
            reason=exc.reason,
        )
        uid = 0
        with suppress(Exception):
            raw_session = await sio.get_session(socket_sid, namespace=namespace)
            uid = int((raw_session or {}).get("uid") or 0)
        if uid > 0:
            await unregister_user_socket(
                user_id=uid,
                socket_sid=socket_sid,
                namespace=namespace,
            )
        await _disconnect_socket(
            user_id=uid,
            socket_sid=socket_sid,
            namespace=namespace,
            reason=exc.reason,
            emit_force_logout=exc.emit_force_logout,
        )
        return None

    except Exception as exc:
        log.exception(
            "sio.session.validation_unavailable",
            namespace=namespace,
            reason=type(exc).__name__,
        )
        uid = 0
        with suppress(Exception):
            raw_session = await sio.get_session(socket_sid, namespace=namespace)
            uid = int((raw_session or {}).get("uid") or 0)
        await _disconnect_socket(
            user_id=uid,
            socket_sid=socket_sid,
            namespace=namespace,
            reason="auth_service_unavailable",
            emit_force_logout=False,
        )
        return None
