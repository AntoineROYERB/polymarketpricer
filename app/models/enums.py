from enum import StrEnum


class TradeSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class MarketCategory(StrEnum):
    POLITICS = "Politics"
    CRYPTO = "Crypto"
    SPORTS = "Sports"
    ECONOMICS = "Economics"
    TECHNOLOGY = "Technology"
    AI = "AI"
    GEOPOLITICS = "Geopolitics"
    ENTERTAINMENT = "Entertainment"
