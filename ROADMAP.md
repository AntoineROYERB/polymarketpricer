# Polymarket Smart Money Tracker

## Vision

Build a platform that identifies the most skilled Polymarket traders, measures their performance by niche, detects when they open new positions, and generates actionable alerts.

The goal is **not** to blindly copy whales.

The goal is to identify traders with a demonstrable edge and surface their activity in real time.

---

# Phase 0 — Feasibility Study (Mandatory)

## Objective

Before writing any production code, validate that the required data can be reliably collected.

### Deliverables

Produce a technical report answering:

- Can historical wallet PnL be reconstructed accurately?
- Can open positions be reconstructed from available data?
- Can trader performance be tracked over time?
- Can new positions be detected in near real-time?
- What are the API rate limits?
- Which source should be considered the source of truth?
  - Polymarket API
  - Polygon blockchain
  - Third-party indexers
- Is a custom blockchain indexer required?

### Success Criteria

The report must contain:

- Architecture recommendation
- Risks
- Limitations
- Estimated implementation complexity

No implementation should begin until this report is completed.

---

# Phase 1 — MVP Leaderboard

## Objective

Build a leaderboard of Polymarket traders ranked by skill.

---

## Data Collection

Collect and store:

- Markets
- Events
- Outcomes
- Wallet addresses
- Trades
- Position sizes
- Prices
- Timestamps
- Resolution outcomes

---

## Database Schema

### markets

| Column | Type |
|----------|----------|
| id | string |
| question | text |
| category | string |
| created_at | datetime |
| resolved_at | datetime |
| outcome | string |

### trades

| Column | Type |
|----------|----------|
| id | string |
| wallet | string |
| market_id | string |
| side | string |
| price | float |
| shares | float |
| amount_usd | float |
| timestamp | datetime |

### wallets

| Column | Type |
|----------|----------|
| wallet | string |
| first_seen | datetime |
| last_seen | datetime |

### positions

| Column | Type |
|----------|----------|
| wallet | string |
| market_id | string |
| avg_entry_price | float |
| shares | float |
| realized_pnl | float |
| unrealized_pnl | float |

---

## Wallet Analytics

For every wallet calculate:

- Total PnL
- ROI
- Win Rate
- Number of Trades
- Average Position Size
- Risk Adjusted Return
- Average Holding Duration

Store metrics daily.

---

## Wallet Filtering

Ignore wallets with:

- Less than 50 resolved trades
- Less than $1,000 volume
- Less than 3 months of history

---

## Ranking Engine

```python
wallet_score = (
    0.35 * normalized_roi +
    0.25 * normalized_winrate +
    0.15 * consistency_score +
    0.15 * experience_score +
    0.10 * risk_adjusted_return
)
```

### Outputs

- Top 100 Traders
- Top 10 Emerging Traders
- Top 10 Most Consistent Traders

---

# Phase 2 — Niche Expertise Detection

## Objective

Determine what each trader is actually good at.

---

## Categories

- Politics
- Crypto
- Sports
- Economics
- Technology
- AI
- Geopolitics
- Entertainment

---

## Metrics Per Category

For every wallet calculate:

- ROI by category
- Win Rate by category
- Volume by category
- Trade Count by category

Example:

```json
{
  "wallet": "0x123",
  "politics_roi": 42,
  "crypto_roi": -12,
  "sports_roi": 4
}
```

---

## Expertise Criteria

A trader becomes a specialist if:

- Trade count > 30
- ROI > category median
- Volume > threshold

---

## Outputs

- Top Politics Traders
- Top Crypto Traders
- Top Sports Traders
- Top AI Traders

---

# Phase 3 — Smart Money Detection

## Objective

Detect high-signal trades in real time.

---

## Events To Detect

- New market entry
- Position increase
- Position decrease
- Full exit

---

## Alert Payload

```json
{
  "wallet": "0x123",
  "score": 89,
  "category": "Politics",
  "market": "Will candidate X win?",
  "action": "BUY YES",
  "price": 0.42,
  "position_size": 12000
}
```

---

## Alert Rules

Send alerts when:

- Trader score > 80
- Position size > $500
- Market liquidity above threshold

---

## Delivery Channels

- Telegram
- Discord
- Email (optional)

---

# Phase 4 — Edge Scoring

## Objective

Measure predictive skill rather than raw profitability.

This phase is the core competitive advantage.

---

## Market Timing Analysis

For every trade calculate:

- Entry price
- Exit price
- Resolution price
- Market consensus evolution
- Expected value

---

## Edge Example

```text
Trader buys YES at 0.35

Market later converges to 0.75

Edge = +40%
```

---

## Edge Metrics

Calculate:

- Average Edge
- Median Edge
- Edge Consistency
- Edge Volatility

---

## Updated Ranking Formula

```python
wallet_score = (
    0.40 * edge_score +
    0.20 * consistency +
    0.20 * roi +
    0.10 * experience +
    0.10 * risk_adjusted_return
)
```

---

# Phase 5 — Follow Recommendation Engine

## Objective

Recommend which traders are worth following.

---

## Recommendation Output

```json
{
  "wallet": "0x123",
  "recommendation": "FOLLOW",
  "confidence": 92,
  "reason": [
    "Top 1% Politics ROI",
    "Positive edge for 8 months",
    "512 resolved markets"
  ]
}
```

---

## Confidence Inputs

- Edge Score
- ROI
- Consistency
- Specialization
- Trade Volume
- Historical Decay

---

## Confidence Output

```text
0-100
```

---

# Phase 6 — Dashboard

## Frontend

- Next.js
- TypeScript
- Tailwind
- shadcn/ui

---

## Backend

- Python
- FastAPI
- PostgreSQL
- Redis

---

## Data Pipelines

Choose one:

- Mage AI
- Airflow

---

## Infrastructure

- Docker
- GitHub Actions
- Railway / Fly.io / AWS

---

## Dashboard Pages

### Leaderboard

Display:

- Rank
- Wallet
- Score
- ROI
- Win Rate
- PnL

---

### Wallet Profile

Display:

- Performance
- Trade History
- Category Expertise
- Current Positions

---

### Smart Money Feed

Display:

- Recent high-signal trades
- New positions
- Market activity

---

### Market View

Display:

- Active top traders
- Bullish/Bearish sentiment
- Concentration of positions

---

# Phase 7 — Advanced Features

## Trader Clustering

Identify groups of traders with similar behavior.

Potential algorithms:

- DBSCAN
- HDBSCAN
- UMAP

---

## Copy Portfolio Simulation

Backtest strategies:

- Copy Trader X
- Copy Top 10 Politics Traders
- Copy Top 20 Edge Traders

Metrics:

- ROI
- Max Drawdown
- Sharpe Ratio

---

## ML Prediction Layer

Objective:

Predict whether a trader will outperform during the next 30 days.

Models:

- LightGBM
- XGBoost

Inputs:

- Historical ROI
- Edge Score
- Consistency
- Category Expertise
- Trade Frequency

Output:

```text
Probability of Outperformance
```

---

# Technical Requirements

## Code Quality

Mandatory:

- Python 3.12+
- Full Type Hints
- Ruff
- MyPy
- Pytest
- Pre-commit Hooks

---

## Architecture

```text
app/
├── api/
├── analytics/
├── alerts/
├── db/
├── pipelines/
├── ranking/
├── services/
├── models/
├── utils/
└── tests/
```

---

## Deliverables Per Phase

For each phase:

1. Implement functionality
2. Add tests
3. Add documentation
4. Add Docker support
5. Add database migrations
6. Produce demo screenshots
7. Update architecture diagrams
8. Ensure CI passes

Do not start the next phase until all deliverables are complete.

---

# Future Monetization Ideas

- Premium trader alerts
- API access
- Portfolio tracking
- Smart money newsletters
- Real-time whale monitoring
- Copy-trading integrations
- Advanced analytics subscriptions
- Institutional dashboards
```
:::

Tu peux donner ce document tel quel à Claude Code comme "master specification", puis lui demander d'exécuter les phases une par une avec une PR et une revue d'architecture à chaque étape. Cela évite qu'il parte directement dans une implémentation trop complexe sans valider les hypothèses de données.