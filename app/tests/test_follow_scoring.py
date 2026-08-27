"""Unit tests for follow scoring formulas (pure functions)."""

import math

import pytest

# ── Category specialization (pure function helpers) ─────────────────

def compute_category_specialization(specialist_count: int, avg_rank: float) -> float:
    score = 0.5 * min(specialist_count / 8, 1) + 0.5 * max(1 - avg_rank / 100, 0)
    return score


def compute_recency_score(days_since: float) -> float:
    return math.exp(-days_since / 90)


def compute_frequency_score(total_trades: float, months_active: float) -> float:
    tpm = total_trades / max(months_active, 1)
    return 1 / (1 + math.exp(-0.1 * (tpm - 10)))


def compute_global_follow_score(
    edge: float, consistency: float, spec: float, recency: float, frequency: float
) -> float:
    return 0.30 * edge + 0.20 * consistency + 0.20 * spec + 0.15 * recency + 0.15 * frequency


def compute_category_follow_score_formula(
    edge: float,
    roi_percentile: float,
    win_rate: float,
    is_specialist: bool,
    volume_percentile: float,
    recency_score: float,
) -> float:
    specialist_bonus = 1.0 if is_specialist else 0.5
    score = (
        0.25 * edge
        + 0.25 * roi_percentile
        + 0.20 * win_rate
        + 0.15 * specialist_bonus
        + 0.10 * volume_percentile
        + 0.05 * recency_score
    )
    return max(0.0, min(1.0, score))


def get_recommendation(score: float) -> str:
    if score >= 0.70:
        return "FOLLOW"
    elif score >= 0.35:
        return "WATCH"
    return "IGNORE"


class TestCategorySpecialization:
    @pytest.mark.parametrize("specialist_count,avg_rank,expected_min", [
        (8, 1, 0.99),
        (4, 25, 0.5 * 4/8 + 0.5 * (1 - 25/100)),
        (0, 50, 0.5 * 0 + 0.5 * (1 - 50/100)),
        (0, 0, 0.5 * 0 + 0.5 * 1.0),
    ])
    def test_compute(self, specialist_count: int, avg_rank: float, expected_min: float) -> None:
        result = compute_category_specialization(specialist_count, avg_rank)
        assert result >= expected_min - 0.01
        assert 0 <= result <= 1

    def test_max_specialization(self) -> None:
        result = compute_category_specialization(8, 1)
        assert result == pytest.approx(0.5 * 1 + 0.5 * (1 - 1/100), abs=0.01)

    def test_zero_specialization_no_data(self) -> None:
        result = compute_category_specialization(0, 50)
        assert result == pytest.approx(0.5 * 0 + 0.5 * 0.5, abs=0.01)


class TestRecencyScore:
    @pytest.mark.parametrize("days_since,expected", [
        (0, 1.0),
        (90, round(math.exp(-1), 6)),
        (365, round(math.exp(-365/90), 6)),
    ])
    def test_recency(self, days_since: int, expected: float) -> None:
        assert abs(compute_recency_score(days_since) - expected) < 0.01

    def test_recency_today(self) -> None:
        assert compute_recency_score(0) == 1.0

    def test_recency_old(self) -> None:
        score = compute_recency_score(365)
        assert score < 0.05


class TestFrequencyScore:
    def test_low_frequency(self) -> None:
        score = compute_frequency_score(2, 12)
        assert score < 0.30

    def test_high_frequency(self) -> None:
        score = compute_frequency_score(500, 10)
        assert score > 0.90

    def test_zero_trades(self) -> None:
        score = compute_frequency_score(0, 1)
        assert score == pytest.approx(1 / (1 + math.exp(1)), abs=0.01)

    def test_zero_months_uses_minimum(self) -> None:
        score = compute_frequency_score(0, 0)
        assert score > 0


class TestGlobalFollowScore:
    def test_perfect_wallet_score(self) -> None:
        score = compute_global_follow_score(1.0, 1.0, 1.0, 1.0, 1.0)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_zero_edge_wallet(self) -> None:
        score = compute_global_follow_score(0, 0.5, 0, 0.37, 0.27)
        expected = 0.20 * 0.5 + 0.15 * 0.37 + 0.15 * 0.27
        assert score == pytest.approx(expected, abs=0.01)

    def test_all_zeros(self) -> None:
        score = compute_global_follow_score(0, 0, 0, 0, 0)
        assert score == 0.0

    def test_half_scores(self) -> None:
        score = compute_global_follow_score(0.5, 0.5, 0.5, 0.5, 0.5)
        assert score == 0.5

    def test_score_in_bounds(self) -> None:
        for _ in range(100):
            import random
            s = compute_global_follow_score(
                random.random(), random.random(), random.random(),
                random.random(), random.random(),
            )
            assert 0 <= s <= 1


class TestCategoryFollowScore:
    def test_perfect_category_score(self) -> None:
        score = compute_category_follow_score_formula(1.0, 1.0, 1.0, True, 1.0, 1.0)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_zero_category_score(self) -> None:
        score = compute_category_follow_score_formula(0, 0, 0, False, 0, 0)
        expected = 0.15 * 0.5  # specialist_bonus = 0.5
        assert score == pytest.approx(expected, abs=0.01)

    def test_imperfect_but_good(self) -> None:
        score = compute_category_follow_score_formula(0.8, 0.7, 0.6, True, 0.5, 0.9)
        assert 0.5 < score < 1.0

    def test_specialist_bonus_impact(self) -> None:
        specialist = compute_category_follow_score_formula(0.5, 0.5, 0.5, True, 0.5, 0.5)
        non_specialist = compute_category_follow_score_formula(0.5, 0.5, 0.5, False, 0.5, 0.5)
        assert specialist > non_specialist

    def test_clamped_to_one(self) -> None:
        score = compute_category_follow_score_formula(2.0, 2.0, 2.0, True, 2.0, 2.0)
        assert score == 1.0

    def test_clamped_to_zero(self) -> None:
        score = compute_category_follow_score_formula(-1, -1, -1, False, -1, -1)
        assert score == 0.0


class TestRecommendationThresholds:
    @pytest.mark.parametrize("score_value,expected", [
        (0.85, "FOLLOW"),
        (0.70, "FOLLOW"),
        (0.69, "WATCH"),
        (0.50, "WATCH"),
        (0.35, "WATCH"),
        (0.34, "IGNORE"),
        (0.20, "IGNORE"),
        (0.00, "IGNORE"),
    ])
    def test_thresholds(self, score_value: float, expected: str) -> None:
        assert get_recommendation(score_value) == expected
