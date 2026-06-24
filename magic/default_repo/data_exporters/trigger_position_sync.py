if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

from mage_ai.orchestration.triggers.api import trigger_pipeline


@data_exporter
def export_data(data, **kwargs) -> None:
    for tier in [1, 2, 3]:
        batch = 0
        while True:
            result = trigger_pipeline(
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
            wallets_processed = (result or {}).get("wallets_processed", 0)
            if wallets_processed == 0:
                break
            batch += 1
