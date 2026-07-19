from __future__ import annotations
import secrets
import structlog
from fastapi import Response
from ..core.clients import get_redis
from ..security.auth_tokens import create_access_token, create_refresh_token, parse_refresh_token
from ..realtime.connections import disconnect_user_sockets, revoke_user_session
from ..realtime.utils import cleanup_user_from_room
from ..core.settings import settings

log = structlog.get_logger()


def _set_refresh_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(
        key="rt",
        value=token,
        max_age=settings.REFRESH_EXP_DAY * 86400,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/api",
        domain=settings.DOMAIN
    )


async def cleanup_user_rooms_on_login(r, uid: int) -> None:
    try:
        room_ids_raw = await r.zrange("rooms:index", 0, -1)
    except Exception:
        room_ids_raw = []

    room_ids: list[int] = []
    for raw in room_ids_raw or []:
        try:
            room_ids.append(int(raw))
        except Exception:
            continue

    if not room_ids:
        return

    try:
        async with r.pipeline() as p:
            for rid in room_ids:
                await p.sismember(f"room:{rid}:members", str(uid))
                await p.sismember(f"room:{rid}:spectators", str(uid))
            res = await p.execute()
    except Exception:
        res = None

    for idx, rid in enumerate(room_ids):
        try:
            if res is None:
                is_member = await r.sismember(f"room:{rid}:members", str(uid))
                is_spectator = await r.sismember(f"room:{rid}:spectators", str(uid))
            else:
                is_member = bool(res[2 * idx])
                is_spectator = bool(res[2 * idx + 1])
        except Exception:
            continue

        if not is_member and not is_spectator:
            continue

        await cleanup_user_from_room(r, rid, uid, was_member=is_member, was_spectator=is_spectator, sid=None, actor_username=None)


async def new_login_session(resp: Response, *, user_id: int, username: str, role: str) -> tuple[str, str]:
    try:
        r = get_redis()
        sid = secrets.token_urlsafe(16)
        jti = secrets.token_urlsafe(16)

        rt = create_refresh_token(sub=user_id, sid=sid, jti=jti, ttl_days=settings.REFRESH_EXP_DAY)
        replace_script = """
        local previous_sid = redis.call('GET', KEYS[1])
        redis.call('SETEX', KEYS[2], tonumber(ARGV[3]), ARGV[2])
        redis.call('SET', KEYS[1], ARGV[1])
        if previous_sid and previous_sid ~= ARGV[1] then
            redis.call('DEL', 'session:' .. previous_sid .. ':rjti')
        end
        return previous_sid or ''
        """
        prev_sid = await r.eval(
            replace_script,
            2,
            f"user:{user_id}:sid",
            f"session:{sid}:rjti",
            sid,
            jti,
            settings.REFRESH_EXP_DAY * 86400,
        )

        _set_refresh_cookie(resp, rt)
        at = create_access_token(sub=user_id, username=username, role=role, sid=sid, ttl_minutes=settings.ACCESS_EXP_MIN)

        if prev_sid and prev_sid != sid:
            await disconnect_user_sockets(
                user_id,
                reason="replaced",
                only_auth_sid=str(prev_sid),
            )
        try:
            await cleanup_user_rooms_on_login(r, user_id)
        except Exception:
            log.exception("session.cleanup_rooms_failed", user_id=user_id)
        return at, sid

    except Exception:
        log.exception("session.login.db_update_failed", user_id=user_id)
        raise


async def rotate_refresh(resp: Response, *, raw_refresh_jwt: str) -> tuple[bool, int, str | None]:
    r = get_redis()
    ok, uid, sid, jti = parse_refresh_token(raw_refresh_jwt)
    if not ok:
        return False, 0, None

    new_jti = secrets.token_urlsafe(16)
    rotate_script = """
    local current_sid = redis.call('GET', KEYS[1])
    if not current_sid or current_sid ~= ARGV[1] then return -1 end
    local current_jti = redis.call('GET', KEYS[2])
    if not current_jti then return -2 end
    if current_jti ~= ARGV[2] then return -3 end
    redis.call('SETEX', KEYS[2], tonumber(ARGV[4]), ARGV[3])
    for i = 3, #KEYS do
        redis.call('EXPIRE', KEYS[i], tonumber(ARGV[5]))
    end
    return 1
    """
    result = int(await r.eval(
        rotate_script,
        6,
        f"user:{uid}:sid",
        f"session:{sid}:rjti",
        f"sio:user:{uid}:auth",
        f"sio:user:{uid}:chat",
        f"sio:user:{uid}:room",
        f"sio:user:{uid}:rooms",
        sid,
        jti,
        new_jti,
        settings.REFRESH_EXP_DAY * 86400,
        settings.REFRESH_EXP_DAY * 86400 + 3600,
    ))

    if result == -1:
        await logout(resp, user_id=uid, sid=sid)
        log.warning("session.refresh.not_current", user_id=uid, sid=sid)
        return False, 0, None

    if result == -2:
        await logout(resp, user_id=uid, sid=sid)
        log.warning("session.refresh.missing_jti", user_id=uid, sid=sid)
        return False, 0, None

    if result == -3:
        await logout(resp, user_id=uid, sid=sid)
        log.warning("session.refresh.stale_jti", user_id=uid, sid=sid)
        return False, 0, None

    if result != 1:
        log.error("session.refresh.unexpected_cas_result", user_id=uid, result=result)
        return False, 0, None

    rt = create_refresh_token(sub=uid, sid=sid, jti=new_jti, ttl_days=settings.REFRESH_EXP_DAY)
    _set_refresh_cookie(resp, rt)
    return True, uid, sid


async def logout(resp: Response, *, user_id: int, sid: str | None = None) -> None:
    resp.delete_cookie(key="rt", path="/api", domain=settings.DOMAIN, samesite="strict", secure=True)
    await revoke_user_session(
        user_id,
        reason="logout",
        expected_auth_sid=sid,
    )
