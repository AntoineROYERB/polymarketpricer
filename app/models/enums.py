from enum import StrEnum


class TradeSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class TradeType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class PositionStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    RESOLVED = "RESOLVED"


class RankingListType(StrEnum):
    TOP_100 = "top_100"
    EMERGING = "emerging"
    CONSISTENT = "consistent"


class MarketCategory(StrEnum):
    POLITICS = "Politics"
    CRYPTO = "Crypto"
    SPORTS = "Sports"
    ECONOMICS = "Economics"
    TECHNOLOGY = "Technology"
    AI = "AI"
    GEOPOLITICS = "Geopolitics"
    ENTERTAINMENT = "Entertainment"
