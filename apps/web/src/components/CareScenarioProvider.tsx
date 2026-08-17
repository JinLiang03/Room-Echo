import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { SimulatedCareScenario } from "../generated/contracts";
import { fetchCareScenario } from "../lib/api";
import {
  CareScenarioContext,
  type CareLoadStatus,
  type CareMomentKey,
} from "../lib/care-state";
import {
  CARE_MOMENT_ORDER,
  isCareScenarioPayload,
  nextCareMoment,
  selectedCareMoment,
} from "../lib/care";
import { parseHash, routeParams } from "../lib/router";

const VALID_MOMENTS = new Set<CareMomentKey>([
  "routine",
  "bathroom_timeout",
  "fall_drill",
  "pet_night",
]);

export const CARE_MOMENT_INTERVAL_MS = 8_000;

export function CareScenarioProvider({ children }: { children: ReactNode }) {
  const [initialSelection] = useState(readRouteSelection);
  const [enabled, setEnabled] = useState(initialSelection.enabled);
  const [selectedMoment, setSelectedMoment] = useState(initialSelection.moment);
  const [scenario, setScenario] = useState<SimulatedCareScenario | null>(null);
  const [status, setStatus] = useState<CareLoadStatus>(
    initialSelection.enabled ? "loading" : "idle",
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const syncSelection = () => {
      const next = readRouteSelection();
      setEnabled(next.enabled);
      setSelectedMoment(next.moment);
      if (!next.enabled) {
        setScenario(null);
        setStatus("idle");
        setError(null);
      }
    };
    window.addEventListener("hashchange", syncSelection);
    return () => window.removeEventListener("hashchange", syncSelection);
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setScenario(null);
    setStatus("loading");
    setError(null);
    // One response contains the complete ordered day. The URL parameter only
    // chooses the first frame; cycling never re-fetches or changes the URL.
    void fetchCareScenario(CARE_MOMENT_ORDER[0], controller.signal)
      .then((payload) => {
        if (controller.signal.aborted) return;
        if (!isCareScenarioPayload(payload)) {
          throw new Error("care scenario payload failed runtime validation");
        }
        setScenario(payload);
        setStatus("ready");
        setError(null);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setStatus("unavailable");
        setError(reason instanceof Error ? reason.message : "care scenario unavailable");
      });
    return () => controller.abort();
  }, [enabled]);

  useEffect(() => {
    if (!enabled || status !== "ready" || scenario === null) return;
    const timer = window.setInterval(() => {
      setSelectedMoment((current) => nextCareMoment(current));
    }, CARE_MOMENT_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [enabled, scenario, status]);

  const selectMoment = useCallback((moment: CareMomentKey) => {
    setSelectedMoment(moment);
  }, []);

  const value = useMemo(
    () => ({
      enabled,
      scenario: enabled ? scenario : null,
      moment: enabled
        ? selectedCareMoment(scenario, selectedMoment)
        : null,
      selectedMoment,
      status: enabled ? status : "idle",
      error: enabled ? error : null,
      selectMoment,
    }),
    [enabled, error, scenario, selectMoment, selectedMoment, status],
  );

  return (
    <CareScenarioContext.Provider value={value}>
      {children}
    </CareScenarioContext.Provider>
  );
}

function readRouteSelection(): {
  enabled: boolean;
  moment: CareMomentKey;
} {
  if (parseHash() !== "home") {
    return { enabled: false, moment: "routine" };
  }
  const candidate = routeParams().get("care") as CareMomentKey | null;
  return {
    enabled: true,
    moment: candidate && VALID_MOMENTS.has(candidate) ? candidate : "routine",
  };
}
