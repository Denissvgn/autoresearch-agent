# Latency Minimization Benchmark Package (`skills/latency-benchmark/`)

This directory holds the frozen workload and agent primer for the measured
latency-minimization qualification domain (`src/core/latency_benchmark.py`).

## Contents

- `SKILL.md` — Domain instructions for the measured latency minimization loop.
- `workload.json` — Frozen key/value workload specification, seeded request mix,
  protocol parameters (`warmup_requests`, `repeats`, `requests_per_repeat`,
  `p_target`, guardrails, `max_uncertainty`, `min_improvement`, resource
  envelope), and the pinned `context_digest`.

## Relationship to `SkillRegistry`

Unlike the three manifest-driven `research_skill.v1` skills (`prompt-engineering`,
`code-refactor`, and `db-config-tuning`), `latency-benchmark` does not declare a
`SKILL.yaml` manifest; `SkillRegistry().discover()` intentionally enumerates only
`SKILL.yaml` packages. The latency benchmark harness consumes `workload.json`
and `SKILL.md` directly via `src/core/latency_benchmark.py` so the frozen
protocol and workload digests remain immutable across baseline and candidate
comparisons.
