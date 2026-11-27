import { useId, useState } from "react";
import { planJourney } from "../api";
import type {
  DayType,
  JourneyOption,
  PlanResponse,
  Preference,
  StretchCrowding,
} from "../types";
import {
  DAY_TYPE_OPTIONS,
  TIER_META,
  clockToMinutes,
  formatMinutesToClock,
} from "../utils/crowding";
import { CrowdingPill } from "./CrowdingPill";
import { StopAutocomplete } from "./StopAutocomplete";

interface CommuterPlannerProps {
  onAnnounce: (message: string) => void;
}

const PREFERENCE_OPTIONS: ReadonlyArray<{ value: Preference; label: string }> = [
  { value: "fastest", label: "Fastest" },
  { value: "balanced", label: "Balanced" },
  { value: "comfort", label: "Comfort (Least Crowded)" },
];

function StretchBar({
  optionId,
  stretches,
}: {
  optionId: string;
  stretches: StretchCrowding[];
}) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  if (stretches.length === 0) return null;
  const activeStretch =
    selectedIdx !== null && stretches[selectedIdx] ? stretches[selectedIdx] : null;

  return (
    <div className="stretch-bar-section">
      <div className="stretch-bar-label">
        <span>Per-stretch crowding profile ({stretches.length} stretches)</span>
        <span>Select a segment to inspect load</span>
      </div>
      <div className="stretch-bar" role="group" aria-label={`Stretches for ${optionId}`}>
        {stretches.map((stretch, idx) => {
          const tierLabel = TIER_META[stretch.crowding_tier].label;
          const isSelected = selectedIdx === idx;
          return (
            <button
              key={`${optionId}-seg-${stretch.seq_idx}`}
              type="button"
              className={`stretch-segment tier-${stretch.crowding_tier}${
                isSelected ? " is-selected" : ""
              }`}
              aria-pressed={isSelected}
              aria-label={`${stretch.from_stop} to ${stretch.to_stop}: ${tierLabel}, ${stretch.load_factor.toFixed(
                2
              )}x capacity`}
              title={`${stretch.from_stop} → ${stretch.to_stop} (${tierLabel}, ${stretch.load_factor.toFixed(
                2
              )}x)`}
              onClick={() => setSelectedIdx(isSelected ? null : idx)}
            />
          );
        })}
      </div>
      {activeStretch && (
        <div className="stretch-inspector">
          <span>
            <strong>
              {activeStretch.from_stop} → {activeStretch.to_stop}
            </strong>
          </span>
          <span>
            {TIER_META[activeStretch.crowding_tier].label} ·{" "}
            {activeStretch.load_factor.toFixed(2)}x seated cap ·{" "}
            {Math.round(activeStretch.est_total_load)} est. pax ({activeStretch.confidence} conf.)
          </span>
        </div>
      )}
    </div>
  );
}

function JourneyOptionCard({ option }: { option: JourneyOption }) {
  const allStretches = option.legs.flatMap((leg) => leg.stretches);
  const routeSummary = option.legs.map((l) => l.route_id).join(" → ");
  const transferLabel =
    option.transfers === 0
      ? "Direct (0 transfers)"
      : `${option.transfers} ${option.transfers === 1 ? "transfer" : "transfers"}`;

  return (
    <li className="option-card">
      <div className="option-header">
        <div className="option-tag-group">
          <span className="option-tag">{option.tag}</span>
          <span className="route-chip">Route {routeSummary}</span>
        </div>
        <CrowdingPill tier={option.worst_tier} loadFactor={option.max_load_factor} />
      </div>

      <div className="option-metrics">
        <span className="metric-duration">{option.total_minutes} min</span>
        <span className="metric-sub">{transferLabel}</span>
        <span className="metric-sub">
          {formatMinutesToClock(option.depart_min)} →{" "}
          {formatMinutesToClock(option.arrive_min)}
        </span>
        <span className="metric-sub">
          Avg load {option.avg_load_factor.toFixed(2)}x
        </span>
      </div>

      {option.legs.map((leg, i) => (
        <div key={`${option.id}-leg-${i}`} className="metric-sub">
          Leg {i + 1}: {leg.from_stop} → {leg.to_stop} ({leg.stop_count} stops)
        </div>
      ))}

      <StretchBar optionId={option.id} stretches={allStretches} />
    </li>
  );
}

export function CommuterPlanner({ onAnnounce }: CommuterPlannerProps) {
  const formTitleId = useId();

  const [originHub, setOriginHub] = useState("");
  const [destHub, setDestHub] = useState("");
  const [dayType, setDayType] = useState<DayType>("weekday");
  const [departTime, setDepartTime] = useState("18:00");
  const [preference, setPreference] = useState<Preference>("balanced");

  const [fieldErrors, setFieldErrors] = useState<{
    origin?: string;
    dest?: string;
  }>({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [result, setResult] = useState<PlanResponse | null>(null);

  async function executePlan(overrideClock?: string) {
    const o = originHub.trim();
    const d = destHub.trim();
    const nextErrors: { origin?: string; dest?: string } = {};
    if (o.length < 2) nextErrors.origin = "Select an origin stop hub.";
    if (d.length < 2) nextErrors.dest = "Select a destination stop hub.";
    if (o && d && o.toLowerCase() === d.toLowerCase()) {
      nextErrors.dest = "Destination must differ from origin.";
    }
    setFieldErrors(nextErrors);
    if (nextErrors.origin || nextErrors.dest) {
      const targetId = nextErrors.origin ? "origin-hub" : "dest-hub";
      document.getElementById(targetId)?.focus();
      onAnnounce("Please correct the highlighted origin or destination stop.");
      return;
    }

    const clock = overrideClock ?? departTime;
    if (overrideClock) setDepartTime(overrideClock);

    setLoading(true);
    setApiError(null);
    try {
      const data = await planJourney({
        origin_hub: o,
        dest_hub: d,
        day_type: dayType,
        depart_min: clockToMinutes(clock),
        preference,
      });
      setResult(data);
      onAnnounce(
        data.options.length > 0
          ? `Found ${data.options.length} route options from ${o} to ${d}.`
          : `No direct route options found between ${o} and ${d}.`
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to plan journey.";
      setApiError(msg);
      onAnnounce(`Journey planning error: ${msg}`);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    void executePlan();
  }

  function handleSwap() {
    setOriginHub(destHub);
    setDestHub(originHub);
    setFieldErrors({});
  }

  return (
    <div className="panel-body">
      <section className="surface-card" aria-labelledby={formTitleId}>
        <h2 id={formTitleId} className="section-heading">
          Plan a Crowding-Aware Bus Journey
        </h2>
        <p className="section-lead">
          Compare Delhi bus options by travel time, transfers, and predicted segment crowding.
        </p>

        <search>
          <form className="planner-form" onSubmit={handleSubmit} aria-labelledby={formTitleId} noValidate>
            <div className="stops-row">
              <StopAutocomplete
                id="origin-hub"
                name="origin_hub"
                label="Origin stop hub"
                value={originHub}
                placeholder="e.g. Kashmere Gate"
                errorText={fieldErrors.origin}
                onChange={(val) => {
                  setOriginHub(val);
                  if (fieldErrors.origin) setFieldErrors((p) => ({ ...p, origin: undefined }));
                }}
              />

              <button
                type="button"
                className="swap-btn"
                aria-label="Swap origin and destination stops"
                onClick={handleSwap}
              >
                ⇄ Swap
              </button>

              <StopAutocomplete
                id="dest-hub"
                name="dest_hub"
                label="Destination stop hub"
                value={destHub}
                placeholder="e.g. Nehru Place"
                errorText={fieldErrors.dest}
                onChange={(val) => {
                  setDestHub(val);
                  if (fieldErrors.dest) setFieldErrors((p) => ({ ...p, dest: undefined }));
                }}
              />
            </div>

            <div className="controls-grid">
              <fieldset className="radio-fieldset">
                <legend className="radio-legend">Day type</legend>
                <div className="radio-group">
                  {DAY_TYPE_OPTIONS.map((opt) => (
                    <label key={opt.value} className="radio-option" htmlFor={`planner-day-${opt.value}`}>
                      <input
                        id={`planner-day-${opt.value}`}
                        type="radio"
                        name="planner_day_type"
                        value={opt.value}
                        checked={dayType === opt.value}
                        onChange={() => setDayType(opt.value)}
                      />
                      <span>{opt.label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>

              <div className="field">
                <label className="field-label" htmlFor="depart-time">
                  Departure time
                </label>
                <span id="depart-time-hint" className="field-hint">
                  24-hour local IST departure window.
                </span>
                <input
                  id="depart-time"
                  name="depart_time"
                  type="time"
                  className="time-input"
                  aria-describedby="depart-time-hint"
                  value={departTime}
                  onChange={(e) => setDepartTime(e.target.value || "18:00")}
                />
              </div>

              <fieldset className="radio-fieldset">
                <legend className="radio-legend">Route preference</legend>
                <div className="radio-group">
                  {PREFERENCE_OPTIONS.map((opt) => (
                    <label key={opt.value} className="radio-option" htmlFor={`pref-${opt.value}`}>
                      <input
                        id={`pref-${opt.value}`}
                        type="radio"
                        name="preference"
                        value={opt.value}
                        checked={preference === opt.value}
                        onChange={() => setPreference(opt.value)}
                      />
                      <span>{opt.label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>

            <div className="form-actions">
              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? "Finding routes…" : "Find Bus Options"}
              </button>
            </div>
          </form>
        </search>
      </section>

      {apiError && (
        <div role="alert" className="banner banner-error">
          <span>{apiError}</span>
        </div>
      )}

      {result?.leave_later_tip && (
        <div className="banner banner-tip" role="region" aria-label="Departure timing suggestion">
          <div>
            <strong>Leave-Later Tip:</strong> {result.leave_later_tip.message}{" "}
            <span>
              (New departure: {formatMinutesToClock(result.leave_later_tip.new_depart_min)})
            </span>
          </div>
          <button
            type="button"
            className="btn-secondary"
            onClick={() =>
              void executePlan(
                formatMinutesToClock(result.leave_later_tip!.new_depart_min)
              )
            }
          >
            Shift +{result.leave_later_tip.shift_minutes} min &amp; Re-check
          </button>
        </div>
      )}

      {result && (
        <section aria-label="Journey options">
          {result.options.length === 0 ? (
            <div className="surface-card empty-state">
              <p>{result.note || "No matching bus routes found for these hubs at this time."}</p>
            </div>
          ) : (
            <ul className="options-list">
              {result.options.map((opt) => (
                <JourneyOptionCard key={opt.id} option={opt} />
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
