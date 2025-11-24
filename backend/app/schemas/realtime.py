from typing import Dict, List, Optional, TypedDict, Literal


class JoinAck(TypedDict, total=False):
    ok: bool
    error: str
    status: int
    room_id: int
    token: str
    privacy: Literal["open", "private"]
    snapshot: Dict[str, Dict[str, str]]
    self_pref: Dict[str, str]
    positions: Dict[str, int]
    blocked: Dict[str, Dict[str, str]]
    roles: Dict[str, str]
    profiles: Dict[str, Dict[str, Optional[str]]]
    screen_owner: int
    pending: bool
    game: dict
    game_runtime: dict


class RoomListItem(TypedDict):
    id: int
    title: str
    user_limit: int
    privacy: Literal["open", "private"]
    creator: int
    creator_name: str
    creator_avatar_name: Optional[str]
    created_at: str
    occupancy: int
    in_game: bool
    game_phase: str


class RoomsListAck(TypedDict):
    ok: bool
    rooms: List[RoomListItem]


class StateAck(TypedDict):
    ok: bool


class ModerateAck(TypedDict, total=False):
    ok: bool
    status: int
    error: str
    applied: Dict[str, str]
    forced_off: Dict[str, str]


class ScreenAck(TypedDict, total=False):
    ok: bool
    on: bool
    error: str
    status: int
    owner: int


class GameStartAck(TypedDict, total=False):
    ok: bool
    status: int
    error: str
    room_id: int
    phase: str
    min_ready: int
    seats: Dict[str, int]
    can_start: bool
    streaming_owner: int
    blocking_users: List[int]
    conflict_users: List[int]
