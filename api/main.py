"""FastAPI Main Entry Point for RIOT RADAR.

Exposes REST API endpoints for:
- /api/health
- /api/control-tower/*
- /api/depots, /api/skus, /api/sku-depot/*
- /api/scenarios/*
- /api/alarms/*, /api/recommendations/*
- /api/copilot/*
- /api/reports/*
- Static SPA fallback serving built React control tower
"""

import datetime
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Load environment variables (.env)
load_dotenv()

from services.data_gen import generate_all_seed_data
from api.schemas import HealthResponse

from api.routes.control_tower import router as control_tower_router
from api.routes.depot_explorer import router as depot_explorer_router
from api.routes.scenarios import router as scenarios_router
from api.routes.alarms import router as alarms_router
from api.routes.copilot import router as copilot_router
from api.routes.reports import router as reports_router
from api.routes.upload import router as upload_router

# Ensure seed CSV files exist
generate_all_seed_data()

app = FastAPI(
    title="RIOT RADAR — S&OP Control Tower API",
    description="Deterministic Supply Chain Decision Engine & LangGraph Orchestration for Pulp Riot Juice Co.",
    version="1.0.0",
)

# Configure CORS for local React development server
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint
@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def get_health():
    """Health check endpoint confirming API status and operating mode."""
    groq_key = os.getenv("GROQ_API_KEY")
    mode = "LIVE_LLM_API" if groq_key else "DETERMINISTIC_FALLBACK_ENGINE"
    return {
        "status": "HEALTHY",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
        "version": "1.0.0",
        "database_mode": "CSV_ONLY_PERSISTENCE",
        "operating_mode": mode,
    }

# Include routers under /api
app.include_router(control_tower_router, prefix="/api")
app.include_router(depot_explorer_router, prefix="/api")
app.include_router(scenarios_router, prefix="/api")
app.include_router(alarms_router, prefix="/api")
app.include_router(copilot_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(upload_router, prefix="/api")

# Mount React static build if available so http://127.0.0.1:8000 renders the dashboard directly
DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST_DIR.exists() and (DIST_DIR / "index.html").exists():
    if (DIST_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        target = DIST_DIR / full_path
        if full_path and target.exists() and target.is_file():
            return FileResponse(target)
        return FileResponse(DIST_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
