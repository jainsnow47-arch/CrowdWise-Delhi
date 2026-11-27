"""
FastAPI backend for CrowdWise Delhi.
Serves /api/* endpoints and (when built) static React frontend from frontend/dist.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.planner.raptor import CrowdWisePlanner

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "processed"
DB_PATH = DATA_DIR / "crowdwise.sqlite"
RAPTOR_PATH = DATA_DIR / "raptor_index.pkl"
VAL_PATH = DATA_DIR / "validation_report.json"
FRONTEND_DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="CrowdWise Delhi API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

planner = CrowdWisePlanner(DB_PATH, RAPTOR_PATH)


class PlanRequest(BaseModel):
    origin_hub: str
    dest_hub: str
    day_type: str = "weekday"
    depart_min: int = 1080  # 18:00
    preference: str = "balanced"


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "db_ready": DB_PATH.exists(),
        "raptor_ready": RAPTOR_PATH.exists(),
        "routes_indexed": len(planner.route_stops),
        "stops_indexed": len(planner.stop_names),
    }


@app.get("/api/stops/search")
def search_stops(q: str = Query(..., min_length=2)):
    if not DB_PATH.exists():
        return {"stops": []}
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        q_low = q.lower()
        rows = conn.execute(
            """
            SELECT hub_name, GROUP_CONCAT(stop_id) AS stop_ids, AVG(lat) AS lat, AVG(lon) AS lon
            FROM stops
            WHERE LOWER(hub_name) LIKE ?
            GROUP BY hub_name
            ORDER BY
                CASE
                    WHEN LOWER(hub_name) = ? THEN 0
                    WHEN LOWER(hub_name) LIKE ? THEN 1
                    ELSE 2
                END,
                LENGTH(hub_name),
                hub_name
            LIMIT 15
            """,
            (f"%{q_low}%", q_low, f"{q_low}%"),
        ).fetchall()
    return {
        "stops": [
            {
                "hub_name": r["hub_name"],
                "stop_ids": r["stop_ids"].split(",") if r["stop_ids"] else [],
                "lat": r["lat"],
                "lon": r["lon"],
            }
            for r in rows
        ]
    }


@app.post("/api/journeys/plan")
def plan_journey(req: PlanRequest):
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="Processed database not ready.")
    with sqlite3.connect(DB_PATH) as conn:
        o_rows = conn.execute("SELECT stop_id FROM stops WHERE hub_name = ?", (req.origin_hub,)).fetchall()
        d_rows = conn.execute("SELECT stop_id FROM stops WHERE hub_name = ?", (req.dest_hub,)).fetchall()
    o_ids = [r[0] for r in o_rows]
    d_ids = [r[0] for r in d_rows]
    if not o_ids or not d_ids:
        raise HTTPException(status_code=404, detail="Origin or destination stop hub not found.")
    return planner.plan(o_ids, d_ids, req.day_type, req.depart_min, req.preference)


@app.get("/api/routes/{route_id}/profile")
def route_profile(route_id: str, day_type: str = "weekday", time_bin: int = 18):
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="Database not ready.")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT sc.*, s1.stop_name AS from_name, s1.lat AS from_lat, s1.lon AS from_lon,
                   s2.stop_name AS to_name, s2.lat AS to_lat, s2.lon AS to_lon
            FROM segment_crowding sc
            JOIN stops s1 ON sc.from_stop_id = s1.stop_id
            JOIN stops s2 ON sc.to_stop_id = s2.stop_id
            WHERE sc.route_id = ? AND sc.day_type = ? AND sc.time_bin = ?
            ORDER BY sc.seq_idx
            """,
            (route_id, day_type, time_bin),
        ).fetchall()
    return {"route_id": route_id, "day_type": day_type, "time_bin": time_bin, "stretches": [dict(r) for r in rows]}


@app.get("/api/analytics/overloaded")
def analytics_overloaded(day_type: str = "weekday", time_bin: int = 18, limit: int = 25):
    if not DB_PATH.exists():
        return {"bottlenecks": [], "validation": {}}
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT sc.route_id, r.route_short_name, r.bus_class, r.seated_cap,
                   MAX(sc.load_factor) AS max_load_factor,
                   AVG(sc.load_factor) AS avg_load_factor,
                   MAX(sc.est_total_load) AS peak_est_load,
                   COUNT(*) AS stretches,
                   MIN(sc.confidence) AS confidence
            FROM segment_crowding sc
            JOIN routes r ON sc.route_id = r.route_id
            WHERE sc.day_type = ? AND sc.time_bin = ?
            GROUP BY sc.route_id
            ORDER BY max_load_factor DESC
            LIMIT ?
            """,
            (day_type, time_bin, limit),
        ).fetchall()
    val = json.loads(VAL_PATH.read_text()) if VAL_PATH.exists() else {}
    return {"bottlenecks": [dict(r) for r in rows], "validation": val}


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


def crowding_tier(ratio: float) -> str:
    if ratio <= 0.85:
        return "seats_available"
    elif ratio <= 1.35:
        return "standing_room"
    else:
        return "crowded"


def sum_passenger_counts(counts: list[int]) -> int:
    return sum(counts)


def alighting_distribution() -> list[float]:
    return [0.15, 0.70, 0.15]

