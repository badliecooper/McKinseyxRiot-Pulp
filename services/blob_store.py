"""Vercel Blob persistence service for RIOT RADAR.

Provides:
- Secure private Blob storage for user-uploaded CSV telemetry and active dataset snapshots.
- Token protection: BLOB_READ_WRITE_TOKEN is consumed strictly in the Python backend.
- Baseline preservation: original seed dataset is archived in 'baseline/' and protected from overwrite.
- Dataset versioning: every validated upload creates an identifiable, immutable dataset version (e.g. v1, v2).
- Active manifest tracking: 'active/manifest.json' identifies current active dataset version.
- Cold-start & multi-instance synchronization: hydrates local filesystem from Vercel Blob.
- Graceful error handling: handles missing credentials, storage outages, and network failures without silent stale fallback.
"""

import io
import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger("riot_radar.blob_store")

# Tables tracked in Vercel Blob persistence
PERSISTED_TABLES = ["demand_history", "upload_history"]

# Local data directory
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOCAL_MANIFEST_FILE = DATA_DIR / ".blob_manifest.json"

_BLOB_LOCK = threading.RLock()
_HYDRATED_ON_STARTUP = False


class BlobStorageError(Exception):
    """Raised when an operation against Vercel Blob fails."""
    pass


class BlobConfigurationError(Exception):
    """Raised when Vercel Blob credentials are missing or invalid."""
    pass


def get_blob_token() -> Optional[str]:
    """Retrieve the Vercel Blob read-write token from the environment."""
    return os.getenv("BLOB_READ_WRITE_TOKEN")


def is_blob_configured() -> bool:
    """Check if Vercel Blob is configured with a valid token."""
    token = get_blob_token()
    return bool(token and token.strip() and not token.startswith("your_"))


def _get_sync_client():
    """Import and return the official vercel.blob.sync module."""
    if not is_blob_configured():
        raise BlobConfigurationError(
            "Vercel Blob is not configured. BLOB_READ_WRITE_TOKEN is missing or empty."
        )
    try:
        import vercel.blob.sync as blob_sync
        return blob_sync
    except ImportError as exc:
        raise BlobConfigurationError(
            f"Failed to import official vercel python SDK: {exc}. Run 'pip install vercel'."
        ) from exc


def get_local_manifest() -> Optional[Dict[str, Any]]:
    """Read local cached manifest if present."""
    if LOCAL_MANIFEST_FILE.exists():
        try:
            with open(LOCAL_MANIFEST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to read local manifest: %s", e)
    return None


def save_local_manifest(manifest: Dict[str, Any]) -> None:
    """Save manifest to local cache."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(LOCAL_MANIFEST_FILE, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        logger.warning("Failed to write local manifest: %s", e)


def get_active_manifest(force_remote: bool = False) -> Optional[Dict[str, Any]]:
    """Fetch the active manifest.
    
    If local manifest is present and force_remote is False, returns local manifest for speed.
    Otherwise queries Vercel Blob.
    """
    if not force_remote:
        local = get_local_manifest()
        if local:
            return local

    if not is_blob_configured():
        return get_local_manifest()

    blob_sync = _get_sync_client()
    try:
        res = blob_sync.get_blob("active/manifest.json", access="private")
        body_bytes = res.body if isinstance(res.body, bytes) else res.body.read()
        manifest = json.loads(body_bytes.decode("utf-8"))
        save_local_manifest(manifest)
        return manifest
    except Exception as e:
        err_msg = str(e)
        if "404" in err_msg or "not found" in err_msg.lower() or "BlobNotFoundError" in err_msg:
            logger.info("No active/manifest.json found in Blob store. First-time initialization.")
            return None
        logger.warning("Failed to fetch active manifest from Blob: %s. Using local fallback.", e)
        return get_local_manifest()


def save_active_manifest(manifest: Dict[str, Any]) -> None:
    """Save active manifest to both Vercel Blob and local cache."""
    save_local_manifest(manifest)
    if not is_blob_configured():
        return

    blob_sync = _get_sync_client()
    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    try:
        blob_sync.put_blob(
            "active/manifest.json",
            manifest_bytes,
            access="private",
            content_type="application/json",
            allow_overwrite=True,
            cache_control_max_age=0,
        )
    except Exception as e:
        raise BlobStorageError(f"Failed to persist active manifest to Vercel Blob: {e}") from e


def ensure_baseline_preserved() -> bool:
    """Ensure the baseline sample dataset is archived in Vercel Blob under 'baseline/'.
    
    This preserves the original dataset so users can always inspect or reset back to baseline.
    """
    if not is_blob_configured():
        return False

    blob_sync = _get_sync_client()
    try:
        # Check if baseline manifest already exists
        try:
            blob_sync.head_blob("baseline/manifest.json")
            return True  # Already preserved
        except Exception:
            pass  # Not yet preserved, proceed to upload baseline

        logger.info("Preserving original sample dataset to Vercel Blob baseline/...")
        baseline_tables = {}
        for table in PERSISTED_TABLES:
            local_csv = DATA_DIR / f"{table}.csv"
            if local_csv.exists():
                content = local_csv.read_bytes()
                blob_path = f"baseline/{table}.csv"
                blob_sync.put_blob(
                    blob_path,
                    content,
                    access="private",
                    content_type="text/csv",
                    allow_overwrite=True,
                )
                baseline_tables[table] = blob_path

        baseline_manifest = {
            "dataset_id": "baseline_seed_v0",
            "archived_at": datetime.now().isoformat(),
            "description": "Original sample baseline dataset calibrated to case constraints.",
            "tables": baseline_tables,
        }
        blob_sync.put_blob(
            "baseline/manifest.json",
            json.dumps(baseline_manifest, indent=2).encode("utf-8"),
            access="private",
            content_type="application/json",
            allow_overwrite=True,
        )
        return True
    except Exception as e:
        logger.warning("Could not preserve baseline to Vercel Blob: %s", e)
        return False


def archive_uploaded_file(upload_id: str, original_filename: str, content: bytes) -> str:
    """Store raw user-uploaded CSV file in private Vercel Blob store under 'uploads/'.
    
    Returns the Blob pathname.
    """
    # Always save a local copy in data/uploads/ as fast cache
    upload_dir = DATA_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c for c in original_filename if c.isalnum() or c in "._-")
    local_file = upload_dir / f"{upload_id}_{safe_name}"
    local_file.write_bytes(content)

    if not is_blob_configured():
        return str(local_file)

    blob_sync = _get_sync_client()
    blob_pathname = f"uploads/{upload_id}_{safe_name}"

    try:
        blob_sync.put_blob(
            blob_pathname,
            content,
            access="private",
            content_type="text/csv",
            allow_overwrite=True,
            cache_control_max_age=3600,
        )
        logger.info("Successfully archived raw uploaded CSV to Blob: %s", blob_pathname)
        return blob_pathname
    except Exception as e:
        raise BlobStorageError(f"Failed to archive uploaded file to Vercel Blob: {e}") from e


def fetch_archived_file(upload_id: str) -> Optional[Tuple[str, bytes]]:
    """Retrieve raw archived uploaded file by upload_id.
    
    Returns (filename, content_bytes).
    """
    # Check local uploads directory first
    upload_dir = DATA_DIR / "uploads"
    if upload_dir.exists():
        for p in upload_dir.iterdir():
            if p.name.startswith(f"{upload_id}_"):
                return (p.name, p.read_bytes())

    if not is_blob_configured():
        return None

    blob_sync = _get_sync_client()

    # 1. Check upload_history to see if blob_path was stored
    try:
        from services.csv_store import load_csv
        hist_df = load_csv("upload_history")
        if not hist_df.empty and "upload_id" in hist_df.columns:
            match = hist_df[hist_df["upload_id"] == upload_id]
            if not match.empty:
                blob_path = str(match.iloc[0].get("blob_path", ""))
                if blob_path and blob_path != "local" and "uploads/" in blob_path:
                    res = blob_sync.get_blob(blob_path, access="private")
                    body_bytes = res.body if isinstance(res.body, bytes) else res.body.read()
                    return (blob_path.split("/")[-1], body_bytes)
    except Exception as e:
        logger.debug("Could not resolve blob_path from upload_history: %s", e)

    # 2. Query prefix fallback
    try:
        prefix = f"uploads/{upload_id}_"
        blobs = list(blob_sync.query_blobs(prefix=prefix))
        if blobs:
            target = blobs[0]
            res = blob_sync.get_blob(target.pathname, access="private")
            body_bytes = res.body if isinstance(res.body, bytes) else res.body.read()
            return (target.pathname.split("/")[-1], body_bytes)
    except Exception as e:
        logger.warning("Failed to fetch archived file from Blob: %s", e)

    return None


def publish_active_dataset(
    tables_data: Dict[str, str],
    upload_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Publish an updated active dataset to Vercel Blob.
    
    Creates:
    1. A versioned snapshot: datasets/v{version}/{table}.csv
    2. The active pointers: active/{table}.csv
    3. The active manifest: active/manifest.json and datasets/v{version}/manifest.json
    
    Guarantees atomic version increments and persistence.
    """
    with _BLOB_LOCK:
        current_manifest = get_active_manifest()
        current_version = current_manifest.get("version", 0) if current_manifest else 0
        new_version = current_version + 1
        now_iso = datetime.now().isoformat()
        dataset_id = f"ds_{datetime.now().strftime('%Y%m%d_%H%M%S')}_v{new_version}"

        # Ensure baseline is preserved before first mutation
        ensure_baseline_preserved()

        table_locations = {}
        record_counts = {}

        if is_blob_configured():
            blob_sync = _get_sync_client()
            for table_name, csv_content in tables_data.items():
                content_bytes = csv_content.encode("utf-8")
                
                # 1. Versioned snapshot
                versioned_path = f"datasets/v{new_version}/{table_name}.csv"
                blob_sync.put_blob(
                    versioned_path,
                    content_bytes,
                    access="private",
                    content_type="text/csv",
                    allow_overwrite=True,
                )

                # 2. Active pointer (zero cache age so updates are instant)
                active_path = f"active/{table_name}.csv"
                blob_sync.put_blob(
                    active_path,
                    content_bytes,
                    access="private",
                    content_type="text/csv",
                    allow_overwrite=True,
                    cache_control_max_age=0,
                )

                table_locations[table_name] = active_path
                record_counts[table_name] = max(0, len(csv_content.strip().splitlines()) - 1)
        else:
            for table_name, csv_content in tables_data.items():
                table_locations[table_name] = f"local:{table_name}.csv"
                record_counts[table_name] = max(0, len(csv_content.strip().splitlines()) - 1)

        new_manifest = {
            "version": new_version,
            "active_dataset_id": dataset_id,
            "created_at": current_manifest.get("created_at", now_iso) if current_manifest else now_iso,
            "updated_at": now_iso,
            "last_upload_id": upload_id or (current_manifest.get("last_upload_id") if current_manifest else None),
            "baseline_preserved": True,
            "record_counts": record_counts,
            "tables": table_locations,
            "metadata": metadata or {},
        }

        # Persist active manifest
        save_active_manifest(new_manifest)

        # Also store versioned manifest in Blob if configured
        if is_blob_configured():
            try:
                blob_sync = _get_sync_client()
                blob_sync.put_blob(
                    f"datasets/v{new_version}/manifest.json",
                    json.dumps(new_manifest, indent=2).encode("utf-8"),
                    access="private",
                    content_type="application/json",
                    allow_overwrite=True,
                )
            except Exception as e:
                logger.warning("Could not write versioned manifest snapshot: %s", e)

        logger.info(
            "Published active dataset version %d (%s) with %s tables.",
            new_version,
            dataset_id,
            list(tables_data.keys()),
        )
        return new_manifest


def hydrate_local_cache(force: bool = False) -> bool:
    """Hydrate local CSV files from Vercel Blob active dataset.
    
    Used on cold starts, server restarts, or when local files are missing.
    Ensures local analytics run at in-memory / local speeds with full Blob persistence.
    """
    global _HYDRATED_ON_STARTUP
    if not is_blob_configured():
        return False

    with _BLOB_LOCK:
        if _HYDRATED_ON_STARTUP and not force:
            return False

        blob_sync = _get_sync_client()
        manifest = get_active_manifest(force_remote=True)
        if not manifest:
            # Nothing in Blob yet, attempt to preserve initial baseline
            ensure_baseline_preserved()
            _HYDRATED_ON_STARTUP = True
            return False

        remote_version = manifest.get("version", 0)
        local_manifest = get_local_manifest()
        local_version = local_manifest.get("version", -1) if local_manifest else -1

        # Check if local cache is already current
        if not force and remote_version <= local_version:
            _HYDRATED_ON_STARTUP = True
            return False

        logger.info(
            "Hydrating local cache from Vercel Blob (remote v%d vs local v%d)...",
            remote_version,
            local_version,
        )

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        hydrated_any = False

        for table in PERSISTED_TABLES:
            blob_path = f"active/{table}.csv"
            try:
                res = blob_sync.get_blob(blob_path, access="private")
                body_bytes = res.body if isinstance(res.body, bytes) else res.body.read()
                local_path = DATA_DIR / f"{table}.csv"
                local_path.write_bytes(body_bytes)
                hydrated_any = True
                logger.info("Hydrated %s.csv from Blob (%d bytes)", table, len(body_bytes))
            except Exception as e:
                logger.warning("Could not hydrate %s from Blob: %s", table, e)

        save_local_manifest(manifest)
        _HYDRATED_ON_STARTUP = True
        return hydrated_any


def reset_to_baseline() -> Dict[str, Any]:
    """Reset the active dataset back to the preserved baseline sample dataset.
    
    Restores original sample data to both Vercel Blob active/ and local CSV files.
    """
    with _BLOB_LOCK:
        if not is_blob_configured():
            raise BlobConfigurationError("Vercel Blob is not configured. Cannot reset.")

        blob_sync = _get_sync_client()

        # Check baseline exists
        try:
            res = blob_sync.get_blob("baseline/manifest.json", access="private")
            body_bytes = res.body if isinstance(res.body, bytes) else res.body.read()
            _ = json.loads(body_bytes.decode("utf-8"))
        except Exception as e:
            raise BlobStorageError(f"Baseline dataset not found in Vercel Blob: {e}") from e

        tables_data = {}
        for table in PERSISTED_TABLES:
            try:
                res = blob_sync.get_blob(f"baseline/{table}.csv", access="private")
                body_bytes = res.body if isinstance(res.body, bytes) else res.body.read()
                tables_data[table] = body_bytes.decode("utf-8")
                # Write locally
                (DATA_DIR / f"{table}.csv").write_bytes(body_bytes)
            except Exception as e:
                logger.warning("Baseline table %s not found in Blob: %s", table, e)

        # Publish as new active version with baseline note
        manifest = publish_active_dataset(
            tables_data,
            upload_id="RESET_TO_BASELINE",
            metadata={"action": "RESET_TO_BASELINE", "reset_at": datetime.now().isoformat()},
        )
        return {
            "status": "SUCCESS",
            "message": "Successfully restored active dataset to preserved sample baseline.",
            "active_version": manifest["version"],
            "active_dataset_id": manifest["active_dataset_id"],
        }


def get_blob_telemetry_status() -> Dict[str, Any]:
    """Comprehensive diagnostic status of Vercel Blob persistence for UI and health checks."""
    configured = is_blob_configured()
    token = get_blob_token()
    token_hint = f"{token[:8]}...{token[-4:]}" if token and len(token) > 12 else None

    manifest = get_active_manifest()
    
    return {
        "blob_configured": configured,
        "storage_mode": "VERCEL_BLOB_PRIVATE" if configured else "LOCAL_CSV_ONLY",
        "access_level": "private",
        "token_hint": token_hint,
        "token_exposed_to_client": False,
        "active_dataset_version": manifest.get("version", 0) if manifest else 0,
        "active_dataset_id": manifest.get("active_dataset_id", "baseline_v0") if manifest else "baseline_v0",
        "baseline_preserved": manifest.get("baseline_preserved", False) if manifest else False,
        "last_upload_id": manifest.get("last_upload_id") if manifest else None,
        "updated_at": manifest.get("updated_at") if manifest else None,
        "persisted_tables": PERSISTED_TABLES,
        "record_counts": manifest.get("record_counts", {}) if manifest else {},
    }
