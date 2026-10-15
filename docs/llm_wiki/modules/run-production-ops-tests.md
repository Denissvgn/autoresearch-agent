# run-production-ops-tests Module

**Path:** `ui/scripts/run-production-ops-tests.mjs`

## Description

_Auto-generated from `ui/scripts/run-production-ops-tests.mjs`._

## Imports

| Source | Symbols |
|--------|---------|
| `` | ``, `` |
| `node:assert/strict` | `assert` |
| `node:child_process` | `execFileSync` |
| `node:fs` | `existsSync`, `mkdirSync`, `rmSync`, `readdirSync`, `writeFileSync` |
| `node:os` | `tmpdir` |
| `node:path` | `join`, `dirname` |
| `node:test` | `test` |
| `node:url` | `fileURLToPath`, `pathToFileURL` |

## Module Signals

| Signal | Values |
|--------|--------|
| Constants | `root`, `outDir`, `compiledPath`, `ops`, `compiledClientPath`, `client` |
| Module calls | `root = dirname`, `outDir = join`, `mkdirSync`, `writeFileSync`, `execFileSync`, `compiledPath = findCompiledModule`, `ok`, `compiledClientPath = findCompiledModule`, `ok`, `test`, `test`, `test`, `test`, `test` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `findCompiledModule` | `(dir, fileName)` | — | — |
