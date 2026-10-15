# IterationsTable Module

**Path:** `ui/src/components/IterationsTable.tsx`

## Description

_Auto-generated from `ui/src/components/IterationsTable.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../api/client` | `Iteration`, `MetricColumn` |
| `react` | `useState` |

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `default` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/api/client.ts"]
    n1["ui/src/components/__tests__/IterationsTable.test.tsx"]
    n2["ui/src/components/IterationsTable.tsx"]
    n3["ui/src/pages/ResearchDetail.tsx"]
    n1 --> n0
    n1 --> n2
    n2 --> n0
    n3 --> n0
    n3 --> n2
    click n0 "../modules/client.md"
    click n1 "../modules/IterationsTable.test.md"
    click n2 "../modules/IterationsTable.md"
    click n3 "../modules/ResearchDetail.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [IterationsTable.test](../modules/IterationsTable.test.md) |
| Inbound | [ResearchDetail](../modules/ResearchDetail.md) |
| Outbound | [client](../modules/client.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| typescript | 1 | 0 |

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [Props](../entities/IterationsTable_Props.md) | Class | 4 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `IterationsTable` | `({ iterations, bestIteration, tableColumns }: Props)` | — | — |
