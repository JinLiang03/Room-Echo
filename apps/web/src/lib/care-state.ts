import { createContext, useContext } from "react";
import type {
  SimulatedCareMoment,
  SimulatedCareScenario,
} from "../generated/contracts";

export type CareMomentKey = SimulatedCareScenario["selected_moment"];
export type CareLoadStatus = "idle" | "loading" | "ready" | "unavailable";

export interface CareScenarioState {
  enabled: boolean;
  scenario: SimulatedCareScenario | null;
  moment: SimulatedCareMoment | null;
  selectedMoment: CareMomentKey;
  status: CareLoadStatus;
  error: string | null;
  selectMoment: (moment: CareMomentKey) => void;
}

export const EMPTY_CARE_SCENARIO_STATE: CareScenarioState = {
  enabled: false,
  scenario: null,
  moment: null,
  selectedMoment: "bathroom_timeout",
  status: "idle",
  error: null,
  selectMoment: () => undefined,
};

export const CareScenarioContext = createContext<CareScenarioState>(
  EMPTY_CARE_SCENARIO_STATE,
);

export function useCareScenario(): CareScenarioState {
  return useContext(CareScenarioContext);
}
