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

NBA_TEAMS = [
    "celtics", "nets", "knicks", "sixers", "raptors",
    "bulls", "cavaliers", "pistons", "pacers", "bucks",
    "hawks", "hornets", "heat", "magic", "wizards",
    "nuggets", "timberwolves", "thunder", "trail blazers", "jazz",
    "warriors", "clippers", "lakers", "suns", "kings",
    "mavericks", "rockets", "grizzlies", "pelicans", "spurs",
]

NFL_TEAMS = [
    "chiefs", "bills", "bengals", "ravens", "steelers", "browns",
    "patriots", "dolphins", "jets", "colts", "titans", "jaguars",
    "texans", "chargers", "raiders", "broncos",
    "eagles", "cowboys", "giants", "commanders",
    "49ers", "rams", "seahawks", "cardinals",
    "lions", "packers", "vikings", "bears",
    "saints", "buccaneers", "panthers", "falcons",
]

MLB_TEAMS = [
    "yankees", "red sox", "blue jays", "rays", "orioles",
    "astros", "rangers", "mariners", "athletics", "angels",
    "guardians", "twins", "white sox", "royals", "tigers",
    "braves", "mets", "phillies", "marlins", "nationals",
    "dodgers", "padres", "giants", "diamondbacks", "rockies",
    "brewers", "cardinals", "cubs", "pirates", "reds",
]

NHL_TEAMS = [
    "bruins", "maple leafs", "canadiens", "lightning", "panthers",
    "rangers", "hurricanes", "devils", "islanders", "flyers",
    "avalanche", "stars", "jets", "predators", "blues",
    "golden knights", "oilers", "flames", "kraken", "canucks",
    "ducks", "sharks", "kings", "coyotes", "blackhawks",
]

SOCCER_TEAMS = [
    "arsenal", "chelsea", "liverpool", "manchester", "man city",
    "tottenham", "juventus", "milan", "inter", "napoli",
    "barcelona", "real madrid", "atletico", "bayern", "dortmund",
    "psg", "marseille", "ajax", "porto", "benfica",
]

ALL_SPORTS_TEAMS = NBA_TEAMS + NFL_TEAMS + MLB_TEAMS + NHL_TEAMS + SOCCER_TEAMS

SPORTS_BETTING_TERMS = [
    "spread: ", "o/u ", "over ", "under ", "over/under",
    "moneyline", "prop bet", "parlay", "total points",
    "first touchdown", "first goal", "first basket",
    "player to score", "to win the ", "win the series",
    "conference tournament", "championship game",
    "regular season", "postseason", "playoffs",
    "ballon d'or", "golden boot", "most valuable player",
    "mvp", "rookie of the year", "defensive player",
    "all-star", "all star", "hall of fame",
]

ESPORTS_TERMS = [
    "roshan", "barracks", "dota", "esports",
    "counter-strike", "valorant", "overwatch",
    "league of legends", "lol ", "worlds ",
    "map ", "total kills", "first blood",
    "first map", "game ", "odd/even",
    "first to ", "win the map", "total rounds",
    "ends in daytime", "ends in night",
]

COLLEGE_CONFERENCES = [
    "sec ", "acc ", "big 12", "big ten", "big east",
    "pac-12", "pac 12", "mountain west",
    "atlantic coast", "southeastern conference",
]


def infer_category(
    question: str,
    raw_category: str | None = None,
    event_category: str | None = None,
) -> str | None:
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
        "electoral", "ballot", "campaign", "debate",
        "legislature", "constitutional",
    ]):
        return "Politics"

    if any(kw in q for kw in [
        "war", "sanction", "military", "nato", "invasion",
        "nuclear", "treaty", "ceasefire", "refugee",
        "terrorist", "diplomat", "embargo", "annex",
        "border ", "sovereignty", "intervention",
    ]):
        return "Geopolitics"

    if any(kw in q for kw in [
        "bitcoin", "ethereum", "crypto", "solana", "defi",
        "nft", "blockchain", "polygon", "token", "web3",
        "etf", "btc", "eth", "altcoin", "stablecoin",
        "cryptocurrency", "halving",
    ]):
        return "Crypto"

    if any(kw in q for kw in (
        SPORTS_BETTING_TERMS + ESPORTS_TERMS + COLLEGE_CONFERENCES
        + [
            "nfl", "nba", "mlb", "nhl", "soccer", "tennis",
            "champion", "playoff", "super bowl", "world cup",
            " vs ", "fight", "match", "race", "grand slam",
            "goal", "touchdown", "homerun", "quarterback",
            "player", "coach", "manager", "transfer", "stadium",
            "ufc", "boxing", "wrestling", "cricket", "golf",
            "formula", "grand prix", "ncaa", "final four",
            "winner", "wins the ", "to beat ",
            "point spread", "over/under",
            "any other score", "exact score",
            "games total", "total runs", "total goals",
            "correct score", "set ", "sets ",
            "tie ", "draw ", "series",
            "combined points", "first inning",
            "leading at halftime", "score in his next",
            "score a goal", "run scored",
            "win the world series", "win the stanley cup",
            "win the nba finals", "win the super bowl",
            "will they make the", "to make the",
            "highest scoring", "points scored",
            "match winner", "to qualify for",
            "win percentage", "field goal",
            "free throw", "three pointer",
            "corner kick", "yellow card", "red card",
            "inning", "strikeout", "home run",
            "halftime", "fulltime", "extra time",
            "penalty shootout", "quarter final",
            "semi final", "round of",
            "group stage", "knockout",
        ] + ALL_SPORTS_TEAMS
    )):
        return "Sports"

    if any(kw in q for kw in [
        "artificial intelligence", "ai ", "gpt", "llm", "chatgpt",
        "agi", "deep learning", "neural", "machine learning",
        "openai", "claude", "gemini", "copilot",
        "large language model",
    ]):
        return "AI"

    if any(kw in q for kw in [
        "iphone", "apple", "google", "microsoft", "tesla",
        "rocket", "launch", "space", "satellite",
        "ipo", "startup", "acquisition",
        "quantum", "chip", "semiconductor", "nvidia",
        "meta", "amazon", "twitter", "x.com",
        "algorithm", "software", "database",
    ]):
        return "Technology"

    if any(kw in q for kw in [
        "inflation", "gdp", "interest rate", "fed", "recession",
        "stock market", "s&p", "nasdaq", "unemployment",
        "trade deficit", "tariff", "treasury", "yield",
        "federal reserve", "housing", "consumer price",
        "cpi", "pmi", "nonfarm", "payroll",
        "nikkei", "fear & greed", "index ",
        "s&p 500", "dow jones",
    ]):
        return "Economics"

    if any(kw in q for kw in [
        "movie", "oscar", "grammy", "album", "concert",
        "actor", "actress", "celebrity", "netflix", "disney",
        "award", "film", "tv", "television", "reality",
        "musician", "singer", "director", "producer",
        "tweet", "twitter follower", "instagram",
        "tiktok", "youtube", "streamer", "influencer",
        "box office", "song", "spotify",
    ]):
        return "Entertainment"

    return None
