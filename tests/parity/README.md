# ARC-011 Parity Fixtures (X-002)

Golden-master fixtures that capture the **current behavior** of the
autoresearch-agent's domain-coupling surfaces. Every later refactor in
ARC-011 Phases 1–2 must keep these fixtures green; if a fixture's `expected`
block changes, either the refactor is wrong, or the behavior change is
intentional and must be re-captured with a linked task.

## Layout

```
tests/parity/
├── _engine.py            # shared engine (load, dispatch, normalize)
├── conftest.py           # registers the `parity` pytest marker
├── test_parity.py        # discovers *.json and asserts expected == actual
├── capture.py            # (re)generates the `expected` block + source_sha
├── README.md             # this file
├── experiment_parser/    # parse_prepare_output + parse_iteration_marker
├── command_policy/       # evaluate_command_policy (allow/deny + reason)
├── session_start/        # legacy request → ResearchConfig
├── phase_advancement/    # build_phase_state
└── promotion_preview/    # ConfigPromoter.preview (async, seeded store)
```

## Running

```bash
# verify (the suite): fails on any drift vs the recorded golden output
poetry run pytest tests/parity -q          # or:  pytest -m parity

# record (regenerate golden output from current code)
python tests/parity/capture.py             # refuses on a dirty git tree
python tests/parity/capture.py --force     # allow dirty (while iterating)
```

`capture` and `test_parity` share `_engine.py`, so they invoke the target
functions identically. Re-running `capture` against the same commit is
**idempotent** (byte-identical output).

## Fixture format

One JSON file per case (`input` + recorded `expected`, inline):

```json
{
  "category": "command_policy",
  "function": "evaluate_command_policy",
  "description": "human-readable summary",
  "source_sha": "<full git SHA at capture time>",
  "input": { "...": "function-specific kwargs (tokens substituted)" },
  "input_setup": { "create_files": { "train.yaml": "..." } },
  "expected": { "...": "normalized golden output" }
}
```

### Tokens

- `<workspace>` — substituted with a per-case tmp dir; `input_setup.create_files`
  materializes files there. Useful for `command_policy` (cp/cat need real files).
- `<host_configs>` — promotion-target root, substituted into `ConfigPromoter`
  settings during preview.

Outputs are **detokenized** (real paths → tokens) and **redacted**
(`sha256*`, `*_at`, `*timestamp*`, `*run_id` → `<redacted>`) before compare, so
golden blocks are stable across machines and runs.

### Promotion-preview cases

These carry a `replay_fixture` field naming a file under `tests/fixtures/`
(e.g. `res_a1ba6cbd520f_minimal`) that seeds the `ResultsStore` — reusing the
service's existing replay infrastructure rather than duplicating seed data.

## Adding / changing fixtures (append-only rule)

- **Within a phase**, fixtures are append-only: never edit an existing
  `expected` block to make a refactor pass. If `test_parity` fails, the
  refactor changed behavior — investigate before re-capturing.
- **Intentional behavior change**: re-run `capture.py` on a clean tree at the
  new HEAD, then commit the updated fixtures with the linked task ID in the
  commit message (e.g. `test(parity): refresh command_policy after P1-013`).
- **New case**: add a `<category>/<name>.json` with `input` (+ `input_setup`
  / `replay_fixture` as needed), then run `capture.py` to populate `expected`.

## Categories → functions

| Category | Function | Notes |
|---|---|---|
| `experiment_parser` | `parse_prepare_output`, `parse_iteration_marker` | `---` block + `ITERATION_RESULT:` marker |
| `command_policy` | `evaluate_command_policy` | allow/deny + reason |
| `session_start` | `construct_research_config` | legacy request → `ResearchConfig` asdict |
| `phase_advancement` | `build_phase_state` | phase-plan derivation |
| `promotion_preview` | `config_promoter.preview` | async; seeded via `replay_fixture` |
