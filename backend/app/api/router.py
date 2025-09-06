from fastapi import APIRouter
from .v1 import health, auth, rooms, users

api_router = APIRouter()
api_router.include_router(health.router, prefix="/v1/health", tags=["health"])
api_router.include_router(auth.router,   prefix="/v1/auth",   tags=["auth"])
api_router.include_router(users.router,  prefix="/v1/users",  tags=["users"])
api_router.include_router(rooms.router,  prefix="/v1/rooms",  tags=["rooms"])
