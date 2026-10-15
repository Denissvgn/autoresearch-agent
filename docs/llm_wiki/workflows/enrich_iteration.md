# enrich_iteration

**Entry point:** `results._enrich_iteration`
**Modules involved:** [artifact_reference](../modules/artifact_reference.md), [compat_legacy_alias](../modules/compat_legacy_alias.md), [consistency_validator](../modules/consistency_validator.md), [gate_status](../modules/gate_status.md), [ml_enrichment](../modules/ml_enrichment.md), [results](../modules/results.md)

> Add parsed metrics, MLflow link, and secondary metrics to an iteration dict.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `gate_status.training_gates_passed_from`
2. `artifact_reference.first_valid_artifact_ref`
3. `consistency_validator.parse_consistency_report`
4. `consistency_validator.build_consistency_report`
5. `artifact_reference.first_valid_artifact_ref`
6. `ml_enrichment._rl_economic_replay`
7. `ml_enrichment._rl_economic_replay_summary`
8. `ml_enrichment._feature_readiness_metrics`
9. `compat_legacy_alias.model_type_to_skill_id`

## Touches

- [artifact_reference](../modules/artifact_reference.md)
- [compat_legacy_alias](../modules/compat_legacy_alias.md)
- [consistency_validator](../modules/consistency_validator.md)
- [gate_status](../modules/gate_status.md)
- [ml_enrichment](../modules/ml_enrichment.md)
- [results](../modules/results.md)

## Behavior

This workflow starts at `results._enrich_iteration`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
