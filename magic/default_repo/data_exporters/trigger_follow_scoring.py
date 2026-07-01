"""Trigger the enrichment_follow_scoring pipeline from the orchestration chain."""

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

from mage_ai.orchestration.triggers.api import trigger_pipeline


@data_exporter
def export_data(data, **kwargs) -> None:
    trigger_pipeline(
        'enrichment_follow_scoring',
        variables={},
        check_status=False,
        error_on_failure=True,
        poll_interval=30,
        poll_timeout=300,
        schedule_name=None,
        verbose=True,
    )
