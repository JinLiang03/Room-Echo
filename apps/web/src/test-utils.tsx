import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import type { SimulatedCareScenario } from "./generated/contracts";
import { selectedCareMoment } from "./lib/care";
import { CareScenarioContext, type CareMomentKey } from "./lib/care-state";
import { StreamContext, type StreamControls } from "./lib/state";
import type { StreamState } from "./lib/types";
import { initialState } from "./lib/state";

export const STUB_CONTROLS: StreamControls = {
  pause: () => undefined,
  resume: () => undefined,
  step: () => undefined,
  seek: () => undefined,
  rate: () => undefined,
  record: () => undefined,
  start: async () => undefined,
  stop: async () => undefined,
  loadBundles: async () => undefined,
  setSettings: () => undefined,
};

export function renderWithStream(
  ui: ReactNode,
  state: StreamState = initialState(),
) {
  return render(
    <StreamContext.Provider value={{ state, controls: STUB_CONTROLS }}>
      {ui}
    </StreamContext.Provider>,
  );
}

export function renderWithStreamAndCare(
  ui: ReactNode,
  scenario: SimulatedCareScenario,
  state: StreamState = initialState(),
  selectedMoment: CareMomentKey = "bathroom_timeout",
) {
  return render(
    <StreamContext.Provider value={{ state, controls: STUB_CONTROLS }}>
      <CareScenarioContext.Provider
        value={{
          enabled: true,
          scenario,
          moment: selectedCareMoment(scenario, selectedMoment),
          selectedMoment,
          status: "ready",
          error: null,
          selectMoment: () => undefined,
        }}
      >
        {ui}
      </CareScenarioContext.Provider>
    </StreamContext.Provider>,
  );
}
