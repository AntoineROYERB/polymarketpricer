from app.models.enums import MarketCategory

_CATEGORY_MAP: dict[str, str] = {
    member.value.lower(): member.value
    for member in MarketCategory
}


def validate_category(category: str) -> str | None:
    return _CATEGORY_MAP.get(category.lower())


def get_valid_categories() -> list[str]:
    return sorted(_CATEGORY_MAP.keys())
