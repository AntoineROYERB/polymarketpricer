_LIKE_ESCAPE = str.maketrans({"\\": r"\\", "%": r"\%", "_": r"\_"})


def escape_like(value: str) -> str:
    """Neutralise LIKE/ILIKE metacharacters in a caller-supplied search term.

    Without this, a search for "%" matches every row and "_" matches any single
    character — the filter silently stops filtering. Use with ``escape="\\"``.
    """
    return value.translate(_LIKE_ESCAPE)
