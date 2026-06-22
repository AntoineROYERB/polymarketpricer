# Phase 2 — Testing Strategy

> **Goal**: Comprehensive test coverage for category analytics features.
> **Pattern**: Mirrors Phase 1 test structure — mock-based API tests + real-DB integration tests.
> **Status**: Planning — ready for spec.

---

## 1. Test Organization

```
app/tests/
├── test_api/
│   ├── __init__.py
│   ├── test_endpoints.py          # Existing 9 tests (no change)
│   └── test_category_endpoints.py # NEW — 8+ tests for Phase 2 endpoints
├── __init__.py
├── conftest.py                    # Updated with new fixtures
└── test_db_integrity.py           # +8 new integration tests for Phase 2 tables
```

**Target: 41 → 57 tests** (16 new: 8 API + 8 integration)

---

## 2. API Tests: `test_category_endpoints.py` (NEW — 8 tests)

Mock-based, no database required. Tests:

| # | Test | Description |
|---|---|---|
| 1 | `test_category_leaderboard_valid` | `GET /api/v1/leaderboard/politics` returns correct shape |
| 2 | `test_category_leaderboard_invalid_category` | `GET /api/v1/leaderboard/invalid` returns 404 |
| 3 | `test_category_leaderboard_with_params` | limit/offset parameters work |
| 4 | `test_category_specialists` | `GET /api/v1/leaderboard/crypto/specialists` returns list |
| 5 | `test_wallet_categories` | `GET /api/v1/wallets/{addr}/categories` returns breakdown |
| 6 | `test_wallet_categories_not_found` | Unknown wallet returns 404 |
| 7 | `test_wallet_category_detail` | `GET /api/v1/wallets/{addr}/categories/politics` returns detail |
| 8 | `test_wallet_category_detail_not_found` | Unknown category for wallet returns 404 |

### Mock Patterns

Reuse the existing `conftest.py` pattern: `AsyncMock` sessions that return empty results for Phase 1 data, plus new mock data for `CategoryAnalytic` and `CategoryRanking` models.

---

## 3. Integration Tests: `test_db_integrity.py` (+8 tests)

New tests added to the existing integration test suite:

### Row Count Thresholds (+2)

| Test | Threshold | Rationale |
|---|---|---|
| `test_category_analytics_row_count` | ≥ 100 rows | At least some wallets have per-category data |
| `test_category_rankings_row_count` | ≥ 50 rows | At least the top categories have rankings |

### Referential Integrity (+2)

| Test | Child → Parent |
|---|---|
| `test_category_analytics_fk_wallets` | `category_analytics.wallet` → `wallets.wallet` |
| `test_category_rankings_fk_wallets` | `category_rankings.wallet` → `wallets.wallet` |

### Not-Null Constraints (+1)

| Test | Table / Column |
|---|---|
| `test_category_analytics_not_null` | `wallet`, `category`, `snapshot_date` in `category_analytics` |

### Data Quality (+2)

| Test | What it validates |
|---|---|
| `test_category_analytics_roi_range` | ROI within reasonable bounds (e.g., -100% to +10000%) |
| `test_category_analytics_win_rate_range` | win_rate in [0, 1] |

### Cross-Table Consistency (+1)

| Test | What it validates |
|---|---|
| `test_category_analytics_wallets_exist` | All wallets in `category_analytics` exist in `wallets` table |

---

## 4. Category Classifier Tests (NEW — separate file)

### `app/tests/test_category_classifier.py` (NEW — 10+ tests)

Pure unit tests for the `infer_category()` function. No database needed.

| # | Test | Input | Expected |
|---|---|---|---|
| 1 | `test_classify_politics` | "Will Donald Trump win the 2024 election?" | "Politics" |
| 2 | `test_classify_crypto` | "Will Bitcoin reach $100k by end of 2025?" | "Crypto" |
| 3 | `test_classify_sports` | "Will the Chiefs win the Super Bowl?" | "Sports" |
| 4 | `test_classify_ai` | "Will GPT-5 be released before 2026?" | "AI" |
| 5 | `test_classify_geopolitics` | "Will there be a ceasefire in Ukraine by June?" | "Geopolitics" |
| 6 | `test_classify_economics` | "Will the Fed cut rates in March?" | "Economics" |
| 7 | `test_classify_technology` | "Will Apple release a VR headset?" | "Technology" |
| 8 | `test_classify_entertainment` | "Will Oppenheimer win Best Picture?" | "Entertainment" |
| 9 | `test_classify_unclassifiable` | "Will it rain in Paris tomorrow?" | None |
| 10 | `test_classify_case_insensitive` | Lowercase, uppercase, mixed input | Correct category |

---

## 5. Edge Cases

| Scenario | Expected Behavior |
|---|---|
| Wallet has 0 trades in category | Not included in `category_analytics` for that category |
| Wallet has < 30 trades in category | Included in analytics but `is_specialist = False` |
| Category has only 1 trader | That trader is ranked #1, ROI > median (median = their own ROI) |
| All ROI values are equal | All get the same rank; none flagged as above-median specialist |
| Market category changes | New analytics run picks up new mapping (snapshot-based) |
| Empty categories (no traders) | No `category_rankings` rows for that category |
| Wallet appears in multiple categories | Independent rows per (wallet, category) |

---

## 6. Migration Test

| Test | Verification |
|---|---|
| `alembic upgrade head` completes | No errors |
| `alembic downgrade -1` completes | No errors |
| Both new tables exist after upgrade | `\dt` shows both |
| Both tables disappear after downgrade | `\dt` shows neither |
| Existing Phase 1 data intact after upgrade | Row counts match before/after |

---

## 7. Test Target Summary

| Suite | Existing | New | Total |
|---|---|---|---|
| API tests (mocked) | 9 | 8 | 17 |
| Integration tests (real DB) | 32 | 8 | 40 |
| Classifier tests (pure unit) | 0 | 10 | 10 |
| **Total** | **41** | **26** | **67** |

---

## 8. Acceptance Criteria

- [ ] All 67 tests pass in CI
- [ ] All 41 existing tests still pass (no regression)
- [ ] Category classifier correctly identifies all 8 categories
- [ ] Unclassifiable markets return `None` without error
- [ ] Integration tests validate real data from the seeded database
- [ ] Migration forward + backward works cleanly
- [ ] Mock tests cover all new endpoints
