#!/usr/bin/env python3
"""
Orchestration script for running all data inspection and validation checks for CrowdWise Delhi.
Executes:
1. inspect_tickets.py
2. inspect_gtfs.py
3. cross_validate.py
4. validate_tickets_deep.py
Outputs consolidated statistics and ensures repeatability.
"""

import sys
import time
import json
from pathlib import Path

# Add backend/scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from inspect_tickets import inspect_tickets
from inspect_gtfs import inspect_gtfs
from cross_validate import cross_validate
from validate_tickets_deep import deep_inspect_tickets

def run_all():
    start_time = time.time()
    print("=" * 60)
    print("CROWDWISE DELHI: FULL DATA INSPECTION & VALIDATION SUITE")
    print("=" * 60)

    # 1. Ticket inspection
    print("\n[Step 1/4] Inspecting October Ticket Dataset...")
    t0 = time.time()
    ticket_results = inspect_tickets()
    print(f"Ticket inspection completed in {time.time() - t0:.2f}s.")

    # 2. GTFS inspection
    print("\n[Step 2/4] Inspecting GTFS Static Dataset...")
    t0 = time.time()
    gtfs_results = inspect_gtfs()
    print(f"GTFS inspection completed in {time.time() - t0:.2f}s.")

    # 3. Cross validation
    print("\n[Step 3/4] Running Cross-Validation & Matching Feasibility...")
    t0 = time.time()
    cross_results = cross_validate()
    print(f"Cross-validation completed in {time.time() - t0:.2f}s.")

    # 4. Deep ticket anomalies
    print("\n[Step 4/4] Running Deep Anomaly Checks on Tickets...")
    t0 = time.time()
    deep_results = deep_inspect_tickets()
    print(f"Deep validation completed in {time.time() - t0:.2f}s.")

    # Save consolidated summary
    consolidated = {
        "execution_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "total_execution_seconds": round(time.time() - start_time, 2),
        "tickets": ticket_results,
        "gtfs": gtfs_results,
        "cross_validation": cross_results,
        "deep_tickets": deep_results
    }

    out_file = Path("docs/consolidated_inspection_summary.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(consolidated, f, indent=2)
    print(f"\nAll inspections completed in {time.time() - start_time:.2f}s.")
    print(f"Consolidated results saved to: {out_file}")

if __name__ == "__main__":
    run_all()
