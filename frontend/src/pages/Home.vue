<template>
  <div class="container">
    <div class="card">
      <h1>Добро пожаловать в Mafia</h1>
      <p>Стартовый каркас развёрнут. Реалтайм-каналы подготовлены, вход в комнаты будет позже.</p>
      <ul>
        <li>API health: <code>/api/v1/health/ping</code></li>
        <li>SSE: <code>/sse/events</code></li>
        <li>Socket.IO: <code>/ws-sio</code></li>
        <li>LiveKit WS: <code>/rtc</code> (проксируется Nginx)</li>
      </ul>
    </div>
  </div>
</template>
