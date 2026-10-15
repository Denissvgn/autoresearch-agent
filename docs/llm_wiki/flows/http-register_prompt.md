# register_prompt

**Entry point:** `register_prompt` (`http`)
**Source:** [examples_prompt-registry_main](../modules/examples_prompt-registry_main.md)
**Modules touched:** [examples_prompt-registry_main](../modules/examples_prompt-registry_main.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as register_prompt
    participant p1 as _authorized
    participant p2 as HTTPException
    participant p3 as request.headers.get
    participant p4 as RegisterResponse
    participant p5 as payload.get
    participant p6 as time.time
    participant p7 as os.environ.get
    p0->>p1: _authorized
    p0-->>p2: HTTPException(status_code=401, detail='invalid bearer token')
    p0-->>p3: request.headers.get('Idempotency-Key', '')
    p0->>p4: RegisterResponse
    p0-->>p5: payload.get('config')
    p0-->>p5: payload.get('target_path')
    p0-->>p5: payload.get('endpoint')
    p0-->>p5: payload.get('promoted_at')
    p0-->>p6: time.time
    p0->>p4: RegisterResponse
    p1-->>p7: os.environ.get('PROMPT_REGISTRY_AUTH_TOKEN', '')
```

> Call sequence diagram shows 11 of 11 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 3 of 3 (0 omitted); unresolved 5 of 5 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. register_prompt"]
    s2["2. _authorized"]
    s3["3. os.environ.get"]
    s4["4. HTTPException"]
    s5["5. request.headers.get"]
    s6["6. RegisterResponse"]
    s7["7. payload.get"]
    s8["8. payload.get"]
    s9["9. payload.get"]
    s10["10. payload.get"]
    s11["11. time.time"]
    s12["12. RegisterResponse"]
    s1 -->|"_authorized(authorization)"| s2
    s2 -. "os.environ.get('PROMPT_REGISTRY_AUTH_TOKEN', '')" .-> s3
    s1 -. "HTTPException(status_code=401, detail='invalid bearer token')" .-> s4
    s1 -. "request.headers.get('Idempotency-Key', '')" .-> s5
    s1 -->|"RegisterResponse(prompt_id=prior[...], status=prior[...], idempotent_replay=True)"| s6
    s1 -. "payload.get('config')" .-> s7
    s1 -. "payload.get('target_path')" .-> s8
    s1 -. "payload.get('endpoint')" .-> s9
    s1 -. "payload.get('promoted_at')" .-> s10
    s1 -. "time.time(data not statically known)" .-> s11
    s1 -->|"RegisterResponse(prompt_id=prompt_id, status='registered')"| s12
    b0["environment_read os.environ.get"]
    s2 -. "environment_read os.environ.get" .-> b0
    click s1 "../modules/examples_prompt-registry_main.md"
    click s2 "../modules/examples_prompt-registry_main.md"
    click s6 "../modules/examples_prompt-registry_main.md"
    click s12 "../modules/examples_prompt-registry_main.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `register_prompt` | `payload: dict[str, Any]`, `request: Request`, `authorization: str \| None` | `_BY_IDEMPOTENCY`, `_BY_IDEMPOTENCY`, `_SEQ` | `_SEQ[...]`, `_PROMPTS[...]`, `_BY_IDEMPOTENCY[...]` | `RegisterResponse(...)`, `RegisterResponse(...)` |
| `_authorized` | `authorization: str \| None` | - | - | `True`, `...` |
| `os.environ.get` | - | - | - | - |
| `HTTPException` | - | - | - | - |
| `request.headers.get` | - | - | - | - |
| `RegisterResponse` | - | - | - | - |
| `payload.get` | - | - | - | - |
| `payload.get` | - | - | - | - |
| `payload.get` | - | - | - | - |
| `payload.get` | - | - | - | - |
| `time.time` | - | - | - | - |
| `RegisterResponse` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| register_prompt | _authorized | 62 | `_authorized(authorization)` |
| _authorized | os.environ.get | 44 | `os.environ.get('PROMPT_REGISTRY_AUTH_TOKEN', '')` |
| register_prompt | HTTPException | 63 | `HTTPException(status_code=401, detail='invalid bearer token')` |
| register_prompt | request.headers.get | 64 | `request.headers.get('Idempotency-Key', '')` |
| register_prompt | RegisterResponse | 67 | `RegisterResponse(prompt_id=prior[...], status=prior[...], idempotent_replay=True)` |
| register_prompt | payload.get | 76 | `payload.get('config')` |
| register_prompt | payload.get | 77 | `payload.get('target_path')` |
| register_prompt | payload.get | 78 | `payload.get('endpoint')` |
| register_prompt | payload.get | 79 | `payload.get('promoted_at')` |
| register_prompt | time.time | 81 | `time.time(data not statically known)` |
| register_prompt | RegisterResponse | 86 | `RegisterResponse(prompt_id=prompt_id, status='registered')` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| environment_read | `os.environ.get` | `_authorized` | 44 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `register_prompt` | `HTTPException` | 63 |
| unresolved_call | `register_prompt` | `request.headers.get` | 64 |
| unresolved_call | `register_prompt` | `payload.get` | 76 |
| unresolved_call | `register_prompt` | `payload.get` | 77 |
| unresolved_call | `register_prompt` | `payload.get` | 78 |
| unresolved_call | `register_prompt` | `payload.get` | 79 |
| external_call | `register_prompt` | `time.time` | 81 |

## Behavior

This flow starts at `register_prompt` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
