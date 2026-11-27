# CrowdWise Delhi — Crowdedness-Aware Bus Journey Planner
**Transport Stack Hackathon 2026 · Problem 2 / Phase 1**
**Live Demo:** https://crowdwise-web-production.up.railway.app

CrowdWise Delhi estimates segment-level bus crowding across Delhi from October 2026 e-ticketing/ETM records (`2,559,899` tickets) and static GTFS (`2,574` routes, `6,862` stops), and surfaces crowding alongside travel time in a commuter journey planner and operator bottleneck dashboard.

## Architecture
- **Offline Pipeline & ML (`notebooks/crowdwise_colab.ipynb`)**:
  - Route & route-scoped stop canonicalization (`98.8%` route match, `85.75%` ordered itinerary match).
  - Two-tier trip reconstruction: Tier-1 vehicle runs (`51.48%` with `vehicle_number`) + Tier-2 route-time window allocation (`48.52%` null).
  - `passenger_count` accumulation with `0.15 / 0.70 / 0.15` soft alighting, `is_ac`-aware unobserved rider expansion, `9m` (22 seats) vs `12m` (38 seats) capacity normalization, LightGBM quantile imputation for sparse cells, and holiday-aware stratification (`Oct 2`, `Oct 20`).
  - Exports `crowdwise.sqlite`, `raptor_index.pkl`, and `validation_report.json` to `data/processed/`.
- **Backend (`backend/app/main.py`, `backend/planner/raptor.py`)**: FastAPI + RAPTOR bus router with crowding-aware Pareto scoring (`Fastest`, `Balanced`, `Most Comfortable`, and `+20 min` leave-later advisor).
- **Frontend (`frontend/`)**: Vite + React + TypeScript UI with **Commuter Planner** and **Operator & Planner** (`+1 / +2 Extra Bus` simulator) views.
- **Technical Note**: See [docs/TECHNICAL_NOTE.md](docs/TECHNICAL_NOTE.md) and [docs/DATA_INSPECTION.md](docs/DATA_INSPECTION.md).

## Quickstart (Local)
```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
PYTHONPATH=. .venv/bin/pytest -q backend/tests/test_contracts.py
cd frontend && npm install && npm run build && cd ..
.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
Open `http://localhost:8000`.
