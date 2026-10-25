"""RIOT RADAR — FastAPI Backend Server Entry Point.

Starts the Uvicorn server hosting the RIOT RADAR REST API for the React + TypeScript frontend.
"""

import sys
import uvicorn
from services.data_gen import generate_all_seed_data


def main():
    # Ensure seed data is present without regenerating unless missing
    generate_all_seed_data()

    print("[RIOT RADAR] Launching FastAPI backend server on http://127.0.0.1:8000...")
    print("[RIOT RADAR] React Frontend runs on http://localhost:5173 (via 'cd frontend && npm run dev')")
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
