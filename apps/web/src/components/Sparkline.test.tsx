import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Sparkline } from "./Sparkline";

describe("Sparkline", () => {
  it("renders one finite centered point without NaN coordinates", () => {
    const { container } = render(
      <Sparkline values={[0.4]} width={200} ariaLabel="单点曲线" />,
    );
    const points = container.querySelector("polyline")?.getAttribute("points");
    expect(points).toBe("100.0,28.2");
    expect(container.innerHTML).not.toContain("NaN");
    expect(container.querySelector("circle")?.getAttribute("cx")).toBe("100");
  });

  it("bounds invalid samples instead of emitting invalid SVG", () => {
    const { container } = render(
      <Sparkline values={[Number.NaN, -1, 2]} ariaLabel="容错曲线" />,
    );
    expect(container.innerHTML).not.toContain("NaN");
    expect(container.innerHTML).not.toContain("Infinity");
  });
});
