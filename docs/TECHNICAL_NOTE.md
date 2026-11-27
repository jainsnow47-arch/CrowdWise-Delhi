# Technical Note: CrowdWise-Delhi Transit Passenger & Capacity Reconstruction Pipeline

## 1. Method & Architecture

The CrowdWise-Delhi pipeline reconstructs fine-grained transit passenger demand and capacity utilization across Delhi Transport Corporation (DTC) and cluster bus networks using a rigorous multi-stage methodology:

- **Two-Tier Trip Reconstruction**: Vehicle runs are reconstructed using a hybrid approach combining **51.48% Tier-1** direct vehicle tracking logs (`vehicle_number` deterministic sequence matching) and **48.52% Tier-2** heuristic route-time window allocation for unassigned departures.
- **Passenger Count & Soft Alighting**: Ticketing transactions are aggregated into spatial-temporal segment cells with a distributed **0.15 / 0.70 / 0.15** soft alighting kernel across adjacent route stops to smooth boarding/alighting drop-offs.
- **Unobserved Rider Expansion**: Explicitly scales observed ticketing data using an `is_ac`-aware expansion factor accounting for unobserved ridership segments (bus pass holders, women's free-travel pink tickets, and un-scanned cash fares).
- **Fleet Capacity Normalization**: Standardizes capacity based on bus form-factor specifications—**9-meter midi buses (22 seats)** versus **12-meter standard buses (38 seats)**—yielding standardized occupancy and crowding ratios (`seats_available`).
- **Sparsity Imputation & Day-Type Stratification**: Employs **LightGBM quantile regression** to impute sparse segment-hour cells. Days are stratified into weekday, saturday, and `sunday_holiday` regimes, incorporating explicit holiday overrides (`Oct 2`, `Oct 20`).

---

## 2. Validation Results

Based on `data/processed/validation_report.json`, the validation metrics across **2,732,736 segment cells** (`segment_cells`) are summarized below:

- **Total Ticket Volume**: `2,559,899` transactions processed (`total_tickets`).
- **Matching Quality**: `98.8%` route match percentage (`route_matched_pct`) and `85.75%` strict ordered itinerary match (`ordered_itinerary_pct`).
- **Tier Distribution**: `100%` coverage across reconstructed spatial-temporal segment cells (`seats_available`: `2,732,736`).
- **Confidence Distribution**: 
  - High Confidence: `1,004,200` cells
  - Medium Confidence: `765,232` cells
  - Low Confidence: `963,304` cells
- **Day-Type Breakdown**:
  - Weekday: `1,892,259` tickets
  - Saturday: `372,691` tickets
  - Sunday / Holiday: `264,146` tickets
- **Diurnal Hourly Breakdown (Tickets)**:
  - `00:00`: 1,330 | `01:00`: 496 | `02:00`: 370 | `03:00`: 420 | `04:00`: 1,914
  - `05:00`: 23,826 | `06:00`: 67,519 | `07:00`: 148,403 | `08:00`: 312,849 | `09:00`: 348,460
  - `10:00`: 202,247 | `11:00`: 110,190 | `12:00`: 84,290 | `13:00`: 69,011 | `14:00`: 67,026
  - `15:00`: 71,922 | `16:00`: 96,660 | `17:00`: 162,204 | `18:00`: 232,294 | `19:00`: 219,356
  - `20:00`: 163,375 | `21:00`: 94,983 | `22:00`: 41,989 | `23:00`: 7,962

---

## 3. Limitations & Least Reliable Regimes

1. **Night Hours (`00:00–04:00`)**: Extremely sparse ticketing transactions (<0.2% of daily volume) result in high variance and unreliable occupancy estimates.
2. **Low-Volume Routes (`confidence = low`)**: `963,304` cells fall under low confidence due to sparse GPS pings and infrequent service schedules.
3. **Missing Vehicle Identifiers**: Routes exhibiting >80% missing `vehicle_number` rely entirely on Tier-2 heuristic window allocation, increasing assignment uncertainty.
4. **Unobserved Cash & Pink-Ticket Variance**: Expansion models assume static scaling factors for free pink tickets and cash transactions, which fluctuate during peak congestion and special events.
