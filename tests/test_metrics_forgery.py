"""P4-006 — Metrics forgery rejection tests (ARC-011 W11 anti-forgery).

Validates the ``_verify_nonce`` contract (P4-003/P4-005) through the
``JSONMarkerParser`` and ``DelimitedKVParser`` entry points:

* Forged marker (wrong nonce) → rejected (``None``).
* Forged marker (missing nonce) → rejected (``None``).
* Valid nonce → accepted with ``metrics_verification: "metrics_verified"``.
* Legacy session (no nonce, ``require_signed_metrics=True``) → graceful
  downgrade with ``"metrics_unverified"``.
* Default (``require_signed_metrics=False``) → accepted, **no** key added
  (parity preservation — the X-002 fixture shape is unchanged).
"""
from __future__ import annotations

from src.core.output_parser import DelimitedKVParser, JSONMarkerParser

# ── JSONMarkerParser ─────────────────────────────────────────────────────────

_NONCE = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"


def _marker(nonce: str | None = None, **extra: object) -> str:
    """Build an ``ITERATION_RESULT:`` JSON line with optional nonce."""
    import json

    payload = {"status": "completed", "primary_metric": 0.75, "metric_name": "composite_eval_score"}
    if nonce is not None:
        payload["server_nonce"] = nonce
    payload.update(extra)
    return "ITERATION_RESULT: " + json.dumps(payload)


class TestJSONMarkerParserForgery:
    def test_valid_nonce_accepted_and_verified(self):
        p = JSONMarkerParser()
        result = p.parse_iteration(
            _marker(nonce=_NONCE),
            session_nonce=_NONCE,
            nonce_field="server_nonce",
            require_signed_metrics=True,
        )
        assert result is not None
        assert result["metrics_verification"] == "metrics_verified"
        assert result["primary_metric"] == 0.75

    def test_wrong_nonce_rejected(self):
        p = JSONMarkerParser()
        result = p.parse_iteration(
            _marker(nonce="wrong"),
            session_nonce=_NONCE,
            nonce_field="server_nonce",
            require_signed_metrics=True,
        )
        assert result is None  # forged → rejected

    def test_missing_nonce_rejected(self):
        p = JSONMarkerParser()
        result = p.parse_iteration(
            _marker(nonce=None),
            session_nonce=_NONCE,
            nonce_field="server_nonce",
            require_signed_metrics=True,
        )
        assert result is None  # forged → rejected

    def test_legacy_session_graceful_downgrade(self):
        """require_signed_metrics=True but no session nonce → unverified."""
        p = JSONMarkerParser()
        result = p.parse_iteration(
            _marker(nonce=None),
            session_nonce=None,
            nonce_field="server_nonce",
            require_signed_metrics=True,
        )
        assert result is not None
        assert result["metrics_verification"] == "metrics_unverified"

    def test_default_no_key_added(self):
        """require_signed_metrics=False → no validation, no key (parity)."""
        p = JSONMarkerParser()
        result = p.parse_iteration(_marker(nonce=None))
        assert result is not None
        assert "metrics_verification" not in result

    def test_bytes_nonce_accepted(self):
        """session_nonce as bytes is hex-encoded for comparison."""
        p = JSONMarkerParser()
        nonce_bytes = bytes.fromhex(_NONCE)
        result = p.parse_iteration(
            _marker(nonce=_NONCE),
            session_nonce=nonce_bytes,
            nonce_field="server_nonce",
            require_signed_metrics=True,
        )
        assert result is not None
        assert result["metrics_verification"] == "metrics_verified"

    def test_no_marker_returns_none(self):
        """Text without a marker → None regardless of nonce config."""
        p = JSONMarkerParser()
        result = p.parse_iteration(
            "no marker here",
            session_nonce=_NONCE,
            nonce_field="server_nonce",
            require_signed_metrics=True,
        )
        assert result is None


# ── DelimitedKVParser ────────────────────────────────────────────────────────


def _kv_block(nonce: str | None = None) -> str:
    """Build a ``---`` delimited KV block with optional nonce."""
    lines = ["---", "status: completed", "primary_metric: 0.68", "metric_name: test"]
    if nonce is not None:
        lines.append(f"server_nonce: {nonce}")
    lines.append("---")
    return "\n".join(lines)


class TestDelimitedKVParserForgery:
    def test_valid_nonce_accepted(self):
        p = DelimitedKVParser()
        result = p.parse_iteration(
            _kv_block(nonce=_NONCE),
            session_nonce=_NONCE,
            nonce_field="server_nonce",
            require_signed_metrics=True,
        )
        assert result is not None
        assert result["metrics_verification"] == "metrics_verified"

    def test_wrong_nonce_rejected(self):
        p = DelimitedKVParser()
        result = p.parse_iteration(
            _kv_block(nonce="wrong"),
            session_nonce=_NONCE,
            nonce_field="server_nonce",
            require_signed_metrics=True,
        )
        assert result is None

    def test_missing_nonce_rejected(self):
        p = DelimitedKVParser()
        result = p.parse_iteration(
            _kv_block(nonce=None),
            session_nonce=_NONCE,
            nonce_field="server_nonce",
            require_signed_metrics=True,
        )
        assert result is None

    def test_default_no_key_added(self):
        """require_signed_metrics=False → no validation, no key (parity)."""
        p = DelimitedKVParser()
        result = p.parse_iteration(_kv_block(nonce=None))
        assert result is not None
        assert "metrics_verification" not in result
