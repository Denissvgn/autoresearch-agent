# Topbar Module

**Path:** `ui/src/components/hifi/Topbar.tsx`

## Description

_Auto-generated from `ui/src/components/hifi/Topbar.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../../hooks/useResearch` | `useStatus` |
| `../../hooks/useWebSocket` | `useWebSocket` |
| `./primitives` | `Icon` |
| `react` | `useEffect`, `useState` |
| `react-router-dom` | `NavLink`, `useLocation` |

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `AccentName`, `DensityName`, `ThemeName`, `Topbar`, `TopbarProps`, `useDesignPrefs` |
| Constants | `THEME_KEY`, `DENSITY_KEY`, `ACCENT_KEY` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/App.tsx"]
    n1["ui/src/components/hifi/primitives.tsx"]
    n2["ui/src/components/hifi/Topbar.tsx"]
    n3["ui/src/hooks/useResearch.ts"]
    n4["ui/src/hooks/useWebSocket.tsx"]
    n5["ui/src/pages/Settings.tsx"]
    n0 --> n1
    n0 --> n2
    n0 --> n3
    n0 --> n4
    n0 --> n5
    n2 --> n1
    n2 --> n3
    n2 --> n4
    n3 --> n4
    n5 --> n1
    n5 --> n2
    click n0 "../modules/App.md"
    click n1 "../modules/primitives.md"
    click n2 "../modules/Topbar.md"
    click n3 "../modules/useResearch.md"
    click n4 "../modules/useWebSocket.md"
    click n5 "../modules/Settings.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [App](../modules/App.md) |
| Inbound | [Settings](../modules/Settings.md) |
| Outbound | [primitives](../modules/primitives.md) |
| Outbound | [useResearch](../modules/useResearch.md) |
| Outbound | [useWebSocket](../modules/useWebSocket.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| typescript | 2 | 0 |

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [TopbarProps](../entities/TopbarProps.md) | Class | 62 | — | — |
| [ThemeName](../entities/ThemeName.md) | Type alias | 8 | — | — |
| [DensityName](../entities/DensityName.md) | Type alias | 9 | — | — |
| [AccentName](../entities/AccentName.md) | Type alias | 10 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `useDesignPrefs` | `()` | — | — |
| `Topbar` | `({ onToggleTheme, theme }: TopbarProps)` | — | — |
