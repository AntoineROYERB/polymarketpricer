if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter


@data_exporter
def export_data(**kwargs) -> None:
    from mage_ai.orchestration.triggers.api import trigger_pipeline

    trigger_pipeline(
        'smart_money_detection',
        variables={},
        check_status=True,
        error_on_failure=True,
        poll_interval=30,
        poll_timeout=120,
        verbose=True,
    )
