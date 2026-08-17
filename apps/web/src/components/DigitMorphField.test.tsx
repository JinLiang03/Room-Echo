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
  it("keeps the perimeter compatible by default and can hide it independently", () => {
    const { container, rerender } = render(
      <DigitMorphField
        lifeState="rest"
        pointCount={120}
        result={null}
        stale={false}
        theme="sofa"
        triplet={activeTriplet}
      />,
    );
    expect(container.querySelector(".digit-field")?.getAttribute("data-show-perimeter"))
      .toBe("true");

    rerender(
      <DigitMorphField
        lifeState="rest"
        pointCount={120}
        result={null}
        showPerimeter={false}
        stale={false}
        theme="sofa"
        triplet={activeTriplet}
      />,
    );
    expect(container.querySelector(".digit-field")?.getAttribute("data-show-perimeter"))
      .toBe("false");
  });

  it("can enable the Home fluid treatment without changing the default field", () => {
    const { container } = render(
      <DigitMorphField
        fluid
        fluidMode="fall_drill"
        lifeState="flow"
        pointCount={120}
        result={null}
        showPerimeter={false}
        stale={false}
        theme="abstract_presence"
        triplet={activeTriplet}
      />,
    );
    expect(container.querySelector(".digit-field")?.getAttribute("data-fluid"))
      .toBe("true");
    expect(container.querySelector(".digit-field")?.getAttribute("data-fluid-mode"))
      .toBe("fall_drill");
    expect(container.querySelector(".digit-field")?.getAttribute("data-show-perimeter"))
      .toBe("false");
  });

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
    act(() => vi.advanceTimersByTime(3_200));
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
