"""Skill-parameter resolution and validation over a declared schema subset.

Validator: the reference ``jsonschema`` implementation (the maintained
standard), pinned to the **Draft 2020-12** dialect. Skills declare
``param_schema`` using exactly this subset of JSON Schema keywords — anything
outside it is rejected at manifest load so it can never be silently
misinterpreted:

* structure: ``type`` (object / string / integer / number / boolean / array),
  ``properties``, ``required``, ``items``, and arbitrary nesting of these
* numeric/string/array bounds: ``minimum``, ``maximum``,
  ``exclusiveMinimum``, ``exclusiveMaximum``, ``minLength``, ``maxLength``,
  ``pattern``, ``minItems``, ``maxItems``
* value sets: ``enum``, ``const``
* extra-property policy: ``additionalProperties`` (true / false — unknown
  keys are permitted or rejected exactly as declared)

Canonical resolution path — one entry point, :func:`resolve_and_validate`:

1. an omitted or ``null`` parameter object resolves to ``{}`` (schemas that
   declare required fields then fail exactly as an empty submission does);
2. declared defaults are applied **deliberately** by :func:`apply_defaults`
   — validation never inserts values;
3. the resolved object is validated **once** against the schema;
4. violations come back field-addressed (``skill_params.a.b``) in the
   server-authoritative error contract that API responses and UI form
   validation share.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

#: The declared dialect for skill parameter schemas.
SCHEMA_DIALECT = "draft 2020-12"

#: The declared keyword subset (see the module docstring).
SUPPORTED_KEYWORDS: frozenset[str] = frozenset({
    "type", "properties", "required", "items", "additionalProperties",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "minLength", "maxLength", "pattern", "minItems", "maxItems",
    "enum", "const",
    # Resolution/annotation keywords: ``default`` is consumed deliberately by
    # :func:`apply_defaults`; ``description``/``title`` are annotations.
    "default", "description", "title",
})

_SCOPING_KEYWORDS = ("properties", "items")


def schema_to_json_schema(schema: Any) -> dict[str, Any]:
    """Normalize a manifest ``ParamSchema`` (or plain mapping) to a dict."""
    if isinstance(schema, Mapping):
        return dict(schema)
    out: dict[str, Any] = {
        "type": getattr(schema, "type", None) or "object",
        "additionalProperties": bool(getattr(schema, "additionalProperties", False)),
    }
    properties = getattr(schema, "properties", None) or {}
    if properties:
        out["properties"] = {
            name: prop.model_dump(exclude_unset=True)
            if hasattr(prop, "model_dump") else dict(prop)
            for name, prop in properties.items()
        }
    required = getattr(schema, "required", None) or []
    if required:
        out["required"] = list(required)
    for key, value in (getattr(schema, "model_extra", None) or {}).items():
        out.setdefault(key, value)
    return out


def unsupported_schema_keywords(schema: Any) -> frozenset[str]:
    """Keywords used by ``schema`` outside the declared subset (recursive)."""
    document = schema_to_json_schema(schema)
    found: set[str] = set()

    def walk(node: Any) -> None:
        if not isinstance(node, Mapping):
            return
        for key, value in node.items():
            if key not in SUPPORTED_KEYWORDS:
                found.add(str(key))
            if key in _SCOPING_KEYWORDS:
                if isinstance(value, Mapping):
                    for nested in value.values():
                        walk(nested)
                else:
                    walk(value)

    walk(document)
    return frozenset(found)


def apply_defaults(schema: Any, value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Resolve one parameter object by filling declared defaults.

    Defaults are applied deliberately here — validation never inserts values.
    Nested object properties are resolved recursively; array items are taken
    as provided (an item default is not auto-materialized).
    """
    document = schema_to_json_schema(schema)
    return _apply_defaults_at(document, dict(value or {}))


def _apply_defaults_at(node: Mapping[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(value)
    properties = node.get("properties") or {}
    for name, prop in properties.items():
        if not isinstance(prop, Mapping):
            continue
        if name not in resolved:
            if "default" in prop:
                default = prop["default"]
                resolved[name] = (
                    _apply_defaults_at(prop, dict(default))
                    if isinstance(default, Mapping) and prop.get("type") == "object"
                    else default
                )
            continue
        current = resolved[name]
        if isinstance(current, Mapping) and prop.get("type") == "object":
            resolved[name] = _apply_defaults_at(prop, dict(current))
    return resolved


def validate_resolved(
    skill_id: str, schema: Any, resolved: Mapping[str, Any]
) -> list[dict[str, str]]:
    """Validate an already-resolved parameter object exactly once.

    Returns field-addressed violations in the server-authoritative error
    contract (``{"field": "skill_params.a.b", "message": ...}``) shared by
    API responses and UI form validation. Unknown-property violations are
    addressed per offending key (``skill_params.<key>``) rather than at the
    object root, so a form can bind each error to its field.
    """
    document = schema_to_json_schema(schema)
    validator = Draft202012Validator(document)
    violations: list[dict[str, str]] = []
    properties = document.get("properties") or {}
    if document.get("additionalProperties") is False:
        for key in resolved:
            if key not in properties:
                violations.append({
                    "field": f"skill_params.{key}",
                    "message": "unknown field (additionalProperties is false)",
                })
    for error in sorted(validator.iter_errors(dict(resolved)), key=lambda e: list(e.absolute_path)):
        if error.validator == "additionalProperties":
            continue  # reported per key above
        violations.append({
            "field": _field_address(error.absolute_path),
            "message": error.message,
        })
    return violations


def _field_address(absolute_path: Sequence[Any]) -> str:
    parts = ["skill_params"]
    for part in absolute_path:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        else:
            parts.append(f".{part}")
    return "".join(parts)


def resolve_and_validate(
    skill_id: str, schema: Any, raw: Mapping[str, Any] | None
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """The one canonical resolution path: resolve defaults, validate once.

    ``raw`` may be omitted or ``None`` (treated as an empty object); the
    returned object is the resolved parameter set to bind into execution.
    """
    resolved = apply_defaults(schema, raw)
    return resolved, validate_resolved(skill_id, schema, resolved)


__all__ = [
    "SCHEMA_DIALECT",
    "SUPPORTED_KEYWORDS",
    "schema_to_json_schema",
    "unsupported_schema_keywords",
    "apply_defaults",
    "validate_resolved",
    "resolve_and_validate",
]
