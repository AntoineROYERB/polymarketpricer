if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

from mage_ai.orchestration.triggers.api import trigger_pipeline

from default_repo.utils.pipeline_status import record_status


@data_exporter
def export_data(data, **kwargs) -> None:
    for tier in [1, 2, 3]:
        try:
            trigger_pipeline(
                "ingestion_trade_history",
                variables={
                    "TIER": tier,
                    "FULL_SYNC": kwargs.get("FULL_SYNC", "false"),
                },
                check_status=True,
                error_on_failure=True,
                poll_interval=30,
                verbose=True,
            )
            record_status(f'ingestion_trade_history_tier{tier}', 'success')
        except Exception as e:
            record_status(f'ingestion_trade_history_tier{tier}', f'failed: {e}')
            raise
