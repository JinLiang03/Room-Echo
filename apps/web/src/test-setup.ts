import { vi } from "vitest";

// React 18 requires this flag so act(...) warnings are not emitted in tests.
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

// JSDOM deliberately leaves Canvas unimplemented and logs an error even when
// application code handles the null/throw fallback. Unit tests exercise that
// fallback; real drawing behavior is covered by Playwright and the perf smoke.
HTMLCanvasElement.prototype.getContext = vi.fn(() => null);

// Lenis reads the reduced-motion media query during construction. JSDOM does
// not implement matchMedia, so provide the browser-shaped no-match default;
// reduced-motion behavior itself remains covered by real-browser tests.
Object.defineProperty(window, "matchMedia", {
  configurable: true,
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(() => false),
  })),
});

class ResizeObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

vi.stubGlobal("ResizeObserver", ResizeObserverMock);

// JSDOM does not implement scrolling. App route changes deliberately reset
// scroll position; mock only the browser primitive so tests stay noise-free.
Object.defineProperty(window, "scrollTo", {
  configurable: true,
  writable: true,
  value: vi.fn(),
});
