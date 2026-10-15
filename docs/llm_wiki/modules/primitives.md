# primitives Module

**Path:** `ui/src/components/hifi/primitives.tsx`

## Description

_Auto-generated from `ui/src/components/hifi/primitives.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `react` | `CSSProperties`, `ReactNode` |

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `Field`, `FieldProps`, `Icon`, `IconName`, `IconProps`, `MetricChart`, `MetricChartProps`, `MetricPoint`, `PhaseBar`, `PhaseBarItem`, `PhaseBarProps`, `Segmented`, `SegmentedOption`, `SegmentedProps`, `Sparkline`, `SparklineProps`, `Stat`, `StatProps`, `StatusBadge` |
| Constants | `ICON_PATHS`, `STATUS_MAP` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/App.tsx"]
    n1["ui/src/components/DynamicFormFields.tsx"]
    n2["ui/src/components/hifi/primitives.tsx"]
    n3["ui/src/components/hifi/Topbar.tsx"]
    n4["ui/src/pages/Dashboard.tsx"]
    n5["ui/src/pages/History.tsx"]
    n6["ui/src/pages/Leaderboard.tsx"]
    n7["ui/src/pages/NewResearch.tsx"]
    n8["ui/src/pages/Promote.tsx"]
    n9["ui/src/pages/ResearchDetail.tsx"]
    n10["ui/src/pages/Settings.tsx"]
    n0 --> n2
    n0 --> n3
    n0 --> n4
    n0 --> n5
    n0 --> n6
    n0 --> n7
    n0 --> n8
    n0 --> n9
    n0 --> n10
    n1 --> n2
    n3 --> n2
    n4 --> n2
    n5 --> n2
    n6 --> n2
    n7 --> n1
    n7 --> n2
    n8 --> n2
    n9 --> n2
    n10 --> n2
    n10 --> n3
    click n0 "../modules/App.md"
    click n1 "../modules/DynamicFormFields.md"
    click n2 "../modules/primitives.md"
    click n3 "../modules/Topbar.md"
    click n4 "../modules/Dashboard.md"
    click n5 "../modules/History.md"
    click n6 "../modules/Leaderboard.md"
    click n7 "../modules/NewResearch.md"
    click n8 "../modules/Promote.md"
    click n9 "../modules/ResearchDetail.md"
    click n10 "../modules/Settings.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [App](../modules/App.md) |
| Inbound | [DynamicFormFields](../modules/DynamicFormFields.md) |
| Inbound | [Topbar](../modules/Topbar.md) |
| Inbound | [Dashboard](../modules/Dashboard.md) |
| Inbound | [History](../modules/History.md) |
| Inbound | [Leaderboard](../modules/Leaderboard.md) |
| Inbound | [NewResearch](../modules/NewResearch.md) |
| Inbound | [Promote](../modules/Promote.md) |
| Inbound | [ResearchDetail](../modules/ResearchDetail.md) |
| Inbound | [Settings](../modules/Settings.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| typescript | 1 | 0 |

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [IconProps](../entities/IconProps.md) | Class | 46 | — | — |
| [StatProps](../entities/StatProps.md) | Class | 105 | — | — |
| [SparklineProps](../entities/SparklineProps.md) | Class | 136 | — | — |
| [MetricPoint](../entities/MetricPoint.md) | Class | 169 | — | — |
| [MetricChartProps](../entities/MetricChartProps.md) | Class | 175 | — | — |
| [PhaseBarItem](../entities/PhaseBarItem.md) | Class | 289 | — | — |
| [PhaseBarProps](../entities/PhaseBarProps.md) | Class | 295 | — | — |
| [FieldProps](../entities/FieldProps.md) | Class | 329 | — | — |
| [SegmentedOption](../entities/SegmentedOption.md) | Class | 349 | — | — |
| [SegmentedProps](../entities/SegmentedProps.md) | Class | 354 | — | — |
| [IconName](../entities/IconName.md) | Type alias | 44 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `Icon` | `({ name, size = 16, color = 'currentColor', stroke = 1.5, style, className }: IconProps)` | — | — |
| `StatusBadge` | `({ s }: { s: string })` | — | — |
| `Stat` | `({ label, value, sub, delta, deltaDir, valueSize }: StatProps)` | — | — |
| `Sparkline` | `({ data, color, height = 32, fill = false }: SparklineProps)` | — | — |
| `MetricChart` | `({ points, height = 280, showAxis = true, showBest = true }: MetricChartProps)` | — | — |
| `PhaseBar` | `({ phases, active }: PhaseBarProps)` | — | — |
| `Field` | `({ label, required, help, children }: FieldProps)` | — | — |
| `Segmented` | `({ options, value, onChange }: SegmentedProps)` | — | — |
