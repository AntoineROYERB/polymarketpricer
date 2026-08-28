# Phase 6 — Dashboard — Portfolio Page

> **Goal**: Display the paper trading portfolio — balance, positions, trade history, PnL tracking.
> **AI Agent Instructions**: Create `src/app/portfolio/page.tsx` with summary cards, positions table, and trade history.

---

## Route: `/portfolio`

## API Endpoints Used

| Action | Endpoint |
|--------|----------|
| Portfolio overview | `GET /api/v1/portfolio` |
| Open positions | `GET /api/v1/portfolio/positions` |
| Trade history | `GET /api/v1/portfolio/trades` |
| Close position | `POST /api/v1/portfolio/positions/{id}/close` |
| Reset portfolio | `POST /api/v1/portfolio/reset` |

**All require auth (API key)** — without auth, show "Login to view portfolio" with CTA.

---

## Layout

### Portfolio Summary Row
4 metric cards showing key stats:
| Metric | Format | Source |
|--------|--------|--------|
| Balance | `$XX,XXX.XX` | `portfolio.current_balance` |
| Total PnL | `+$X,XXX.XX` (green/red) | `portfolio.total_pnl` |
| ROI | `+XX.X%` (green/red) | `portfolio.total_roi` |
| Open Positions | Count | `positions.length` |
| Total Trades | Count | `portfolio.total_trades` |
| Total Volume | `$XX,XXX.XX` | `portfolio.total_volume` |

### Open Positions Table
| Column | Format |
|--------|--------|
| Market | Title + link to `/markets/{id}` |
| Outcome | Yes/No badge |
| Side | BUY/SELL badge |
| Shares | `X.XXXX` |
| Avg Entry | `$X.XXXX` |
| Current Price | `$X.XXXX` |
| Cost Basis | `$X,XXX.XX` |
| Unrealized PnL | `+$X,XXX.XX` (green/red) |
| PnL % | `+XX.X%` |
| Action | "Close" button |

### Close Position Confirmation
```tsx
// Dialog: "Close position in [market title]?"
// Shows: Shares, avg entry, current price, estimated PnL
// [Cancel] [Close Position]
```

### Trade History Table
| Column | Format |
|--------|--------|
| Date | Relative + absolute |
| Market | Title + link |
| Side | BUY/SELL badge |
| Price | `$X.XXXX` |
| Shares | `X.XXXX` |
| Amount | `$X,XXX.XX` |
| Followed Wallet | Address → profile |
| Copy Mode | Badge |
| Source Alert | Link to alert |

### Reset Portfolio
- Button in settings area
- Confirmation dialog: "Reset portfolio to $10,000?"
- Warning: "This will close all open positions and clear trade history"
- Input field for new initial balance (default $10,000)

---

## States

| State | Behaviour |
|-------|-----------|
| Not authenticated | "Login to view portfolio" |
| Loading | Skeleton cards + table rows |
| No portfolio | "Start following wallets with auto-copy to build your portfolio" |
| No positions | "No open positions" |
| No trades | "No trade history yet" |
| Reset success | Toast + page refresh |

---

## Files to Create

| Action | Path |
|--------|------|
| CREATE | `src/app/portfolio/page.tsx` |

---

## Verification

```bash
curl http://localhost:3000/portfolio
# Expected: portfolio metrics + positions/trades (or empty states)

# Test:
# - Summary cards show correct metrics
# - Positions table with open positions
# - Close position → confirmation → POST → table updates
# - Trade history paginated
# - Reset portfolio → confirmation → POST → page resets
# - PnL values color-coded (green/red)
```
