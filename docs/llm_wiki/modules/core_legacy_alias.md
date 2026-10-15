# legacy_alias Module

**Path:** `src/core/legacy_alias.py`

## Description

Back-compat shim (P1-2): the legacy alias registry moved to
src/compat/legacy_alias.py; every importer keeps working.

## Imports

| Source | Symbols |
|--------|---------|
| `src.compat.legacy_alias` | `is_known_model_type`, `model_type_to_skill_id`, `skill_id_to_model_type` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/api/promotion.py"]
    n1["src/api/research.py"]
    n2["src/api/results.py"]
    n3["src/api/skills.py"]
    n4["src/compat/legacy_alias.py"]
    n5["src/core/config_promoter.py"]
    n6["src/core/legacy_alias.py"]
    n7["src/core/research_manifest.py"]
    n8["src/ws/events.py"]
    n9["tests/test_research_config.py"]
    n0 --> n5
    n0 --> n6
    n1 --> n6
    n2 --> n6
    n3 --> n6
    n5 --> n6
    n6 --> n4
    n7 --> n6
    n8 --> n6
    n9 --> n6
    click n0 "../modules/promotion.md"
    click n1 "../modules/research.md"
    click n2 "../modules/results.md"
    click n3 "../modules/src_api_skills.md"
    click n4 "../modules/compat_legacy_alias.md"
    click n5 "../modules/config_promoter.md"
    click n6 "../modules/core_legacy_alias.md"
    click n7 "../modules/research_manifest.md"
    click n8 "../modules/events.md"
    click n9 "../modules/test_research_config.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [promotion](../modules/promotion.md) |
| Inbound | [research](../modules/research.md) |
| Inbound | [results](../modules/results.md) |
| Inbound | [src_api_skills](../modules/src_api_skills.md) |
| Inbound | [config_promoter](../modules/config_promoter.md) |
| Inbound | [research_manifest](../modules/research_manifest.md) |
| Inbound | [events](../modules/events.md) |
| Inbound | [test_research_config](../modules/test_research_config.md) |
| Outbound | [compat_legacy_alias](../modules/compat_legacy_alias.md) |
