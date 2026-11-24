#!/usr/bin/env python3
"""
Inspect the October 2026 Delhi bus ticket dataset ZIP file.
Efficiently streams the CSV directly from the ZIP archive without writing uncompressed copies to disk.
"""

import sys
import io
import csv
import zipfile
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

def inspect_tickets(zip_path="data/raw/October-Delhi.csv.zip", csv_filename="October-Delhi.csv"):
    zip_p = Path(zip_path)
    if not zip_p.exists():
        raise FileNotFoundError(f"Ticket zip not found at {zip_path}")

    print(f"Opening {zip_path}...")
    with zipfile.ZipFile(zip_p) as z:
        # Check files inside zip
        infolist = z.infolist()
        file_info = {f.filename: f.file_size for f in infolist if not f.filename.startswith("__MACOSX")}
        print(f"Files in zip: {file_info}")

        if csv_filename not in file_info:
            # fallback: find first csv
            csv_candidates = [f for f in file_info if f.endswith(".csv")]
            if not csv_candidates:
                raise ValueError("No CSV file found in archive")
            csv_filename = csv_candidates[0]

        print(f"Inspecting '{csv_filename}' (Uncompressed: {file_info[csv_filename]:,} bytes)...")
        
        with z.open(csv_filename) as f:
            # Wrap as text stream
            text_stream = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
            reader = csv.reader(text_stream)
            
            headers = next(reader)
            print(f"Headers ({len(headers)} columns): {headers}")

            total_records = 0
            null_counts = {col: 0 for col in headers}
            unique_routes = set()
            unique_vehicles = set()
            unique_start_stops = set()
            unique_end_stops = set()
            ticket_types = Counter()
            is_ac_counts = Counter()
            passenger_counts = Counter()
            
            min_ts = None
            max_ts = None
            invalid_ts_count = 0
            date_distribution = Counter()
            hour_distribution = Counter()
            
            # Check for candidate composite keys or duplicate records
            # To avoid huge memory consumption for 2.5M rows, sample or track hash of composite keys
            # Let's track exact duplicates of full row or duplicate timestamps for same vehicle
            seen_vehicle_ts = set()
            vehicle_ts_duplicates = 0
            
            sample_rows = []

            for row in reader:
                total_records += 1
                if total_records <= 5:
                    sample_rows.append(dict(zip(headers, row)))

                row_dict = dict(zip(headers, row))
                
                # Check nulls / missing values
                for col, val in row_dict.items():
                    val_str = val.strip()
                    if val_str == "" or val_str.upper() == "NULL" or val_str.upper() == "NONE" or val_str.upper() == "NAN":
                        null_counts[col] += 1

                # Routes
                r = row_dict.get("route", "").strip()
                if r and r.upper() != "NULL":
                    unique_routes.add(r)

                # Vehicles
                v = row_dict.get("vehicle_number", "").strip()
                if v and v.upper() != "NULL":
                    unique_vehicles.add(v)

                # Stops
                s_stop = row_dict.get("start_stop_name", "").strip()
                if s_stop and s_stop.upper() != "NULL":
                    unique_start_stops.add(s_stop)
                    
                e_stop = row_dict.get("end_stop_name", "").strip()
                if e_stop and e_stop.upper() != "NULL":
                    unique_end_stops.add(e_stop)

                # Ticket type
                tt = row_dict.get("ticket_type_id", "").strip()
                ticket_types[tt] += 1

                # AC flag
                ac = row_dict.get("is_ac", "").strip()
                is_ac_counts[ac] += 1

                # Passenger count
                pc = row_dict.get("passenger_count", "").strip()
                try:
                    passenger_counts[int(pc)] += 1
                except ValueError:
                    passenger_counts[pc] += 1

                # Timestamps
                ts_str = row_dict.get("created_at", "").strip()
                if ts_str and ts_str.upper() != "NULL":
                    try:
                        # Format example: '2026-10-28 10:19:18.780611+05:30'
                        # Python 3.11+ fromisoformat supports +05:30
                        dt = datetime.fromisoformat(ts_str)
                        if min_ts is None or dt < min_ts:
                            min_ts = dt
                        if max_ts is None or dt > max_ts:
                            max_ts = dt
                        date_distribution[dt.strftime("%Y-%m-%d")] += 1
                        hour_distribution[dt.hour] += 1
                        
                        # Vehicle timestamp collision check
                        if v and v.upper() != "NULL":
                            veh_ts_key = (v, ts_str)
                            if veh_ts_key in seen_vehicle_ts:
                                vehicle_ts_duplicates += 1
                            else:
                                if len(seen_vehicle_ts) < 2000000:
                                    seen_vehicle_ts.add(veh_ts_key)
                    except Exception:
                        invalid_ts_count += 1
                else:
                    invalid_ts_count += 1

                if total_records % 500000 == 0:
                    print(f"Processed {total_records:,} records...")

    all_unique_stops = unique_start_stops.union(unique_end_stops)

    results = {
        "file_name": csv_filename,
        "total_records": total_records,
        "columns": headers,
        "has_unique_ticket_identifier": False,
        "null_counts": null_counts,
        "null_percentages": {col: round(cnt / total_records * 100, 2) for col, cnt in null_counts.items()},
        "unique_counts": {
            "routes": len(unique_routes),
            "vehicles": len(unique_vehicles),
            "start_stops": len(unique_start_stops),
            "end_stops": len(unique_end_stops),
            "all_stops": len(all_unique_stops),
        },
        "sample_routes": sorted(list(unique_routes))[:15],
        "sample_vehicles": sorted(list(unique_vehicles))[:10],
        "ticket_type_distribution": dict(ticket_types),
        "is_ac_distribution": dict(is_ac_counts),
        "passenger_count_distribution": dict(passenger_counts),
        "timestamp_analysis": {
            "min_timestamp": min_ts.isoformat() if min_ts else None,
            "max_timestamp": max_ts.isoformat() if max_ts else None,
            "invalid_timestamp_count": invalid_ts_count,
            "date_coverage_days": len(date_distribution),
            "daily_record_counts": dict(sorted(date_distribution.items())),
            "hourly_distribution": dict(sorted(hour_distribution.items())),
        },
        "duplicate_analysis": {
            "vehicle_timestamp_collisions_sample": vehicle_ts_duplicates
        },
        "sample_rows": sample_rows
    }
    
    return results

if __name__ == "__main__":
    res = inspect_tickets()
    print("\n--- SUMMARY OF TICKET INSPECTION ---")
    print(f"Total Records: {res['total_records']:,}")
    print(f"Columns: {res['columns']}")
    print(f"Null Counts: {res['null_counts']}")
    print(f"Null Percentages: {res['null_percentages']}")
    print(f"Unique Counts: {res['unique_counts']}")
    print(f"Date range: {res['timestamp_analysis']['min_timestamp']} to {res['timestamp_analysis']['max_timestamp']}")
    print(f"Days covered: {res['timestamp_analysis']['date_coverage_days']}")
    print(f"Dates: {list(res['timestamp_analysis']['daily_record_counts'].keys())}")
    print(f"Ticket Type IDs: {res['ticket_type_distribution']}")
    print(f"AC Distribution: {res['is_ac_distribution']}")
    print(f"Passenger Counts: {res['passenger_count_distribution']}")
    
    output_json = Path("docs/ticket_inspection.json")
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as out:
        json.dump(res, out, indent=2)
    print(f"Saved inspection JSON to {output_json}")
