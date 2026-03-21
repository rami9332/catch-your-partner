# Catch Your Partner

Core is now the only production-ready module target. Identity, Companion, Mind and Astro remain capability-driven stubs until later releases.

## One-command local run

1. Create env:
```bash
cp .env.example .env
```
2. Start everything:
```bash
docker compose up --build
```
3. Open:
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## Commands

Run:
```bash
make run
```

Migrate:
```bash
make migrate
```

Test:
```bash
make test
```

Smoke test against a running stack:
```bash
make smoke
```

## Local verification on a new machine

Prerequisites:
- Docker Desktop or another Docker runtime
- Docker Compose support via `docker compose`

Run:
```bash
./compose-smoke.sh
```

Expected output:
- stack builds and starts
- Postgres becomes healthy
- migrations apply
- smoke flow completes
- final line shows `PASS`

Reset everything:
```bash
docker compose down -v
```

## Stack

- FastAPI
- Postgres
- SQLAlchemy
- Alembic
- JWT auth
- Pytest E2E
- Docker Compose

## Core endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness + DB check |
| `POST` | `/auth/register` | Create user + JWT |
| `POST` | `/auth/login` | Login + JWT |
| `GET` | `/auth/me` | Current user |
| `GET` | `/capabilities` | Active modules + flags |
| `POST` | `/core/radar/start` | Start radar session |
| `POST` | `/core/radar/stop` | Stop radar session |
| `GET` | `/core/radar` | Nearby active radar users |
| `POST` | `/core/meeting/start` | Create meeting |
| `POST` | `/core/navigation/start` | Mark navigation started |
| `POST` | `/core/check-in` | Check in at meeting spot |
| `POST` | `/core/ok` | Confirm safety/comfort |
| `POST` | `/core/chat/unlock` | Open chat after both OK |
| `POST` | `/core/chat/send` | Send message |
| `GET` | `/core/chat/history/{meeting_id}` | Read chat |
| `POST` | `/core/safety/panic` | Trigger panic flow |
| `POST` | `/core/safety/abort` | Abort meeting and lock chat |

## Notes

- Production DB choice is now Postgres.
- Module stubs stay stubs in phase 2.
- `docker compose up` runs migrations before the API starts via `beta_backend/entrypoint.sh`.
- OpenAPI remains the main live contract at `/docs`.
- One-minute smoke path:
  `GET /health` -> `GET /capabilities` -> register 2 users -> radar start -> meeting start -> navigation -> both check-in -> both OK -> chat unlock -> chat send -> panic.

## 2-Min Demo Flow

- Open `http://127.0.0.1:3000/index.html` for APP mode
- Open `http://127.0.0.1:3000/index.html?debug=1` or `http://127.0.0.1:3000/admin/` for DEMO mode
- Register or login on the Identity screen
- Enroll one selfie, then verify with a second selfie
- Enable Premium, then run `Find Doppelgänger`
- Switch to `Core` and click:
  `Start Radar` -> `Create Meeting` -> `Start Navigation` -> `Check-in A/B` -> `OK A/B` -> `Chat Unlock`
- Watch the Companion card react with XP, mood, streak and level-up
- Type one short message into the Companion input and send it
- If needed, use `Reset Demo` to bring the flow back to a clean state

## iPhone Demo App

- Start the backend on your Mac: `docker compose up -d`
- Serve the frontend from the repo root: `python3 -m http.server 3000`
- Open [CatchYourPartnerMobile.xcodeproj](/Volumes/T7/catch_your_partner%202/ios/CatchYourPartnerMobile.xcodeproj) in Xcode
- Choose your iPhone as the run target and press Run
- On first launch, enter your Mac's local IP, for example `192.168.1.24`
- The wrapper opens `http://YOUR-MAC-IP:3000/index.html` in APP mode by default
- Use `?debug=1` or `/admin/` only when you want DEMO mode with backend and module diagnostics
