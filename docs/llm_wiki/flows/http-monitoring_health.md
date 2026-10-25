# monitoring_health

**Entry point:** `monitoring_health` (`http`)
**Source:** [src_main](../modules/src_main.md)
**Modules touched:** [preflight](../modules/preflight.md), [service_preflight](../modules/service_preflight.md), [src_main](../modules/src_main.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as monitoring_health
    participant p1 as run_service_preflight
    participant p2 as build_not_run_preflight
    participant p3 as preflight_check_from_target
    participant p4 as sanitize_service_url
    participant p5 as TCPConnectCheck
    participant p6 as HTTPHealthCheck
    participant p7 as str
    participant p8 as preflight.get
    participant p9 as datetime.now(…).isoformat
    participant p10 as datetime.now
    participant p11 as list (src/core/service_prefligh…py:build_not_run_preflight)
    participant p12 as bool
    participant p13 as list (src/core/service_preflight.py:run_service_preflight)
    participant p14 as base.update
    participant p15 as httpx.Timeout
    participant p16 as min
    participant p17 as httpx.AsyncClient
    participant p18 as asyncio.gather
    participant p19 as pc.check
    participant p20 as active_client.aclose
    participant p21 as services.items
    participant p22 as check.get
    participant p23 as urlsplit
    participant p24 as raw.split(…)[…].split
    participant p25 as raw.split
    participant p26 as host.startswith
    participant p27 as urlunsplit
    participant p28 as parsed.path.rstrip
    p0->>p1: run_service_preflight
    p0->>p2: build_not_run_preflight
    p1->>p3: preflight_check_from_target
    p2->>p4: sanitize_service_url
    p3->>p5: TCPConnectCheck
    p3->>p6: HTTPHealthCheck
    p0-->>p7: str(exc)
    p0-->>p8: preflight.get('status')
    p1-->>p9: datetime.now(…).isoformat
    p1-->>p10: datetime.now(timezone.utc)
    p2-->>p11: list (src/core/service_prefligh…py:build_not_run_preflight)(target.health_paths)
    p1-->>p12: bool(settings_obj.allow_unready_services)
    p1-->>p13: list (src/core/service_preflight.py:run_service_preflight)(target.health_paths)
    p1-->>p14: base.update({...})
    p1-->>p13: list (src/core/service_preflight.py:run_service_preflight)(target.health_paths)
    p1-->>p15: httpx.Timeout(settings_obj.preflight_timeout_s, connect=min(...))
    p1-->>p16: min(settings_obj.preflight_timeout_s, 2.0)
    p1-->>p17: httpx.AsyncClient(timeout=timeout, follow_redirects=True)
    p1-->>p18: asyncio.gather(...)
    p1-->>p19: pc.check(active_client)
    p1-->>p20: active_client.aclose
    p1-->>p21: services.items
    p1-->>p22: check.get('required')
    p1-->>p22: check.get('status')
    p4-->>p23: urlsplit(raw)
    p4-->>p24: raw.split(…)[…].split(' ', 1)
    p4-->>p25: raw.split('?', 1)
    p4-->>p26: host.startswith('[')
    p4-->>p27: urlunsplit((...))
    p4-->>p28: parsed.path.rstrip('/')
```

> Call sequence diagram shows 30 of 32 interactions; 2 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 12 of 12 (0 omitted); unresolved 12 of 12 (0 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/service_preflight.py:run_service_preflight` | 2 | [src/core/service_preflight.py](../modules/service_preflight.md) | internal | 2 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. monitoring_health"]
    s2["2. run_service_preflight"]
    s3["3. datetime.now(…).isoformat"]
    s4["4. datetime.now"]
    s5["5. bool"]
    s6["6. sanitize_service_url"]
    s7["7. urlsplit"]
    s8["8. raw.split(…)[…].split"]
    s9["9. raw.split"]
    s10["10. host.startswith"]
    s11["11. urlunsplit"]
    s12["12. parsed.path.rstrip"]
    s1 -->|"run_service_preflight(targets=[...])"| s2
    s2 -. "datetime.now(…).isoformat(data not statically known)" .-> s3
    s2 -. "datetime.now(timezone.utc)" .-> s4
    s2 -. "bool(settings_obj.allow_unready_services)" .-> s5
    s2 -->|"sanitize_service_url(target.url)"| s6
    s6 -. "urlsplit(raw)" .-> s7
    s6 -. "raw.split(…)[…].split('#35;', 1)" .-> s8
    s6 -. "raw.split('?', 1)" .-> s9
    s6 -. "host.startswith('[')" .-> s10
    s6 -. "urlunsplit((...))" .-> s11
    s6 -. "parsed.path.rstrip('/')" .-> s12
    b0["mutation base.update"]
    s2 -. "mutation base.update" .-> b0
    b1["network httpx.Timeout"]
    s2 -. "network httpx.Timeout" .-> b1
    b2["network httpx.AsyncClient"]
    s2 -. "network httpx.AsyncClient" .-> b2
    click s1 "../modules/src_main.md"
    click s2 "../modules/service_preflight.md"
    click s6 "../modules/service_preflight.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
    class b1 boundary
    class b2 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `monitoring_health` | - | `_session_manager`, `settings`, `settings` | - | `{...}` |
| `run_service_preflight` | `targets: 'list[ServicePreflightTarget]'`, `settings_obj`, `client: httpx.AsyncClient \| None` | `SCHEMA_VERSION` | `base[...]`, `base[...]`, `base[...]`, `base[...]`, `base[...]`, `base[...]` | `base`, `base` |
| `datetime.now(…).isoformat` | - | - | - | - |
| `datetime.now` | - | - | - | - |
| `bool` | - | - | - | - |
| `sanitize_service_url` | `raw: str \| None` | - | - | `''`, `...`, `urlunsplit(...)` |
| `urlsplit` | - | - | - | - |
| `raw.split(…)[…].split` | - | - | - | - |
| `raw.split` | - | - | - | - |
| `host.startswith` | - | - | - | - |
| `urlunsplit` | - | - | - | - |
| `parsed.path.rstrip` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| monitoring_health | run_service_preflight | 283 | `run_service_preflight(targets=[...])` |
| run_service_preflight | datetime.now(…).isoformat | 97 | `datetime.now(timezone.utc).isoformat(data not statically known)` |
| run_service_preflight | datetime.now | 97 | `datetime.now(timezone.utc)` |
| run_service_preflight | bool | 99 | `bool(settings_obj.allow_unready_services)` |
| run_service_preflight | sanitize_service_url | 103 | `sanitize_service_url(target.url)` |
| sanitize_service_url | urlsplit | 43 | `urlsplit(raw)` |
| sanitize_service_url | raw.split(…)[…].split | 45 | `raw.split('?', 1)[0].split('#', 1)` |
| sanitize_service_url | raw.split | 45 | `raw.split('?', 1)` |
| sanitize_service_url | host.startswith | 47 | `host.startswith('[')` |
| sanitize_service_url | urlunsplit | 50 | `urlunsplit((...))` |
| sanitize_service_url | parsed.path.rstrip | 50 | `parsed.path.rstrip('/')` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `base.update` | `run_service_preflight` | 115 |
| network | `httpx.Timeout` | `run_service_preflight` | 133 |
| network | `httpx.AsyncClient` | `run_service_preflight` | 138 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `run_service_preflight` | `datetime.now(timezone.utc).isoformat` | 97 |
| external_call | `run_service_preflight` | `datetime.now` | 97 |
| external_call | `sanitize_service_url` | `urlsplit` | 43 |
| unresolved_call | `sanitize_service_url` | `raw.split('?', 1)[0].split` | 45 |
| unresolved_call | `sanitize_service_url` | `raw.split` | 45 |
| unresolved_call | `sanitize_service_url` | `host.startswith` | 47 |
| external_call | `sanitize_service_url` | `urlunsplit` | 50 |
| unresolved_call | `sanitize_service_url` | `parsed.path.rstrip` | 50 |
| step_limit | `monitoring_health` | `first 12 steps` | 0 |

## Behavior

This flow starts at `monitoring_health` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
