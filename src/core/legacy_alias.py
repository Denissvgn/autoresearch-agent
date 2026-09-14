"""Back-compat shim (P1-2): the legacy alias registry moved to
src/compat/legacy_alias.py; every importer keeps working.
"""
from src.compat.legacy_alias import (  # noqa: F401
    is_known_model_type,
    model_type_to_skill_id,
    skill_id_to_model_type,
)

__all__ = [
    "model_type_to_skill_id",
    "skill_id_to_model_type",
    "is_known_model_type",
]
