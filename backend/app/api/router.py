from fastapi import APIRouter
from .routes import auth, users, rooms, media, notifs

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
api_router.include_router(notifs.router, prefix="/notifs", tags=["notifs"])

# @require_roles_deco("admin","moder")
# @router.get("/staff/metrics")
# async def staff_metrics():
