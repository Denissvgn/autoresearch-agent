import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Vitest configuration (ARC-011 P3-029). Component contract tests run in jsdom
// so the form/chart/table/modal logic is exercised without a browser. Kept
// separate from vite.config.ts so the dev server config (proxy etc.) does not
// bleed into the test run.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
});
