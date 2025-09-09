FROM node:20-alpine AS build
WORKDIR /app/frontend

ARG VITE_TG_BOT_NAME
ENV VITE_TG_BOT_NAME=${VITE_TG_BOT_NAME}

COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/frontend/dist/ /usr/share/nginx/html/
