# lifespan

**Entry point:** `main.lifespan`
**Modules involved:** [config_promoter](../modules/config_promoter.md), [harnesses](../modules/harnesses.md), [postgres_state_store](../modules/postgres_state_store.md), [promotion](../modules/promotion.md), [research](../modules/research.md), [results](../modules/results.md), [session_manager](../modules/session_manager.md), [skill_registry](../modules/skill_registry.md), [src_api_skills](../modules/src_api_skills.md), [src_main](../modules/src_main.md), [subjects](../modules/subjects.md)

> Startup and shutdown logic.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `postgres_state_store.build_state_store`
2. `session_manager.SessionManager`
3. `config_promoter.ConfigPromoter`
4. `skill_registry.SkillRegistry`
5. `skill_registry.SkillRegistry.discover`
6. `src_api_skills.init`
7. `subjects.init`
8. `research.init`
9. `results.init`
10. `promotion.init`
11. `harnesses.init`

## Touches

- [config_promoter](../modules/config_promoter.md)
- [harnesses](../modules/harnesses.md)
- [postgres_state_store](../modules/postgres_state_store.md)
- [promotion](../modules/promotion.md)
- [research](../modules/research.md)
- [results](../modules/results.md)
- [session_manager](../modules/session_manager.md)
- [skill_registry](../modules/skill_registry.md)
- [src_api_skills](../modules/src_api_skills.md)
- [src_main](../modules/src_main.md)
- [subjects](../modules/subjects.md)

## Behavior

This workflow starts at `main.lifespan`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
