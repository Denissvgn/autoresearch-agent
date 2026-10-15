# run

**Entry point:** `main` (`process`)
**Source:** [db-config-tuning_eval_run](../modules/db-config-tuning_eval_run.md)
**Modules touched:** [db-config-tuning_eval_run](../modules/db-config-tuning_eval_run.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as main
    participant p1 as _emit
    participant p2 as argparse.ArgumentParser
    participant p3 as ap.add_argument
    participant p4 as ap.parse_args
    participant p5 as yaml.safe_load
    participant p6 as open
    participant p7 as json.load
    participant p8 as str
    participant p9 as float
    participant p10 as cfg.get
    participant p11 as int
    participant p12 as hashlib.sha256(…).hexdigest
    participant p13 as hashlib.sha256
    participant p14 as json.dumps(…).encode
    participant p15 as json.dumps (skills/db-config-tuning/eval/run.py:main)
    participant p16 as max
    participant p17 as round
    p0->>p1: _emit
    p0-->>p2: argparse.ArgumentParser
    p0-->>p3: ap.add_argument('--config', required=True)
    p0-->>p3: ap.add_argument('--target-latency-ms', type=float, default=10.0)
    p0-->>p3: ap.add_argument('--baseline-tps', type=float, default=0.0)
    p0-->>p4: ap.parse_args
    p0-->>p5: yaml.safe_load(open(...))
    p0-->>p6: open(a.config, encoding='utf-8')
    p0-->>p7: json.load(open(...))
    p0-->>p6: open(a.config, encoding='utf-8')
    p0-->>p8: str(exc)
    p0-->>p9: float(cfg.get(...))
    p0-->>p10: cfg.get('shared_buffers_mb', 128)
    p0-->>p9: float(cfg.get(...))
    p0-->>p10: cfg.get('work_mem_mb', 4)
    p0-->>p9: float(cfg.get(...))
    p0-->>p10: cfg.get('effective_cache_size_mb', 512)
    p0-->>p9: float(cfg.get(...))
    p0-->>p10: cfg.get('max_connections', 100)
    p0-->>p11: int(..., 16)
    p0-->>p12: hashlib.sha256(…).hexdigest
    p0-->>p13: hashlib.sha256(...)
    p0-->>p14: json.dumps(…).encode
    p0-->>p15: json.dumps (skills/db-config-tuning/eval/run.py:main)(cfg, sort_keys=True)
    p0-->>p16: max(0, ...)
    p0-->>p16: max(50.0, round(...))
    p0-->>p17: round(tps, 1)
    p0-->>p17: round(max(...), 2)
    p0-->>p16: max(1.0, ...)
    p0-->>p16: max(0, ...)
```

> Call sequence diagram shows 30 of 41 interactions; 11 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 19 of 25 (6 omitted); unresolved 10 of 14 (4 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `skills/db-config-tuning/eval/run.py:_emit` | 11 | - | external | 4 |
| `skills/db-config-tuning/eval/run.py:_emit` | 11 | - | unresolved | 3 |
| `skills/db-config-tuning/eval/run.py:main` | 1 | - | unresolved | 1 |
| `skills/db-config-tuning/eval/run.py:main` | 1 | - | external | 2 |
| `skills/db-config-tuning/eval/run.py:main` | 1 | [skills/db-config-tuning/eval/run.py](../modules/db-config-tuning_eval_run.md) | internal | 1 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. main"]
    s2["2. argparse.ArgumentParser"]
    s3["3. ap.add_argument"]
    s4["4. ap.add_argument"]
    s5["5. ap.add_argument"]
    s6["6. ap.parse_args"]
    s7["7. yaml.safe_load"]
    s8["8. open"]
    s9["9. json.load"]
    s10["10. open"]
    s11["11. _emit"]
    s12["12. dict"]
    s1 -. "argparse.ArgumentParser(data not statically known)" .-> s2
    s1 -. "ap.add_argument('--config', required=True)" .-> s3
    s1 -. "ap.add_argument('--target-latency-ms', type=float, default=10.0)" .-> s4
    s1 -. "ap.add_argument('--baseline-tps', type=float, default=0.0)" .-> s5
    s1 -. "ap.parse_args(data not statically known)" .-> s6
    s1 -. "yaml.safe_load(open(...))" .-> s7
    s1 -. "open(a.config, encoding='utf-8')" .-> s8
    s1 -. "json.load(open(...))" .-> s9
    s1 -. "open(a.config, encoding='utf-8')" .-> s10
    s1 -->|"_emit(status='bench_failed', error=str(...))"| s11
    s11 -. "dict(fields)" .-> s12
    b0["filesystem_read open"]
    s1 -. "filesystem_read open" .-> b0
    b1["filesystem_read json.load"]
    s1 -. "filesystem_read json.load" .-> b1
    b2["filesystem_read open"]
    s1 -. "filesystem_read open" .-> b2
    b3["environment_read os.environ.get"]
    s11 -. "environment_read os.environ.get" .-> b3
    b4["output print"]
    s11 -. "output print" .-> b4
    click s1 "../modules/db-config-tuning_eval_run.md"
    click s11 "../modules/db-config-tuning_eval_run.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
    class b1 boundary
    class b2 boundary
    class b3 boundary
    class b4 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `main` | - | - | - | `1`, `0` |
| `argparse.ArgumentParser` | - | - | - | - |
| `ap.add_argument` | - | - | - | - |
| `ap.add_argument` | - | - | - | - |
| `ap.add_argument` | - | - | - | - |
| `ap.parse_args` | - | - | - | - |
| `yaml.safe_load` | - | - | - | - |
| `open` | - | - | - | - |
| `json.load` | - | - | - | - |
| `open` | - | - | - | - |
| `_emit` | `fields` | - | `p[...]` | - |
| `dict` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| main | argparse.ArgumentParser | 10 | `argparse.ArgumentParser(data not statically known)` |
| main | ap.add_argument | 11 | `ap.add_argument('--config', required=True)` |
| main | ap.add_argument | 12 | `ap.add_argument('--target-latency-ms', type=float, default=10.0)` |
| main | ap.add_argument | 13 | `ap.add_argument('--baseline-tps', type=float, default=0.0)` |
| main | ap.parse_args | 14 | `ap.parse_args(data not statically known)` |
| main | yaml.safe_load | 17 | `yaml.safe_load(open(...))` |
| main | open | 17 | `open(a.config, encoding='utf-8')` |
| main | json.load | 20 | `json.load(open(...))` |
| main | open | 20 | `open(a.config, encoding='utf-8')` |
| main | _emit | 22 | `_emit(status='bench_failed', error=str(...))` |
| _emit | dict | 6 | `dict(fields)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| filesystem_read | `open` | `main` | 17 |
| filesystem_read | `json.load` | `main` | 20 |
| filesystem_read | `open` | `main` | 20 |
| environment_read | `os.environ.get` | `_emit` | 6 |
| output | `print` | `_emit` | 8 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `main` | `argparse.ArgumentParser` | 10 |
| unresolved_call | `main` | `ap.add_argument` | 11 |
| unresolved_call | `main` | `ap.add_argument` | 12 |
| unresolved_call | `main` | `ap.add_argument` | 13 |
| unresolved_call | `main` | `ap.parse_args` | 14 |
| step_limit | `main` | `first 12 steps` | 0 |

## Behavior

This flow starts at `main` and is classified as `process`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
