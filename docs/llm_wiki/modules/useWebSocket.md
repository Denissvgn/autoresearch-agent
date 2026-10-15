# useWebSocket Module

**Path:** `ui/src/hooks/useWebSocket.tsx`

## Description

_Auto-generated from `ui/src/hooks/useWebSocket.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../api/client` | `getAutoresearchWebSocketProtocols` |
| `react` | `createContext`, `ReactNode`, `useCallback`, `useContext`, `useEffect`, `useRef`, `useState` |

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `WSEvent`, `WebSocketProvider`, `useWebSocket` |
| Constants | `WebSocketContext` |
| Module calls | `WebSocketContext = createContext` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/api/client.ts"]
    n1["ui/src/App.tsx"]
    n2["ui/src/components/AgentLog.tsx"]
    n3["ui/src/components/hifi/Topbar.tsx"]
    n4["ui/src/hooks/useResearch.ts"]
    n5["ui/src/hooks/useWebSocket.tsx"]
    n6["ui/src/pages/ResearchDetail.tsx"]
    n1 --> n0
    n1 --> n3
    n1 --> n4
    n1 --> n5
    n1 --> n6
    n2 --> n0
    n2 --> n4
    n2 --> n5
    n3 --> n4
    n3 --> n5
    n4 --> n0
    n4 --> n5
    n5 --> n0
    n6 --> n0
    n6 --> n2
    n6 --> n4
    n6 --> n5
    click n0 "../modules/client.md"
    click n1 "../modules/App.md"
    click n2 "../modules/AgentLog.md"
    click n3 "../modules/Topbar.md"
    click n4 "../modules/useResearch.md"
    click n5 "../modules/useWebSocket.md"
    click n6 "../modules/ResearchDetail.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [App](../modules/App.md) |
| Inbound | [AgentLog](../modules/AgentLog.md) |
| Inbound | [Topbar](../modules/Topbar.md) |
| Inbound | [useResearch](../modules/useResearch.md) |
| Inbound | [ResearchDetail](../modules/ResearchDetail.md) |
| Outbound | [client](../modules/client.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| typescript | 1 | 0 |

## Classes

| Class | Kind | Line | Bases / Target | Description |
|-------|------|------|----------------|-------------|
| [WSEvent](../entities/WSEvent.md) | Class | 12 | — | — |
| [WebSocketContextValue](../entities/WebSocketContextValue.md) | Class | 20 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `WebSocketProvider` | `({ children }: { children: ReactNode })` | — | — |
| `useWebSocket` | `()` | — | — |
