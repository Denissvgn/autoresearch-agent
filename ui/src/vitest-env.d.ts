// Type references for the vitest test environment (ARC-011 P3-029).
//
// Pulls in vitest's globals + the jest-dom matcher augmentation so
// `tsc --noEmit` type-checks the *.test.tsx files. The base tsconfig covers the
// app; this file adds the test-only type surface.
/// <reference types="vitest/globals" />
/// <reference path="../node_modules/@testing-library/jest-dom/types/vitest.d.ts" />
