import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { signalTriplets } from "../generated/fixtures";
import type { SignalTriplet } from "../lib/types";
import { DigitMorphField } from "./DigitMorphField";

const activeTriplet = signalTriplets[1] as SignalTriplet;

afterEach(() => {
  vi.useRealTimers();
});

describe("DigitMorphField theme lifecycle", () => {
  it("accepts a dynamic theme after its one-time spatial introduction", () => {
    vi.useFakeTimers();
    const { container, rerender, unmount } = render(
      <DigitMorphField
        autoMorph
        lifeState="rest"
        pointCount={120}
        result={null}
        stale={false}
        theme="sofa"
        triplet={activeTriplet}
      />,
    );
    const field = () => container.querySelector(".digit-field");

    expect(field()?.getAttribute("data-visual-stage")).toBe("floorplan");
    act(() => vi.advanceTimersByTime(1_200));
    expect(field()?.getAttribute("data-visual-stage")).toBe("volume");
    act(() => vi.advanceTimersByTime(2_000));
    expect(field()?.getAttribute("data-visual-stage")).toBe("sofa");

    rerender(
      <DigitMorphField
        autoMorph
        lifeState="rest"
        pointCount={120}
        result={null}
        stale={false}
        theme="lounge"
        triplet={activeTriplet}
      />,
    );
    expect(field()?.getAttribute("data-visual-stage")).toBe("river");
    act(() => vi.advanceTimersByTime(1_450));
    expect(field()?.getAttribute("data-visual-stage")).toBe("lounge");
    unmount();
  });
});
