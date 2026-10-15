# MetricsChart Module

**Path:** `ui/src/components/MetricsChart.tsx`

## Description

_Auto-generated from `ui/src/components/MetricsChart.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../api/client` | `Iteration`, `MetricColumn` |
| `react` | `useState` |
| `recharts` | `LineChart`, `Line`, `XAxis`, `YAxis`, `Tooltip`, `CartesianGrid`, `ResponsiveContainer`, `Legend` |

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `default` |
| Constants | `DEFAULT_COLORS` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/api/client.ts"]
    n1["ui/src/components/__tests__/MetricsChart.test.tsx"]
    n2["ui/src/components/MetricsChart.tsx"]
    n3["ui/src/pages/ResearchDetail.tsx"]
    n1 --> n0
    n1 --> n2
    n2 --> n0
    n3 --> n0
    n3 --> n2
    click n0 "../modules/client.md"
    click n1 "../modules/MetricsChart.test.md"
    click n2 "../modules/MetricsChart.md"
    click n3 "../modules/ResearchDetail.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [MetricsChart.test](../modules/MetricsChart.test.md) |
| Inbound | [ResearchDetail](../modules/ResearchDetail.md) |
| Outbound | [client](../modules/client.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| typescript | 2 | 0 |

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [Props](../entities/MetricsChart_Props.md) | Class | 5 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `MetricsChart` | `({ iterations, selectedIteration = null, onSelectIteration, chartSeries }: Props)` | — | — |
