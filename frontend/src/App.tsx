import { useCallback, useEffect, useRef, useState } from "react";
import { fetchHealth } from "./api";
import { CommuterPlanner } from "./components/CommuterPlanner";
import { OperatorDashboard } from "./components/OperatorDashboard";
import type { HealthResponse } from "./types";

type ActiveTab = "commuter" | "operator";

export function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("commuter");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [announcement, setAnnouncement] = useState("");

  const commuterTabRef = useRef<HTMLButtonElement>(null);
  const operatorTabRef = useRef<HTMLButtonElement>(null);
  const commuterPanelRef = useRef<HTMLDivElement>(null);
  const operatorPanelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then(setHealth)
      .catch(() => {
        setHealth(null);
      });
    return () => controller.abort();
  }, []);

  // Sync tab state when browser Find-in-Page reveals a hidden="until-found" panel
  useEffect(() => {
    const cPanel = commuterPanelRef.current;
    const oPanel = operatorPanelRef.current;
    const onCommuterMatch = () => setActiveTab("commuter");
    const onOperatorMatch = () => setActiveTab("operator");

    cPanel?.addEventListener("beforematch", onCommuterMatch);
    oPanel?.addEventListener("beforematch", onOperatorMatch);
    return () => {
      cPanel?.removeEventListener("beforematch", onCommuterMatch);
      oPanel?.removeEventListener("beforematch", onOperatorMatch);
    };
  }, []);

  const announce = useCallback((message: string) => {
    setAnnouncement(message);
  }, []);

  function handleTabKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (
      e.key === "ArrowRight" ||
      e.key === "ArrowLeft" ||
      e.key === "Home" ||
      e.key === "End"
    ) {
      e.preventDefault();
      const next: ActiveTab =
        e.key === "Home"
          ? "commuter"
          : e.key === "End"
          ? "operator"
          : activeTab === "commuter"
          ? "operator"
          : "commuter";
      setActiveTab(next);
      const targetBtn =
        next === "commuter" ? commuterTabRef.current : operatorTabRef.current;
      targetBtn?.focus();
      targetBtn?.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
  }

  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link visually-hidden">
        Skip to main content
      </a>

      <header className="app-header">
        <div className="header-inner">
          <div className="brand-lockup">
            <div className="brand-mark" aria-hidden="true">
              CW
            </div>
            <div>
              <h1 id="main-content" className="brand-title" tabIndex={-1}>
                CrowdWise Delhi
              </h1>
              <p className="brand-subtitle">
                Bus Crowding Intelligence &amp; Journey Planner
              </p>
            </div>
          </div>

          <div className="status-badge" aria-live="polite">
            <span
              className={`status-dot${
                health?.db_ready ? "" : " is-offline"
              }`}
              aria-hidden="true"
            />
            {health ? (
              health.db_ready ? (
                <span>
                  {health.routes_indexed} routes · {health.stops_indexed} stops ready
                </span>
              ) : (
                <span>API online · DB pending</span>
              )
            ) : (
              <span>Connecting to API…</span>
            )}
          </div>
        </div>
      </header>

      <main className="main-container">
        <div className="tabs-root">
          <div
            role="tablist"
            aria-label="CrowdWise Delhi workspaces"
            className="tablist"
            onKeyDown={handleTabKeyDown}
          >
            <button
              ref={commuterTabRef}
              id="tab-commuter"
              type="button"
              role="tab"
              aria-selected={activeTab === "commuter"}
              tabIndex={activeTab === "commuter" ? 0 : -1}
              className="tab-button"
              onClick={() => setActiveTab("commuter")}
            >
              Commuter Planner (Passengers)
            </button>
            <button
              ref={operatorTabRef}
              id="tab-operator"
              type="button"
              role="tab"
              aria-selected={activeTab === "operator"}
              tabIndex={activeTab === "operator" ? 0 : -1}
              className="tab-button"
              onClick={() => setActiveTab("operator")}
            >
              Operator &amp; Planner (Schedulers)
            </button>
          </div>

          <div className="tab-panels">
            <div
              ref={commuterPanelRef}
              role="tabpanel"
              aria-labelledby="tab-commuter"
              className="tab-panel"
              hidden={
                activeTab === "commuter"
                  ? undefined
                  : ("until-found" as unknown as boolean)
              }
            >
              <CommuterPlanner onAnnounce={announce} />
            </div>

            <div
              ref={operatorPanelRef}
              role="tabpanel"
              aria-labelledby="tab-operator"
              className="tab-panel"
              hidden={
                activeTab === "operator"
                  ? undefined
                  : ("until-found" as unknown as boolean)
              }
            >
              <OperatorDashboard onAnnounce={announce} />
            </div>
          </div>
        </div>

        <div className="visually-hidden" aria-live="polite" aria-atomic="true">
          {announcement}
        </div>
      </main>

      <footer className="app-footer">
        CrowdWise Delhi · Crowding thresholds: Seats Available (&le;0.85x) · Standing
        Room (0.86x–1.35x) · Crowded (&gt;1.35x)
      </footer>
    </div>
  );
}

export default App;
