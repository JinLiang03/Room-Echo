import { describe, expect, it } from "vitest";
import { SignalCard } from "./SignalCard";
import { renderWithStream } from "../test-utils";
import type { SignalTriplet } from "../lib/types";
import { signalTriplets } from "../generated/fixtures";

const validTriplet = signalTriplets[1] as SignalTriplet;

function renderCard(
  triplet: SignalTriplet | null,
  stale = false,
  history: SignalTriplet[] = [],
) {
  return renderWithStream(
    <SignalCard
      kind="motion"
      triplet={triplet}
      history={history}
      result={null}
      stale={stale}
      now={Date.now()}
      lastEventAt={Date.now()}
    />,
  );
}

describe("SignalCard", () => {
  it("shows value and measurement/model/agreement scores for valid data", () => {
    const { getByText, getByLabelText } = renderCard(validTriplet);
    expect(getByLabelText("运动强度变化曲线")).toBeDefined();
    expect(getByText("测量质量")).toBeDefined();
    expect(getByText("模型支持")).toBeDefined();
    expect(getByText("推理一致性")).toBeDefined();
  });

  it("renders unknown state without residual values", () => {
    const unknown: SignalTriplet = {
      ...validTriplet,
      status: "insufficient_signal",
      motion: { value: 0, state: "unknown", confidence: 0 },
      occupancy_density: {
        probabilities: { low: 0, medium: 0, high: 0, unknown: 1 },
        state: "unknown",
        confidence: 0,
      },
      depth_zone: {
        probabilities: { near: 0, mid: 0, far: 0, unknown: 1 },
        state: "unknown",
        confidence: 0,
      },
      sensor_confidence_cap: 0,
    };
    const { container } = renderCard(unknown);
    expect(container.querySelector(".card-state-unknown")).not.toBeNull();
  });

  it("shows placeholder when stale (no previous value residue)", () => {
    const { container } = renderCard(validTriplet, true);
    expect(container.querySelector(".card-state-stale")).not.toBeNull();
    expect(container.textContent).toContain("—");
  });

  it("shows degraded state with status label", () => {
    const degraded: SignalTriplet = { ...validTriplet, status: "degraded" };
    const { container } = renderCard(degraded);
    expect(container.querySelector(".card-state-degraded")).not.toBeNull();
  });

  it("plots the bounded real motion history instead of only the latest value", () => {
    const history = [
      { ...validTriplet, window_id: "history-1", motion: { ...validTriplet.motion, value: 0.1 } },
      { ...validTriplet, window_id: "history-2", motion: { ...validTriplet.motion, value: 0.9 } },
    ];
    const { container } = renderCard(history[1], false, history);
    const points = container.querySelector("polyline")?.getAttribute("points") ?? "";
    expect(points.split(" ")).toHaveLength(2);
    expect(points).not.toContain("NaN");
  });
});
