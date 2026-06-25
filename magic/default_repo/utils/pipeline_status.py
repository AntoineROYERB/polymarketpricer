"""Shared pipeline status collector backed by PostgreSQL.

Each trigger block (runs in its own process) writes its status here.
The notification block reads aggregated status from the same table.
"""

from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from default_repo.utils.db_helpers import DATABASE_URL


def record_status(pipeline_name: str, status: str) -> None:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO pipeline_run_log (pipeline_name, status, updated_at)
                VALUES (:name, :status, :now)
                ON CONFLICT (pipeline_name)
                DO UPDATE SET status = :status, updated_at = :now
            """),
            {"name": pipeline_name, "status": status, "now": datetime.now(timezone.utc)},
        )
    engine.dispose()


def get_all_statuses() -> dict[str, str]:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT pipeline_name, status FROM pipeline_run_log")
        ).fetchall()
    engine.dispose()
    return {row.pipeline_name: row.status for row in rows}


def reset() -> None:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM pipeline_run_log"))
    engine.dispose()
