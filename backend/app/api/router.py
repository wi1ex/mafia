from fastapi import APIRouter
from .routes import auth, users, rooms, media, notifs, admin, updates

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
api_router.include_router(notifs.router, prefix="/notifs", tags=["notifs"])
api_router.include_router(updates.router, prefix="/updates", tags=["updates"])
