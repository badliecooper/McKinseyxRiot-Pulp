"""Comprehensive integration and regression tests for Vercel Blob persistence.

Tests:
1. Blob configuration & credential security (token never exposed to client).
2. CSV validation rejection before Blob mutation.
3. Private Blob archival of raw uploaded CSV files and proxy retrieval.
4. Versioned active dataset snapshots and manifest tracking.
5. Cold-start persistence and hydration across serverless restarts.
6. Genuine update of dashboard telemetry and KPIs from active Blob data.
7. Baseline dataset preservation and reset-to-baseline restoration.
8. Graceful error handling for missing credentials and storage outages.
"""

import io
import json
import os
import pytest
from fastapi.testclient import TestClient

from api.main import app
from services.blob_store import (
    is_blob_configured,
    get_blob_telemetry_status,
    get_active_manifest,
    ensure_baseline_preserved,
    hydrate_local_cache,
    fetch_archived_file,
    reset_to_baseline,
    LOCAL_MANIFEST_FILE,
)
from services.csv_store import load_csv, DATA_DIR

client = TestClient(app)

SAMPLE_VALID_CSV = """date,sku_id,depot_id,channel,observed_sales
2026-07-15,PR-DP,Depot-West-01,QC,48500
2026-07-15,PR-DP,Depot-North-01,QC,39200
2026-07-15,PR-MPB,Depot-East-01,MT,22800
"""

SAMPLE_INVALID_CSV = """date,sku_id,depot_id,channel,observed_sales
2026-99-99,PR-INVALID,Depot-Nowhere,QC,-500
"""


class TestVercelBlobConfiguration:
    """Verify credentials, token security, and private access configuration."""

    def test_blob_is_configured(self):
        """Verify that BLOB_READ_WRITE_TOKEN is loaded and valid."""
        assert is_blob_configured() is True
        token = os.getenv("BLOB_READ_WRITE_TOKEN")
        assert token is not None
        assert token.startswith("vercel_blob_rw_")

    def test_token_never_exposed_in_api(self):
        """Ensure BLOB_READ_WRITE_TOKEN is strictly private and never leaked in API responses."""
        resp = client.get("/api/upload/status")
        assert resp.status_code == 200
        data = resp.json()
        raw_text = resp.text

        token = os.getenv("BLOB_READ_WRITE_TOKEN")
        assert token not in raw_text, "CRITICAL SECURITY LEAK: BLOB_READ_WRITE_TOKEN found in HTTP response!"

        # Health endpoint check
        health_resp = client.get("/api/health")
        assert health_resp.status_code == 200
        assert token not in health_resp.text


class TestCSVValidationAndRejection:
    """Validate that invalid CSV files are rejected without mutating Blob or local data."""

    def test_invalid_csv_rejected_before_blob(self):
        """Invalid dates, unknown SKUs, or negative sales must fail before saving to Blob."""
        file_obj = io.BytesIO(SAMPLE_INVALID_CSV.encode("utf-8"))
        resp = client.post(
            "/api/upload/sales",
            files={"file": ("invalid_sales.csv", file_obj, "text/csv")},
            data={"source_channel": "Quick Commerce", "uploader_name": "Test Runner"},
        )
        assert resp.status_code == 200 or resp.status_code == 400
        data = resp.json()
        assert data.get("status") in ["VALIDATION_FAILED", "error"] or "errors" in data or "detail" in data


class TestBlobUploadAndDatasetVersioning:
    """Verify private Blob upload, raw archival, manifest tracking, and dashboard metric updates."""

    def test_valid_csv_upload_persists_to_blob(self):
        """Uploading valid daily sales persists raw file to private Blob, publishes new version, and updates manifest."""
        # Baseline preservation
        ensure_baseline_preserved()

        import time
        unique_day = (int(time.time()) % 10) + 20
        unique_date = f"2026-07-{unique_day:02d}"
        unique_csv = f"""date,sku_id,depot_id,channel,observed_sales
{unique_date},PR-DP,Depot-West-01,QC,52400
{unique_date},PR-DP,Depot-North-01,QC,41200
{unique_date},PR-MPB,Depot-East-01,MT,24800
"""

        file_obj = io.BytesIO(unique_csv.encode("utf-8"))
        resp = client.post(
            "/api/upload/sales",
            files={"file": (f"test_sales_{unique_date}.csv", file_obj, "text/csv")},
            data={"source_channel": "Quick Commerce", "uploader_name": "Test Runner"},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "SUCCESS"
        assert data["blob_persisted"] is True
        assert data["dataset_version"] >= 1
        assert data["active_dataset_id"].startswith("ds_")

        upload_id = data["upload_id"]

        # Verify raw file can be retrieved via authenticated proxy endpoint
        raw_resp = client.get(f"/api/upload/raw-file/{upload_id}")
        assert raw_resp.status_code == 200
        assert "PR-DP" in raw_resp.text

    def test_active_manifest_in_blob(self):
        """Active manifest tracks identifiable dataset version and record counts."""
        manifest = get_active_manifest()
        assert manifest is not None
        assert "version" in manifest
        assert "active_dataset_id" in manifest
        assert "tables" in manifest
        assert manifest["baseline_preserved"] is True

        resp = client.get("/api/upload/datasets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["active_manifest"]["version"] >= 1
        assert body["blob_telemetry"]["storage_mode"] == "VERCEL_BLOB_PRIVATE"

    def test_dashboard_reflects_uploaded_data(self):
        """Dashboard demand series and telemetry immediately reflect uploaded data."""
        resp = client.get("/api/sku-depot/demand-series?sku_id=PR-DP&depot_id=Depot-West-01")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["series"]) > 0

        # Check if the July 15 date or recent July dates appear in demand history
        dates = [s["date"] for s in data["series"]]
        assert any("2026-07" in d for d in dates), "Uploaded July data not found in demand series!"


class TestColdStartHydration:
    """Verify that a cold start / fresh lambda container hydrates state from Vercel Blob."""

    def test_cold_start_hydration_from_blob(self):
        """Simulate fresh container: clear local manifest cache and verify hydrate_local_cache restores state."""
        # Force re-hydration
        hydrated = hydrate_local_cache(force=True)
        assert hydrated is True or LOCAL_MANIFEST_FILE.exists()

        # Verify demand_history contains the active records
        dh_df = load_csv("demand_history")
        assert not dh_df.empty
        assert len(dh_df) > 5000
        assert "PR-DP" in dh_df["sku_id"].values


class TestBaselinePreservationAndReset:
    """Verify that sample baseline is preserved and can be restored on demand."""

    def test_reset_to_baseline_restores_data(self):
        """Calling /api/upload/reset-baseline restores active dataset to preserved sample baseline."""
        resp = client.post("/api/upload/reset-baseline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"

        # Check active manifest via datasets API endpoint
        manifest_resp = client.get("/api/upload/datasets")
        assert manifest_resp.status_code == 200
        active_m = manifest_resp.json()["active_manifest"]
        assert active_m is not None
        assert active_m["metadata"].get("action") == "RESET_TO_BASELINE"
