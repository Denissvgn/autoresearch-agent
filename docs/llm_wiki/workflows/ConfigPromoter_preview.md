# ConfigPromoter_preview

**Entry point:** `config_promoter.ConfigPromoter.preview`
**Modules involved:** [artifact_reference](../modules/artifact_reference.md), [blocker_classifier](../modules/blocker_classifier.md), [compat_legacy_alias](../modules/compat_legacy_alias.md), [config_promoter](../modules/config_promoter.md), [consistency_validator](../modules/consistency_validator.md), [development_inference_validation](../modules/development_inference_validation.md), [development_signal_health](../modules/development_signal_health.md), [gate_status](../modules/gate_status.md), [objective_comparator](../modules/objective_comparator.md), [promotion_approval](../modules/promotion_approval.md), [research_phase_plan](../modules/research_phase_plan.md)

> Dry-run promotion: returns the diff/preview without writing.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `objective_comparator.objective_comparator_for_skill_id`
2. `objective_comparator.ObjectiveComparator`
3. `research_phase_plan.build_phase_state`
4. `gate_status.training_gates_passed_from_iteration`
5. `artifact_reference.first_valid_artifact_ref`
6. `development_signal_health.build_development_signal_health`
7. `development_inference_validation.build_development_inference_validation`
8. `consistency_validator.build_consistency_report`
9. `compat_legacy_alias.model_type_to_skill_id`
10. `promotion_approval.target_identity`
11. `blocker_classifier.classify_blockers`

## Touches

- [artifact_reference](../modules/artifact_reference.md)
- [blocker_classifier](../modules/blocker_classifier.md)
- [compat_legacy_alias](../modules/compat_legacy_alias.md)
- [config_promoter](../modules/config_promoter.md)
- [consistency_validator](../modules/consistency_validator.md)
- [development_inference_validation](../modules/development_inference_validation.md)
- [development_signal_health](../modules/development_signal_health.md)
- [gate_status](../modules/gate_status.md)
- [objective_comparator](../modules/objective_comparator.md)
- [promotion_approval](../modules/promotion_approval.md)
- [research_phase_plan](../modules/research_phase_plan.md)

## Behavior

This workflow starts at `config_promoter.ConfigPromoter.preview`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
