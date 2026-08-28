# Design records

Phase-by-phase specifications and implementation plans, written before each phase was
built and kept as a record of how the system was designed.

**These are historical documents.** They describe intent at the time of writing, not the
current state of the code — commands, file paths and row counts in them may be stale.
For what the system does today, see [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md),
[`docs/API.md`](../API.md) and [`docs/DATABASE.md`](../DATABASE.md).

| Directory | Contents |
|---|---|
| `plans/phase-01/` | MVP leaderboard — database redesign, ETL pipelines, wallet filtering, CI |
| `plans/phase-02/` | Niche expertise — category mapping, per-category analytics, API |
| `plans/phase-03/` | Smart money detection — alert pipeline, cash-flow PnL, Discord delivery |
| `plans/phase-04/` | Edge scoring — FIFO trade matching, edge leaderboard, ranking integration |
| `plans/phase-05/` | Recommendation engine — follow scoring, paper trading, portfolio API |
| `plans/phase-06/` | Dashboard — backend auth, Next.js frontend, Docker deployment |
| `plans/phase-07/` | Pipeline monitoring |
| `plans/db-seed-dump.md` | How the committed database snapshot is built (current) |
| `specs/` | Detailed phase-02 specifications |
