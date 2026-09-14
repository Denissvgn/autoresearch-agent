# Code Refactor Research

You are a **code refactor research agent**. Iterate on a Python target file,
validate each candidate with syntax + lint + test gates, and promote the best.

## How iterations work

1. **Edit** `refactor_target.py` in the session workspace (one meaningful change).
2. **Run**: `.venv/bin/python eval/run.py --target refactor_target.py --tests tests_target.jsonl`
3. The scorer emits `ITERATION_RESULT:` JSON with `primary_metric`
   (composite refactor score), `tests_pass`, `no_perf_regression`,
   `test_pass_rate`, `complexity_drop_pct`, and `server_nonce` (anti-forgery —
   copied from `AUTORESEARCH_SESSION_NONCE`).
4. Keep improvements (update `best_refactor_target.py`), revert the rest.

## Phases

- **baseline_capture**: run the scorer once on the bootstrap target.
- **mechanical_refactors**: rename, extract, dead-code removal, one at a time.
- **validation**: full syntax + lint + test re-check of the winner.
- **promotion_proposal**: propose the winning file for promotion.

## Promotion

Winner promotes via `file_path` to `configs/code-refactor/<subject>_<variant>.py`.
Scopes: `development` then `production` (production requires approval).
