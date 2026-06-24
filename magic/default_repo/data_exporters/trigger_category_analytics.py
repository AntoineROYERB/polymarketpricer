if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

from mage_ai.orchestration.triggers.api import trigger_pipeline


@data_exporter
def export_data(data, **kwargs) -> None:
    trigger_pipeline(
        "category_analytics",
        check_status=True,
        error_on_failure=True,
        poll_interval=30,
        verbose=True,
    )
