# LiveKit Local Setup — Day 2

Self-hosted LiveKit server for local dev, plus room creation and scoped
short-lived token generation, tested with the `lk` CLI as a stand-in client.

## Prerequisites
- Docker Desktop running
- `lk` CLI on PATH (https://github.com/livekit/livekit-cli/releases)
- `.env` copied from `.env.example` (dev keys already match `docker/livekit.yaml`)

## 1. Start the server
```
cd docker
docker compose up livekit -d
```
Confirm it's up: `docker compose logs livekit` should show `starting LiveKit server`.

## 2. Install agent deps
```
cd agent
pip install -r ../requirements.txt
```

## 3. Generate a scoped token
```
python generate_token.py demo-room test-client
```
Copy the printed JWT.

## 4. Join as a test client
```
lk room join --url ws://localhost:7880 --token <paste-jwt> --identity test-client demo-room
```
If the CLI reports it joined without error, the acceptance criteria for
Day 2 is met: a test client can join a room using a generated token.

## Review checklist (Day 2)
- [ ] Token has a short TTL (default 10 min) — confirm an expired token is rejected
- [ ] Token is scoped to the one room passed in (`VideoGrants(room=...)`) — a
      token for `demo-room` must fail to join a differently-named room
- [ ] No room is joinable without a valid token (server rejects anonymous/invalid JWTs)

## Notes
- The `devkey` / `devsecretkey...` pair in `.env.example` and
  `docker/livekit.yaml` is for **local dev only**. Generate a real random
  secret before staging/production and never commit that one.
