# cli Module

**Path:** `src/cli.py`

## Description

autoresearch CLI — operator entry points (P2 Skill SDK).

``autoresearch new-skill --goal "..."`` wraps the Phase-5 generator machinery
(``SkillGenerator`` + the ``PluginRunner`` dry-bootstrap preview +
``SkillRegistryPromotionTarget`` promotion) into one operator command, so a new
research domain goes from a sentence to an installed, policy-audited skill
package without writing YAML by hand.

Design decisions (P1-007 house style):

* **argparse, zero new deps** — no click/typer in the repo; subcommands share
  one parser with a shared promote flag-group.
* **The CLI is operator-local.** No audit store, no HTTP surface: promotion
  confirmations are interactive (``--yes`` to skip), and critical
  command-policy findings block promotion unless ``--allow-critical``
  (mirrors the API's gate-keeping posture — the operator is the approval).
* **``--dry-run`` reuses the generator's existing seam.** The draft is
  generated into a throwaway ``drafts_root_override`` dir; nothing under
  ``skills/`` is touched.
* **``--dry-bootstrap`` is the T5 overlay preview.** The generated
  ``bootstrap.py`` executes under ``PluginRunner``'s strictest workspace caps
  into a temp preview dir; the rendered file tree is printed, then discarded.
* **Promotion records a git tag when it can.** ``skill/<id>/<version>`` is
  created best-effort (skills tree inside a git repo); failures warn and
  continue — a docker deployment without git must still promote.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `argparse` | `argparse` |
| `asyncio` | `asyncio` |
| `pathlib` | `Path` |
| `shutil` | `shutil` |
| `src.config` | `settings` |
| `src.core.llm_provider` | `build_provider` |
| `src.core.plugin_runner` | `PluginRunner` |
| `src.core.promotion_target` | `SkillPromotionError`, `SkillRegistryPromotionTarget`, `SkillRegistryPromotionTarget` |
| `src.core.skill_generator` | `CommandPolicyFinding`, `SkillGenerationError`, `SkillGenerator`, `audit_command_policy` |
| `src.core.skill_loader` | `load_skill_manifest` |
| `src.core.skill_manifest` | `PluginCaps` |
| `subprocess` | `subprocess` |
| `sys` | `sys` |
| `tempfile` | `tempfile` |
| `typing` | `TYPE_CHECKING`, `Any`, `Optional` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/cli.py"]
    n1["src/config.py"]
    n2["src/core/llm_provider.py"]
    n3["src/core/plugin_runner.py"]
    n4["src/core/promotion_target.py"]
    n5["src/core/skill_generator.py"]
    n6["src/core/skill_loader.py"]
    n7["src/core/skill_manifest.py"]
    n8["tests/test_cli.py"]
    n0 --> n1
    n0 --> n2
    n0 --> n3
    n0 --> n4
    n0 --> n5
    n0 --> n6
    n0 --> n7
    n2 --> n1
    n3 --> n7
    n4 --> n1
    n5 --> n6
    n5 --> n7
    n6 --> n1
    n6 --> n7
    n8 --> n0
    n8 --> n2
    click n0 "../modules/cli.md"
    click n1 "../modules/config.md"
    click n2 "../modules/llm_provider.md"
    click n3 "../modules/plugin_runner.md"
    click n4 "../modules/promotion_target.md"
    click n5 "../modules/skill_generator.md"
    click n6 "../modules/skill_loader.md"
    click n7 "../modules/skill_manifest.md"
    click n8 "../modules/test_cli.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [test_cli](../modules/test_cli.md) |
| Outbound | [config](../modules/config.md) |
| Outbound | [llm_provider](../modules/llm_provider.md) |
| Outbound | [plugin_runner](../modules/plugin_runner.md) |
| Outbound | [promotion_target](../modules/promotion_target.md) |
| Outbound | [skill_generator](../modules/skill_generator.md) |
| Outbound | [skill_loader](../modules/skill_loader.md) |
| Outbound | [skill_manifest](../modules/skill_manifest.md) |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `build_parser` | `() -> argparse.ArgumentParser` | — | — |
| `_add_promote_flags` | `(p: argparse.ArgumentParser, *, inline: bool) -> None` | — | — |
| `_print_draft_report` | `(draft: Any, *, dry_run: bool) -> None` | — | — |
| `_print_findings` | `(findings: list[Any]) -> None` | — | — |
| `_confirm` | `(question: str, *, yes: bool) -> bool` | — | — |
| `cmd_new_skill` | *(async)* `(args: argparse.Namespace) -> int` | — | — |
| `_preview_bootstrap` | *(async)* `(draft_dir: Path) -> None` | — | Run the draft bootstrap.py under strict caps; print the rendered tree. |
| `_promote_flow` | *(async)* `(*, skill_id: str, findings: list[Any], args: argparse.Namespace) -> int` | — | — |
| `_tag_promoted_skill` | `(skill_id: str, stable_dir: Path) -> None` | — | Best-effort annotated git tag ``skill/<id>/<version>`` for the promotion. |
| `cmd_promote_skill` | *(async)* `(args: argparse.Namespace) -> int` | — | — |
| `main` | `(argv: Optional[list[str]] = None) -> int` | — | — |
