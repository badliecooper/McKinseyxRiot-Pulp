# Vercel Blob Persistence Deployment & Data Pipeline Guide

## Overview

RIOT RADAR persists daily sales CSV uploads and demand telemetry using **Vercel Blob** with **private access**.
This architecture preserves the deterministic CSV-only design while providing serverless persistence across ephemeral container restarts, cold starts, and multi-instance Vercel deployments.

---

## 1. Environment Variables & Security

The system requires one environment variable in both local `.env` and Vercel project settings:

```bash
BLOB_READ_WRITE_TOKEN="vercel_blob_rw_..."
```

### Critical Security Rule
- **Zero Client Exposure**: The token is consumed **exclusively** on the Python backend (`services/blob_store.py`).
- **Never Injected into React**: The React/Vite frontend never receives, stores, or handles the read-write token.
- **Private Access Enforcement**: All objects uploaded to Vercel Blob explicitly use `access="private"`. Raw file downloads and previews are served exclusively through an authenticated FastAPI backend proxy (`GET /api/upload/raw-file/{upload_id}`).

---

## 2. Storage Directory Layout in Vercel Blob

```
blob-store/
├── baseline/                                # Preserved original sample dataset
│   ├── manifest.json                        # Baseline metadata and schema
│   ├── demand_history.csv                   # Pristine seed demand telemetry
│   └── upload_history.csv                   # Pristine upload history
│
├── uploads/                                 # Immutable raw uploaded files archive
│   ├── UPL-10251450-045_sales_feed.csv     # Raw file as uploaded by user
│   └── UPL-10251630-315_partner_qc.csv     # Raw partner feed
│
├── datasets/                                # Versioned snapshot history
│   ├── v1/
│   │   ├── manifest.json                    # Snapshot metadata & row counts
│   │   ├── demand_history.csv               # Dataset v1 demand table
│   │   └── upload_history.csv
│   └── v2/
│       ├── manifest.json
│       ├── demand_history.csv
│       └── upload_history.csv
│
└── active/                                  # Current active dataset pointers (cache-control: 0)
    ├── manifest.json                        # Single source of truth for active version
    ├── demand_history.csv                   # Active demand table used by calculations
    └── upload_history.csv                   # Active upload ledger
```

---

## 3. Data Pipeline & Ingestion Workflow

1. **Upload & Validation (`POST /api/upload/sales`)**:
   - The user submits a daily sales CSV via the Control Tower Ingestion modal.
   - The backend validates date formatting (`YYYY-MM-DD`), SKU validity against the 5 canonical flavours, depot codes across the 9 regional nodes, channel types (`QC`, `MT`, `GT`), and non-negative sales values.
   - Invalid files are rejected immediately with HTTP 400 and clear error logs without touching Blob storage.

2. **Private Raw Archival**:
   - Valid uploads are archived to `uploads/{upload_id}_{filename}` with `access="private"`.

3. **Active Snapshot Publication**:
   - Valid rows are appended to `demand_history.csv`.
   - A new dataset version is created (`v{N+1}`) and saved to `datasets/v{N+1}/`.
   - The active pointers `active/demand_history.csv` and `active/manifest.json` are atomically updated.

4. **Telemetry & Dashboard Sync**:
   - The system triggers real-time alarm re-evaluation (`tools._risk_svc.evaluate_and_sync_alarms()`).
   - Sensed demand, bias calculations, and days-of-cover run-rates automatically re-anchor to the latest telemetry date.

5. **Cold-Start Hydration**:
   - When a fresh lambda container spins up, `hydrate_local_cache()` queries `active/manifest.json`.
   - If the local cache is cold or older than the active Blob manifest, it downloads the active dataset tables into the container's local cache.

---

## 4. API Endpoints for Data Governance

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/upload/status` | `GET` | Returns upload status, active dataset version, and Vercel Blob persistence telemetry. |
| `/api/upload/sales` | `POST` | Validates, archives, and ingests daily sales CSV into active Vercel Blob store. |
| `/api/upload/datasets` | `GET` | Inspects active manifest, version number, record counts, and cloud storage status. |
| `/api/upload/reset-baseline` | `POST` | Restores active dataset back to preserved original sample baseline. |
| `/api/upload/raw-file/{upload_id}` | `GET` | Securely downloads archived raw CSV upload via backend proxy. |

---

## 5. Verification & Testing

Run the automated test suite to verify the complete end-to-end flow:

```bash
# Run Vercel Blob persistence integration test suite
python -m pytest tests/test_vercel_blob_persistence.py -v

# Run full project regression suite
python -m pytest tests/
```

All 65 tests in the test suite pass, covering:
- Credential validation and zero token leak in API responses.
- Invalid CSV rejection prior to cloud mutation.
- Private Blob archival and proxy retrieval.
- Dataset version increments and manifest tracking.
- Cold-start hydration across simulated container recycling.
- Live dashboard telemetry updates reflecting uploaded data.
- Baseline dataset preservation and reset functionality.
