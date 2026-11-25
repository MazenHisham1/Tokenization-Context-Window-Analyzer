"""Rules of the context-window planner (pure logic, no tokenizer needed)."""
import random

import pytest

from src.context import STRATEGIES, Size, plan_context

CONV = [Size("system", 10), Size("user", 30), Size("assistant", 40), Size("user", 20)]  # 100 total


def statuses(plan):
    return [d.status for d in plan.decisions]


def test_everything_fits_when_under_budget():
    for strat in STRATEGIES:
        p = plan_context(CONV, 100, strat)
        assert statuses(p) == ["kept"] * 4 and p.fits and p.used == 100


def test_overhead_counts_per_message():
    assert plan_context(CONV, 103, "drop_oldest", overhead=1).total == 104
    assert not plan_context(CONV, 103, "error", overhead=1).fits


def test_error_strategy_changes_nothing_but_reports_overflow():
    p = plan_context(CONV, 60, "error")
    assert statuses(p) == ["kept"] * 4 and not p.fits and p.total == 100


def test_drop_oldest_keeps_system_and_newest():
    p = plan_context(CONV, 50, "drop_oldest")   # system 10 + newest 20 = 30; the 40-token one does not fit in 20 left
    assert statuses(p) == ["kept", "dropped", "dropped", "kept"]
    assert p.used == 30 and p.fits


def test_drop_oldest_never_leaves_a_hole():
    sizes = [Size("user", 5), Size("user", 90), Size("user", 5)]
    p = plan_context(sizes, 20, "drop_oldest")   # the small first message must NOT come back
    assert statuses(p) == ["dropped", "dropped", "kept"]


def test_truncate_start_cuts_the_old_side_of_the_first_message_that_does_not_fit():
    p = plan_context(CONV, 50, "truncate_start")
    assert statuses(p) == ["kept", "dropped", "partial", "kept"]
    part = p.decisions[2]
    assert part.kept_tokens == 20 and part.keeps == "end" and p.used == 50


def test_truncate_end_keeps_the_start():
    p = plan_context(CONV, 50, "truncate_end")  # system 10 + user 30 = 40, then 10 tokens of the assistant message
    assert statuses(p) == ["kept", "kept", "partial", "dropped"]
    assert p.decisions[2].kept_tokens == 10 and p.decisions[2].keeps == "start" and p.used == 50


def test_overhead_is_paid_for_a_partial_message_too():
    p = plan_context([Size("user", 100)], 30, "truncate_end", overhead=4)
    assert p.decisions[0].kept_tokens == 26 and p.used == 30


def test_no_room_for_even_one_token_means_dropped():
    p = plan_context([Size("user", 100)], 4, "truncate_start", overhead=4)
    assert statuses(p) == ["dropped"] and p.nothing_fits


def test_system_messages_alone_too_big():
    p = plan_context([Size("system", 100), Size("user", 5)], 50, "drop_oldest")
    assert p.cannot_fit and not p.fits and statuses(p) == ["kept", "dropped"]


def test_system_message_in_the_middle_is_pinned():
    sizes = [Size("user", 40), Size("system", 10), Size("user", 40)]
    assert statuses(plan_context(sizes, 55, "drop_oldest")) == ["dropped", "kept", "kept"]


def test_bad_input():
    with pytest.raises(ValueError):
        plan_context(CONV, 10, "magic")
    with pytest.raises(ValueError):
        plan_context(CONV, -1, "drop_oldest")
    with pytest.raises(ValueError):
        plan_context([Size("user", -1)], 10, "drop_oldest")


def test_random_conversations_always_respect_the_budget():
    rng = random.Random(7)
    for _ in range(2000):
        roles = [rng.choice(["system", "user", "assistant"]) for _ in range(rng.randint(0, 7))]
        sizes = [Size(role, rng.randint(0, 60)) for role in roles]
        budget, overhead = rng.randint(0, 200), rng.randint(0, 5)
        for strat in ("drop_oldest", "truncate_start", "truncate_end"):
            p = plan_context(sizes, budget, strat, overhead)
            if not p.cannot_fit:
                assert p.fits and p.used <= budget, (sizes, budget, overhead, strat)
            for s, d in zip(sizes, p.decisions, strict=True):
                assert 0 <= d.kept_tokens <= s.tokens
                assert (d.status == "kept") == (d.kept_tokens == s.tokens and d.status != "dropped")
            movable = [d.status for s, d in zip(sizes, p.decisions, strict=True) if s.role != "system"]
            alive = [i for i, st in enumerate(movable) if st != "dropped"]
            assert alive == list(range(alive[0], alive[-1] + 1)) if alive else True   # contiguous run
