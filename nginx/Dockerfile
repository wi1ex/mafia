FROM node:24-alpine AS build
WORKDIR /app/frontend

ARG VITE_TG_BOT_NAME
ARG VITE_BUILD_ID

ENV VITE_TG_BOT_NAME=${VITE_TG_BOT_NAME}
ENV VITE_BUILD_ID=${VITE_BUILD_ID}

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build
RUN sh -c 'echo "${VITE_BUILD_ID:-dev-$(date +%s)}" > dist/version.txt'

FROM nginx:1.28-alpine
COPY --chmod=755 <<'NGINX_ENTRYPOINT' /usr/local/bin/nginx-redacted-entrypoint
#!/bin/sh
set -eu
umask 077

awk -f /usr/local/lib/nginx/redact-logs.awk < /dev/null > /dev/null
log_pipe="/tmp/nginx-log-$$"
mkfifo "$log_pipe"
awk -f /usr/local/lib/nginx/redact-logs.awk < "$log_pipe" >&2 &
filter_pid=$!

/docker-entrypoint.sh "$@" 2> "$log_pipe" &
server_pid=$!
trap 'kill -TERM "$server_pid" 2>/dev/null || true' TERM INT
trap 'kill -QUIT "$server_pid" 2>/dev/null || true' QUIT
trap 'kill -HUP "$server_pid" 2>/dev/null || true' HUP

set +e
wait "$server_pid"
status=$?
while kill -0 "$server_pid" 2>/dev/null; do
    wait "$server_pid"
    status=$?
done
wait "$filter_pid"
rm -f "$log_pipe"
exit "$status"
NGINX_ENTRYPOINT

COPY <<'NGINX_LOG_FILTER' /usr/local/lib/nginx/redact-logs.awk
function redact(value, fragment, prefix) {
    while (match(value, /https?:\/\/api[.]telegram[.]org\/(file\/)?bot[^\/[:space:]"<>]+/)) {
        fragment = substr(value, RSTART, RLENGTH)
        prefix = fragment
        sub(/bot[^\/]*$/, "bot", prefix)
        value = substr(value, 1, RSTART - 1) prefix "[REDACTED]" substr(value, RSTART + RLENGTH)
        # Avoid matching the replacement on the next iteration.
        sub(/bot\[REDACTED\]/, "bot<REDACTED>", value)
    }
    while (match(value, /\/rtc[[:alnum:]_\/-]*[?][^[:space:]"<>]+/)) {
        fragment = substr(value, RSTART, RLENGTH)
        sub(/[?].*$/, "", fragment)
        value = substr(value, 1, RSTART - 1) fragment "?<REDACTED>" substr(value, RSTART + RLENGTH)
    }
    gsub(/eyJ[A-Za-z0-9_-]+[.][A-Za-z0-9_-]+[.][A-Za-z0-9_-]+/, "<REDACTED_JWT>", value)
    while (match(value, /(access_token|refresh_token|token|api_key|api_secret|password|secret)=[^&[:space:]"<>]+/)) {
        fragment = substr(value, RSTART, RLENGTH)
        sub(/=.*/, "", fragment)
        value = substr(value, 1, RSTART - 1) fragment "=<REDACTED>" substr(value, RSTART + RLENGTH)
    }
    gsub(/[Bb]earer[[:space:]]+[^[:space:],;"<>]+/, "Bearer <REDACTED>", value)
    return value
}
{ print redact($0); fflush() }
NGINX_LOG_FILTER

RUN sed -i 's/\r$//' /usr/local/bin/nginx-redacted-entrypoint /usr/local/lib/nginx/redact-logs.awk
COPY nginx/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/frontend/dist/ /usr/share/nginx/html/
ENTRYPOINT ["/usr/local/bin/nginx-redacted-entrypoint"]
CMD ["nginx", "-g", "daemon off;"]
