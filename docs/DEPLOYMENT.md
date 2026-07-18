# Production Deployment — Day 14

Target: a single cloud VM (DigitalOcean droplet / EC2 / Azure VM — any
Linux box with Docker). Owner: Person 4. Section 8 acceptance criteria:
"Full system reachable and functional on the target cloud instance."
Section 10 requires a joint P3/P4 go/no-go review against this doc before
calling it demo ready — don't skip that for a solo deploy.

## 1. Provision the VM

- Linux VM, Docker + Docker Compose v2 installed.
- Minimum: 4 vCPU / 8GB RAM (Chatterbox-Turbo voice cloning and vLLM/Qwen
  are the heavy pieces — see Section 11 of the backend doc: fall back to
  Qwen2.5-1.5B on CPU if GPU provisioning slips).
- Two DNS A records pointed at the VM's public IP before first deploy:
  - `api.yourdomain.com` → API_DOMAIN
  - `livekit.yourdomain.com` → LIVEKIT_DOMAIN

## 2. Firewall — open only what's needed

| Port | Protocol | Purpose |
|---|---|---|
| 22 | TCP | SSH |
| 80, 443 | TCP | Caddy (HTTP→HTTPS redirect + TLS) |
| 7881 | TCP | LiveKit TCP fallback (TURN/TLS) |
| 50100-51100 | UDP | LiveKit RTC media (WebRTC can't be reverse-proxied) |

Do **not** expose 5432 (Postgres) or 6379 (Redis) — `docker-compose.prod.yml`
already stops publishing them to the host; the firewall is defense in depth
on top of that, not a substitute for it.

## 3. Configure secrets on the VM

```bash
git clone <repo> && cd callforge-backend   # or: git checkout day13-dockerize
cp .env.production.example .env
cp docker/livekit.prod.yaml.example docker/livekit.prod.yaml
```

Edit both copies (never commit them — both are gitignored):
- `.env`: real `POSTGRES_PASSWORD`, `LIVEKIT_API_KEY`/`LIVEKIT_API_SECRET`
  (must match `livekit.prod.yaml`'s `keys:` section exactly), `API_DOMAIN`/
  `LIVEKIT_DOMAIN`, `LLM_BASE_URL`, and the Cal.com/SMTP/CRM values you
  actually have for the demo.
- `docker/livekit.prod.yaml`: generate a real key pair with
  `livekit-server generate-keys`, paste it into `keys:`, keep
  `use_external_ip: true`.

## 4. Bring up the stack

```bash
cd docker
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

`--env-file ../.env` is required, not optional — it's what makes the
`${POSTGRES_PASSWORD}` substitutions in `docker-compose.prod.yml` resolve
from the repo-root `.env` instead of silently failing to find it. Compose
will refuse to start (loudly, by design) if `POSTGRES_PASSWORD` is unset.

## 5. Run migrations

```bash
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.prod.yml \
  exec api alembic upgrade head
```

## 6. Verify health

```bash
curl -f https://api.yourdomain.com/health          # {"status": "ok"}
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.prod.yml ps
```

All services should show `healthy` (postgres, redis, api all have
healthchecks — see `docker-compose.prod.yml`). Then run an actual test
call end to end per Section 10's Friday checklist — a passing `/health`
is necessary, not sufficient.

## 7. Rollback plan

Docker images are tagged by git commit implicitly (rebuilt `--build` each
deploy). To roll back:

```bash
git checkout <last-known-good-commit-or-tag>
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Data isn't lost on rollback — Postgres/Redis are separate named volumes
(`pgdata`, untouched by rebuilding api/agent/caddy images). If a bad
migration is the problem, roll it back explicitly first:
`alembic downgrade -1`, then redeploy the previous commit — don't just
redeploy old code against a newer schema.

## What this deploy does **not** cover (flagged, not silently skipped)

- No authentication on any endpoint yet, including `GET /calls/{id}/recording`
  (real prospect audio/transcripts) — see `docs/API_CONTRACT.md`'s Auth
  section. Do not point this deploy at real prospect data until auth ships.
- No automated CI/CD deploy step — this is a manual runbook, matching the
  spec's Day 14 acceptance criteria ("reachable and functional"), not a
  pipeline.
- No GPU wired up — LLM/voice-clone run CPU fallback per Section 11 unless
  you provision a GPU instance and change `LLM_BASE_URL` accordingly.
