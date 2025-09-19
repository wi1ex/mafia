from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter, Depends, Path
from ...core.clients import get_redis
from ...core.route_utils import log_route
from ...models.user import User
from ...schemas import Ok
from ...services.sessions import get_current_user


router = APIRouter()


@log_route("room.update_state")
@router.post("/{room_id}/state", response_model=Ok)
async def update_state(payload: Dict[str, Any], room_id: int = Path(..., ge=1), user: User = Depends(get_current_user)) -> Ok:
    r = get_redis()
    data = {k: "1" if bool(v) else "0" for k, v in (payload or {}).items() if k in {"mic", "cam", "speakers", "visibility"}}
    if data:
        await r.hset(f"room:{room_id}:user:{user.id}:state", mapping=data)
    return Ok()
