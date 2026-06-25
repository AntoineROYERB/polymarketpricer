if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

from mage_ai.orchestration.triggers.api import trigger_pipeline

from default_repo.utils.pipeline_status import record_status


@data_exporter
def export_data(data, **kwargs) -> None:
    try:
        trigger_pipeline(
            'smart_money_detection',
            variables={},
            check_status=True,
            error_on_failure=True,
            poll_interval=30,
            poll_timeout=120,
            verbose=True,
        )
        record_status('smart_money_detection', 'success')
    except Exception as e:
        record_status('smart_money_detection', f'failed: {e}')
        raise
