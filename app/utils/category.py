from fastapi import HTTPException

from app.models.enums import MarketCategory

_CATEGORY_MAP: dict[str, str] = {
    member.value.lower(): member.value
    for member in MarketCategory
}


def validate_category(category: str) -> str | None:
    return _CATEGORY_MAP.get(category.lower())


def validate_category_or_404(category: str) -> str:
    norm = validate_category(category)
    if norm is None:
        valid = sorted(m.value for m in MarketCategory)
        raise HTTPException(
            status_code=404,
            detail=f"Invalid category '{category}'. Valid categories: {', '.join(valid)}",
        )
    return norm


def get_valid_categories() -> list[str]:
    return sorted(_CATEGORY_MAP.keys())
