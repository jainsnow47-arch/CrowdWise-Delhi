#!/usr/bin/env python3
"""
Deep inspection into ticket dataset anomalies:
1. Candidate unique identifiers and collision analysis.
2. Vehicle number missingness breakdown (by route, is_ac, agency).
3. Ticket amount and passenger count distributions (including zero fares/pink tickets).
4. Timestamp distribution and peak hours.
"""

import io
import csv
import zipfile
import json
from collections import Counter, defaultdict
from pathlib import Path

def deep_inspect_tickets(zip_path="data/raw/October-Delhi.csv.zip"):
    print("Running deep validation on tickets...")
    
    fare_distribution = Counter()
    missing_veh_by_route = Counter()
    total_by_route = Counter()
    missing_veh_by_ac = Counter()
    total_by_ac = Counter()
    
    # Check exact row duplicate count on a sample or running hash
    # To find exact duplicates:
    sample_key_counter = Counter()
    total_rows = 0
    
    # Check amount data types and invalid amounts
    invalid_amounts = 0
    zero_or_negative_amounts = 0
    amounts = []
    
    with zipfile.ZipFile(zip_path) as z:
        with z.open("October-Delhi.csv") as f:
            text_stream = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
            reader = csv.DictReader(text_stream)
            
            for row in reader:
                total_rows += 1
                r = row["route"].strip()
                v = row["vehicle_number"].strip()
                ac = row["is_ac"].strip()
                amt_str = row["amount"].strip()
                ts = row["created_at"].strip()
                s_stop = row["start_stop_name"].strip()
                e_stop = row["end_stop_name"].strip()
                
                # Missing vehicle checks
                total_by_route[r] += 1
                total_by_ac[ac] += 1
                is_missing_veh = (v == "" or v.upper() == "NULL")
                if is_missing_veh:
                    missing_veh_by_route[r] += 1
                    missing_veh_by_ac[ac] += 1
                    
                # Fare checks
                try:
                    amt = float(amt_str)
                    fare_distribution[amt] += 1
                    if amt <= 0:
                        zero_or_negative_amounts += 1
                except ValueError:
                    invalid_amounts += 1

                # Sample composite key collision test
                # Hash of: ts, v, r, s_stop, e_stop, amt_str
                # Sample 1 in 10 to keep hash table manageable
                if total_rows % 10 == 0:
                    comp_key = (ts, v, r, s_stop, e_stop)
                    sample_key_counter[comp_key] += 1

                if total_rows % 500000 == 0:
                    print(f"Processed {total_rows:,} rows...")

    # Calculate duplicate collisions in sampled keys
    collisions = {k: c for k, c in sample_key_counter.items() if c > 1}
    
    # Top routes with missing vehicle numbers
    missing_veh_route_ratios = []
    for r, total in total_by_route.items():
        if total >= 500: # significant volume
            miss = missing_veh_by_route[r]
            missing_veh_route_ratios.append({
                "route": r,
                "total": total,
                "missing": miss,
                "missing_pct": round(miss / total * 100, 2)
            })
    missing_veh_route_ratios.sort(key=lambda x: x["missing_pct"], reverse=True)

    results = {
        "total_records": total_rows,
        "fare_analysis": {
            "invalid_amount_strings": invalid_amounts,
            "zero_or_negative_amounts": zero_or_negative_amounts,
            "top_fare_amounts": fare_distribution.most_common(20),
            "unique_fare_count": len(fare_distribution)
        },
        "missing_vehicle_analysis": {
            "by_ac_status": {
                ac: {
                    "total": total_by_ac[ac],
                    "missing_vehicle": missing_veh_by_ac[ac],
                    "missing_pct": round(missing_veh_by_ac[ac] / total_by_ac[ac] * 100, 2)
                } for ac in total_by_ac
            },
            "top_routes_with_highest_missing_veh_pct": missing_veh_route_ratios[:15],
            "top_routes_with_lowest_missing_veh_pct": sorted(missing_veh_route_ratios, key=lambda x: x["missing_pct"])[:15]
        },
        "duplicate_analysis": {
            "sampled_records": len(sample_key_counter),
            "duplicate_composite_keys_in_sample": len(collisions),
            "max_occurrences_of_same_key": max(collisions.values()) if collisions else 1
        }
    }
    
    return results

if __name__ == "__main__":
    res = deep_inspect_tickets()
    print("\n--- DEEP TICKET ANALYSIS ---")
    print(f"Fare Distribution (top 10): {res['fare_analysis']['top_fare_amounts'][:10]}")
    print(f"Zero or negative amounts: {res['fare_analysis']['zero_or_negative_amounts']}")
    print(f"Missing vehicles by AC status: {res['missing_vehicle_analysis']['by_ac_status']}")
    print(f"Sample duplicate composite keys: {res['duplicate_analysis']['duplicate_composite_keys_in_sample']}")
    
    out = Path("docs/ticket_deep_analysis.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"Saved to {out}")
