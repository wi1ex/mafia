# --- build SPA ---
FROM node:20-alpine AS build
WORKDIR /app/frontend

# build args из docker-compose
ARG VITE_API_BASE
ARG VITE_TG_BOT_NAME
ENV VITE_API_BASE=${VITE_API_BASE}
ENV VITE_TG_BOT_NAME=${VITE_TG_BOT_NAME}

COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- edge nginx ---
FROM nginx:1.27-alpine
COPY nginx/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/frontend/dist/ /usr/share/nginx/html/
