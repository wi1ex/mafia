from __future__ import annotations
import asyncio
from datetime import timedelta
from typing import Iterable
from urllib.parse import urlparse
from aiohttp import ClientTimeout
import structlog
from livekit.api import AccessToken, LiveKitAPI, VideoGrants
from livekit.api.twirp_client import TwirpError
from livekit.protocol.room import RoomParticipantIdentity
from ..core.settings import settings

log = structlog.get_logger()
_preferred_livekit_api_url: str | None = None


def get_livekit_room_name(rid: int) -> str:
    return f"{settings.PROJECT_NAME}_{int(rid)}"


def _normalize_livekit_url(raw: str) -> str:
    value = str(raw or "").strip().rstrip("/")
    if not value:
        return ""

    parsed = urlparse(value)
    if parsed.scheme:
        return value

    return f"http://{value}"


def _iter_livekit_api_urls() -> Iterable[str]:
    seen: set[str] = set()

    preferred = _normalize_livekit_url(_preferred_livekit_api_url or "")
    if preferred:
        seen.add(preferred)
        yield preferred

    upstream = _normalize_livekit_url(getattr(settings, "LIVEKIT_UPSTREAM", ""))
    if upstream and upstream not in seen:
        seen.add(upstream)
        yield upstream

    nginx_url = "http://nginx/rtc"
    if nginx_url not in seen:
        seen.add(nginx_url)
        yield nginx_url

    domain = str(getattr(settings, "DOMAIN", "") or "").strip()
    if domain:
        domain_url = f"https://{domain}/rtc"
        if domain_url not in seen:
            yield domain_url


def make_livekit_token(*, identity: str, name: str, room: str, ttl_minutes: int = 60, can_publish: bool = True) -> str:
    try:
        publish_sources = ["camera", "microphone", "screen_share", "screen_share_audio"] if can_publish else []
        tok = (
            AccessToken(api_key=settings.LIVEKIT_API_KEY, api_secret=settings.LIVEKIT_API_SECRET)
            .with_identity(identity)
            .with_name(name)
            .with_grants(VideoGrants(
                room_join=True,
                room=room,
                can_publish=can_publish,
                can_subscribe=True,
                can_publish_data=can_publish,
                can_update_own_metadata=True,
                can_publish_sources=publish_sources,
            ))
            .with_ttl(timedelta(minutes=ttl_minutes))
            .to_jwt()
        )
        log.info("livekit.token.issued", identity=identity, room=room, ttl_minutes=ttl_minutes)
        return tok

    except Exception:
        log.exception("livekit.token.issue_failed", identity=identity, room=room)
        raise


async def remove_livekit_participant(*, rid: int, uid: int, timeout_seconds: float = 1.0, retry_rounds: int = 3) -> bool:
    global _preferred_livekit_api_url
    room = get_livekit_room_name(rid)
    identity = str(int(uid))
    timeout = ClientTimeout(total=max(0.35, float(timeout_seconds)))
    urls = list(_iter_livekit_api_urls())
    attempted_urls: list[str] = []
    last_err: str | None = None
    rounds = max(1, int(retry_rounds))

    for round_idx in range(rounds):
        for url in urls:
            attempted_urls.append(url)
            api: LiveKitAPI | None = None
            try:
                api = LiveKitAPI(
                    url=url,
                    api_key=settings.LIVEKIT_API_KEY,
                    api_secret=settings.LIVEKIT_API_SECRET,
                    timeout=timeout,
                )
                await api.room.remove_participant(RoomParticipantIdentity(room=room, identity=identity))
                _preferred_livekit_api_url = url
                log.info("livekit.participant.removed", rid=rid, uid=uid, room=room, url=url, round=round_idx + 1)
                return True

            except TwirpError as err:
                if err.code == "not_found":
                    _preferred_livekit_api_url = url
                    log.info("livekit.participant.already_absent", rid=rid, uid=uid, room=room, url=url, round=round_idx + 1)
                    return True

                last_err = f"{type(err).__name__}:{err.code}"

            except Exception as err:
                last_err = type(err).__name__

            finally:
                if api is not None:
                    try:
                        await api.aclose()
                    except Exception:
                        log.warning("livekit.client.close_failed", rid=rid, uid=uid, room=room, url=url)

        if round_idx + 1 < rounds:
            await asyncio.sleep(min(0.25 * (round_idx + 1), 1.0))

    log.warning("livekit.participant.remove_failed", rid=rid, uid=uid, room=room, urls=attempted_urls, err=last_err, rounds=rounds)
    return False
