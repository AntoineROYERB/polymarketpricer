if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

from mage_ai.orchestration.triggers.api import trigger_pipeline
from sqlalchemy import create_engine, text

from default_repo.utils.sync_mode import get_sync_cutoff, is_full_sync

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"
BATCH_SIZE = 5000


@data_exporter
def export_data(data, **kwargs) -> None:
    engine = create_engine(DATABASE_URL)
    try:
        for tier in [1, 2, 3]:
            cutoff = get_sync_cutoff(tier) if not is_full_sync() else None
            with engine.begin() as conn:
                if cutoff is None:
                    total = conn.execute(
                        text("SELECT COUNT(*) FROM wallets WHERE is_tracked = true"),
                    ).scalar()
                else:
                    total = conn.execute(
                        text("SELECT COUNT(*) FROM wallets WHERE is_tracked = true AND (last_position_sync IS NULL OR last_position_sync < :cutoff)"),
                        {"cutoff": cutoff},
                    ).scalar()

            batch = 0
            while batch * BATCH_SIZE < total:
                trigger_pipeline(
                    "ingestion_position_sync",
                    variables={
                        "TIER": tier,
                        "BATCH": batch,
                        "FULL_SYNC": kwargs.get("FULL_SYNC", "false"),
                    },
                    check_status=True,
                    error_on_failure=True,
                    poll_interval=30,
                    verbose=True,
                )
                batch += 1
    finally:
        engine.dispose()
