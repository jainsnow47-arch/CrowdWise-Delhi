#!/usr/bin/env python3
"""
Inspect GTFS static files for Delhi Buses.
Handles stop_times.txt (122 MB) efficiently using streaming line-by-line parsing.
Validates referential integrity, coordinate ranges, and calendar coverage for October 2026.
"""

import os
import csv
import json
from collections import Counter
from pathlib import Path

def inspect_gtfs(gtfs_dir="data/gtfs/extracted"):
    gtfs_path = Path(gtfs_dir)
    if not gtfs_path.exists():
        raise FileNotFoundError(f"GTFS directory not found at {gtfs_dir}")

    results = {}
    print(f"Inspecting GTFS directory: {gtfs_path}...")

    # 1. feed_info.txt
    feed_info_path = gtfs_path / "feed_info.txt"
    if feed_info_path.exists():
        with open(feed_info_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            feed_info_rows = list(reader)
            results["feed_info"] = {
                "headers": reader.fieldnames,
                "records": feed_info_rows
            }
            print(f"feed_info: {feed_info_rows}")

    # 2. agency.txt
    agency_path = gtfs_path / "agency.txt"
    agencies = []
    agency_ids = set()
    with open(agency_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            agencies.append(r)
            agency_ids.add(r.get("agency_id", ""))
    results["agency"] = {
        "count": len(agencies),
        "records": agencies,
        "agency_ids": list(agency_ids)
    }
    print(f"agency: {len(agencies)} agencies found: {agency_ids}")

    # 3. calendar.txt
    calendar_path = gtfs_path / "calendar.txt"
    services = []
    service_ids = set()
    calendar_coverage_oct_2026 = True
    with open(calendar_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            services.append(r)
            sid = r.get("service_id", "")
            service_ids.add(sid)
            s_date = r.get("start_date", "")
            e_date = r.get("end_date", "")
            # Check if October 2026 is fully covered (20261001 to 20261031)
            if not (s_date <= "20261001" and e_date >= "20261031"):
                calendar_coverage_oct_2026 = False
    results["calendar"] = {
        "count": len(services),
        "services": services,
        "covers_october_2026": calendar_coverage_oct_2026
    }
    print(f"calendar: {len(services)} service schedules, covers Oct 2026: {calendar_coverage_oct_2026}")

    # 4. routes.txt
    routes_path = gtfs_path / "routes.txt"
    route_ids = set()
    route_short_names = set()
    route_long_names = set()
    route_type_counter = Counter()
    agency_route_counter = Counter()
    total_routes = 0
    with open(routes_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        routes_headers = reader.fieldnames
        for r in reader:
            total_routes += 1
            rid = r.get("route_id", "")
            route_ids.add(rid)
            sn = r.get("route_short_name", "")
            ln = r.get("route_long_name", "")
            if sn: route_short_names.add(sn)
            if ln: route_long_names.add(ln)
            route_type_counter[r.get("route_type", "")] += 1
            agency_route_counter[r.get("agency_id", "")] += 1

    results["routes"] = {
        "headers": routes_headers,
        "total_routes": total_routes,
        "unique_route_ids": len(route_ids),
        "unique_short_names": len(route_short_names),
        "unique_long_names": len(route_long_names),
        "route_types": dict(route_type_counter),
        "agency_distribution": dict(agency_route_counter),
        "sample_routes": sorted(list(route_short_names))[:15]
    }
    print(f"routes: {total_routes} routes across {len(agency_route_counter)} agencies")

    # 5. stops.txt
    stops_path = gtfs_path / "stops.txt"
    stop_ids = set()
    stop_names = set()
    stop_codes = set()
    min_lat, max_lat = 90.0, -90.0
    min_lon, max_lon = 180.0, -180.0
    invalid_coords = 0
    total_stops = 0

    with open(stops_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        stops_headers = reader.fieldnames
        for r in reader:
            total_stops += 1
            sid = r.get("stop_id", "")
            stop_ids.add(sid)
            sname = r.get("stop_name", "")
            if sname: stop_names.add(sname)
            scode = r.get("stop_code", "")
            if scode: stop_codes.add(scode)
            
            try:
                lat = float(r.get("stop_lat", ""))
                lon = float(r.get("stop_lon", ""))
                if lat < min_lat: min_lat = lat
                if lat > max_lat: max_lat = lat
                if lon < min_lon: min_lon = lon
                if lon > max_lon: max_lon = lon
                # Delhi bounds roughly 28.3 - 28.9 N, 76.8 - 77.4 E
                if not (27.0 <= lat <= 30.0 and 75.0 <= lon <= 79.0):
                    invalid_coords += 1
            except ValueError:
                invalid_coords += 1

    results["stops"] = {
        "headers": stops_headers,
        "total_stops": total_stops,
        "unique_stop_ids": len(stop_ids),
        "unique_stop_names": len(stop_names),
        "unique_stop_codes": len(stop_codes),
        "lat_range": [min_lat, max_lat],
        "lon_range": [min_lon, max_lon],
        "invalid_or_out_of_bounds_coords": invalid_coords,
        "sample_stop_names": sorted(list(stop_names))[:15]
    }
    print(f"stops: {total_stops} stops, lat [{min_lat:.4f}, {max_lat:.4f}], lon [{min_lon:.4f}, {max_lon:.4f}]")

    # 6. trips.txt
    trips_path = gtfs_path / "trips.txt"
    trip_ids = set()
    trips_by_route = Counter()
    unmatched_route_ids_in_trips = set()
    unmatched_service_ids_in_trips = set()
    direction_counter = Counter()
    shape_ids = set()
    total_trips = 0

    with open(trips_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        trips_headers = reader.fieldnames
        for r in reader:
            total_trips += 1
            tid = r.get("trip_id", "")
            trip_ids.add(tid)
            rid = r.get("route_id", "")
            trips_by_route[rid] += 1
            if rid not in route_ids:
                unmatched_route_ids_in_trips.add(rid)
            sid = r.get("service_id", "")
            if sid not in service_ids:
                unmatched_service_ids_in_trips.add(sid)
            direction_counter[r.get("direction_id", "")] += 1
            shp = r.get("shape_id", "")
            if shp: shape_ids.add(shp)

    results["trips"] = {
        "headers": trips_headers,
        "total_trips": total_trips,
        "unique_trip_ids": len(trip_ids),
        "routes_in_trips": len(trips_by_route),
        "unmatched_route_ids": len(unmatched_route_ids_in_trips),
        "unmatched_service_ids": len(unmatched_service_ids_in_trips),
        "direction_distribution": dict(direction_counter),
        "unique_shapes": len(shape_ids),
        "trips_per_route": {
            "min": min(trips_by_route.values()) if trips_by_route else 0,
            "max": max(trips_by_route.values()) if trips_by_route else 0,
            "avg": round(total_trips / len(trips_by_route), 2) if trips_by_route else 0
        }
    }
    print(f"trips: {total_trips} trips, unique routes: {len(trips_by_route)}")

    # 7. stop_times.txt (Efficient streaming, ~122 MB)
    stop_times_path = gtfs_path / "stop_times.txt"
    total_stop_times = 0
    trips_in_stop_times = set()
    stops_in_stop_times = set()
    missing_trip_in_stop_times = 0
    missing_stop_in_stop_times = 0
    max_stop_sequence = 0
    post_midnight_trips = 0

    print("Streaming stop_times.txt (122 MB)...")
    with open(stop_times_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        stop_times_headers = reader.fieldnames
        for r in reader:
            total_stop_times += 1
            tid = r.get("trip_id", "")
            sid = r.get("stop_id", "")
            trips_in_stop_times.add(tid)
            stops_in_stop_times.add(sid)

            if tid not in trip_ids:
                missing_trip_in_stop_times += 1
            if sid not in stop_ids:
                missing_stop_in_stop_times += 1

            try:
                seq = int(r.get("stop_sequence", "0"))
                if seq > max_stop_sequence:
                    max_stop_sequence = seq
            except ValueError:
                pass

            arr = r.get("arrival_time", "")
            if arr and arr.split(":")[0].isdigit() and int(arr.split(":")[0]) >= 24:
                post_midnight_trips += 1

            if total_stop_times % 1000000 == 0:
                print(f"Processed {total_stop_times:,} stop_times records...")

    results["stop_times"] = {
        "headers": stop_times_headers,
        "total_stop_times": total_stop_times,
        "unique_trips": len(trips_in_stop_times),
        "unique_stops": len(stops_in_stop_times),
        "unmatched_trip_ids": missing_trip_in_stop_times,
        "unmatched_stop_ids": missing_stop_in_stop_times,
        "max_stop_sequence": max_stop_sequence,
        "records_past_midnight": post_midnight_trips
    }
    print(f"stop_times: {total_stop_times:,} stop-time records processed successfully")

    # Referential checks
    results["integrity"] = {
        "routes_without_trips": len(route_ids - set(trips_by_route.keys())),
        "trips_without_stop_times": len(trip_ids - trips_in_stop_times),
        "stops_without_stop_times": len(stop_ids - stops_in_stop_times)
    }

    return results

if __name__ == "__main__":
    res = inspect_gtfs()
    print("\n--- GTFS INSPECTION COMPLETE ---")
    out_file = Path("docs/gtfs_inspection.json")
    with open(out_file, "w", encoding="utf-8") as fp:
        json.dump(res, fp, indent=2)
    print(f"Saved GTFS inspection JSON to {out_file}")
