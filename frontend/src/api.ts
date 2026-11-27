import type {
  DayType,
  HealthResponse,
  OverloadedResponse,
  PlanRequest,
  PlanResponse,
  StopHub,
} from "./types";

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/health", { signal });
}

export async function searchStops(
  query: string,
  signal?: AbortSignal
): Promise<StopHub[]> {
  const trimmed = query.trim();
  if (trimmed.length < 2) return [];
  const params = new URLSearchParams({ q: trimmed });
  const data = await requestJson<{ stops: StopHub[] }>(
    `/api/stops/search?${params.toString()}`,
    { signal }
  );
  return data.stops ?? [];
}

export function planJourney(
  payload: PlanRequest,
  signal?: AbortSignal
): Promise<PlanResponse> {
  return requestJson<PlanResponse>("/api/journeys/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
}

export function fetchOverloadedRoutes(
  dayType: DayType,
  timeBin: number,
  limit = 25,
  signal?: AbortSignal
): Promise<OverloadedResponse> {
  const params = new URLSearchParams({
    day_type: dayType,
    time_bin: String(timeBin),
    limit: String(limit),
  });
  return requestJson<OverloadedResponse>(
    `/api/analytics/overloaded?${params.toString()}`,
    { signal }
  );
}
