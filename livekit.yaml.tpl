port: ${LIVEKIT_HTTP_PORT}
log_level: info
region: eu-nl

rtc:
  port_range_start: ${LIVEKIT_PORT_RANGE_START}
  port_range_end: ${LIVEKIT_PORT_RANGE_END}
  tcp_port: ${LIVEKIT_TCP_PORT}
  use_external_ip: true

turn:
  enabled: true
  domain: ${DOMAIN}
  udp_port: ${LIVEKIT_UDP_PORT}
  tls_port: ${LIVEKIT_TLS_PORT}
  cert_file: ${SSL_CERT_PATH}
  key_file: ${SSL_KEY_PATH}

redis:
  address: 127.0.0.1:${REDIS_PORT}
  password: ${REDIS_PASSWORD}
  db: 0

keys:
  ${LIVEKIT_API_KEY}: ${LIVEKIT_API_SECRET}
