"""Category inference for Polymarket markets.

Three-tier fallback strategy:
  Tier 1 — Map raw Gamma API category to one of 8 target categories
  Tier 2 — Inherit category from the parent event
  Tier 3 — Keyword-based classification on market question text
"""

RAW_CATEGORY_MAP: dict[str, str] = {
    "Sports": "Sports",
    "NBA Playoffs": "Sports",
    "Olympics": "Sports",
    "Chess": "Sports",
    "Poker": "Sports",
    "Crypto": "Crypto",
    "NFTs": "Crypto",
    "Politics": "Politics",
    "US-current-affairs": "Politics",
    "Global Politics": "Geopolitics",
    "Ukraine & Russia": "Geopolitics",
    "Business": "Economics",
    "Coronavirus": "Economics",
    "Coronavirus-": "Economics",
    "Pop-Culture": "Entertainment",
    "Art": "Entertainment",
    "Science": "Technology",
    "Tech": "Technology",
    "Space": "Technology",
}


def infer_category(
    question: str,
    raw_category: str | None = None,
    event_category: str | None = None,
) -> str | None:
    """Assign a market to one of 8 target categories.

    Tiers:
      1. Map raw_category via RAW_CATEGORY_MAP
      2. Map event_category via RAW_CATEGORY_MAP
      3. Keyword classification on question text
    """
    if raw_category:
        mapped = RAW_CATEGORY_MAP.get(raw_category)
        if mapped:
            return mapped

    if event_category:
        mapped = RAW_CATEGORY_MAP.get(event_category)
        if mapped:
            return mapped

    return _classify_by_keywords(question)


def _classify_by_keywords(question: str) -> str | None:
    q = question.lower()

    if any(kw in q for kw in [
        "president", "election", "vote", "democrat", "republican",
        "senate", "congress", "governor", "candidate", "primary",
        "trump", "biden", "harris", "newsom", "european union",
        "parliament", "prime minister", "chancellor",
        "supreme court", "justice", "senator", "representative",
        "mayor", "cabinet", "nominee", "impeach",
    ]):
        return "Politics"

    if any(kw in q for kw in [
        "war", "sanction", "military", "nato", "invasion",
        "nuclear", "treaty", "ceasefire", "refugee",
        "terrorist", "diplomat", "embargo", "annex",
    ]):
        return "Geopolitics"

    if any(kw in q for kw in [
        "bitcoin", "ethereum", "crypto", "solana", "defi",
        "nft", "blockchain", "polygon", "token", "web3",
        "etf", "btc", "eth", "altcoin", "stablecoin",
    ]):
        return "Crypto"

    if any(kw in q for kw in [
        "nfl", "nba", "mlb", "nhl", "soccer", "tennis",
        "champion", "playoff", "super bowl", "world cup",
        " vs ", "fight", "match", "race", "grand slam",
        "goal", "touchdown", "homerun", "quarterback",
        "player", "coach", "manager", "transfer", "stadium",
        "ufc", "boxing", "wrestling", "cricket", "golf",
        "formula", "grand prix", "ncaa", "final four",
    ]):
        return "Sports"

    if any(kw in q for kw in [
        "artificial intelligence", "ai ", "gpt", "llm", "chatgpt",
        "agi", "deep learning", "neural", "machine learning",
        "openai", "claude", "gemini", "copilot",
    ]):
        return "AI"

    if any(kw in q for kw in [
        "iphone", "apple", "google", "microsoft", "tesla",
        "rocket", "launch", "space", "satellite",
        "ipo", "startup", "acquisition",
        "quantum", "chip", "semiconductor", "nvidia",
        "meta", "amazon", "twitter", "x.com",
    ]):
        return "Technology"

    if any(kw in q for kw in [
        "inflation", "gdp", "interest rate", "fed", "recession",
        "stock market", "s&p", "nasdaq", "unemployment",
        "trade deficit", "tariff", "treasury", "yield",
        "federal reserve", "housing", "consumer price",
    ]):
        return "Economics"

    if any(kw in q for kw in [
        "movie", "oscar", "grammy", "album", "concert",
        "actor", "actress", "celebrity", "netflix", "disney",
        "award", "film", "tv", "television", "reality",
        "musician", "singer", "director", "producer",
    ]):
        return "Entertainment"

    return None
