# Phase 2 — Category Mapping Strategy

> **Goal**: Assign every tradeable market to one of 8 target categories for per-category wallet analytics.
> **Problem**: 95.2% of markets have `category IS NULL` in the raw Gamma API data.
> **Status**: Planning — ready for spec.

---

## 1. Target Categories

From `MarketCategory` enum (already defined):

| Category | Examples |
|---|---|
| Politics | Elections, policy, candidates |
| Crypto | Bitcoin, Ethereum, DeFi, NFTs |
| Sports | NFL, NBA, soccer, tennis |
| Economics | Inflation, GDP, Fed rates |
| Technology | Tech companies, startups, hardware |
| AI | LLMs, AI regulation, AGI |
| Geopolitics | Wars, sanctions, international relations |
| Entertainment | Movies, music, pop culture, awards |

---

## 2. Category Inference Pipeline

Since 95%+ of markets lack a category from the API, we need a **3-tier fallback strategy**:

### Tier 1 — Direct API Match (est. ~5% of markets)

The Gamma API provides raw categories on some markets. Map them to our 8 standardized categories:

| Raw API Category | Maps To |
|---|---|
| `Sports` | Sports |
| `NBA Playoffs` | Sports |
| `Olympics` | Sports |
| `Chess` | Sports |
| `Poker` | Sports |
| `Crypto` | Crypto |
| `NFTs` | Crypto |
| `Politics` | Politics |
| `US-current-affairs` | Politics |
| `Global Politics` | Geopolitics |
| `Ukraine & Russia` | Geopolitics |
| `Business` | Economics |
| `Coronavirus` | Economics |
| `Pop-Culture` | Entertainment |
| `Art` | Entertainment |
| `Science` | Technology |
| `Tech` | Technology |
| `Space` | Technology |

### Tier 2 — Event Category (est. <1% of markets)

Markets linked to events inherit the event's category if `markets.category` is NULL but `events.category` is not NULL. Apply the same mapping table as Tier 1.

### Tier 3 — Keyword Classifier (est. ~90% of markets)

For markets where both `markets.category` and `events.category` are NULL, classify based on `market.question` text using keyword rules.

**Implementation**: A Python function `infer_category(question: str, raw_category: str | None, event_category: str | None) -> str | None`

Rules (ordered, first match wins):

```python
def infer_category(question: str) -> str | None:
    q = question.lower()
    
    # Politics
    if any(kw in q for kw in [
        "president", "election", "vote", "democrat", "republican", 
        "senate", "congress", "governor", "candidate", "primary",
        "trump", "biden", "harris", "newsom", "european union",
        "parliament", "prime minister", "chancellor",
    ]):
        return "Politics"
    
    # Geopolitics
    if any(kw in q for kw in [
        "war", "sanction", "military", "nato", "invasion",
        "nuclear", "treaty", "ceasefire", "refugee",
    ]):
        return "Geopolitics"
    
    # Crypto
    if any(kw in q for kw in [
        "bitcoin", "ethereum", "crypto", "solana", "defi",
        "nft", "blockchain", "polygon", "token", "web3",
    ]):
        return "Crypto"
    
    # Sports
    if any(kw in q for kw in [
        "nfl", "nba", "mlb", "nhl", "soccer", "tennis",
        "champion", "playoff", "super bowl", "world cup",
        " vs ", "fight", "match", "race", "grand slam",
        "goal", "touchdown", "homerun",
    ]):
        return "Sports"
    
    # AI
    if any(kw in q for kw in [
        "artificial intelligence", "ai ", "gpt", "llm", "chatgpt",
        "agi", "deep learning", "neural",
    ]):
        return "AI"
    
    # Technology
    if any(kw in q for kw in [
        "iphone", "apple", "google", "microsoft", "tesla",
        "rocket", "launch", "space", "satellite",
        "ipo", "startup", "acquisition",
    ]):
        return "Technology"
    
    # Economics
    if any(kw in q for kw in [
        "inflation", "gdp", "interest rate", "fed", "recession",
        "stock market", "s&p", "nasdaq", "unemployment",
        "trade deficit", "tariff",
    ]):
        return "Economics"
    
    # Entertainment
    if any(kw in q for kw in [
        "movie", "oscar", "grammy", "album", "concert",
        "actor", "actress", "celebrity", "netflix", "disney",
    ]):
        return "Entertainment"
    
    return None  # unclassified
```

### Unclassifiable Markets

Markets that don't match any rule remain unclassified. They are excluded from category analytics but remain in global analytics. Target: < 5% unclassified.

---

## 3. Category Assignment in ETL

There are two strategies:

### Option A: Classify at Load Time (Recommended)

Add the classification step to `market_discovery` pipeline's `merge_markets` transformer. Every market gets a `mapped_category` column after the keyword classifier runs.

**Pros**: Category available immediately for all consumers; single source of truth.

**Cons**: Requires re-running `market_discovery` to backfill categories.

### Option B: Classify at Analytics Time

Classify during the `category_analytics` pipeline's transformer, on-the-fly when joining trades → markets.

**Pros**: No schema changes to `markets` table; no pipeline rerun needed.

**Cons**: Same logic runs every analytics cycle; harder to audit.

**Recommendation**: **Option A** — add a `mapped_category` column to `markets` table, populated by the `market_discovery` pipeline. This is cleaner and follows the existing pattern of storing derived data.

---

## 4. Proposed Schema Change to `markets`

Add column:

```python
mapped_category = Column(Text, nullable=True)  # Inferred category from classifier
```

This stores the best-effort category separately from the raw API `category` field. The `category` column retains the raw API value; `mapped_category` contains the classified value using all 3 tiers.

```sql
ALTER TABLE markets ADD COLUMN mapped_category TEXT;
CREATE INDEX idx_markets_mapped_category ON markets (mapped_category);
```

---

## 5. Acceptance Criteria

- [ ] All raw API categories correctly mapped to 8 target categories (0 loss)
- [ ] Keyword classifier covers ≥ 95% of previously NULL markets
- [ ] Tier 1 → Tier 2 → Tier 3 fallback works as expected
- [ ] `mapped_category` populated for ≥ 95% of markets
- [ ] No regression in existing market_discovery pipeline
- [ ] Classifier is testable with known input/output examples
