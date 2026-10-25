# ResearchDetail Module

**Path:** `ui/src/pages/ResearchDetail.tsx`

## Description

_Auto-generated from `ui/src/pages/ResearchDetail.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../api/client` | `api`, `Iteration`, `MetricColumn`, `ResearchState` |
| `../components/AgentLog` | `AgentLog` |
| `../components/HarnessContextPanel` | `HarnessContextPanel` |
| `../components/IterationsTable` | `IterationsTable` |
| `../components/MetricsChart` | `MetricsTrendChart` |
| `../components/hifi/primitives` | `Icon`, `PhaseBar`, `Stat`, `StatusBadge` |
| `../hooks/useResearch` | `useIterations`, `useAgentLog`, `useHarnessContext`, `usePauseSession`, `useResearchState`, `useResumeSession`, `useSession`, `useSkillMetricSchema`, `useStopSession` |
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
    n3["ui/src/components/HarnessContextPanel.tsx"]
    n4["ui/src/components/hifi/primitives.tsx"]
    n5["ui/src/components/IterationsTable.tsx"]
    n6["ui/src/components/MetricsChart.tsx"]
    n7["ui/src/hooks/useResearch.ts"]
    n8["ui/src/hooks/useWebSocket.tsx"]
    n9["ui/src/pages/ResearchDetail.tsx"]
    n1 --> n0
    n1 --> n4
    n1 --> n7
    n1 --> n8
    n1 --> n9
    n2 --> n0
    n2 --> n7
    n2 --> n8
    n3 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n7 --> n8
    n8 --> n0
    n9 --> n0
    n9 --> n2
    n9 --> n3
    n9 --> n4
    n9 --> n5
    n9 --> n6
    n9 --> n7
    n9 --> n8
    click n0 "../modules/client.md"
    click n1 "../modules/App.md"
    click n2 "../modules/AgentLog.md"
    click n3 "../modules/HarnessContextPanel.md"
    click n4 "../modules/primitives.md"
    click n5 "../modules/IterationsTable.md"
    click n6 "../modules/MetricsChart.md"
    click n7 "../modules/useResearch.md"
    click n8 "../modules/useWebSocket.md"
    click n9 "../modules/ResearchDetail.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [App](../modules/App.md) |
| Outbound | [client](../modules/client.md) |
| Outbound | [AgentLog](../modules/AgentLog.md) |
| Outbound | [HarnessContextPanel](../modules/HarnessContextPanel.md) |
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
| [Tab](../entities/Tab.md) | Type alias | 31 | — | — |
| [MetricDef](../entities/MetricDef.md) | Type alias | 637 | — | — |
| [MetricDiagnostic](../entities/MetricDiagnostic.md) | Type alias | 638 | — | — |
| [DetailEntry](../entities/DetailEntry.md) | Type alias | 642 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `ResearchDetail` | `()` | — | — |
