# PromotionTarget

**Location:** `src/core/promotion_target.py:56`
**Kind:** Class
**Bases:** `Protocol`
**Module:** [promotion_target](../modules/promotion_target.md)

## Description

Where a promoted config is written and how its path is derived
(ARC-011 P1-015).

A concrete target (``FilePathPromotionTarget`` in P1-016) implements this
surface. ``ConfigPromoter`` (P1-017) is wired to accept any
``PromotionTarget`` and delegates the file writes to it while keeping the
gate-evaluation logic (``preview`` / ``confirm`` / ``rollback``).

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `target_path` | `(*, model_type: str, instrument: str, timeframe: str, skill_id: str = '') -> str` | — | Derive the host config file path for a promoted config. |
| `metadata_sidecar_path` | `(target_path: str, iteration: int, *, scope: str = 'development') -> str` | — | Derive the JSON sidecar path recording this promotion's metadata. |
| `rollback_snapshot_path` | `(*, target_path: str, research_id: str, iteration: int) -> str` | — | Derive the path of the pre-promotion YAML snapshot used for rollback. |
| `rollback_metadata_sidecar_path` | `(target_path: str, promotion_id: int) -> str` | — | Derive the JSON sidecar path recording a rollback's metadata. |
| `write` | *(async)* `(path: str, content: str) -> None` | — | Atomically write ``content`` to ``path`` (tmp → fsync → os.replace). |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["PromotionTarget (src/core/promotion_target.py)"]
    n1["Protocol"]
    n2["ConfigPromoter.__init__ (src/core/config_promoter.py)"]
    n3["promotion_target_from_manifest (src/core/promotion_target.py)"]
    n4["ManifestSkillRuntime.promotion_target (src/core/skill_runtime.py)"]
    n5["SkillRuntime.promotion_target (src/core/skill_runtime.py)"]
    n6["tests/test_promotion_target.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    click n0 "../modules/promotion_target.md"
    click n2 "../modules/config_promoter.md"
    click n3 "../modules/promotion_target.md"
    click n4 "../modules/skill_runtime.md"
    click n5 "../modules/skill_runtime.md"
    click n6 "../modules/test_promotion_target.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [promotion_target](../modules/promotion_target.md) | 5 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `Protocol` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `ConfigPromoter.__init__` | type_reference | [config_promoter](../modules/config_promoter.md) | — |
| `promotion_target_from_manifest` | type_reference | [promotion_target](../modules/promotion_target.md) | — |
| `ManifestSkillRuntime.promotion_target` | type_reference | [skill_runtime](../modules/skill_runtime.md) | — |
| `SkillRuntime.promotion_target` | type_reference | [skill_runtime](../modules/skill_runtime.md) | — |
| `test_promotion_target` | import | [test_promotion_target](../modules/test_promotion_target.md) | — |
