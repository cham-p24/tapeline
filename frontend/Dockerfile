# Frontend container for Fly.io — Vercel-independent host.
# Multi-stage: install deps -> build (standalone) -> slim runner.
# NEXT_PUBLIC_* are inlined at BUILD time, so anything that GATES a feature has
# to be passed as a build arg here. `fly secrets set NEXT_PUBLIC_… -a tapeline-web`
# does NOT work: Fly secrets are runtime env, and by runtime the value is already
# baked into the client bundle. You get a green deploy, a passing smoke check and
# zero effect — which is exactly how Turnstile sat inert in production and how the
# NEXT_PUBLIC_VERCEL analytics sink went unnoticed for months.
# GA/Ads IDs survive without args only because layout.tsx hardcodes them as `??`
# defaults; the founder vars are cosmetic. Guarded by the "build-arg hole" suite
# in frontend/__tests__/FunnelInstrumentation.test.tsx — add an ARG below when you
# add a feature-gating NEXT_PUBLIC_* var, or that test will fail.

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
# Feature-gating keys. Both are PUBLIC by design (a Turnstile site key and a
# PostHog project key are served to every browser), so committing the real values
# in fly.toml [build.args] is fine — the secrets are the paired *server* keys.
# Empty default = feature stays off, which is the correct dev/PR-preview state.
ARG NEXT_PUBLIC_TURNSTILE_SITE_KEY=""
ARG NEXT_PUBLIC_POSTHOG_KEY=""
ARG NEXT_PUBLIC_POSTHOG_HOST=""
ARG NEXT_PUBLIC_CLARITY_PROJECT_ID=""
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL \
    NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_PUBLIC_TURNSTILE_SITE_KEY=$NEXT_PUBLIC_TURNSTILE_SITE_KEY \
    NEXT_PUBLIC_POSTHOG_KEY=$NEXT_PUBLIC_POSTHOG_KEY \
    NEXT_PUBLIC_POSTHOG_HOST=$NEXT_PUBLIC_POSTHOG_HOST \
    NEXT_PUBLIC_CLARITY_PROJECT_ID=$NEXT_PUBLIC_CLARITY_PROJECT_ID \
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
