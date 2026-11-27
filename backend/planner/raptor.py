"""
Lightweight, fast RAPTOR-style bus journey planner & crowding scorer.
Loads pre-indexed `raptor_index.pkl` and queries `crowdwise.sqlite` in <50ms.
"""
from __future__ import annotations
import math
import pickle
import sqlite3
from pathlib import Path
from typing import Any

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def classify_tier(load_factor: float) -> str:
    if load_factor <= 0.85:
        return "seats_available"
    if load_factor <= 1.35:
        return "standing_room"
    return "crowded"

class CrowdWisePlanner:
    def __init__(self, db_path: Path, raptor_path: Path):
        self.db_path = db_path
        self.raptor_path = raptor_path
        self.route_stops: dict[str, list[str]] = {}
        self.stop_routes: dict[str, list[tuple[str, int]]] = {}
        self.stop_coords: dict[str, tuple[float, float]] = {}
        self.stop_names: dict[str, str] = {}
        if raptor_path.exists():
            with open(raptor_path, "rb") as f:
                data = pickle.load(f)
            self.route_stops = data.get("route_stops", {})
            self.stop_coords = data.get("stop_coords", {})
            self.stop_names = data.get("stop_names", {})
            for rid, stops in self.route_stops.items():
                for idx, sid in enumerate(stops):
                    self.stop_routes.setdefault(sid, []).append((rid, idx))

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_leg_crowding(
        self, conn: sqlite3.Connection, route_id: str, s_idx: int, e_idx: int, day_type: str, time_bin: int
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT seq_idx, from_stop_id, to_stop_id, est_total_load, load_factor, crowding_tier, confidence
            FROM segment_crowding
            WHERE route_id = ? AND day_type = ? AND time_bin = ? AND seq_idx >= ? AND seq_idx < ?
            ORDER BY seq_idx
            """,
            (route_id, day_type, time_bin, s_idx, e_idx),
        ).fetchall()
        if not rows:
            # Fallback to default moderate estimate when artifacts are partial
            return [
                {
                    "seq_idx": k,
                    "from_stop": self.stop_names.get(self.route_stops[route_id][k], ""),
                    "to_stop": self.stop_names.get(self.route_stops[route_id][k + 1], ""),
                    "est_total_load": 18.0,
                    "load_factor": 0.55,
                    "crowding_tier": "seats_available",
                    "confidence": "low",
                }
                for k in range(s_idx, e_idx)
            ]
        return [
            {
                "seq_idx": r["seq_idx"],
                "from_stop": self.stop_names.get(r["from_stop_id"], r["from_stop_id"]),
                "to_stop": self.stop_names.get(r["to_stop_id"], r["to_stop_id"]),
                "est_total_load": r["est_total_load"],
                "load_factor": r["load_factor"],
                "crowding_tier": r["crowding_tier"],
                "confidence": r["confidence"],
            }
            for r in rows
        ]

    def plan(
        self, origin_stops: list[str], dest_stops: list[str], day_type: str, depart_min: int, preference: str = "balanced"
    ) -> dict[str, Any]:
        if not self.db_path.exists() or not self.route_stops:
            return {"options": [], "leave_later_tip": None, "note": "Processed artifacts not loaded yet."}

        time_bin = max(0, min(23, depart_min // 60))
        dest_set = set(dest_stops)
        candidates: list[dict[str, Any]] = []
        seen_routes: set[str] = set()

        with self._conn() as conn:
            # 0-transfer direct routes
            for osid in origin_stops:
                for rid, s_idx in self.stop_routes.get(osid, []):
                    if rid in seen_routes:
                        continue
                    stops = self.route_stops[rid]
                    for e_idx in range(s_idx + 1, len(stops)):
                        if stops[e_idx] in dest_set:
                            seen_routes.add(rid)
                            stretches = self._get_leg_crowding(conn, rid, s_idx, e_idx, day_type, time_bin)
                            max_lf = max(s["load_factor"] for s in stretches)
                            avg_lf = sum(s["load_factor"] for s in stretches) / len(stretches)
                            base_min = max(8, (e_idx - s_idx) * 2.4)
                            dwell_pen = sum(0.6 for s in stretches if s["crowding_tier"] == "crowded")
                            total_min = round(base_min + dwell_pen)
                            candidates.append({
                                "id": f"direct-{rid}",
                                "transfers": 0,
                                "total_minutes": total_min,
                                "depart_min": depart_min,
                                "arrive_min": depart_min + total_min,
                                "worst_tier": classify_tier(max_lf),
                                "max_load_factor": round(max_lf, 2),
                                "avg_load_factor": round(avg_lf, 2),
                                "legs": [{
                                    "route_id": rid,
                                    "from_stop": self.stop_names.get(osid, osid),
                                    "to_stop": self.stop_names.get(stops[e_idx], stops[e_idx]),
                                    "stop_count": e_idx - s_idx,
                                    "stretches": stretches,
                                }],
                            })
                            break

        # Score & tag Pareto options
        if not candidates:
            return {"options": [], "leave_later_tip": None}

        fastest = min(candidates, key=lambda x: x["total_minutes"])
        comfiest = min(candidates, key=lambda x: (x["max_load_factor"], x["total_minutes"]))
        balanced = min(candidates, key=lambda x: x["total_minutes"] * (1.0 + 0.35 * x["max_load_factor"]))

        tagged = []
        used = set()
        for tag, opt in [("Fastest", fastest), ("Most Comfortable", comfiest), ("Balanced", balanced)]:
            if opt["id"] not in used:
                used.add(opt["id"])
                opt_copy = dict(opt)
                opt_copy["tag"] = tag
                tagged.append(opt_copy)
        for opt in sorted(candidates, key=lambda x: x["total_minutes"]):
            if len(tagged) >= 5:
                break
            if opt["id"] not in used:
                used.add(opt["id"])
                opt_copy = dict(opt)
                opt_copy["tag"] = "Alternative"
                tagged.append(opt_copy)

        if preference == "fastest":
            tagged.sort(key=lambda x: x["total_minutes"])
        elif preference == "comfort":
            tagged.sort(key=lambda x: (x["max_load_factor"], x["total_minutes"]))

        # Check +20 min departure shift for crowded trips
        leave_later_tip = None
        if fastest["worst_tier"] == "crowded":
            later_bin = min(23, (depart_min + 20) // 60)
            if later_bin != time_bin:
                with self._conn() as conn:
                    rid = fastest["legs"][0]["route_id"]
                    s_len = len(fastest["legs"][0]["stretches"])
                    # Quick check on same route at later_bin
                    row = conn.execute(
                        "SELECT MAX(load_factor) as mlf FROM segment_crowding WHERE route_id=? AND day_type=? AND time_bin=?",
                        (rid, day_type, later_bin),
                    ).fetchone()
                    if row and row["mlf"] is not None and classify_tier(row["mlf"]) != "crowded":
                        leave_later_tip = {
                            "shift_minutes": 20,
                            "new_depart_min": depart_min + 20,
                            "new_tier": classify_tier(row["mlf"]),
                            "message": f"Leaving 20 min later drops crowding to {classify_tier(row['mlf']).replace('_', ' ')}."
                        }

        return {"options": tagged, "leave_later_tip": leave_later_tip}
