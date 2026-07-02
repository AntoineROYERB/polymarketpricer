# Phase 6 — Dashboard — Wallet Profile Page

> **Goal**: Implement a detailed wallet profile page showing performance metrics, category expertise, trade history, and positions.
> **AI Agent Instructions**: Create `src/app/wallets/[address]/page.tsx` with metrics cards, charts, and tabbed data tables.

---

## Route: `/wallets/[address]`

## API Endpoints Used

| Data | Endpoint |
|------|----------|
| Wallet profile | `GET /api/v1/wallets/{address}` |
| Edge metrics | `GET /api/v1/wallets/{address}/edge` |
| Category breakdown | `GET /api/v1/wallets/{address}/categories` |
| Per-category detail | `GET /api/v1/wallets/{address}/categories/{category}` |
| Category follow scores (Phase 5) | `GET /api/v1/follow/recommendations/{address}/by-category` |

---

## Layout

### Header Section
- Wallet address (full, copyable) with identicon/gradient avatar
- Global wallet score (large number)
- Follow/Unfollow button (if authenticated)
- Last active badge

### Performance Metrics Row
4 metric cards in a row:
| Metric | Source | Format |
|--------|--------|--------|
| Total ROI | wallet profile | `+X.X%` |
| Total PnL | wallet profile | `$X,XXX.XX` |
| Win Rate | wallet profile | `XX.X%` |
| Edge Score | wallet profile | `0.XX` |
| Sharpe Ratio | wallet profile | `X.XX` |
| Total Trades | wallet profile | count |

### Category Expertise Section
- Bar chart showing ROI per category
- Specialist badges per category
- Each bar clickable → expand per-category detail
- Below chart: category follow scores (Phase 5) — small badges showing FOLLOW/WATCH/IGNORE per category

### Tabbed Data Section
| Tab | Content | API |
|-----|---------|-----|
| Trades | Trade history table (paginated) | `GET /api/v1/trades?wallet=` (via wallet service) |
| Positions | Current open positions | `GET /api/v1/wallets/{address}` (positions field) |
| Positions (closed) | Historical resolved positions | Same, filtered |
| Edge History | Edge score over time | `GET /api/v1/wallets/{address}/edge` |

---

## Follow Button

```tsx
// Check if wallet is already followed:
// GET /api/v1/follow → find matching wallet in list
// If followed: show "Unfollow" button
// If not followed: show "+ Follow" button → POST /api/v1/follow/{wallet}
// Follow modal: label, auto_copy toggle, copy_mode, copy_value, category_filter
```

---

## States

| State | Behaviour |
|-------|-----------|
| Invalid address | Redirect to 404 page |
| Loading | Skeleton layout with placeholder cards |
| Wallet not found | "Wallet not found" message |
| No trades | "No trade history" in trades tab |
| No positions | "No current positions" in positions tab |

---

## Files to Create

| Action | Path |
|--------|------|
| CREATE | `src/app/wallets/[address]/page.tsx` |

---

## Verification

```bash
# Navigate to a known wallet
curl http://localhost:3000/wallets/0x...

# Test:
# - All metric cards populated
# - Category bar chart renders
# - Trades tab shows paginated table
# - Follow button works (requires auth)
# - Follow modal opens with config fields
```
