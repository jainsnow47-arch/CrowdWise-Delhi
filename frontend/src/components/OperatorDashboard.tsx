import { useEffect, useId, useMemo, useState } from "react";
import { fetchOverloadedRoutes } from "../api";
import type { BottleneckRoute, DayType } from "../types";
import {
  DAY_TYPE_OPTIONS,
  classifyCrowdingTier,
  formatHourRange,
  simulateExtraBuses,
} from "../utils/crowding";
import { CrowdingPill } from "./CrowdingPill";

interface OperatorDashboardProps {
  onAnnounce: (message: string) => void;
}

const MIN_HOUR = 5;
const MAX_HOUR = 23;
const BASELINE_FREQUENCIES = [2, 3, 4, 6] as const;

export function OperatorDashboard({ onAnnounce }: OperatorDashboardProps) {
  const sectionTitleId = useId();
  const tableCaptionId = useId();
  const sliderId = useId();
  const baselineId = useId();

  const [dayType, setDayType] = useState<DayType>("weekday");
  const [hour, setHour] = useState<number>(18);
  const [bottlenecks, setBottlenecks] = useState<BottleneckRoute[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Simulator state: assumed baseline buses/hr and extra buses per route_id
  const [baselineBuses, setBaselineBuses] = useState<number>(3);
  const [extraBusesMap, setExtraBusesMap] = useState<Record<string, number>>({});

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    fetchOverloadedRoutes(dayType, hour, 25, controller.signal)
      .then((data) => {
        setBottlenecks(data.bottlenecks ?? []);
        onAnnounce(
          `Loaded ${data.bottlenecks?.length ?? 0} bottleneck routes for ${dayType.replace(
            "_",
            " "
          )} at ${formatHourRange(hour)}.`
        );
      })
      .catch((err) => {
        if ((err as Error).name !== "AbortError") {
          setError(
            err instanceof Error ? err.message : "Failed to load bottleneck analytics."
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [dayType, hour, onAnnounce]);

  const sliderProgress = ((hour - MIN_HOUR) / (MAX_HOUR - MIN_HOUR)) * 100;

  function setRouteExtra(routeId: string, extra: number) {
    setExtraBusesMap((prev) => ({ ...prev, [routeId]: extra }));
  }

  function applyAllExtra(extra: number) {
    if (extra === 0) {
      setExtraBusesMap({});
      return;
    }
    const next: Record<string, number> = {};
    for (const row of bottlenecks) {
      next[row.route_id] = extra;
    }
    setExtraBusesMap(next);
  }

  const summary = useMemo(() => {
    let baseCrowded = 0;
    let simCrowded = 0;
    let totalExtra = 0;
    for (const row of bottlenecks) {
      const extra = extraBusesMap[row.route_id] ?? 0;
      totalExtra += extra;
      if (classifyCrowdingTier(row.max_load_factor) === "crowded") {
        baseCrowded += 1;
      }
      const sim = simulateExtraBuses(
        row.max_load_factor,
        row.peak_est_load,
        baselineBuses,
        extra
      );
      if (sim.tier === "crowded") {
        simCrowded += 1;
      }
    }
    return {
      baseCrowded,
      simCrowded,
      resolved: Math.max(0, baseCrowded - simCrowded),
      totalExtra,
    };
  }, [bottlenecks, extraBusesMap, baselineBuses]);

  return (
    <div className="panel-body">
      <section className="surface-card" aria-labelledby={sectionTitleId}>
        <h2 id={sectionTitleId} className="section-heading">
          Network Bottlenecks &amp; Extra Bus Simulator
        </h2>
        <p className="section-lead">
          Inspect peak-load corridors by day type and hour, then simulate adding +1 or +2 extra buses per hour.
        </p>

        <div className="operator-controls">
          <fieldset className="radio-fieldset">
            <legend className="radio-legend">Day type</legend>
            <div className="radio-group">
              {DAY_TYPE_OPTIONS.map((opt) => (
                <label key={opt.value} className="radio-option" htmlFor={`op-day-${opt.value}`}>
                  <input
                    id={`op-day-${opt.value}`}
                    type="radio"
                    name="operator_day_type"
                    value={opt.value}
                    checked={dayType === opt.value}
                    onChange={() => setDayType(opt.value)}
                  />
                  <span>{opt.label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="slider-field">
            <div className="slider-header">
              <label className="field-label" htmlFor={sliderId}>
                Time window (hour)
              </label>
              <span className="hour-readout">{formatHourRange(hour)}</span>
            </div>
            <input
              id={sliderId}
              name="time_bin"
              type="range"
              min={MIN_HOUR}
              max={MAX_HOUR}
              step={1}
              value={hour}
              className="hour-slider"
              style={{ "--progress": `${sliderProgress}%` } as React.CSSProperties}
              aria-valuetext={formatHourRange(hour)}
              onChange={(e) => setHour(Number(e.target.value))}
            />
            <div className="slider-ticks" aria-hidden="true">
              <span>05:00</span>
              <span>11:00</span>
              <span>17:00</span>
              <span>23:00</span>
            </div>
          </div>
        </div>
      </section>

      <section className="surface-card panel-body" aria-label="Fleet dispatch simulation">
        <div className="sim-toolbar">
          <div className="sim-group">
            <label className="field-label" htmlFor={baselineId}>
              Baseline frequency:
            </label>
            <select
              id={baselineId}
              className="sim-select"
              value={baselineBuses}
              onChange={(e) => setBaselineBuses(Number(e.target.value))}
            >
              {BASELINE_FREQUENCIES.map((freq) => (
                <option key={freq} value={freq}>
                  {freq} buses/hr (every {Math.round(60 / freq)} min)
                </option>
              ))}
            </select>
          </div>

          <div className="sim-group" role="group" aria-label="Apply extra buses to all listed routes">
            <span className="field-hint">Bulk simulate:</span>
            <button type="button" className="seg-btn" onClick={() => applyAllExtra(0)}>
              Reset All
            </button>
            <button type="button" className="seg-btn" onClick={() => applyAllExtra(1)}>
              +1 Bus All
            </button>
            <button type="button" className="seg-btn" onClick={() => applyAllExtra(2)}>
              +2 Buses All
            </button>
          </div>
        </div>

        <div className="kpi-strip">
          <div className="kpi-card">
            <div className="kpi-label">Crowded Routes (Base)</div>
            <div className="kpi-value">{summary.baseCrowded}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Crowded Routes (Simulated)</div>
            <div className="kpi-value">{summary.simCrowded}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Bottlenecks Relieved</div>
            <div className="kpi-value">{summary.resolved}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Extra Buses Dispatched</div>
            <div className="kpi-value">+{summary.totalExtra}</div>
          </div>
        </div>

        {error && (
          <div role="alert" className="banner banner-error">
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="empty-state">
            <progress aria-label="Loading bottleneck leaderboard" />
            <p>Loading bottleneck leaderboard…</p>
          </div>
        ) : bottlenecks.length === 0 ? (
          <div className="empty-state">
            <p>No bottleneck data available for {formatHourRange(hour)}.</p>
          </div>
        ) : (
          <div
            tabIndex={0}
            role="region"
            aria-labelledby={tableCaptionId}
            className="table-wrapper"
          >
            <table className="bottleneck-table">
              <caption id={tableCaptionId}>
                Top overloaded routes — {dayType.replace("_", " ")} ({formatHourRange(hour)})
              </caption>
              <thead>
                <tr>
                  <th scope="col">Route</th>
                  <th scope="col">Bus Class</th>
                  <th scope="col">Max Load Factor</th>
                  <th scope="col">Peak Est. Load</th>
                  <th scope="col">Confidence</th>
                  <th scope="col">Extra Bus Simulator</th>
                  <th scope="col">Simulated Load</th>
                </tr>
              </thead>
              <tbody>
                {bottlenecks.map((row) => {
                  const extra = extraBusesMap[row.route_id] ?? 0;
                  const sim = simulateExtraBuses(
                    row.max_load_factor,
                    row.peak_est_load,
                    baselineBuses,
                    extra
                  );
                  return (
                    <tr key={row.route_id}>
                      <th scope="row">{row.route_short_name}</th>
                      <td>{row.bus_class}</td>
                      <td className="mono-cell">
                        <CrowdingPill
                          tier={classifyCrowdingTier(row.max_load_factor)}
                          loadFactor={row.max_load_factor}
                        />
                      </td>
                      <td className="mono-cell">
                        {Math.round(row.peak_est_load)} / {row.seated_cap} seats
                      </td>
                      <td>{row.confidence}</td>
                      <td>
                        <div
                          className="segmented-group"
                          role="group"
                          aria-label={`Extra buses for route ${row.route_short_name}`}
                        >
                          {[0, 1, 2].map((inc) => (
                            <button
                              key={inc}
                              type="button"
                              className="seg-btn"
                              aria-pressed={extra === inc}
                              onClick={() => setRouteExtra(row.route_id, inc)}
                            >
                              {inc === 0 ? "Base" : `+${inc}`}
                            </button>
                          ))}
                        </div>
                      </td>
                      <td className="mono-cell">
                        <div className="sim-delta">
                          <CrowdingPill tier={sim.tier} loadFactor={sim.loadFactor} />
                          {extra > 0 && (
                            <span className="field-hint">
                              ({sim.peakLoad} pax/bus)
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
