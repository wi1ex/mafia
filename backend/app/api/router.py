from fastapi import APIRouter
from .routes import auth, users, rooms, media

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
api_router.include_router(media.router, prefix="/media", tags=["media"])

# @router.post("/admin-only")
# async def admin_task(_: bool = Depends(require_roles("admin"))):
#     return {"status": "ok"}
