from fastapi import APIRouter, Depends
from .routes import admin, auth, bot, friends, media, moderation, notifs, payments, rooms, users
from ..security.decorators import audit_router_guards, minimal_route_rate_limit

api_router = APIRouter(dependencies=[Depends(minimal_route_rate_limit)])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(bot.router, prefix="/bot", tags=["bot"])
api_router.include_router(admin.public_router, prefix="/admin", tags=["admin"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(moderation.router, prefix="/moderation", tags=["moderation"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
api_router.include_router(friends.router, prefix="/friends", tags=["friends"])
api_router.include_router(notifs.router, prefix="/notifs", tags=["notifs"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
audit_router_guards(api_router)
