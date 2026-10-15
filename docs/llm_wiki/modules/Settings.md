# Settings Module

**Path:** `ui/src/pages/Settings.tsx`

## Description

_Auto-generated from `ui/src/pages/Settings.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../api/client` | `clearAutoresearchApiToken`, `getAutoresearchApiToken`, `hasBuildTimeAutoresearchApiToken`, `setAutoresearchApiToken` |
| `../components/hifi/Topbar` | `AccentName`, `DensityName`, `ThemeName`, `useDesignPrefs` |
| `../components/hifi/primitives` | `Field`, `Icon`, `Segmented` |
| `react` | `FormEvent`, `useState` |
| `react-router-dom` | `Link` |

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `default` |
| Constants | `ACCENTS` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/api/client.ts"]
    n1["ui/src/App.tsx"]
    n2["ui/src/components/hifi/primitives.tsx"]
    n3["ui/src/components/hifi/Topbar.tsx"]
    n4["ui/src/pages/Settings.tsx"]
    n1 --> n0
    n1 --> n2
    n1 --> n3
    n1 --> n4
    n3 --> n2
    n4 --> n0
    n4 --> n2
    n4 --> n3
    click n0 "../modules/client.md"
    click n1 "../modules/App.md"
    click n2 "../modules/primitives.md"
    click n3 "../modules/Topbar.md"
    click n4 "../modules/Settings.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [App](../modules/App.md) |
| Outbound | [client](../modules/client.md) |
| Outbound | [primitives](../modules/primitives.md) |
| Outbound | [Topbar](../modules/Topbar.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| typescript | 2 | 0 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `Settings` | `()` | — | — |
