# Frontend container for Fly.io — Vercel-independent host.
# Multi-stage: install deps -> build (standalone) -> slim runner.
# NEXT_PUBLIC_* are inlined at BUILD time, so the two real ones are passed
# as build args. Everything else has a safe in-code fallback (Turnstile off,
# GA/Ads IDs hardcoded defaults, founder vars cosmetic).

# ---- deps ----
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# ---- build ----
FROM node:20-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_URL=https://api.tapeline.io
ARG NEXT_PUBLIC_APP_URL=https://tapeline.io
ARG NEXT_PUBLIC_SITE_URL=https://tapeline.io
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL \
    NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---- runner ----
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
# Standalone output: server.js + minimal node_modules, plus static + public.
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
