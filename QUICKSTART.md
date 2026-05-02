# Tapeline — Quickstart

## Prerequisites (install once)
- **Docker Desktop** — https://www.docker.com/products/docker-desktop/
- **Python 3.12+** — https://www.python.org/downloads/
- **Node.js 20+** — https://nodejs.org/
- PowerShell (included with Windows)

## Run it

From `C:\Project 1\` in PowerShell:

```powershell
.\scripts\run_local.ps1
```

This one command:
1. Starts Postgres + Redis in Docker
2. Creates a Python venv and installs backend deps
3. Copies `.env.example` → `.env` with dev defaults
4. Runs DB migrations
5. Launches the FastAPI server on port 8000
6. Launches the scoring worker (writes mock data every 60s)
7. Installs frontend deps (first run only, ~2 min)
8. Launches Next.js on port 3000
9. Opens `http://localhost:3000` in your browser

## What you'll see

- **http://localhost:3000** — public landing page with pricing
- **http://localhost:3000/app/scanner** — live ticker scanner, updates every 60s
- **http://localhost:3000/app/squeeze** — squeeze setups
- **http://localhost:3000/app/regime** — market regime dashboard
- **http://localhost:3000/app/congress** — congressional trades feed
- **http://localhost:8000/docs** — FastAPI interactive API docs

Watch the live badge in the top-right of any dashboard page — it pulses green when the SSE stream is connected and each new update comes through.

## It's using mock data right now

The scoring worker writes plausible fake data every 60 seconds so you can see the whole pipeline work before you have a market-data API key. When you subscribe to Massive (Stocks Starter $29/mo at https://massive.com/pricing):

1. Put your API key in `.env`: `MASSIVE_API_KEY=your_key_here` (`POLYGON_API_KEY` also works — Massive accepts legacy Polygon keys)
2. Swap the import in `backend/app/workers/signal_publisher.py`:
   ```python
   # from app.services.mock_feed import fetch_snapshots, fetch_squeezes, fetch_regime, fetch_congress_trades, universe
   from app.services.polygon_feed import fetch_snapshots  # adapter calls api.massive.com
   ```
3. Restart the worker. Real scores.

(Polygon.io rebranded to Massive on 2025-10-30. The adapter file is still named `polygon_feed.py` but `BASE_URL` points at `api.massive.com`. The legacy `api.polygon.io` host still works for an extended grace period.)

## Troubleshooting

**Docker errors:** make sure Docker Desktop is running.

**`docker compose` not found:** use `docker-compose` (with hyphen) instead, or update Docker Desktop.

**Port 3000 / 5432 / 6379 / 8000 already in use:** something else is using the port. Either stop the other process or edit `infra/docker-compose.yml` and `frontend/next.config.js` to use different ports.

**Python 3.12 missing:** `python --version` should print 3.12 or higher. Install from python.org if not.

**`npm install` fails:** delete `frontend/node_modules` and `frontend/package-lock.json`, try again.

**Frontend shows "Connecting…" forever:** the API isn't reachable. Check the FastAPI window for errors and that `http://localhost:8000/api/health` returns OK.

## Stop everything

Close the three service windows (uvicorn, worker, next) and:

```powershell
docker compose -f infra\docker-compose.yml down
```

Data in Postgres persists between restarts (it's in a Docker volume). To wipe:

```powershell
docker compose -f infra\docker-compose.yml down -v
```
