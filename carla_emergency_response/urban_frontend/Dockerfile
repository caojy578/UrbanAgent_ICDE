# syntax=docker/dockerfile:1.7

# ────────────────────────────────────────────────────────────
# Stage 1 — build the static bundle
# ────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Install deps using a deterministic lockfile install. Mounting the npm
# cache as a buildkit cache makes repeated builds fast.
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

COPY . .
# Allow build-time injection of public env vars (VITE_*).
ARG VITE_SOCKET_URL
ARG VITE_UAV_FEED_URL
ARG VITE_UGV_FEED_URL
ARG VITE_CITY_FEED_URL
ENV VITE_SOCKET_URL=${VITE_SOCKET_URL}
ENV VITE_UAV_FEED_URL=${VITE_UAV_FEED_URL}
ENV VITE_UGV_FEED_URL=${VITE_UGV_FEED_URL}
ENV VITE_CITY_FEED_URL=${VITE_CITY_FEED_URL}

RUN npm run build


# ────────────────────────────────────────────────────────────
# Stage 2 — serve the bundle via nginx
# ────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runner

# Strip the default config and drop in our own.
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/site.conf.template /etc/nginx/conf.d/site.conf.template

# Copy the built bundle.
COPY --from=builder /app/dist /usr/share/nginx/html

# Optional: backend host override at run-time.
# `docker run -e BACKEND_HOST=bridge:5000 ...`
ENV BACKEND_HOST=localhost:5000

# Render config with the runtime backend host before launching nginx.
COPY nginx/entrypoint.sh /docker-entrypoint.d/40-render-backend.sh
RUN chmod +x /docker-entrypoint.d/40-render-backend.sh

EXPOSE 80

# nginx image already provides the canonical CMD; we just inherit it.
