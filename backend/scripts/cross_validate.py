#!/usr/bin/env python3
"""
Cross-validation script between October 2026 Delhi bus tickets and static GTFS dataset.
Computes exact match rates for:
1. Routes (exact, case-insensitive, normalized)
2. Stops (exact, case-insensitive, normalized)
3. Ticket-level match rates (route matched, stops matched, both matched)
4. Route-Stop itinerary consistency (start stop before end stop on the matched route)
5. Analysis of unmatched routes and stops
"""

import sys
import io
import csv
import zipfile
import re
import json
from collections import Counter, defaultdict
from pathlib import Path

def normalize_name(s):
    if not s:
        return ""
    # Lowercase, replace multiple spaces/tabs with single space, strip punctuation
    s = s.strip().lower()
    s = re.sub(r'[\(\)\[\]\/\-\,\.]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def cross_validate(ticket_zip="data/raw/October-Delhi.csv.zip", gtfs_dir="data/gtfs/extracted"):
    gtfs_path = Path(gtfs_dir)
    print("Loading GTFS routes and stops...")
    
    # 1. Load GTFS routes
    # Map route_short_name and route_long_name -> route_id
    gtfs_route_short = set()
    gtfs_route_long = set()
    gtfs_route_id_by_name = {} # name -> route_id
    gtfs_route_norm_map = {}   # normalized name -> original name

    with open(gtfs_path / "routes.txt", "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rid = r.get("route_id", "").strip()
            sn = r.get("route_short_name", "").strip()
            ln = r.get("route_long_name", "").strip()
            if sn:
                gtfs_route_short.add(sn)
                gtfs_route_id_by_name[sn] = rid
                gtfs_route_norm_map[sn.lower()] = sn
            if ln:
                gtfs_route_long.add(ln)
                gtfs_route_id_by_name[ln] = rid
                gtfs_route_norm_map[ln.lower()] = ln

    all_gtfs_route_names = gtfs_route_short.union(gtfs_route_long)
    print(f"Loaded {len(all_gtfs_route_names)} GTFS route names.")

    # 2. Load GTFS stops
    gtfs_stop_names = set()
    gtfs_stop_ids_by_name = defaultdict(set) # stop_name -> set(stop_ids)
    gtfs_stop_norm_map = {}                  # normalized stop name -> set of original stop_names

    with open(gtfs_path / "stops.txt", "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            sid = r.get("stop_id", "").strip()
            sname = r.get("stop_name", "").strip()
            if sname:
                gtfs_stop_names.add(sname)
                gtfs_stop_ids_by_name[sname].add(sid)
                norm = normalize_name(sname)
                if norm not in gtfs_stop_norm_map:
                    gtfs_stop_norm_map[norm] = set()
                gtfs_stop_norm_map[norm].add(sname)

    print(f"Loaded {len(gtfs_stop_names)} unique GTFS stop names.")

    # 3. Load Route -> Stops sequence from trips and stop_times
    # To check if ticket start_stop -> end_stop is valid for route
    print("Building GTFS Route -> Stop sequence mapping from trips and stop_times...")
    # First: trip_id -> route_name
    trip_to_route_name = {}
    with open(gtfs_path / "trips.txt", "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        # We also need route_id -> route_short_name
        # Build route_id -> short_name map
        pass

    route_id_to_name = {}
    with open(gtfs_path / "routes.txt", "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            route_id_to_name[r["route_id"]] = r["route_short_name"]

    with open(gtfs_path / "trips.txt", "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            tid = r["trip_id"]
            rid = r["route_id"]
            trip_to_route_name[tid] = route_id_to_name.get(rid, rid)

    # stop_id -> stop_name
    stop_id_to_name = {}
    with open(gtfs_path / "stops.txt", "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            stop_id_to_name[r["stop_id"]] = r["stop_name"]

    # For each route_name, keep set of stops that appear on that route
    route_to_stops = defaultdict(set)
    # Also keep sample trip stop sequences for order checking (sample first trip for each route)
    route_stop_sequences = {} # route_name -> list of stop_names in sequence

    with open(gtfs_path / "stop_times.txt", "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        current_trip = None
        current_route = None
        trip_seq = []
        for r in reader:
            tid = r["trip_id"]
            sid = r["stop_id"]
            sname = stop_id_to_name.get(sid, "")
            
            if tid != current_trip:
                if current_trip and current_route and current_route not in route_stop_sequences:
                    route_stop_sequences[current_route] = trip_seq
                current_trip = tid
                current_route = trip_to_route_name.get(tid)
                trip_seq = []

            if sname and current_route:
                route_to_stops[current_route].add(sname)
                trip_seq.append(sname)

        if current_trip and current_route and current_route not in route_stop_sequences:
            route_stop_sequences[current_route] = trip_seq

    print(f"Mapped stops for {len(route_to_stops)} GTFS routes.")

    # 4. Stream tickets and match
    print("Streaming October ticket dataset to calculate exact match rates...")
    ticket_routes = Counter()
    ticket_start_stops = Counter()
    ticket_end_stops = Counter()

    # Match counts at record level
    total_tickets = 0
    exact_route_match_count = 0
    norm_route_match_count = 0
    unmatched_route_tickets = 0

    exact_start_match_count = 0
    norm_start_match_count = 0
    
    exact_end_match_count = 0
    norm_end_match_count = 0

    both_stops_exact_count = 0
    both_stops_norm_count = 0

    route_and_both_stops_exact = 0
    route_and_both_stops_norm = 0

    stops_on_route_count = 0 # start & end stop both exist on that route in GTFS
    itinerary_order_correct = 0 # start_stop appears BEFORE end_stop on that route

    # Unmatched trackers
    unmatched_routes_counter = Counter()
    unmatched_start_stops_counter = Counter()
    unmatched_end_stops_counter = Counter()

    with zipfile.ZipFile(ticket_zip) as z:
        with z.open("October-Delhi.csv") as f:
            text_stream = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
            reader = csv.DictReader(text_stream)

            for row in reader:
                total_tickets += 1
                r = row.get("route", "").strip()
                s_stop = row.get("start_stop_name", "").strip()
                e_stop = row.get("end_stop_name", "").strip()

                ticket_routes[r] += 1
                ticket_start_stops[s_stop] += 1
                ticket_end_stops[e_stop] += 1

                # Route match
                r_matched_name = None
                if r in all_gtfs_route_names:
                    exact_route_match_count += 1
                    r_matched_name = r
                elif r.lower() in gtfs_route_norm_map:
                    norm_route_match_count += 1
                    r_matched_name = gtfs_route_norm_map[r.lower()]
                else:
                    unmatched_route_tickets += 1
                    unmatched_routes_counter[r] += 1

                # Start stop match
                s_exact = s_stop in gtfs_stop_names
                s_norm = s_exact or (normalize_name(s_stop) in gtfs_stop_norm_map)
                if s_exact:
                    exact_start_match_count += 1
                elif s_norm:
                    norm_start_match_count += 1
                else:
                    unmatched_start_stops_counter[s_stop] += 1

                # End stop match
                e_exact = e_stop in gtfs_stop_names
                e_norm = e_exact or (normalize_name(e_stop) in gtfs_stop_norm_map)
                if e_exact:
                    exact_end_match_count += 1
                elif e_norm:
                    norm_end_match_count += 1
                else:
                    unmatched_end_stops_counter[e_stop] += 1

                # Both stops
                if s_exact and e_exact:
                    both_stops_exact_count += 1
                if s_norm and e_norm:
                    both_stops_norm_count += 1

                # Route AND both stops
                route_ok = (r_matched_name is not None)
                if route_ok and s_exact and e_exact:
                    route_and_both_stops_exact += 1
                if route_ok and s_norm and e_norm:
                    route_and_both_stops_norm += 1

                # Stop membership on route
                if route_ok and s_stop in route_to_stops.get(r_matched_name, set()) and e_stop in route_to_stops.get(r_matched_name, set()):
                    stops_on_route_count += 1
                    # Check sequence order
                    seq = route_stop_sequences.get(r_matched_name, [])
                    if s_stop in seq and e_stop in seq:
                        try:
                            idx_s = seq.index(s_stop)
                            idx_e = seq.index(e_stop)
                            if idx_s < idx_e:
                                itinerary_order_correct += 1
                        except ValueError:
                            pass

                if total_tickets % 500000 == 0:
                    print(f"Validated {total_tickets:,} tickets...")

    # Distinct route matching
    distinct_ticket_routes = set(ticket_routes.keys())
    matched_distinct_routes_exact = distinct_ticket_routes.intersection(all_gtfs_route_names)
    matched_distinct_routes_norm = {r for r in distinct_ticket_routes if r.lower() in gtfs_route_norm_map}
    all_matched_distinct_routes = matched_distinct_routes_exact.union(matched_distinct_routes_norm)

    # Distinct stop matching
    all_ticket_stops = set(ticket_start_stops.keys()).union(set(ticket_end_stops.keys()))
    matched_distinct_stops_exact = all_ticket_stops.intersection(gtfs_stop_names)
    matched_distinct_stops_norm = {s for s in all_ticket_stops if normalize_name(s) in gtfs_stop_norm_map}
    all_matched_distinct_stops = matched_distinct_stops_exact.union(matched_distinct_stops_norm)

    results = {
        "summary": {
            "total_tickets": total_tickets,
            "unique_ticket_routes": len(distinct_ticket_routes),
            "unique_gtfs_routes": len(all_gtfs_route_names),
            "unique_ticket_stops": len(all_ticket_stops),
            "unique_gtfs_stops": len(gtfs_stop_names)
        },
        "route_matching": {
            "distinct_matched_routes_exact": len(matched_distinct_routes_exact),
            "distinct_matched_routes_total": len(all_matched_distinct_routes),
            "distinct_match_percentage": round(len(all_matched_distinct_routes) / len(distinct_ticket_routes) * 100, 2),
            "ticket_record_exact_matches": exact_route_match_count,
            "ticket_record_norm_matches": norm_route_match_count,
            "ticket_record_total_matches": exact_route_match_count + norm_route_match_count,
            "ticket_record_match_percentage": round((exact_route_match_count + norm_route_match_count) / total_tickets * 100, 2),
            "unmatched_ticket_records": unmatched_route_tickets,
            "top_unmatched_routes": unmatched_routes_counter.most_common(15)
        },
        "stop_matching": {
            "distinct_matched_stops_exact": len(matched_distinct_stops_exact),
            "distinct_matched_stops_total": len(all_matched_distinct_stops),
            "distinct_match_percentage": round(len(all_matched_distinct_stops) / len(all_ticket_stops) * 100, 2),
            "start_stop_matches_exact": exact_start_match_count,
            "start_stop_matches_total": exact_start_match_count + norm_start_match_count,
            "start_stop_match_percentage": round((exact_start_match_count + norm_start_match_count) / total_tickets * 100, 2),
            "end_stop_matches_exact": exact_end_match_count,
            "end_stop_matches_total": exact_end_match_count + norm_end_match_count,
            "end_stop_match_percentage": round((exact_end_match_count + norm_end_match_count) / total_tickets * 100, 2),
            "both_stops_exact": both_stops_exact_count,
            "both_stops_exact_percentage": round(both_stops_exact_count / total_tickets * 100, 2),
            "both_stops_normalized": both_stops_norm_count,
            "both_stops_normalized_percentage": round(both_stops_norm_count / total_tickets * 100, 2),
            "top_unmatched_start_stops": unmatched_start_stops_counter.most_common(15),
            "top_unmatched_end_stops": unmatched_end_stops_counter.most_common(15)
        },
        "combined_matching": {
            "route_and_both_stops_exact": route_and_both_stops_exact,
            "route_and_both_stops_exact_percentage": round(route_and_both_stops_exact / total_tickets * 100, 2),
            "route_and_both_stops_norm": route_and_both_stops_norm,
            "route_and_both_stops_norm_percentage": round(route_and_both_stops_norm / total_tickets * 100, 2),
            "both_stops_present_on_gtfs_route": stops_on_route_count,
            "both_stops_present_percentage": round(stops_on_route_count / total_tickets * 100, 2),
            "valid_itinerary_order_count": itinerary_order_correct,
            "valid_itinerary_order_percentage": round(itinerary_order_correct / total_tickets * 100, 2)
        }
    }

    return results

if __name__ == "__main__":
    results = cross_validate()
    print("\n================ CROSS VALIDATION RESULTS ================")
    print(f"Total tickets: {results['summary']['total_tickets']:,}")
    print(f"Route Match Rate: {results['route_matching']['ticket_record_match_percentage']}% ({results['route_matching']['ticket_record_total_matches']:,} / {results['summary']['total_tickets']:,})")
    print(f"Distinct Routes Matched: {results['route_matching']['distinct_matched_routes_total']} / {results['summary']['unique_ticket_routes']} ({results['route_matching']['distinct_match_percentage']}%)")
    print(f"Start Stop Match Rate: {results['stop_matching']['start_stop_match_percentage']}%")
    print(f"End Stop Match Rate: {results['stop_matching']['end_stop_match_percentage']}%")
    print(f"Both Stops Matched Rate: {results['stop_matching']['both_stops_normalized_percentage']}%")
    print(f"Combined (Route + Both Stops) Rate: {results['combined_matching']['route_and_both_stops_norm_percentage']}%")
    print(f"Stops on GTFS Route Pattern: {results['combined_matching']['both_stops_present_percentage']}%")
    print(f"Valid Directional Order: {results['combined_matching']['valid_itinerary_order_percentage']}%")
    
    out_file = Path("docs/cross_validation.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Saved results to {out_file}")
