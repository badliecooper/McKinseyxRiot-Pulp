# RIOT RADAR — S&OP Autonomous Control Tower

Deterministic Supply Chain Decision Engine & LangGraph Multi-Agent Orchestration for Pulp Riot Juice Co.

---

## Architecture Overview

- **Frontend**: React 18, Vite, ECharts, Lucide Icons, Institutional Cohere/Linear Anti-Slop Design System.
- **Backend API**: FastAPI (REST endpoints under `/api`), Pydantic v2 strict schemas.
- **Agent Orchestration**: LangGraph stategraph pipeline for autonomous demand sensing, stockout triage, and feasible rebalancing proposals.
- **Persistence Layer**: Deterministic CSV Store backed by **private Vercel Blob cloud persistence** for serverless multi-instance synchronization.

---

## Quick Start

### 1. Requirements & Dependencies
Ensure Python 3.10+ and Node.js 18+ are installed.

```bash
# Install backend dependencies (including official vercel Python SDK)
python -m pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
npm run build
cd ..
```

### 2. Environment Variables (.env)
Create or configure `.env` in the root directory:

```bash
# Required for live LLM agent (falls back to deterministic SCM engine if omitted)
GROQ_API_KEY="gsk_..."

# Required for Vercel Blob cloud persistence
BLOB_READ_WRITE_TOKEN="vercel_blob_rw_..."
```

### 3. Running the Server

```bash
# Launch FastAPI backend with built React UI on http://127.0.0.1:8000
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## Vercel Blob Persistence

Full deployment and persistence architecture documentation is available in [docs/vercel_blob_deployment.md](docs/vercel_blob_deployment.md).

- **Private Storage**: All uploads and datasets are stored with `access="private"`.
- **Baseline Preservation**: Pristine sample dataset is preserved in `baseline/`.
- **Dataset Versioning**: Every valid daily upload creates an identifiable version (`v1`, `v2`, ...).
- **Cold-Start Hydration**: Automatically synchronizes local cache from Vercel Blob on startup.

---

## Test Suite

Run the full automated test suite (65 tests):

```bash
python -m pytest tests/
```
https://mc-kinseyx-riot-pulp-uvzu.vercel.app/control-tower - interactive hosted dashboard
