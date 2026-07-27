# --- Stage 1: build the static Vite bundle ---
FROM node:22-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build
# Vite's default output dir is /app/dist

# --- Stage 2: serve it with nginx, proxying /api to the backend container ---
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
