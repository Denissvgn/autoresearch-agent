"""Append-only, idempotent usage ledger with explicit cost knowledge.

One usage event per logical provider call (agent, insight, or evaluator
role), keyed for idempotency so retries and replayed events never
double-charge. Money knowledge is explicit: reported usage, estimated money,
billed money, and unavailable cost are distinct — an unavailable cost is
never displayed as zero. Each event snapshots the versioned pricing basis it
used, so later price changes cannot silently rewrite history.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from src.core.llm_provider import (
    COST_BILLED,
    COST_ESTIMATED,
    COST_UNAVAILABLE,
    CostEstimate,
    Usage,
)

ROLE_AGENT = "agent"
ROLE_INSIGHT = "insight"
ROLE_EVALUATOR = "evaluator"

USAGE_EVENT_SCHEMA_VERSION = "usage-event.v1"


@dataclass(frozen=True)
class UsageEvent:
    """One metered provider call with its cost knowledge."""

    event_key: str
    research_id: str
    role: str
    provider: str
    model: str
    usage: Usage
    cost_status: str
    cost_usd: Optional[float]
    pricing_basis: Dict[str, Any] = field(default_factory=dict)
    iteration: Optional[int] = None
    turn: Optional[int] = None

    def as_row(self) -> Dict[str, Any]:
        return {
            "schema_version": USAGE_EVENT_SCHEMA_VERSION,
            "event_key": self.event_key,
            "research_id": self.research_id,
            "role": self.role,
            "provider": self.provider,
            "model": self.model,
            "iteration": self.iteration,
            "turn": self.turn,
            "usage": asdict(self.usage),
            "cost_status": self.cost_status,
            "cost_usd": self.cost_usd,
            "pricing_basis": dict(self.pricing_basis),
        }


def event_from_quote(
    *,
    event_key: str,
    research_id: str,
    role: str,
    provider: str,
    model: str,
    usage: Usage,
    quote: CostEstimate,
    iteration: Optional[int] = None,
    turn: Optional[int] = None,
) -> UsageEvent:
    """Build an event from a provider's price quote.

    ``COST_UNAVAILABLE`` quotes carry ``cost_usd=None`` — the event is
    recorded with its usage and an explicit unavailable cost, never a zero.
    """
    if quote.status == COST_UNAVAILABLE:
        cost_status: str = COST_UNAVAILABLE
        cost_usd: Optional[float] = None
    else:
        cost_status = COST_ESTIMATED
        cost_usd = quote.money_usd
    return UsageEvent(
        event_key=event_key,
        research_id=research_id,
        role=role,
        provider=provider,
        model=model,
        usage=usage,
        cost_status=cost_status,
        cost_usd=cost_usd,
        pricing_basis=dict(quote.basis),
        iteration=iteration,
        turn=turn,
    )


def mark_billed(event: UsageEvent, billed_usd: float) -> UsageEvent:
    """The billed outcome for an event (actual money, replacing estimates)."""
    return UsageEvent(
        event_key=event.event_key,
        research_id=event.research_id,
        role=event.role,
        provider=event.provider,
        model=event.model,
        usage=event.usage,
        cost_status=COST_BILLED,
        cost_usd=billed_usd,
        pricing_basis=dict(event.pricing_basis),
        iteration=event.iteration,
        turn=event.turn,
    )


async def record_usage_event(store: Any, event: UsageEvent) -> bool:
    """Append one event; returns False when the key was already recorded.

    Idempotent by ``event_key``: a retried call or a replayed event stream
    inserts nothing the second time and cannot double-charge.
    """
    return bool(await store.record_usage_event(event.as_row()))


def summarize_usage(events: List[Mapping[str, Any]]) -> Dict[str, Any]:
    """Aggregate one session's events without conflating cost knowledge.

    ``estimated_usd`` and ``billed_usd`` sum only events that carry money;
    ``unavailable_events`` counts the rest — a missing cost is reported as
    missing, never folded into either sum as zero.
    """
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
    }
    estimated_usd = 0.0
    billed_usd = 0.0
    estimated_events = 0
    billed_events = 0
    unavailable_events = 0
    by_role: Dict[str, int] = {}
    for event in events:
        usage = dict(event.get("usage") or {})
        for key in totals:
            totals[key] += int(usage.get(key) or 0)
        status = str(event.get("cost_status") or "")
        money = event.get("cost_usd")
        by_role[str(event.get("role") or "")] = (
            by_role.get(str(event.get("role") or ""), 0) + 1
        )
        if status == COST_BILLED and money is not None:
            billed_usd += float(money)
            billed_events += 1
        elif status == COST_UNAVAILABLE or money is None:
            unavailable_events += 1
        else:
            estimated_usd += float(money)
            estimated_events += 1
    return {
        "usage": totals,
        "estimated_usd": estimated_usd,
        "billed_usd": billed_usd,
        "estimated_events": estimated_events,
        "billed_events": billed_events,
        "unavailable_events": unavailable_events,
        "events_by_role": by_role,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
