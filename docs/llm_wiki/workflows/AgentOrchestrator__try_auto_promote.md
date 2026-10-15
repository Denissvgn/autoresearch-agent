# AgentOrchestrator__try_auto_promote

**Entry point:** `orchestrator.AgentOrchestrator._try_auto_promote`
**Modules involved:** [config_promoter](../modules/config_promoter.md), [gate_status](../modules/gate_status.md), [orchestrator](../modules/orchestrator.md), [research_phase_plan](../modules/research_phase_plan.md)

> Auto-promote the best iteration if it is promotion-ready.

Instantiates ConfigPromoter on-demand (not injected into __init__
to avoid circular dependencies or changing the constructor).

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `gate_status.training_gates_passed_from_iteration`
2. `config_promoter.ConfigPromoter`
3. `config_promoter.ConfigPromoter`
4. `research_phase_plan.incomplete_phase_ids`

## Touches

- [config_promoter](../modules/config_promoter.md)
- [gate_status](../modules/gate_status.md)
- [orchestrator](../modules/orchestrator.md)
- [research_phase_plan](../modules/research_phase_plan.md)

## Behavior

This workflow starts at `orchestrator.AgentOrchestrator._try_auto_promote`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
