import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SimulatedCareScenario } from "../generated/contracts";
import { simulatedCareScenarios } from "../generated/fixtures";
import { useCareScenario } from "../lib/care-state";
import {
  CARE_MOMENT_INTERVAL_MS,
  CareScenarioProvider,
} from "./CareScenarioProvider";

const apiMocks = vi.hoisted(() => ({
  fetchCareScenario: vi.fn(),
}));

vi.mock("../lib/api", () => ({
  fetchCareScenario: apiMocks.fetchCareScenario,
}));

function CareStateProbe() {
  const care = useCareScenario();
  return (
    <output
      aria-label="care state"
      data-enabled={String(care.enabled)}
      data-moment={care.moment?.moment ?? "none"}
      data-scenario={care.scenario?.scenario_id ?? "none"}
      data-selected={care.selectedMoment}
      data-status={care.status}
    />
  );
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

function changeHash(hash: string) {
  act(() => {
    window.location.hash = hash;
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
}

describe("CareScenarioProvider accelerated home day", () => {
  beforeEach(() => {
    window.location.hash = "/home";
    apiMocks.fetchCareScenario.mockReset();
    apiMocks.fetchCareScenario.mockResolvedValue(simulatedCareScenarios[0]);
  });

  afterEach(() => vi.useRealTimers());

  it("loads the full scenario once on default home and cycles in time order", async () => {
    vi.useFakeTimers();
    render(
      <CareScenarioProvider>
        <CareStateProbe />
      </CareScenarioProvider>,
    );
    const state = screen.getByLabelText("care state");

    expect(state.getAttribute("data-enabled")).toBe("true");
    expect(state.getAttribute("data-selected")).toBe("routine");
    expect(state.getAttribute("data-status")).toBe("loading");
    expect(apiMocks.fetchCareScenario).toHaveBeenCalledTimes(1);
    expect(apiMocks.fetchCareScenario.mock.calls[0]?.[0]).toBe("routine");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(state.getAttribute("data-status")).toBe("ready");
    expect(state.getAttribute("data-moment")).toBe("routine");

    for (const expected of [
      "bathroom_timeout",
      "fall_drill",
      "pet_night",
      "routine",
    ]) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(CARE_MOMENT_INTERVAL_MS);
      });
      expect(state.getAttribute("data-moment")).toBe(expected);
    }
    expect(apiMocks.fetchCareScenario).toHaveBeenCalledTimes(1);
    expect(window.location.hash).toBe("#/home");
  });

  it("uses a valid care query only as the first frame and falls invalid values back to routine", async () => {
    window.location.hash = "/home?care=fall_drill";
    const { unmount } = render(
      <CareScenarioProvider>
        <CareStateProbe />
      </CareScenarioProvider>,
    );
    const state = screen.getByLabelText("care state");
    await waitFor(() => expect(state.getAttribute("data-status")).toBe("ready"));
    expect(state.getAttribute("data-moment")).toBe("fall_drill");
    expect(apiMocks.fetchCareScenario).toHaveBeenCalledTimes(1);
    unmount();

    apiMocks.fetchCareScenario.mockClear();
    window.location.hash = "/home?care=not-a-moment";
    render(
      <CareScenarioProvider>
        <CareStateProbe />
      </CareScenarioProvider>,
    );
    const fallback = screen.getByLabelText("care state");
    await waitFor(() => expect(fallback.getAttribute("data-status")).toBe("ready"));
    expect(fallback.getAttribute("data-moment")).toBe("routine");
    expect(apiMocks.fetchCareScenario).toHaveBeenCalledTimes(1);
  });

  it("stops the care day and ignores a late response after leaving home", async () => {
    const scenario = deferred<SimulatedCareScenario>();
    apiMocks.fetchCareScenario.mockReturnValueOnce(scenario.promise);
    render(
      <CareScenarioProvider>
        <CareStateProbe />
      </CareScenarioProvider>,
    );
    const state = screen.getByLabelText("care state");
    await waitFor(() => expect(apiMocks.fetchCareScenario).toHaveBeenCalledTimes(1));

    changeHash("/replay");
    expect(state.getAttribute("data-enabled")).toBe("false");
    expect(state.getAttribute("data-status")).toBe("idle");
    expect(state.getAttribute("data-scenario")).toBe("none");

    await act(async () => scenario.resolve(simulatedCareScenarios[0]));
    expect(state.getAttribute("data-enabled")).toBe("false");
    expect(state.getAttribute("data-scenario")).toBe("none");
  });

  it("marks a malformed 200 response unavailable instead of throwing", async () => {
    apiMocks.fetchCareScenario.mockResolvedValueOnce({
      schema_version: "simulated-care-scenario.v2",
      moments: [{ moment: "routine" }],
    });
    render(
      <CareScenarioProvider>
        <CareStateProbe />
      </CareScenarioProvider>,
    );
    const state = screen.getByLabelText("care state");

    await waitFor(() => {
      expect(state.getAttribute("data-status")).toBe("unavailable");
    });
    expect(state.getAttribute("data-enabled")).toBe("true");
    expect(state.getAttribute("data-moment")).toBe("none");
    expect(state.getAttribute("data-scenario")).toBe("none");
  });
});
