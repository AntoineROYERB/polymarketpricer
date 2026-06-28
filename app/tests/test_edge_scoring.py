import sys
from unittest.mock import MagicMock

import pytest
from pandas import DataFrame
from decimal import Decimal

# Mock mage_ai module before importing mage transformers
mage_mock = MagicMock()
mage_mock.data_preparation.decorators.data_loader = lambda x: x
mage_mock.data_preparation.decorators.transformer = lambda x: x
mage_mock.data_preparation.decorators.test = lambda x: x
sys.modules['mage_ai'] = mage_mock
sys.modules['mage_ai.data_preparation'] = mage_mock.data_preparation
sys.modules['mage_ai.data_preparation.decorators'] = mage_mock.data_preparation.decorators

from magic.default_repo.transformers.compute_trade_edge import compute_wallet_edge  # noqa: E402


def make_trade(
    trade_id: str, wallet: str, market_id: str, outcome_id: str,
    type: str, price: float, size: float = 100.0,
    created_at: str = "2026-01-01",
) -> dict:
    return {
        "trade_id": trade_id,
        "wallet": wallet,
        "market_id": market_id,
        "outcome_id": outcome_id,
        "type": type,
        "price": price,
        "size": size,
        "amount_usd": price * size,
        "shares": size,
        "created_at": created_at,
        "market_question": "Test market?",
        "resolution": None,
        "resolution_source": None,
        "outcome_label": "Yes",
        "outcome_winner": None,
    }


def make_outcome(outcome_id: str, market_id: str, outcome: str, winner: bool | None) -> dict:
    return {
        "outcome_id": outcome_id,
        "market_id": market_id,
        "outcome": outcome,
        "winner": winner,
    }


class TestComputeTradeEdge:
    def test_buy_hold_to_resolution_win(self):
        trades = DataFrame([make_trade("t1", "wallet_a", "m1", "o1", "BUY", 0.40)])
        outcomes = DataFrame([make_outcome("o1", "m1", "Yes", True)])
        results = compute_wallet_edge(trades, outcomes)
        assert len(results) == 1
        assert results[0]["edge"] == pytest.approx(1.50, rel=1e-3)
        assert results[0]["is_positive"] is True
        assert results[0]["had_sell"] is False

    def test_buy_hold_to_resolution_loss(self):
        trades = DataFrame([make_trade("t1", "wallet_a", "m1", "o2", "BUY", 0.60)])
        outcomes = DataFrame([make_outcome("o2", "m1", "No", False)])
        results = compute_wallet_edge(trades, outcomes)
        assert len(results) == 1
        assert results[0]["edge"] == pytest.approx(-1.0, rel=1e-3)
        assert results[0]["is_positive"] is False

    def test_buy_then_sell(self):
        trades = DataFrame([
            make_trade("t1", "wallet_a", "m1", "o1", "BUY", 0.30),
            make_trade("t2", "wallet_a", "m1", "o1", "SELL", 0.55),
        ])
        outcomes = DataFrame([make_outcome("o1", "m1", "Yes", True)])
        results = compute_wallet_edge(trades, outcomes)
        assert len(results) == 1
        assert float(results[0]["edge"]) == pytest.approx(0.8333, rel=1e-3)
        assert results[0]["had_sell"] is True

    def test_multiple_buys_fifo_matching(self):
        trades = DataFrame([
            make_trade("t1", "wallet_a", "m1", "o1", "BUY", 0.30),
            make_trade("t2", "wallet_a", "m1", "o1", "BUY", 0.40),
            make_trade("t3", "wallet_a", "m1", "o1", "SELL", 0.50),
        ])
        outcomes = DataFrame([make_outcome("o1", "m1", "Yes", True)])
        results = compute_wallet_edge(trades, outcomes)
        assert len(results) == 2
        buy1 = [r for r in results if r["entry_price"] == Decimal("0.30")][0]
        buy2 = [r for r in results if r["entry_price"] == Decimal("0.40")][0]
        assert float(buy1["edge"]) == pytest.approx(0.6667, rel=1e-3)
        assert float(buy2["edge"]) == pytest.approx(1.50, rel=1e-3)

    def test_edge_zero_counts_as_negative(self):
        trades = DataFrame([
            make_trade("t1", "wallet_a", "m1", "o1", "BUY", 0.50),
            make_trade("t2", "wallet_a", "m1", "o1", "SELL", 0.50),
        ])
        outcomes = DataFrame([make_outcome("o1", "m1", "Yes", True)])
        results = compute_wallet_edge(trades, outcomes)
        assert len(results) == 1
        assert results[0]["edge"] == pytest.approx(0.0, abs=1e-6)
        assert results[0]["is_positive"] is False

    def test_sell_without_buy_ignored(self):
        trades = DataFrame([make_trade("t1", "wallet_a", "m1", "o1", "SELL", 0.80)])
        outcomes = DataFrame([make_outcome("o1", "m1", "Yes", True)])
        results = compute_wallet_edge(trades, outcomes)
        assert len(results) == 0

    def test_zero_entry_price_skipped(self):
        trades = DataFrame([make_trade("t1", "wallet_a", "m1", "o1", "BUY", 0.0)])
        outcomes = DataFrame([make_outcome("o1", "m1", "Yes", True)])
        results = compute_wallet_edge(trades, outcomes)
        assert len(results) == 0

    def test_aggregation_correctness(self):
        from magic.default_repo.transformers.compute_trade_edge import compute_edges
        trades = DataFrame([
            make_trade("t1", "wallet_a", "m1", "o1", "BUY", 0.50, size=100),
            make_trade("t2", "wallet_a", "m1", "o1", "SELL", 0.75, size=100),
            make_trade("t3", "wallet_a", "m2", "o2", "BUY", 0.40, size=100),
            make_trade("t4", "wallet_a", "m2", "o2", "BUY", 0.30, size=100),
        ])
        outcomes = DataFrame([
            make_outcome("o1", "m1", "Yes", True),
            make_outcome("o2", "m2", "No", False),
        ])
        result = compute_edges(trades, outcomes)
        assert len(result) == 1
        row = result.iloc[0]
        assert row["num_edge_trades"] == 3
        assert row["avg_edge"] == pytest.approx(-0.50, rel=1e-3)
        assert row["positive_edge_trades"] == 1
        assert row["negative_edge_trades"] == 2

    def test_empty_trades_returns_empty(self):
        from magic.default_repo.transformers.compute_trade_edge import compute_edges
        trades = DataFrame()
        outcomes = DataFrame()
        result = compute_edges(trades, outcomes)
        assert result.empty

    def test_min_max_normalisation(self):
        from magic.default_repo.transformers.compute_trade_edge import compute_edges
        trades = DataFrame([
            make_trade("t1", "wallet_a", "m1", "o1", "BUY", 0.40, size=100),
            make_trade("t2", "wallet_b", "m2", "o2", "BUY", 0.60, size=100),
            make_trade("t3", "wallet_b", "m2", "o2", "SELL", 0.80, size=100),
            make_trade("t4", "wallet_c", "m3", "o3", "BUY", 0.50, size=100),
        ])
        outcomes = DataFrame([
            make_outcome("o1", "m1", "Yes", True),
            make_outcome("o2", "m2", "No", True),
            make_outcome("o3", "m3", "No", False),
        ])
        result = compute_edges(trades, outcomes)
        assert len(result) == 3
        scores = result.set_index("wallet")["edge_score"]
        assert scores["wallet_c"] == pytest.approx(0.0, abs=1e-6)
        assert scores["wallet_a"] == pytest.approx(1.0, abs=1e-6)
