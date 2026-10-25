"""Tests for CSV store service and safe persistence."""

import os
import pytest
import pandas as pd
from services.csv_store import (
    load_csv,
    save_csv,
    append_csv_row,
    update_csv_record,
    initialize_csv,
    SCHEMAS,
    get_data_path,
)


def test_csv_store_initialization():
    """Verify that all schemas can be initialized without errors."""
    for table_name in SCHEMAS.keys():
        path = initialize_csv(table_name)
        assert os.path.exists(path)
        df = load_csv(table_name)
        assert isinstance(df, pd.DataFrame)
        for col in SCHEMAS[table_name]:
            assert col in df.columns


def test_atomic_write_and_update():
    """Verify that append and update work atomically and accurately."""
    test_table = "stockout_reports"
    row = {
        "report_id": "REP-TEST-001",
        "reported_at": "2026-05-20 12:00:00",
        "depot_id": "Depot-West-01",
        "sku_id": "PR-DP",
        "channel": "QC",
        "reported_by": "Test Reporter",
        "evidence_source": "Unit Test",
        "estimated_unmet_bottles": 5000,
        "notes": "Test notes",
    }
    append_csv_row(test_table, row)
    df = load_csv(test_table)
    assert not df[df["report_id"] == "REP-TEST-001"].empty

    # Update
    updated = update_csv_record(test_table, "report_id", "REP-TEST-001", {"notes": "Updated notes"})
    assert updated is True
    df_updated = load_csv(test_table)
    assert df_updated[df_updated["report_id"] == "REP-TEST-001"].iloc[0]["notes"] == "Updated notes"


def test_empty_csv_safe_handling():
    """Verify that loading an empty or non-existent table safely returns an empty DataFrame with schema."""
    df = load_csv("workflow_state")
    assert isinstance(df, pd.DataFrame)
    assert "run_id" in df.columns
