# Phase 6 — Dashboard — Leaderboard Page

> **Goal**: Implement the Leaderboard page showing top-performing Polymarket wallets across multiple ranking dimensions.
> **AI Agent Instructions**: Create `src/app/leaderboard/page.tsx` with tabbed navigation, server-side paginated data table, top-3 highlight cards.

---

## Route: `/leaderboard`

## Features

### Tabbed Navigation
5 tabs switching between leaderboard types:
| Tab | API Endpoint | Description |
|-----|-------------|-------------|
| Main | `GET /api/v1/leaderboard` | Wallet score ranking |
| Emerging | `GET /api/v1/leaderboard/emerging` | New high-potential wallets |
| Consistent | `GET /api/v1/leaderboard/consistent` | Consistent performers |
| Edge | `GET /api/v1/leaderboard/edge` | Predictive accuracy ranking |
| By Category | `GET /api/v1/leaderboard/{category}` | Per-category ranking |

### Top-3 Highlight Cards
- Displayed above the table
- Large format: Rank badge, wallet address, score, ROI, PnL
- Click navigates to `/wallets/{address}`

### Data Table
| Column | Sortable | Format |
|--------|----------|--------|
| Rank | No | `#1`, `#2`, ... |
| Wallet | No | Truncated address + copy button |
| Score | Yes | `0.00–1.00` |
| ROI | Yes | `+12.5%` (green/red) |
| Win Rate | Yes | `65.2%` |
| PnL | Yes | `$1,234.56` (green/red) |
| Edge | Yes | `0.00–1.00` |
| Trades | Yes | Count |

### Pagination
- Previous / Next buttons
- Offset-based (API supports `offset` and `limit` params)
- Default limit: 20
- Shows `Showing 1–20 of X`

### Category Selector (for "By Category" tab)
- Dropdown/select with all categories
- Default: first category
- On change: re-fetches leaderboard for selected category

---

## States

| State | Behaviour |
|-------|-----------|
| Loading | Skeleton rows (8 placeholder rows) |
| Empty | "No wallets found" with illustration |
| Error | Error banner with retry button |
| Tab switch | Show loading state, fetch new data |

---

## Data Flow

```
Page load → fetchActiveTab() → GET /api/v1/leaderboard[?tab_params]
                                        ↓
                              LeaderboardResponse { data[], total }
                                        ↓
                              Render: TopCards + DataTable + Pagination
```

---

## Files to Create

| Action | Path |
|--------|------|
| CREATE | `src/app/leaderboard/page.tsx` |

---

## Verification

```bash
curl http://localhost:3000/leaderboard
# Expected: renders table with top wallets, tabs functional

# Test:
# - Tab switch → URL updates → new data loads
# - Pagination → offset changes → more data
# - Click wallet row → navigates to /wallets/{address}
```
