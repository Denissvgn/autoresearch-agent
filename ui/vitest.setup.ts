// Vitest setup (ARC-011 P3-029). Adds jest-dom matchers globally so component
// assertions read naturally (`expect(el).toBeInTheDocument()`). Kept minimal —
// per-test files mock the api client and any side-effectful modules they need.
import '@testing-library/jest-dom/vitest';

// jsdom omits ResizeObserver; recharts' ResponsiveContainer (used by
// MetricsChart) reads it at mount. Polyfill a no-op observer so the chart's
// series-selection logic is testable without a real layout engine.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;

