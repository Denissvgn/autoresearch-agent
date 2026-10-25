# test_release_promotion_safety Module

**Path:** `tests/test_release_promotion_safety.py`

## Description

Release regressions for durable remote rollback and candidate binding.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `hashlib` | `hashlib` |
| `httpx` | `httpx` |
| `json` | `json` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `src.api` | `promotion` |
| `src.config` | `settings` |
| `src.core.config_promoter` | `ConfigPromoter` |
| `src.core.promotion_approval` | `target_identity` |
| `src.core.promotion_target` | `WebhookDeliveryError`, `WebhookPromotionTarget` |
| `src.core.results_store` | `ResultsStore` |
| `src.core.skill_registry` | `SkillRegistry` |
| `tests.test_webhook_promotion` | `_patch_mock_transport`, `_seed_completed_skill_session` |
| `unittest.mock` | `AsyncMock` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/api/promotion.py"]
    n1["src/config.py"]
    n2["src/core/config_promoter.py"]
    n3["src/core/promotion_approval.py"]
    n4["src/core/promotion_target.py"]
    n5["src/core/results_store.py"]
    n6["src/core/skill_registry.py"]
    n7["tests/test_release_promotion_safety.py"]
    n8["tests/test_webhook_promotion.py"]
    n0 --> n1
    n0 --> n2
    n0 --> n3
    n0 --> n4
    n2 --> n1
    n2 --> n3
    n2 --> n4
    n2 --> n6
    n4 --> n1
    n4 --> n6
    n7 --> n0
    n7 --> n1
    n7 --> n2
    n7 --> n3
    n7 --> n4
    n7 --> n5
    n7 --> n6
    n7 --> n8
    n8 --> n0
    n8 --> n1
    n8 --> n2
    n8 --> n4
    n8 --> n5
    n8 --> n6
    click n0 "../modules/promotion.md"
    click n1 "../modules/config.md"
    click n2 "../modules/config_promoter.md"
    click n3 "../modules/promotion_approval.md"
    click n4 "../modules/promotion_target.md"
    click n5 "../modules/results_store.md"
    click n6 "../modules/skill_registry.md"
    click n7 "../modules/test_release_promotion_safety.md"
    click n8 "../modules/test_webhook_promotion.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Outbound | [promotion](../modules/promotion.md) |
| Outbound | [config](../modules/config.md) |
| Outbound | [config_promoter](../modules/config_promoter.md) |
| Outbound | [promotion_approval](../modules/promotion_approval.md) |
| Outbound | [promotion_target](../modules/promotion_target.md) |
| Outbound | [results_store](../modules/results_store.md) |
| Outbound | [skill_registry](../modules/skill_registry.md) |
| Outbound | [test_webhook_promotion](../modules/test_webhook_promotion.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 2 | 1 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `test_confirmation_rejects_candidate_changed_since_approval` | *(async)* `(field, value)` | `@pytest.mark.asyncio`, `@pytest.mark.parametrize('field,value', [('iteration', 8), ('config_snapshot_sha256', 'b' * 64), ('target_identity', 'c' * 64)])` | — |
| `test_confirmation_records_exact_approved_preview` | *(async)* `(tmp_path)` | `@pytest.mark.asyncio` | — |
| `test_webhook_rollback_after_restart_uses_recorded_destination` | *(async)* `(monkeypatch, tmp_path, fail_restore)` | `@pytest.mark.asyncio`, `@pytest.mark.parametrize('fail_restore', [False, True])` | — |
| `test_failed_delivery_preserves_local_provenance` | *(async)* `(monkeypatch, tmp_path)` | `@pytest.mark.asyncio` | — |
| `test_file_path_skill_rollback_restores_promoted_template` | *(async)* `(monkeypatch, tmp_path)` | `@pytest.mark.asyncio` | ARC-012 P7-014: a ``file_path`` skill's rollback restores the previous |
