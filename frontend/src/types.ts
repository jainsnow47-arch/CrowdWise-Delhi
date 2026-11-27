export type DayType = "weekday" | "saturday" | "sunday_holiday";
export type Preference = "fastest" | "balanced" | "comfort";
export type CrowdingTier = "seats_available" | "standing_room" | "crowded";

export interface HealthResponse {
  status: string;
  db_ready: boolean;
  raptor_ready: boolean;
  routes_indexed: number;
  stops_indexed: number;
}

export interface StopHub {
  hub_name: string;
  stop_ids: string[];
  lat: number;
  lon: number;
}

export interface StretchCrowding {
  seq_idx: number;
  from_stop: string;
  to_stop: string;
  est_total_load: number;
  load_factor: number;
  crowding_tier: CrowdingTier;
  confidence: string;
}

export interface JourneyLeg {
  route_id: string;
  from_stop: string;
  to_stop: string;
  stop_count: number;
  stretches: StretchCrowding[];
}

export interface JourneyOption {
  id: string;
  tag: string;
  transfers: number;
  total_minutes: number;
  depart_min: number;
  arrive_min: number;
  worst_tier: CrowdingTier;
  max_load_factor: number;
  avg_load_factor: number;
  legs: JourneyLeg[];
}

export interface LeaveLaterTip {
  shift_minutes: number;
  new_depart_min: number;
  new_tier: CrowdingTier;
  message: string;
}

export interface PlanRequest {
  origin_hub: string;
  dest_hub: string;
  day_type: DayType;
  depart_min: number;
  preference: Preference;
}

export interface PlanResponse {
  options: JourneyOption[];
  leave_later_tip: LeaveLaterTip | null;
  note?: string;
}

export interface BottleneckRoute {
  route_id: string;
  route_short_name: string;
  bus_class: string;
  seated_cap: number;
  max_load_factor: number;
  avg_load_factor: number;
  peak_est_load: number;
  stretches: number;
  confidence: string;
}

export interface OverloadedResponse {
  bottlenecks: BottleneckRoute[];
  validation: Record<string, unknown>;
}
