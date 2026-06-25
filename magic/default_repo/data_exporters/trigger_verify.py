if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

from mage_ai.orchestration.triggers.api import trigger_pipeline

from default_repo.utils.pipeline_status import record_status


@data_exporter
def export_data(data, **kwargs) -> None:
    try:
        trigger_pipeline(
            "verify_etl_output",
            check_status=True,
            error_on_failure=True,
            poll_interval=30,
            verbose=True,
        )
        record_status('verify_etl_output', 'success')
    except Exception as e:
        record_status('verify_etl_output', f'failed: {e}')
        raise
