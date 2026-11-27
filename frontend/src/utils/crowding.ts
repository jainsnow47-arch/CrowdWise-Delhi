import type { CrowdingTier, DayType } from "../types";

export const DAY_TYPE_OPTIONS: ReadonlyArray<{ value: DayType; label: string }> = [
  { value: "weekday", label: "Weekday" },
  { value: "saturday", label: "Saturday" },
  { value: "sunday_holiday", label: "Sunday / Holiday" },
];

export const TIER_META: Record<
  CrowdingTier,
  { label: string; symbol: string; description: string }
> = {
  seats_available: {
    label: "Seats Available",
    symbol: "●",
    description: "Load factor <= 0.85x seated capacity",
  },
  standing_room: {
    label: "Standing Room",
    symbol: "▲",
    description: "Load factor 0.86x–1.35x seated capacity",
  },
  crowded: {
    label: "Crowded",
    symbol: "■",
    description: "Load factor > 1.35x seated capacity",
  },
};

export function classifyCrowdingTier(loadFactor: number): CrowdingTier {
  if (loadFactor <= 0.85) return "seats_available";
  if (loadFactor <= 1.35) return "standing_room";
  return "crowded";
}

export function formatMinutesToClock(totalMin: number): string {
  const normalized = ((Math.round(totalMin) % 1440) + 1440) % 1440;
  const hh = Math.floor(normalized / 60);
  const mm = normalized % 60;
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}

export function clockToMinutes(clock: string): number {
  const [hStr, mStr] = clock.split(":");
  const h = Number(hStr);
  const m = Number(mStr);
  if (!Number.isFinite(h) || !Number.isFinite(m)) return 1080;
  return Math.max(0, Math.min(1439, h * 60 + m));
}

export function formatHourRange(hour: number): string {
  const start = `${String(hour).padStart(2, "0")}:00`;
  const end = `${String((hour + 1) % 24).padStart(2, "0")}:00`;
  return `${start}–${end}`;
}

export function simulateExtraBuses(
  maxLoadFactor: number,
  peakEstLoad: number,
  baselineBusesPerHr: number,
  extraBuses: number
): {
  loadFactor: number;
  peakLoad: number;
  tier: CrowdingTier;
} {
  const scale = baselineBusesPerHr / (baselineBusesPerHr + extraBuses);
  const simLoadFactor = Number((maxLoadFactor * scale).toFixed(2));
  const simPeakLoad = Math.round(peakEstLoad * scale);
  return {
    loadFactor: simLoadFactor,
    peakLoad: simPeakLoad,
    tier: classifyCrowdingTier(simLoadFactor),
  };
}
