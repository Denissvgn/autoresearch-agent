"""Cross-session research resume: the summary domain bridge.

The orchestrator is domain-agnostic by policy (no legacy model/instrument/
timeframe access); the mapping from a session config onto the legacy-keyed
cross-session summary query lives here, explicitly.
"""

from __future__ import annotations

from typing import Any, List, Optional


async def cross_session_summary(
    store: Any,
    config: Any,
    *,
    exclude_research_id: Optional[str] = None,
    limit: int = 20,
) -> List[Any]:
    """The recorded cross-session iteration summary for this session.

    Keyed by the session's subject and variant through the store's summary
    contract so prior experiments are summarized without the orchestrator
    branching on domain fields.
    """
    return await store.get_cross_session_iteration_summary(
        instrument=config.subject_id,
        timeframe=config.variant,
        model_type=config.model_type,
        exclude_research_id=exclude_research_id,
        limit=limit,
    )
