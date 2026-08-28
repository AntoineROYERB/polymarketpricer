# Security

This is a portfolio project, not a hosted service. There is no production deployment and
no user data: the committed snapshot in `docker/initdb/seed.sql.gz` contains only public
on-chain Polymarket activity — wallet addresses, trades and market metadata that anyone
can read from the chain. It holds no personal data and no credentials.

## Reporting

Open a GitHub issue. Since nothing is deployed, there is no embargo to respect.

## What the threat model assumes

The stack is designed to run on a laptop, bound to `127.0.0.1` by every port mapping in
`docker-compose.yml`. It is *not* hardened for exposure to the public internet. If you
intend to expose it, at minimum:

- Terminate TLS in front of it. The API key is sent as a bearer token, and — for the
  alert WebSocket, where browsers cannot set headers — as a query parameter, which
  proxies and access logs routinely record.
- Replace the single shared API key with real per-user authentication. `require_api_key`
  deliberately returns one constant identity: the app is single-tenant by design, and
  every follow and paper-trading row is scoped to that identity.
- Set `CORS_ORIGINS` to the exact origins you serve, never `*`. The value is also what
  the WebSocket handshake checks the `Origin` header against.
- Put a real rate limiter in front of the app. The built-in one is in-memory and
  per-process, keyed on the client address — behind a reverse proxy, that address is the
  proxy unless you configure it to forward the original.

## Controls that are in place

| Control | Where |
|---|---|
| Bearer-token auth on every write endpoint | `app/api/dependencies/auth.py` |
| Constant-time key comparison (`secrets.compare_digest`) | `app/api/dependencies/auth.py` |
| WebSocket auth — missing, empty and wrong keys all rejected with `4001` | `app/api/v1/alerts.py` |
| WebSocket origin check against `CORS_ORIGINS` | `app/api/v1/alerts.py` |
| Default rate limit on every API route | `app/api/rate_limit.py` |
| Parameterised queries everywhere; LIKE metacharacters escaped in search filters | `app/utils/sql.py` |
| Allowlist validation on category, sort key and list type; bounded `limit`/`offset` | `app/api/v1/`, `app/services/leaderboard_service.py` |
| Container runs as a non-root user | `Dockerfile` |
| All published ports bound to `127.0.0.1` | `docker-compose.yml` |
| `API_KEY` required at startup — the app refuses to boot without one | `app/config.py`, `docker-compose.yml` |
| `bandit`, `pip-audit` and `npm audit` fail the build | `.github/workflows/ci.yml` |
| `detect-private-key` on every commit | `.pre-commit-config.yaml` |

## Secrets

No secret is committed. `.env` is git-ignored; `.env.sample` carries placeholders only.
`API_KEY` has no default — `docker compose up` fails fast if it is unset, rather than
starting with a guessable key.
