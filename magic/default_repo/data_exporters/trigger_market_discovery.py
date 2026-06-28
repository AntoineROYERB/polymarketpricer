if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

from mage_ai.orchestration.triggers.api import trigger_pipeline

from default_repo.utils.pipeline_status import record_status


@data_exporter
def export_data(data, **kwargs) -> None:
    try:
        trigger_pipeline(
            'ingestion_market_discovery',
            variables={},
            check_status=False,
            error_on_failure=True,
            poll_interval=30,
            poll_timeout=30,
            schedule_name=None,
            verbose=True,
        )
        record_status('ingestion_market_discovery', 'success')
    except Exception as e:
        record_status('ingestion_market_discovery', f'failed: {e}')
        raise
