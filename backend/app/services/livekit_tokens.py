from __future__ import annotations
import datetime as dt
import structlog
from livekit.api import AccessToken
from livekit.api.access_token import VideoGrants
from ..settings import settings

log = structlog.get_logger()

def make_livekit_token(*, identity: str, name: str, room: str, ttl_minutes: int = 60) -> str:
    tok = (
        AccessToken(api_key=settings.LIVEKIT_API_KEY, api_secret=settings.LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(name)
        .with_grants(VideoGrants(
            room_join=True,
            room=room,
            can_publish=True,
            can_subscribe=True,
            can_update_own_metadata=True,
            can_publish_data=True
        ))
        .with_ttl(dt.timedelta(minutes=ttl_minutes))
        .to_jwt()
    )
    log.info("livekit.token.issued", identity=identity, room=room, ttl_minutes=ttl_minutes)
    return tok
