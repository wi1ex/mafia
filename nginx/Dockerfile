# --- build SPA ---
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./frontend/
WORKDIR /app/frontend
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- edge nginx ---
FROM nginx:1.27-alpine
COPY nginx/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/frontend/dist/ /usr/share/nginx/html/
