"""LIKE metacharacters in search terms must be neutralised.

An unescaped "%" reaching an ILIKE pattern turns a filter into a match-everything,
and "_" silently widens it — the query stops meaning what the caller asked for.
"""

import pytest

from app.utils.sql import escape_like


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0xabc", "0xabc"),
        ("100%", r"100\%"),
        ("a_b", r"a\_b"),
        ("%", r"\%"),
        ("_", r"\_"),
        ("back\\slash", r"back\\slash"),
        ("%_\\", r"\%\_\\"),
        ("", ""),
    ],
)
def test_escape_like(raw: str, expected: str) -> None:
    assert escape_like(raw) == expected


def test_backslash_escaped_before_metacharacters() -> None:
    """A literal backslash must not end up escaping the following character."""
    assert escape_like("\\%") == r"\\\%"
