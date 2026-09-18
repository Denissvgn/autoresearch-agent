"""ARC-012 P7-005/P7-007 — skill path-template rules (D4).

One closed placeholder vocabulary, load-time validation, sanitized
request-supplied segments. Composed with the G6 loader semantics: dotted
namespaces (``{settings.*}`` / ``{skill_params.*}``) pass through untouched
and absolute templates are accepted (G6 resolves
``{settings.host_configs_path}`` before validation).
"""
from __future__ import annotations

import pytest

from src.core.skill_paths import (
    render_path_template,
    sanitize_path_segment,
    session_workspace_path,
    validate_path_template,
)


class TestValidate:
    def test_identity_placeholders_accepted(self):
        validate_path_template("configs/{skill_id}/{subject_id}_{variant}.yaml")

    def test_unknown_placeholder_rejected(self):
        with pytest.raises(ValueError, match="unknown placeholder"):
            validate_path_template("configs/{subject}.yaml")

    def test_sidecar_placeholder_rejected_in_path_template(self):
        with pytest.raises(ValueError, match="no value at path-derivation"):
            validate_path_template("configs/{iteration}.yaml")

    def test_traversal_rejected(self):
        with pytest.raises(ValueError, match="traverse"):
            validate_path_template("configs/../../etc/passwd")

    def test_backslash_rejected(self):
        with pytest.raises(ValueError, match="backslash"):
            validate_path_template("configs\\x.yaml")

    def test_blank_rejected(self):
        with pytest.raises(ValueError, match="blank"):
            validate_path_template("  ")

    def test_absolute_accepted_g6_resolution(self):
        # The G6 loader resolves {settings.host_configs_path} before
        # validation — an absolute template is legitimate operator config.
        validate_path_template("/host/configs/reference.yaml")

    def test_dotted_namespaces_pass_through(self):
        # {skill_params.*} / {settings.*} are G6 vocabulary, not identity
        # placeholders — the token check must not match them.
        validate_path_template("{skill_params.outfile}")


class TestRender:
    def test_renders_identity_placeholders(self):
        rendered = render_path_template(
            "configs/{skill_id}/{subject_id}_{variant}.py",
            skill_id="code-refactor",
            subject_id="autoresearch-agent",
            variant="lint-hygiene",
        )
        assert rendered == "configs/code-refactor/autoresearch-agent_lint-hygiene.py"

    def test_sanitizes_request_supplied_segments(self):
        with pytest.raises(ValueError, match="subject_id"):
            render_path_template(
                "configs/{subject_id}.yaml",
                skill_id="x",
                subject_id="../escape",
                variant="v",
            )
        with pytest.raises(ValueError, match="variant"):
            render_path_template(
                "configs/{variant}.yaml",
                skill_id="x",
                subject_id="s",
                variant="a/b",
            )

    def test_dotted_tokens_left_untouched(self):
        rendered = render_path_template(
            "{skill_params.outfile}", skill_id="x", subject_id="s", variant="v"
        )
        assert rendered == "{skill_params.outfile}"


class TestSanitizeSegment:
    @pytest.mark.parametrize("bad", ["", ".", "..", "a/b", "a\\b", "a\x00b"])
    def test_rejects_unsafe_segments(self, bad: str):
        with pytest.raises(ValueError):
            sanitize_path_segment(bad, field="subject_id")

    def test_accepts_ordinary_segments(self):
        assert sanitize_path_segment("autoresearch-agent", field="x") == (
            "autoresearch-agent"
        )


class TestSessionWorkspace:
    def test_renders_declared_template(self):
        from types import SimpleNamespace

        manifest = SimpleNamespace(
            workspace=SimpleNamespace(
                session_path_template="runs/{skill_id}/{subject_id}/{variant}"
            )
        )
        rendered = session_workspace_path(
            manifest, skill_id="pe", subject_id="default", variant="production"
        )
        assert rendered == "runs/pe/default/production"

    def test_none_without_template(self):
        from types import SimpleNamespace

        manifest = SimpleNamespace(workspace=SimpleNamespace())
        assert (
            session_workspace_path(
                manifest, skill_id="pe", subject_id="s", variant="v"
            )
            is None
        )
