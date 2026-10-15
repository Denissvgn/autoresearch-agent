# Dashboard Module

**Path:** `ui/src/pages/Dashboard.tsx`

## Description

_Auto-generated from `ui/src/pages/Dashboard.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../api/client` | `ResearchSession` |
| `../components/hifi/primitives` | `Icon`, `Sparkline`, `Stat`, `StatusBadge` |
| `../hooks/useResearch` | `useIterations`, `useSessions`, `useSessionsPage`, `useStatus` |
| `react` | `useMemo`, `useState` |
| `react-router-dom` | `Link`, `useNavigate` |

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `default` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/api/client.ts"]
    n1["ui/src/App.tsx"]
    n2["ui/src/components/hifi/primitives.tsx"]
    n3["ui/src/hooks/useResearch.ts"]
    n4["ui/src/pages/Dashboard.tsx"]
    n1 --> n0
    n1 --> n2
    n1 --> n3
    n1 --> n4
    n3 --> n0
    n4 --> n0
    n4 --> n2
    n4 --> n3
    click n0 "../modules/client.md"
    click n1 "../modules/App.md"
    click n2 "../modules/primitives.md"
    click n3 "../modules/useResearch.md"
    click n4 "../modules/Dashboard.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [App](../modules/App.md) |
| Outbound | [client](../modules/client.md) |
| Outbound | [primitives](../modules/primitives.md) |
| Outbound | [useResearch](../modules/useResearch.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| typescript | 2 | 0 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `Dashboard` | `()` | — | — |
