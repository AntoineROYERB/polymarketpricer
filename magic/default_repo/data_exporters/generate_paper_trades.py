"""Generate paper trades from new alerts for followed wallets with auto-copy enabled.

NOTE: This exporter has been removed from the smart_money_detection pipeline.
Real-time paper trade generation is handled by the background service
app/services/paper_trade_generator.py (running as an asyncio task in app/main.py).

This file is kept as a reference for future batch processing needs. To reinstate
in the pipeline, update the smart_money_detection metadata.yaml.
"""

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter


@data_exporter
def generate_paper_trades(*args, **kwargs) -> None:
    """Hook for paper trade generation (deprecated — use background service)."""
    pass
