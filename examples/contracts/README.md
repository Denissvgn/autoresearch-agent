# Contract examples

Serialized examples of the versioned research and execution contracts defined
in `src/core/execution_contracts.py`. Every file validates against the
contract models and round-trips through JSON unchanged, so these examples
stay in sync with the schema. Digests are synthetic content digests for
illustration.

## Integration bundles

`<direction>-<domain>.json` carries a full lifecycle bundle — run
specification, execution request, and verified result — for each initial
research domain through both integration directions:

| Domain | Objective | Directions |
| --- | --- | --- |
| `prompt-evaluation` | maximize prompt-eval score | `managed`, `attached` |
| `code-test` | maximize composite refactor score (protected tests) | `managed`, `attached` |
| `latency-minimization` | minimize measured p95 latency | `managed`, `attached` |

`managed` is the service-managed direction (the service launches the driver
in an isolated workspace); `attached` is the external-agent direction (an
already-running agent invokes scoped research operations and only receives
run/attempt-scoped harness credentials).

## Review examples

- `review-failure.json` — an evaluation failure: a structured failure record
  and no claimed metrics.
- `review-continuation.json` — a continued run: parent/checkpoint lineage and
  the original nondefault parameters and budget, preserved.
- `review-minimization.json` — a minimize-direction objective where the lower
  measurement wins (`winner_result_id` names it).
- `review-unsupported-capability.json` — a capability descriptor below the
  minimum supported set, rejected before work starts with the missing
  capabilities named in `expected_rejection`.
- `legacy-compatibility.json` — the v1 compatibility mapping: preserved
  legacy behavior versus rejected incomplete features.
