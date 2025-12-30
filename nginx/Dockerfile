FROM node:24-alpine AS build
WORKDIR /app/frontend

ARG VITE_TG_BOT_NAME
ARG VITE_TG_BOT_ID
ARG VITE_BUILD_ID

ENV VITE_TG_BOT_NAME=${VITE_TG_BOT_NAME}
ENV VITE_TG_BOT_ID=${VITE_TG_BOT_ID}
ENV VITE_BUILD_ID=${VITE_BUILD_ID}

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build
RUN sh -c 'echo "${VITE_BUILD_ID:-dev-$(date +%s)}" > dist/version.txt'

FROM nginx:1.28-alpine
COPY nginx/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/frontend/dist/ /usr/share/nginx/html/
