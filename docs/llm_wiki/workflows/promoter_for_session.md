# promoter_for_session

**Entry point:** `promotion._promoter_for_session`
**Modules involved:** [compat_legacy_alias](../modules/compat_legacy_alias.md), [config_promoter](../modules/config_promoter.md), [promotion](../modules/promotion.md), [promotion_target](../modules/promotion_target.md)

> Pick the promoter for a session (P1-3, centralized by P7-007).

Returns ``(promoter, skill_id)`` — the skill id is the session-resolved
identity ``_inject_target_kind`` keys on (ARC-012 P7-011: non-ML sessions
carry model_type="", so it cannot be derived from the preview result's
legacy fields alone).

Default: the injected ``_promoter`` (singleton, file target). When the
session's skill resolves (registry wired, skill_id on the row or derived
from the legacy ``model_type`` alias), the promotion target comes from the
SAME resolution site as the orchestrator's auto-promote path
(``promotion_target_from_manifest``): ``file_path`` (with the skill's
declared ``path_template``) / ``webhook`` / ``registry_api`` all get a
per-request ``ConfigPromoter`` over the resolved target. Anything that
cannot be resolved (unknown skill, missing endpoint, stubbed registry,
unwired target kind) falls back to the injected promoter — never fails
the request here.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `compat_legacy_alias.model_type_to_skill_id`
2. `promotion_target.promotion_target_from_manifest`
3. `config_promoter.ConfigPromoter`

## Touches

- [compat_legacy_alias](../modules/compat_legacy_alias.md)
- [config_promoter](../modules/config_promoter.md)
- [promotion](../modules/promotion.md)
- [promotion_target](../modules/promotion_target.md)

## Behavior

This workflow starts at `promotion._promoter_for_session`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
