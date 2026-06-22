from app.services.category_classifier import infer_category


def test_classify_politics() -> None:
    assert infer_category("Will Donald Trump win the 2024 election?") == "Politics"


def test_classify_crypto() -> None:
    assert infer_category("Will Bitcoin reach $100k by end of 2025?") == "Crypto"


def test_classify_sports() -> None:
    assert infer_category("Will the Chiefs win the Super Bowl?") == "Sports"


def test_classify_ai() -> None:
    assert infer_category("Will GPT-5 be released before 2026?") == "AI"


def test_classify_geopolitics() -> None:
    assert infer_category("Will there be a ceasefire in Ukraine by June?") == "Geopolitics"


def test_classify_economics() -> None:
    assert infer_category("Will the Fed cut rates in March?") == "Economics"


def test_classify_technology() -> None:
    assert infer_category("Will Apple release a VR headset?") == "Technology"


def test_classify_entertainment() -> None:
    assert infer_category("Will Oppenheimer win the Oscar for Best Picture?") == "Entertainment"


def test_classify_unclassifiable() -> None:
    assert infer_category("Will it rain in Paris tomorrow?") is None


def test_classify_case_insensitive() -> None:
    assert infer_category("will donald trump win the 2024 election?") == "Politics"
    assert infer_category("WILL DONALD TRUMP WIN THE 2024 ELECTION?") == "Politics"
    assert infer_category("WiLl DoNaLd TrUmP wIn ThE 2024 ElEcTiOn?") == "Politics"
