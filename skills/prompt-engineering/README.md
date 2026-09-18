# Prompt evaluator deployment contract

## Live evaluation

Pass `skill_params.eval_set` and `skill_params.scorer_url` at session creation.
The bootstrap reads an absolute dataset path, or a path relative to the real
session workspace (including during dry bootstrap). It validates data before
writing anything: UTF-8 JSONL, 1–10,000 rows, at most 5 MiB, each row containing
only nonempty string `input` and `expected` fields. Symlinks, parent traversal,
nonregular files, and non-JSONL paths are rejected. Provision datasets in an
operator-controlled location; path validation is not a filesystem sandbox.
Only validated data is written to `eval_set.jsonl`. Existing prompts are
preserved; a conflicting existing dataset fails rather than being overwritten.
Executable files are never copied from the dataset directory or workspace.

`ManifestSkillRuntime.experiment_command(config)` supplies the selected scorer
explicitly and pins the staged dataset. `evaluator_command_params(config)`
returns the corresponding server-owned argument mapping. No `OPENAI_API_KEY`,
`OPENAI_BASE_URL`, or `SCORER_URL` is forwarded or consumed by this evaluator.
Deploy an explicit remote scorer if provider-backed judging is needed.

The remote service receives `{"prompt": "...", "examples": [...]}` via POST.
A successful HTTP 200 response must be a JSON object with numeric `score` or
`composite_eval_score` in [0,1]. Optional `precision` must also be numeric in
[0,1] (defaults to the score); optional `status` must be `completed`. Nonfinite
values, booleans, malformed or oversized responses, redirects, timeouts and
transport errors emit `eval_error`, a null primary metric, false gates and a
nonzero exit. They never fall through to demo success. Cost remains the
existing estimate of $0.01 per example, not measured provider billing.

## Explicit demo

Only server settings `demo_mode is True`, outside production, authorize the
runtime's `--demo true` parameter and the bootstrap's top-level `demo_mode`
boolean. A `skill_params.demo_mode` value does not grant permission. Without
an explicit dataset, this mode alone supplies the two-row example dataset.
With no remote endpoint, it preserves deterministic `scorer: fallback` results.
A configured remote scorer still fails closed in demo mode.

## Required integration outside this patch's ownership

The execution boundary must consume `evaluator_command_params(config)` and
replace/reject all agent-supplied forms of `--eval`, `--scorer-url`, and `--demo`
(including equals syntax, duplicates and argparse abbreviations). Suggestions
in a prompt are NOT authorization. Resolve the evaluator through packaged
`script_paths`, never a workspace `eval/run.py`. Until this enforcement is
wired, an agent can request `--demo true`; do not treat this patch alone as an
end-to-end live promotion boundary.

The session initialization owner must call `BootstrapRunner.run` with the
persisted session `skill_params`; direct plugin callers must supply the trusted
top-level demo boolean themselves. The mock-provider owner should use the
runtime-resolved experiment command rather than its hardcoded default.
Protect or verify the staged dataset against agent mutation at execution, and
bind promotion evidence to that dataset. No broad credential forwarding is
needed. The server also owns endpoint authorization/network egress policy;
HTTP URL syntax validation alone is not endpoint authorization.
