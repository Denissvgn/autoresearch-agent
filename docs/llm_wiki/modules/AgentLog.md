# AgentLog Module

**Path:** `ui/src/components/AgentLog.tsx`

## Description

_Auto-generated from `ui/src/components/AgentLog.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../api/client` | `AgentLogEntry` |
| `../hooks/useResearch` | `useAgentLog` |
| `../hooks/useWebSocket` | `useWebSocket` |
| `react` | `useEffect`, `useRef`, `useState` |

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `default` |
| Constants | `TYPE_LABELS`, `TYPE_COLORS` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/api/client.ts"]
    n1["ui/src/components/AgentLog.tsx"]
    n2["ui/src/hooks/useResearch.ts"]
    n3["ui/src/hooks/useWebSocket.tsx"]
    n4["ui/src/pages/ResearchDetail.tsx"]
    n1 --> n0
    n1 --> n2
    n1 --> n3
    n2 --> n0
    n2 --> n3
    n3 --> n0
    n4 --> n0
    n4 --> n1
    n4 --> n2
    n4 --> n3
    click n0 "../modules/client.md"
    click n1 "../modules/AgentLog.md"
    click n2 "../modules/useResearch.md"
    click n3 "../modules/useWebSocket.md"
    click n4 "../modules/ResearchDetail.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [ResearchDetail](../modules/ResearchDetail.md) |
| Outbound | [client](../modules/client.md) |
| Outbound | [useResearch](../modules/useResearch.md) |
| Outbound | [useWebSocket](../modules/useWebSocket.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| typescript | 1 | 0 |

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [Props](../entities/AgentLog_Props.md) | Class | 6 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `AgentLog` | `({ researchId, isActive = false }: Props)` | — | — |
