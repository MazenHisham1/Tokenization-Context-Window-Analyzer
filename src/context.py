"""Context-window planning: given message sizes, what survives when the window is too small?

This module knows nothing about tokenizers or the web. It receives token counts and returns
decisions, which makes the rules easy to test. Most vendor APIs do NOT cut anything for you:
they reject a request that is too long. Dropping or cutting is done by the application (or a
framework) before the call, so each strategy here is "what your app could do".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Strategy = Literal["error", "drop_oldest", "truncate_start", "truncate_end"]
STRATEGIES: tuple[str, ...] = ("error", "drop_oldest", "truncate_start", "truncate_end")
Status = Literal["kept", "partial", "dropped"]


@dataclass(frozen=True)
class Size:
    role: str      # "system", "user" or "assistant"
    tokens: int    # tokens of the text itself, without the per-message overhead


@dataclass(frozen=True)
class Decision:
    status: Status
    kept_tokens: int    # of the message's own tokens (overhead not included)
    keeps: str = "all"  # for a partial message: "start" or "end" says which side survives


@dataclass(frozen=True)
class Plan:
    decisions: list[Decision]
    used: int          # tokens the kept messages take, overhead included
    total: int         # tokens of the full conversation, overhead included
    budget: int        # window minus the room reserved for the answer
    fits: bool         # True when the plan fits the budget
    cannot_fit: bool   # True when even the pinned system messages do not fit
    nothing_fits: bool  # True when no non-system message could be kept at all


def plan_context(sizes: list[Size], budget: int, strategy: Strategy, overhead: int = 0) -> Plan:
    """Decide which messages are kept, cut or dropped so that the result fits `budget`.

    - System messages are pinned: they are never dropped or cut.
    - `error`: change nothing. The API would reject the request if it is over the budget.
    - `drop_oldest`: keep the newest messages whole, drop older ones.
    - `truncate_start`: like drop_oldest, but the first message that does not fit is cut so
      that its END survives (the newest part of the conversation is kept).
    - `truncate_end`: keep the oldest messages, and cut the first that does not fit so that
      its START survives. Everything after it is dropped.
    Only a contiguous run is kept, never "skip a big message and keep an older small one",
    because that would leave a hole in the conversation.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}")
    if budget < 0 or overhead < 0:
        raise ValueError("budget and overhead must be >= 0")
    if any(s.tokens < 0 for s in sizes):
        raise ValueError("token counts must be >= 0")

    cost = [s.tokens + overhead for s in sizes]
    total = sum(cost)
    n = len(sizes)
    pinned = [s.role == "system" for s in sizes]

    if strategy == "error" or total <= budget:
        return Plan([Decision("kept", s.tokens) for s in sizes], total, total, budget,
                    fits=total <= budget, cannot_fit=False, nothing_fits=False)

    decisions: list[Decision | None] = [Decision("kept", s.tokens) if p else None
                                        for s, p in zip(sizes, pinned, strict=True)]
    remaining = budget - sum(c for c, p in zip(cost, pinned, strict=True) if p)
    if remaining < 0:   # the system messages alone are too big
        for i in range(n):
            if decisions[i] is None:
                decisions[i] = Decision("dropped", 0)
        used = sum(c for c, p in zip(cost, pinned, strict=True) if p)
        return Plan(decisions, used, total, budget, fits=False, cannot_fit=True, nothing_fits=True)  # type: ignore[arg-type]

    # Walk the movable messages from the side we want to keep first.
    movable = [i for i in range(n) if not pinned[i]]
    order = movable if strategy == "truncate_end" else list(reversed(movable))
    stopped = False
    for i in order:
        if stopped:
            decisions[i] = Decision("dropped", 0)
        elif cost[i] <= remaining:
            decisions[i] = Decision("kept", sizes[i].tokens)
            remaining -= cost[i]
        else:
            stopped = True
            room = remaining - overhead   # tokens of text that still fit next to the overhead
            if strategy != "drop_oldest" and room > 0:
                side = "start" if strategy == "truncate_end" else "end"
                decisions[i] = Decision("partial", room, side)
                remaining = 0
            else:
                decisions[i] = Decision("dropped", 0)

    final: list[Decision] = [d for d in decisions if d is not None]
    used = sum(
        (c if d.status == "kept" else d.kept_tokens + overhead if d.status == "partial" else 0)
        for c, d in zip(cost, final, strict=True)
    )
    nothing = not any(d.status != "dropped" for d, p in zip(final, pinned, strict=True) if not p)
    return Plan(final, used, total, budget, fits=used <= budget, cannot_fit=False, nothing_fits=nothing)
