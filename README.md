# RIOT RADAR
### S&OP Autonomous Control Tower for Pulp Riot Juice Co.

**[Open Live Dashboard](https://mc-kinseyx-riot-pulp-uvzu.vercel.app/control-tower)**

RIOT RADAR is a supply chain decision engine for demand sensing, stockout triage, and inventory rebalancing. It combines deterministic decision logic with LangGraph multi-agent orchestration to support Sales and Operations Planning (S&OP).

## Core Capabilities

- **Demand Sensing:** Identify changes in demand and supply-demand imbalances.
- **Stockout Triage:** Identify inventory risks and prioritize interventions.
- **Inventory Rebalancing:** Generate feasible inventory reallocation proposals.
- **Control Tower:** Monitor operational KPIs and supply chain risks.
- **Agent Orchestration:** Coordinate decision workflows using LangGraph.

## Architecture

| Component | Technology |
|---|---|
| Frontend | React 18, Vite, ECharts, Lucide |
| Backend | FastAPI, Pydantic v2 |
| Orchestration | LangGraph |
| Decision Engine | Deterministic supply chain logic |
| Persistence | CSV storage, Vercel Blob |

## Local Setup

**Requirements:** Python 3.10+ and Node.js 18+.

### Install dependencies

```bash
python -m pip install -r requirements.txt

cd frontend
npm install
npm run build
cd ..
```

### Configure environment

Create a `.env` file in the project root.

```env
GROQ_API_KEY=your_groq_api_key
BLOB_READ_WRITE_TOKEN=your_vercel_blob_token
```

The Groq API key enables LLM-powered agent functionality. Without it, the application can fall back to the deterministic decision engine. The Blob token enables cloud persistence.

### Start the application

```bash
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Data Persistence

Vercel Blob provides private cloud storage for datasets and uploads.

- The original sample dataset is preserved in `baseline/`.
- Valid daily uploads create versioned datasets.
- The local cache synchronizes with cloud storage during startup.

Deployment details: [`docs/vercel_blob_deployment.md`](docs/vercel_blob_deployment.md).

## Tests

Run the automated test suite:

```bash
python -m pytest tests/
```

## Project

RIOT RADAR — Supply Chain Decision Intelligence for Pulp Riot Juice Co.

**[Launch the Control Tower](https://mc-kinseyx-riot-pulp-uvzu.vercel.app/control-tower)**
