# Edge Terminal — frontend

Next.js 16 dashboard for the Polymarket smart money tracker. Consumes the FastAPI
backend's REST API and subscribes to its alert WebSocket.

Full project documentation is in the [repository root](../README.md).

## Pages

| Route | What |
|---|---|
| `/leaderboard` | Main, emerging, consistent, edge and per-category rankings |
| `/feed` | Live smart money alerts over WebSocket |
| `/markets`, `/markets/[id]` | Market view with smart money activity |
| `/wallets/[address]` | Wallet profile: metrics, sentiment, edge, category breakdown |
| `/follow` | Follow list and follow-score recommendations |
| `/portfolio` | Paper-trading portfolio, positions and trades |

## Running

The dashboard needs the API. From the repository root:

```bash
docker compose up -d
```

Then http://localhost:3000.

To run the frontend alone against an API already listening on `:8000`:

```bash
npm install
npm run dev
```

Requests to `/api/v1/*` are proxied by `next.config.ts` to `API_PROXY_URL`
(default `http://localhost:8000`), so the browser never needs a CORS exemption.
Endpoints under `/follow` and `/portfolio` require the backend's `API_KEY`, entered
once on `/login` and kept in `localStorage`.

## Stack

React 19 · TypeScript · Tailwind 4 · shadcn/ui (Base UI) · TanStack Query · Recharts ·
Vitest + Testing Library.

```bash
npm run lint
npm test
npm run build
```
