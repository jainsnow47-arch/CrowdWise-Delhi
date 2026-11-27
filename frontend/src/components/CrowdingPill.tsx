import type { CrowdingTier } from "../types";
import { TIER_META } from "../utils/crowding";

interface CrowdingPillProps {
  tier: CrowdingTier;
  loadFactor?: number;
}

function TierIcon({ tier }: { tier: CrowdingTier }) {
  if (tier === "seats_available") {
    return (
      <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
        <path d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13Zm3.03 5.28-3.6 3.75a.75.75 0 0 1-1.08 0L4.97 9.15a.75.75 0 1 1 1.06-1.06l.86.86 3.06-3.2a.75.75 0 0 1 1.08 1.03Z" />
      </svg>
    );
  }
  if (tier === "standing_room") {
    return (
      <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
        <path d="M7.35 2.38a.75.75 0 0 1 1.3 0l5.5 9.5A.75.75 0 0 1 13.5 13h-11a.75.75 0 0 1-.65-1.12l5.5-9.5ZM8 6a.75.75 0 0 0-.75.75v2.5a.75.75 0 0 0 1.5 0v-2.5A.75.75 0 0 0 8 6Zm0 5.5a.85.85 0 1 0 0-1.7.85.85 0 0 0 0 1.7Z" />
      </svg>
    );
  }
  return (
    <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
      <path d="M5.28 2h5.44L14 5.28v5.44L10.72 14H5.28L2 10.72V5.28L5.28 2ZM8 4.75a.75.75 0 0 0-.75.75v3a.75.75 0 0 0 1.5 0v-3a.75.75 0 0 0-.75-.75Zm0 6.5a.85.85 0 1 0 0-1.7.85.85 0 0 0 0 1.7Z" />
    </svg>
  );
}

export function CrowdingPill({ tier, loadFactor }: CrowdingPillProps) {
  const meta = TIER_META[tier];
  return (
    <span className={`crowding-pill tier-${tier}`} title={meta.description}>
      <TierIcon tier={tier} />
      <span>{meta.label}</span>
      {typeof loadFactor === "number" && (
        <span>({loadFactor.toFixed(2)}x)</span>
      )}
    </span>
  );
}
