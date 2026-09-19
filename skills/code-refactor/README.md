# Code Refactor Research

Iterate refactors of a Python target file against syntax, lint, and test
gates; promote the winner as a file. Fully offline — no external services.

## Session flow

1. The service's start path runs this skill's `bootstrap.py`, rendering the
   session workspace: `refactor_target.py` (the default target),
   `best_refactor_target.py`, and `tests_target.jsonl` (a JSONL ledger of
   `{pattern}` rows the scorer greps the target for).
2. Each iteration edits `refactor_target.py`, then runs the evaluator
   (cwd = workspace root, so paths in the demo command are absolute):

   ```bash
   .venv/bin/python eval/run.py --target <session_ws>/refactor_target.py \
     --tests <session_ws>/tests_target.jsonl
   ```

3. The evaluator (offline static analysis: AST parse, a lint heuristic,
   ledger-based test pass rate, a complexity-drop estimate) emits an
   `ITERATION_RESULT:` marker with the anti-forgery nonce; the server
   verifies the nonce and records the iteration.

## Contract details

- **Config artifact flag**: `command_policy.config_flag: --target` — the
  pre-run snapshot (and policy confinement) key on the `--target` file, so
  every iteration carries its exact refactored source for promotion.
- **Gates**: `tests_pass` (100% ledger pass rate) and `no_perf_regression`
  (≤ 10 lint issues); both must pass for `training_gates_passed`.
- **Promotion**: `file_path` to the declared
  `configs/code-refactor/{subject_id}_{variant}.py` template under
  `AUTORESEARCH_HOST_CONFIGS_PATH` (development scope; production requires
  the HMAC-signed approval). Rollback restores the previous content at the
  recorded path.
