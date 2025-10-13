from __future__ import annotations
from datetime import timedelta
import structlog
from livekit.api import AccessToken, VideoGrants
from ..settings import settings

log = structlog.get_logger()


def make_livekit_token(*, identity: str, name: str, room: str, ttl_minutes: int = 60) -> str:
    try:
        tok = (
            AccessToken(api_key=settings.LIVEKIT_API_KEY, api_secret=settings.LIVEKIT_API_SECRET)
            .with_identity(identity)
            .with_name(name)
            .with_grants(VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
                can_update_own_metadata=True,
                can_publish_sources=["camera", "microphone", "screen_share", "screen_share_audio"],
            ))
            .with_ttl(timedelta(minutes=ttl_minutes))
            .to_jwt()
        )
        log.info("livekit.token.issued", identity=identity, room=room, ttl_minutes=ttl_minutes)
        return tok

    except Exception:
        log.exception("livekit.token.issue_failed", identity=identity, room=room)
        raise
