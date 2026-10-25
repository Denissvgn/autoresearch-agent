"""autoresearch CLI — operator entry points (P2 Skill SDK).

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
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # pragma: no cover - import-time typing only
    from src.core.skill_generator import CommandPolicyFinding

# NOTE: core imports are deliberately lazy (inside the command functions):
# src.config constructs Settings at import time and requires LLM credentials,
# but --help and promote-skill must work on a bare checkout without them.

#: Exit codes (stable contract for scripts/CI).
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BLOCKED = 2  # validation / policy block — nothing was written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autoresearch",
        description=(
            "autoresearch-agent operator CLI. Today: the Skill SDK "
            "(new-skill / promote-skill)."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    from src.agent_cli import build_agent_parser

    build_agent_parser(sub)

    new_skill = sub.add_parser(
        "new-skill",
        help="Draft a new skill package from a natural-language goal (LLM).",
        description=(
            "Generate a research_skill.v1 draft (manifest + bootstrap + eval "
            "+ primer) into skills/_drafts/<id>/ from a goal description. "
            "The draft is validated, linted, and policy-audited before it "
            "is written; it is NOT selectable for production until promoted."
        ),
    )
    new_skill.add_argument(
        "--goal", required=True,
        help="Natural-language description of the research domain.",
    )
    new_skill.add_argument(
        "--id", default=None,
        help="Override the generated kebab-case skill id.",
    )
    new_skill.add_argument(
        "--provider",
        default="anthropic",
        choices=[
            "anthropic",
            "openai",
            "openai-compatible",
            "ollama",
            "vllm",
            "lmstudio",
            "llamacpp",
            "local",
            "openrouter",
        ],
        help=(
            "LLM provider for generation (default: anthropic, or "
            "AUTORESEARCH_LLM_PROVIDER when set)."
        ),
    )
    new_skill.add_argument(
        "--model", default=None,
        help=(
            "Model id (default: settings.anthropic_model for anthropic, or "
            "AUTORESEARCH_LLM_MODEL / OPENAI_MODEL; required otherwise)."
        ),
    )
    new_skill.add_argument(
        "--dry-run", action="store_true",
        help="Generate into a throwaway dir; nothing under skills/ is written.",
    )
    new_skill.add_argument(
        "--dry-bootstrap", action="store_true",
        help=(
            "Execute the generated bootstrap.py under strict plugin caps in "
            "a temp workspace and print the rendered file tree (preview only)."
        ),
    )
    _add_promote_flags(new_skill, inline=True)

    promote = sub.add_parser(
        "promote-skill",
        help="Move a reviewed draft from skills/_drafts/ into skills/.",
        description=(
            "Promote skills/_drafts/<id>/ → skills/<id>/ after review. "
            "Refuses when critical command-policy findings are present "
            "(unless --allow-critical) or a stable package already exists."
        ),
    )
    promote.add_argument("--id", required=True, help="The draft skill id.")
    _add_promote_flags(promote, inline=False)

    reconcile = sub.add_parser(
        "reconcile-bests",
        help="Reconcile historical session bests under their known objective.",
        description=(
            "Re-derive each session's stored best under its declared objective "
            "and report inconsistencies. Rows with enough provenance can be "
            "migrated with --apply; ambiguous legacy objective data is "
            "flagged, never guessed."
        ),
    )
    reconcile.add_argument(
        "--db", default=None,
        help="SQLite DB path (default: settings.db_path).",
    )
    reconcile.add_argument(
        "--apply", action="store_true",
        help="Write corrections for reconcilable sessions (dry-run otherwise).",
    )

    return parser


def _add_promote_flags(p: argparse.ArgumentParser, *, inline: bool) -> None:
    p.add_argument(
        "--promote", action="store_true",
        help=(
            "Promote the draft into skills/ after generation"
            if inline else argparse.SUPPRESS
        ),
    )
    p.add_argument(
        "--yes", action="store_true",
        help="Non-interactive: skip the confirmation prompt.",
    )
    p.add_argument(
        "--allow-critical", action="store_true",
        help="Promote even when the policy audit reported critical findings.",
    )
    p.add_argument(
        "--no-tag", action="store_true",
        help="Skip the best-effort skill/<id>/<version> git tag.",
    )
    p.add_argument(
        "--skills-root", default=None, type=Path,
        help="Override the skills root (default: the packaged skills/ dir).",
    )


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------


def _print_draft_report(draft: Any, *, dry_run: bool) -> None:
    files = ["SKILL.yaml", "bootstrap.py"]
    if draft.skill_md:
        files.append("SKILL.md")
    if draft.eval_run_py:
        files.append("eval/run.py")
    where = (
        f"{draft.skill_dir}  (dry-run — discarded)"
        if dry_run else str(draft.skill_dir)
    )
    print(f"draft generated: {draft.skill_id}")
    print(f"  dir:   {where}")
    print(f"  files: {', '.join(files)}")
    _print_findings(draft.policy_findings)
    if not dry_run:
        print("next: review the draft, then promote it:")
        print(f"  autoresearch promote-skill --id {draft.skill_id}")


def _print_findings(findings: list[Any]) -> None:
    if not findings:
        print("policy audit: clean")
        return
    critical = sum(1 for f in findings if f.severity == "critical")
    print(
        f"policy audit: {len(findings)} finding(s), {critical} critical "
        "(review before promoting; critical blocks promotion)"
    )
    for f in findings:
        print(f"  [{f.severity}] {f.location}: {f.reason}")


def _confirm(question: str, *, yes: bool) -> bool:
    if yes:
        return True
    try:
        answer = input(f"{question} [y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


# ---------------------------------------------------------------------------
# new-skill
# ---------------------------------------------------------------------------


async def cmd_new_skill(args: argparse.Namespace) -> int:
    from src.config import settings
    from src.core.llm_provider import build_provider
    from src.core.skill_generator import SkillGenerationError, SkillGenerator

    provider_id = args.provider
    if provider_id == "anthropic" and getattr(settings, "llm_provider", ""):
        provider_id = settings.llm_provider
    default_non_anthropic_model = (
        getattr(settings, "llm_model", "") or getattr(settings, "openai_model", "")
    )
    model = args.model or (
        (getattr(settings, "llm_model", "") or settings.anthropic_model)
        if provider_id == "anthropic"
        else (default_non_anthropic_model or None)
    )
    if not model:
        print(
            f"error: --model is required for --provider {provider_id} "
            "(no default model is configured)",
            file=sys.stderr,
        )
        return EXIT_ERROR
    try:
        provider = build_provider(provider_id)
    except Exception as exc:  # noqa: BLE001 — surface a friendly credential hint
        print(
            f"error: provider {args.provider!r} is not usable: {exc}\n"
            "hint: new-skill needs a real LLM — set ANTHROPIC_AUTH_TOKEN "
            "(or OPENAI_API_KEY) or pass --provider accordingly.",
            file=sys.stderr,
        )
        return EXIT_ERROR

    # --dry-run: the generator's drafts_root_override seam — a throwaway
    # root means nothing under the real skills/ tree is ever touched.
    # --skills-root governs the whole command coherently: drafts land under
    # <skills-root>/_drafts/ and promotion moves into <skills-root>/.
    drafts_root: Optional[Path] = None
    cleanup_root: Optional[Path] = None
    if args.dry_run:
        cleanup_root = Path(tempfile.mkdtemp(prefix="ar-newskill-dryrun-"))
        drafts_root = cleanup_root / "_drafts"
    elif args.skills_root is not None:
        drafts_root = args.skills_root / "_drafts"

    generator = SkillGenerator(drafts_root_override=drafts_root)
    try:
        draft = await generator.generate(
            description=args.goal,
            provider=provider,
            model=model,
            skill_id=args.id,
        )
    except SkillGenerationError as exc:
        print(f"error: generation failed (nothing written): {exc}", file=sys.stderr)
        if cleanup_root is not None:
            shutil.rmtree(cleanup_root, ignore_errors=True)
        return EXIT_BLOCKED

    _print_draft_report(draft, dry_run=args.dry_run)

    if args.dry_bootstrap:
        await _preview_bootstrap(draft.skill_dir)

    exit_code = EXIT_OK
    if args.promote:
        if args.dry_run:
            print(
                "note: --promote ignored with --dry-run (a discarded draft "
                "cannot be promoted); re-run without --dry-run",
                file=sys.stderr,
            )
        else:
            exit_code = await _promote_flow(
                skill_id=draft.skill_id,
                findings=draft.policy_findings,
                args=args,
            )
    if cleanup_root is not None:
        shutil.rmtree(cleanup_root, ignore_errors=True)
    return exit_code


async def _preview_bootstrap(draft_dir: Path) -> None:
    """Run the draft bootstrap.py under strict caps; print the rendered tree."""
    from src.core.plugin_runner import PluginRunner
    from src.core.skill_manifest import PluginCaps

    if not (draft_dir / "bootstrap.py").is_file():
        print("dry-bootstrap: draft has no bootstrap.py — nothing to preview")
        return
    preview_ws = Path(tempfile.mkdtemp(prefix="ar-bootstrap-preview-"))
    try:
        result = await PluginRunner().run(
            skill_dir=draft_dir,
            plugin="bootstrap.py",
            kind="bootstrap",
            input_json={
                "workspace": str(preview_ws),
                "mode": "live",
                "skill_params": {},
            },
            caps=PluginCaps(fs_write="workspace", timeout_s=30.0),
            workspace=preview_ws,
        )
        if not result.ok:
            print(f"dry-bootstrap: FAILED — {result.error}")
            return
        rendered = sorted(
            str(p.relative_to(preview_ws))
            for p in preview_ws.rglob("*")
            if p.is_file()
        )
        print(f"dry-bootstrap: bootstrap.py rendered {len(rendered)} file(s):")
        for rel in rendered:
            print(f"  {rel}")
    finally:
        shutil.rmtree(preview_ws, ignore_errors=True)


# ---------------------------------------------------------------------------
# promotion
# ---------------------------------------------------------------------------


async def _promote_flow(
    *, skill_id: str, findings: list[Any], args: argparse.Namespace,
) -> int:
    from src.core.promotion_target import (
        SkillPromotionError,
        SkillRegistryPromotionTarget,
    )

    critical = [f for f in findings if f.severity == "critical"]
    if critical and not args.allow_critical:
        print(
            f"error: {len(critical)} critical policy finding(s) block "
            "promotion — review them, then pass --allow-critical to override:",
            file=sys.stderr,
        )
        for f in critical:
            print(f"  [critical] {f.location}: {f.reason}", file=sys.stderr)
        return EXIT_BLOCKED
    target = SkillRegistryPromotionTarget(
        skills_root=args.skills_root,
    )
    if not target.draft_exists(skill_id):
        print(
            f"error: no draft for {skill_id!r} under {target.draft_path(skill_id)}",
            file=sys.stderr,
        )
        return EXIT_ERROR
    if target.stable_exists(skill_id):
        print(
            f"error: a stable package already exists at "
            f"{target.stable_path(skill_id)}",
            file=sys.stderr,
        )
        return EXIT_ERROR
    if not _confirm(
        f"Promote draft {skill_id!r} into the live skills tree?",
        yes=args.yes,
    ):
        print("aborted — nothing was moved.")
        return EXIT_BLOCKED
    try:
        result = await target.promote(skill_id)
    except SkillPromotionError as exc:
        print(f"error: promotion failed: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"promoted: {result.draft_path} → {result.stable_path}")
    if not args.no_tag:
        _tag_promoted_skill(skill_id, Path(result.stable_path))
    print(
        "next: restart the service (or POST /skills/reload in dev) to pick "
        "the skill up."
    )
    return EXIT_OK


def _tag_promoted_skill(skill_id: str, stable_dir: Path) -> None:
    """Best-effort annotated git tag ``skill/<id>/<version>`` for the promotion.

    Skips silently (warn-level) when the skills tree is not inside a git repo
    or git is unavailable — promotion itself must never depend on git.
    """
    from src.core.skill_loader import load_skill_manifest

    try:
        manifest = load_skill_manifest(
            (stable_dir / "SKILL.yaml").read_text(encoding="utf-8")
        )
        version = manifest.version
    except Exception as exc:  # noqa: BLE001 — tag is best-effort, never blocking
        print(f"git tag skipped: could not read promoted manifest version ({exc})")
        return
    tag = f"skill/{skill_id}/{version}"
    try:
        repo = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(stable_dir), capture_output=True, text=True, timeout=10,
        )
        if repo.returncode != 0:
            print("git tag skipped: skills tree is not inside a git repo")
            return
        created = subprocess.run(
            ["git", "tag", "-a", tag, "-m", f"promote skill {skill_id} {version}"],
            cwd=str(stable_dir), capture_output=True, text=True, timeout=10,
        )
        if created.returncode != 0:
            print(f"git tag skipped: {created.stderr.strip() or tag}")
            return
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"git tag skipped: {exc}")
        return
    print(f"git tag: {tag}")


async def cmd_promote_skill(args: argparse.Namespace) -> int:
    # A promote-skill invocation re-runs the audit on the draft's manifest so
    # the critical-finding gate cannot be bypassed by promoting later.
    from src.core.promotion_target import SkillRegistryPromotionTarget
    from src.core.skill_generator import audit_command_policy

    draft_manifest = (
        SkillRegistryPromotionTarget(skills_root=args.skills_root)
        .draft_path(args.id) / "SKILL.yaml"
    )
    if not draft_manifest.is_file():
        print(f"error: no draft manifest at {draft_manifest}", file=sys.stderr)
        return EXIT_ERROR
    findings = audit_command_policy(draft_manifest.read_text(encoding="utf-8"))
    return await _promote_flow(
        skill_id=args.id, findings=findings, args=args,
    )


async def cmd_reconcile_bests(args: argparse.Namespace) -> int:
    """Report (or with --apply, migrate) historical bests under known objectives."""
    from src.config import settings
    from src.core.objective_comparator import reconcile_historical_best
    from src.core.results_store import ResultsStore

    store = ResultsStore(args.db or settings.db_path)
    await store.initialize()
    try:
        sessions = await store.list_sessions(limit=None)
        counts: dict[str, int] = {}
        for session in sessions:
            iterations = await store.get_iterations(session["id"])
            report = reconcile_historical_best(
                session=session, iterations=iterations,
            )
            status = str(report["status"])
            counts[status] = counts.get(status, 0) + 1
            recomputed = report.get("recomputed") or {}
            stored = report["stored"]
            flags = ",".join(report["flags"]) or "-"
            print(
                f"{session['id']}: {status} "
                f"stored=({stored['best_iteration']}, {stored['best_metric']}) "
                f"recomputed=({recomputed.get('best_iteration')}, "
                f"{recomputed.get('best_metric')}) "
                f"objective={report['objective']['direction']} flags={flags}"
            )
            if args.apply and status == "reconciled":
                await store.update_session(
                    session["id"],
                    best_iteration=recomputed["best_iteration"],
                    best_metric=recomputed["best_metric"],
                )
        print(
            "reconcile-bests: "
            + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            + (" (applied)" if args.apply else " (dry-run)")
        )
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            await close()
    return EXIT_OK


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


from src.agent_cli import cmd_agent as _agent_command_handler

_COMMANDS = {
    "new-skill": cmd_new_skill,
    "promote-skill": cmd_promote_skill,
    "reconcile-bests": cmd_reconcile_bests,
    "agent": _agent_command_handler,
}


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    handler = _COMMANDS[args.command]
    try:
        return asyncio.run(handler(args))
    except KeyboardInterrupt:
        print("interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
