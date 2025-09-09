from __future__ import annotations
import datetime as dt
from livekit.api import AccessToken
from livekit.api.access_token import VideoGrants
from ..settings import settings

def make_livekit_token(*, identity: str, name: str, room: str, ttl_minutes: int = 60) -> str:
    return (
        AccessToken(api_key=settings.LIVEKIT_API_KEY, api_secret=settings.LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(name)
        .with_grants(VideoGrants(room_join=True, room=room, can_publish=True, can_subscribe=True))
        .with_ttl(dt.timedelta(minutes=ttl_minutes))
        .to_jwt()
    )
