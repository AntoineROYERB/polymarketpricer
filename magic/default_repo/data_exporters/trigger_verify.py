if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

import json
import sqlite3
from mage_ai.orchestration.triggers.api import trigger_pipeline
from default_repo.utils.pipeline_status import record_status

MAGE_DB_PATH = "/home/src/mage_data/default_repo/mage-ai.db"


def _get_block_error(pipeline_run_id: int) -> str | None:
    try:
        conn = sqlite3.connect(MAGE_DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT metrics FROM block_run WHERE pipeline_run_id=? AND status='failed' LIMIT 1",
            (pipeline_run_id,),
        )
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            metrics = json.loads(row[0])
            error = metrics.get("error", {})
            if isinstance(error, dict):
                return error.get("error", str(error))
            return str(error)
    except Exception:
        pass
    return None


@data_exporter
def export_data(data, **kwargs) -> None:
    try:
        pipeline_run = trigger_pipeline(
            "verify_etl_output",
            check_status=True,
            error_on_failure=False,
            poll_interval=30,
            verbose=True,
        )
        if pipeline_run and pipeline_run.status == "failed":
            msg = _get_block_error(pipeline_run.id) or "unknown error"
            raise RuntimeError(f"verify_etl_output failed: {msg}")
        record_status('verify_etl_output', 'success')
    except Exception as e:
        record_status('verify_etl_output', f'failed: {e}')
        raise
