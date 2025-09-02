from socketio import AsyncServer, ASGIApp

def build_sio(cors):
    sio = AsyncServer(async_mode="asgi", cors_allowed_origins=cors, ping_interval=20, ping_timeout=30)
    @sio.event
    async def connect(sid, environ): ...
    @sio.event
    async def disconnect(sid): ...
    return ASGIApp(sio, socketio_path="socket.io")
