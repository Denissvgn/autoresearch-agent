# ResearchDetail Module

**Path:** `ui/src/pages/ResearchDetail.tsx`

## Description

_Auto-generated from `ui/src/pages/ResearchDetail.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../api/client` | `api`, `Iteration`, `MetricColumn`, `ResearchState` |
| `../components/AgentLog` | `AgentLog` |
| `../components/IterationsTable` | `IterationsTable` |
| `../components/MetricsChart` | `MetricsTrendChart` |
| `../components/hifi/primitives` | `Icon`, `PhaseBar`, `Stat`, `StatusBadge` |
| `../hooks/useResearch` | `useIterations`, `useAgentLog`, `usePauseSession`, `useResearchState`, `useResumeSession`, `useSession`, `useSkillMetricSchema`, `useStopSession` |
| `../hooks/useWebSocket` | `useWebSocket` |
| `react` | `useEffect`, `useMemo`, `useState`, `ReactNode` |
| `react-router-dom` | `Link`, `useNavigate`, `useParams` |

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
    n2["ui/src/components/AgentLog.tsx"]
    n3["ui/src/components/hifi/primitives.tsx"]
    n4["ui/src/components/IterationsTable.tsx"]
    n5["ui/src/components/MetricsChart.tsx"]
    n6["ui/src/hooks/useResearch.ts"]
    n7["ui/src/hooks/useWebSocket.tsx"]
    n8["ui/src/pages/ResearchDetail.tsx"]
    n1 --> n0
    n1 --> n3
    n1 --> n6
    n1 --> n7
    n1 --> n8
    n2 --> n0
    n2 --> n6
    n2 --> n7
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n6 --> n7
    n7 --> n0
    n8 --> n0
    n8 --> n2
    n8 --> n3
    n8 --> n4
    n8 --> n5
    n8 --> n6
    n8 --> n7
    click n0 "../modules/client.md"
    click n1 "../modules/App.md"
    click n2 "../modules/AgentLog.md"
    click n3 "../modules/primitives.md"
    click n4 "../modules/IterationsTable.md"
    click n5 "../modules/MetricsChart.md"
    click n6 "../modules/useResearch.md"
    click n7 "../modules/useWebSocket.md"
    click n8 "../modules/ResearchDetail.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [App](../modules/App.md) |
| Outbound | [client](../modules/client.md) |
| Outbound | [AgentLog](../modules/AgentLog.md) |
| Outbound | [primitives](../modules/primitives.md) |
| Outbound | [IterationsTable](../modules/IterationsTable.md) |
| Outbound | [MetricsChart](../modules/MetricsChart.md) |
| Outbound | [useResearch](../modules/useResearch.md) |
| Outbound | [useWebSocket](../modules/useWebSocket.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| typescript | 2 | 0 |

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [Tab](../entities/Tab.md) | Type alias | 29 | — | — |
| [MetricDef](../entities/MetricDef.md) | Type alias | 603 | — | — |
| [MetricDiagnostic](../entities/MetricDiagnostic.md) | Type alias | 604 | — | — |
| [DetailEntry](../entities/DetailEntry.md) | Type alias | 608 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `ResearchDetail` | `()` | — | — |
