# Phase 6 — Dashboard — Market View Page

> **Goal**: Implement a market detail page showing active traders, sentiment, and alert activity for a specific market.
> **AI Agent Instructions**: Create `src/app/markets/[id]/page.tsx` with trader list, sentiment bar, and alert feed for the market.

---

## Route: `/markets/[id]`

## API Endpoints Used

| Data | Endpoint |
|------|----------|
| Market details | `GET /api/v1/markets` (filter by id or query) |
| Alerts for market | `GET /api/v1/alerts?market_id=` (via filter on alerts endpoint) |

**Note**: There is no dedicated market-detail endpoint. We may need to add a `GET /api/v1/markets/{id}` endpoint to the backend, or infer data from the existing `markets` table and `alerts` endpoint.

### Optional: New Backend Endpoint
```python
@router.get("/markets/{market_id}")
async def get_market_detail(market_id: str, db: AsyncSession = Depends(get_db)):
    """Return market details + active trader count + sentiment."""
    # Query: market + outcome prices + distinct wallets in alerts for this market
    # Return: market info, outcomes, active_trader_count, bullish_pct, bearish_pct
```

---

## Layout

### Market Header
- Market title (large, bold)
- Category badge
- Status (active/resolved)
- Condition ID (copyable)
- Question/description text

### Outcomes Row
- Each outcome as a card: label, current price (large), volume
- YES/NO with green/red coloring

### Active Traders Section
| Column | Description |
|--------|-------------|
| Wallet | Truncated address → profile link |
| Side | BUY/SELL badge |
| Position Size | $X,XXX.XX |
| Entry Price | $X.XX |
| Current PnL | $X,XXX.XX (green/red) |
| Alert Score | 0.XX (if available) |

**Source**: Derived from alerts WHERE market_id = X, grouped by wallet + action type.

### Sentiment Bar
- Horizontal bar chart: % BUY vs % SELL by volume
- Green (BUY) fills from left, Red (SELL) from right
- Center neutral line
- Labels: "XX% Bullish" / "XX% Bearish"

### Recent Alerts for This Market
- Compact alert list (same cards as Feed page, but filtered to this market)
- Paginated (limit 10, load more)

### Concentration Bar
- Optional: bar showing top-5 wallets as % of total volume
- "Top 5 wallets hold XX% of positions"

---

## States

| State | Behaviour |
|-------|-----------|
| Loading | Skeleton layout |
| Market not found | "Market not found" with wallet search link |
| No traders | "No active traders for this market" |
| Resolved market | Show resolution badge, no trading data |

---

## Files to Create

| Action | Path |
|--------|------|
| CREATE | `src/app/markets/[id]/page.tsx` |
| (optional) | backend: `GET /api/v1/markets/{id}` endpoint |

---

## Verification

```bash
curl http://localhost:3000/markets/0x...
# Expected: market title, outcomes, sentiment bar, trader list

# Test:
# - Outcomes display with correct prices
# - Sentiment bar shows BUY/SELL ratio
# - Active trader list populated
# - Alert list paginated
# - Resolved market shows different view
```
