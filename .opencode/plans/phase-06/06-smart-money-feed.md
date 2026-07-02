# Phase 6 — Dashboard — Smart Money Feed Page

> **Goal**: Real-time and historical display of smart money alerts — live WebSocket stream + paginated history.
> **AI Agent Instructions**: Create `src/app/feed/page.tsx` with live alert cards, filtering, and WebSocket integration.

---

## Route: `/feed`

## Features

### Alert Cards
Each alert displays as a card with:
| Field | Format |
|-------|--------|
| Wallet | Truncated address + link to profile |
| Action | Label with colour coding (NEW_POSITION=green, FULL_EXIT=red, etc.) |
| Market | Market title (clickable → `/markets/{id}`) |
| Outcome | "Yes" / "No" |
| Category | Badge |
| Score | `0.XX` with colour |
| Position size | `$X,XXX.XX` |
| Timestamp | Relative + absolute on hover |
| Confidence | If available |

### Live Feed
- WebSocket connection to `ws://localhost:8000/api/v1/alerts/ws?api_key=<key>`
- New alerts appear at the top with a slide-in animation
- "LIVE" badge in header when connected
- Connection status indicator (green dot = connected, red = disconnected)

### Filter Controls
| Filter | Type | API Param |
|--------|------|-----------|
| Category | Dropdown | `category` |
| Min Score | Slider/input | `min_score` |
| Wallet Search | Input | `wallet` (partial match) |
| Action Type | Multi-select | (client-side filter) |

### Pagination
- Server-side pagination with offset/limit
- "Load more" button at bottom (infinite scroll alternative)
- Default 50 alerts per page

---

## Layout

```
┌─────────────────────────────────────────────────┐
│  Smart Money Feed                    ● LIVE     │
│                                                   │
│  Filters: [Category ▼] [Score ≥] [Wallet...]     │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │ 🟢 NEW_POSITION  0x1234...abcd              │  │
│  │ Will Trump win?          Politics           │  │
│  │ Yes @ $0.74              Score: 0.82        │  │
│  │ Size: $12,340            2m ago             │  │
│  └─────────────────────────────────────────────┘  │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │ 🔴 FULL_EXIT     0x5678...ef01              │  │
│  │ BTC to $100K?        Crypto                 │  │
│  │ ...                                         │  │
│  └─────────────────────────────────────────────┘  │
│                                                   │
│  [Load More]                                      │
└─────────────────────────────────────────────────┘
```

---

## WebSocket Integration (`src/hooks/use-websocket.ts`)

```typescript
interface UseWebSocketResult {
  isConnected: boolean;
  lastAlert: AlertItem | null;
  recentAlerts: AlertItem[];     // Last 50 for live display
  connect: () => void;
  disconnect: () => void;
}
```

---

## States

| State | Behaviour |
|-------|-----------|
| Loading | Skeleton cards (5 placeholder) |
| Empty | "No alerts yet" with illustration |
| Live alert arrives | Slide-in animation at top, toast notification |
| Disconnected | Banner: "Reconnecting..." with retry |
| Filter applied | Refetch from API (WebSocket paused during filter mismatch) |

---

## Files to Create

| Action | Path |
|--------|------|
| CREATE | `src/app/feed/page.tsx` |
| EDIT | `src/hooks/use-websocket.ts` (ensure it supports auth query param) |

---

## Verification

```bash
curl http://localhost:3000/feed
# Expected: paginated alert cards

# Test:
# - WebSocket connects → live badge shows
# - New alert appears without page refresh
# - Filters work (category, score, wallet search)
# - Load more fetches next page
# - Disconnect/reconnect handling
```
