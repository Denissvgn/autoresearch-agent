"""Skill path-template rendering (ARC-012 D4 / P7-005 / P7-007).

One closed placeholder vocabulary and one renderer for every path a skill
manifest can influence — the session workspace
(``workspace.session_path_template``) and the promotion target
(``promotion_target.primary.path_template``). Keeping the renderer in one
module is what makes the "add a skill directory, not a code change" guarantee
auditable: a template either renders here under the rules below or it fails
at skill-load time, never silently at first promotion.

Rules (D4, composed with the G6 loader semantics):

* Closed placeholder set. ``{skill_id}``/``{subject_id}``/``{variant}`` are
  the *identity* placeholders valid in path templates; ``{scope}``/
  ``{iteration}`` exist only in ``sidecar_extensions`` (they have no value at
  path-derivation time). Unknown single-word placeholders are rejected.
  Dotted namespaces — ``{settings.*}`` (resolved by the loader before
  validation) and ``{skill_params.*}`` (resolved at session build) — are G6
  vocabulary, pass through untouched, and are not rendered here.
* No ``..`` traversal, no backslashes. Absolute templates are NOT rejected:
  the G6 loader legitimately produces them by resolving
  ``{settings.host_configs_path}`` before validation — the sanctioned,
  operator-controlled escape hatch. Confinement is enforced where the
  untrusted values enter: rendered request-supplied segments.
* Rendered placeholder values are sanitized path segments: request-supplied
  ``subject_id``/``variant`` must not smuggle separators.
"""

from __future__ import annotations

from typing import Any, Optional

#: The full closed placeholder vocabulary for skill path templates.
PATH_TEMPLATE_PLACEHOLDERS = frozenset(
    {"skill_id", "subject_id", "variant", "scope", "iteration"}
)

#: Placeholders valid in a path template (renderable at derivation time).
PATH_TEMPLATE_IDENTITY_PLACEHOLDERS = frozenset(
    {"skill_id", "subject_id", "variant"}
)

_FORBIDDEN_SEGMENT_VALUES = frozenset({"", ".", ".."})


def sanitize_path_segment(value: str, *, field: str) -> str:
    """Reject values that cannot be a single safe path segment."""
    if value in _FORBIDDEN_SEGMENT_VALUES or any(
        char in value for char in ("/", "\\", "\x00")
    ):
        raise ValueError(
            f"{field} {value!r} is not a valid path segment "
            "(blank, '.', '..', or contains a path separator)"
        )
    return value


def validate_path_template(
    template: str, *, allowed: frozenset[str] = PATH_TEMPLATE_IDENTITY_PLACEHOLDERS
) -> None:
    """Validate a skill-declared path template at load time.

    Raises ``ValueError`` for blank templates, traversal, backslashes, or
    single-word placeholders outside the allowed set. Dotted namespaces
    (``{settings.*}`` / ``{skill_params.*}``) are G6 vocabulary and are not
    matched by the token check. Absolute templates are accepted — see the
    module docstring for why (G6 resolution).
    """
    if not template or not template.strip():
        raise ValueError("path template must not be blank")
    if "\\" in template:
        raise ValueError(
            f"path template {template!r} must not contain backslashes"
        )
    segments = template.split("/")
    if any(segment == ".." for segment in segments):
        raise ValueError(f"path template {template!r} must not traverse (..)")
    for token in _template_placeholder_tokens(template):
        if token not in allowed:
            if token in PATH_TEMPLATE_PLACEHOLDERS:
                raise ValueError(
                    f"path template {template!r} uses placeholder {{{token}}} "
                    "that has no value at path-derivation time (sidecar-only)"
                )
            raise ValueError(
                f"path template {template!r} uses unknown placeholder "
                f"{{{token}}}; known placeholders: "
                f"{sorted(PATH_TEMPLATE_PLACEHOLDERS)}"
            )


def render_path_template(
    template: str,
    *,
    skill_id: str,
    subject_id: str,
    variant: str,
) -> str:
    """Render an identity-placeholder template into a relative path.

    Every placeholder value is sanitized as a single path segment, so the
    rendered result can never escape the root the caller joins it under.
    """
    validate_path_template(template)
    values = {
        "skill_id": sanitize_path_segment(skill_id, field="skill_id"),
        "subject_id": sanitize_path_segment(subject_id, field="subject_id"),
        "variant": sanitize_path_segment(variant, field="variant"),
    }
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def _template_placeholder_tokens(template: str) -> list[str]:
    import re

    return re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", template)


def session_workspace_path(
    skill_manifest: Any,
    *,
    skill_id: str,
    subject_id: str,
    variant: str,
) -> Optional[str]:
    """Render a skill's ``workspace.session_path_template``.

    Returns the workspace-relative path (callers join it under
    ``settings.workspace_root``), or ``None`` when the skill declares no
    template — callers then fall back to their incumbent layout.
    """
    template = getattr(
        getattr(skill_manifest, "workspace", None), "session_path_template", None
    )
    if not template:
        return None
    return render_path_template(
        template, skill_id=skill_id, subject_id=subject_id, variant=variant
    )


__all__ = [
    "PATH_TEMPLATE_IDENTITY_PLACEHOLDERS",
    "PATH_TEMPLATE_PLACEHOLDERS",
    "render_path_template",
    "sanitize_path_segment",
    "session_workspace_path",
    "validate_path_template",
]
