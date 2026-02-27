"""Tests for TimerManager, Game.after/every/cancel, and TimerHandle.then() chaining."""

from __future__ import annotations

import pytest

from easygame import Game
from easygame.util.timer import TimerHandle, TimerManager


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def game() -> Game:
    return Game("Test", backend="mock", resolution=(800, 600))


@pytest.fixture
def tm() -> TimerManager:
    return TimerManager()


# ------------------------------------------------------------------
# after()
# ------------------------------------------------------------------


def test_after_fires_after_accumulated_dt(game: Game) -> None:
    """after() fires callback after correct elapsed time across ticks."""
    fired = []

    game.after(0.3, lambda: fired.append(True))

    game.tick(dt=0.1)
    assert len(fired) == 0
    game.tick(dt=0.1)
    assert len(fired) == 0
    game.tick(dt=0.1)
    assert len(fired) == 1


def test_after_returns_monotonic_id(game: Game) -> None:
    """after() returns distinct monotonic IDs."""
    id1 = game.after(1.0, lambda: None)
    id2 = game.after(1.0, lambda: None)
    id3 = game.after(1.0, lambda: None)
    assert id1 < id2 < id3


def test_after_zero_delay_fires_on_next_tick(game: Game) -> None:
    """Timer with 0 delay fires on next update, not immediately."""
    fired = []

    game.after(0.0, lambda: fired.append(True))
    assert len(fired) == 0

    game.tick(dt=0.016)
    assert len(fired) == 1


# ------------------------------------------------------------------
# every()
# ------------------------------------------------------------------


def test_every_fires_repeatedly(game: Game) -> None:
    """every() fires at correct intervals."""
    count = []

    game.every(0.2, lambda: count.append(1))

    game.tick(dt=0.2)
    assert len(count) == 1
    game.tick(dt=0.2)
    assert len(count) == 2
    game.tick(dt=0.2)
    assert len(count) == 3


def test_every_no_catchup_on_large_dt(game: Game) -> None:
    """Repeating timers fire at most once per update (no catch-up)."""
    count = []

    game.every(0.1, lambda: count.append(1))

    game.tick(dt=0.5)  # Would be 5 fires if we caught up
    assert len(count) == 1


# ------------------------------------------------------------------
# cancel()
# ------------------------------------------------------------------


def test_cancel_prevents_fire(game: Game) -> None:
    """cancel() prevents future fires."""
    fired = []

    tid = game.after(0.5, lambda: fired.append(True))
    game.tick(dt=0.2)
    game.cancel(tid)
    game.tick(dt=0.5)
    assert len(fired) == 0


def test_cancel_during_callback_is_safe(game: Game) -> None:
    """Cancelling another timer during a callback is safe."""
    order = []

    def fire_a() -> None:
        order.append("A")
        game.cancel(tid_b)

    def fire_b() -> None:
        order.append("B")

    # A fires first (added first), cancels B before B is processed
    game.after(0.1, fire_a)
    tid_b = game.after(0.1, fire_b)

    game.tick(dt=0.2)
    assert order == ["A"]  # B was cancelled by A's callback, never fired


def test_callback_creates_timer_not_fired_same_frame(game: Game) -> None:
    """Timer created in a callback does not fire in the same frame."""
    fired = []

    def create_timer() -> None:
        game.after(0.0, lambda: fired.append("nested"))

    game.after(0.0, create_timer)
    game.tick(dt=0.016)

    assert "nested" not in fired


def test_callback_creates_timer_fires_next_frame(game: Game) -> None:
    """Timer created in a callback fires on the next tick."""
    fired = []

    def create_timer() -> None:
        game.after(0.0, lambda: fired.append("nested"))

    game.after(0.0, create_timer)
    game.tick(dt=0.016)
    game.tick(dt=0.016)

    assert fired == ["nested"]


# ------------------------------------------------------------------
# cancel_all()
# ------------------------------------------------------------------


def test_cancel_all_clears_timers(game: Game) -> None:
    """cancel_all() clears all active timers."""
    fired = []

    game.after(0.5, lambda: fired.append(1))
    game.every(0.2, lambda: fired.append(2))
    game._timer_manager.cancel_all()

    game.tick(dt=1.0)
    assert len(fired) == 0


# ------------------------------------------------------------------
# Basic chaining with then()
# ------------------------------------------------------------------


def test_basic_then_fires_after_parent(tm: TimerManager) -> None:
    """after().then() fires the child only after the parent completes."""
    order: list[str] = []

    tm.after(0.1, lambda: order.append("A")).then(
        lambda: order.append("B"), 0.1,
    )

    tm.update(0.05)
    assert order == []

    tm.update(0.05)  # t=0.1 — A fires, B scheduled
    assert order == ["A"]

    tm.update(0.05)  # t=0.15 — B not yet
    assert order == ["A"]

    tm.update(0.05)  # t=0.2 — B fires
    assert order == ["A", "B"]


def test_chained_thens_sequential(tm: TimerManager) -> None:
    """A three-step chain fires sequentially, not in parallel."""
    order: list[str] = []

    tm.after(0.1, lambda: order.append("A")).then(
        lambda: order.append("B"), 0.1,
    ).then(
        lambda: order.append("C"), 0.1,
    )

    tm.update(0.1)  # A fires
    assert order == ["A"]

    tm.update(0.1)  # B fires
    assert order == ["A", "B"]

    tm.update(0.1)  # C fires
    assert order == ["A", "B", "C"]


# ------------------------------------------------------------------
# Chaining with cancellation
# ------------------------------------------------------------------


def test_cancel_parent_prevents_chain(tm: TimerManager) -> None:
    """Cancelling before any timer fires prevents the entire chain."""
    order: list[str] = []

    handle = tm.after(0.1, lambda: order.append("A")).then(
        lambda: order.append("B"), 0.1,
    )

    tm.cancel(handle)
    tm.update(0.5)
    assert order == []


def test_cancel_handle_mid_chain(tm: TimerManager) -> None:
    """Cancelling after the first step prevents remaining steps."""
    order: list[str] = []

    handle = tm.after(0.1, lambda: order.append("A")).then(
        lambda: order.append("B"), 0.1,
    ).then(
        lambda: order.append("C"), 0.1,
    )

    tm.update(0.1)  # A fires, B scheduled
    assert order == ["A"]

    tm.cancel(handle)  # cancels B (C was never scheduled)
    tm.update(0.5)
    assert order == ["A"]


# ------------------------------------------------------------------
# Repeating timers with chaining
# ------------------------------------------------------------------


def test_repeating_timer_then_fires_after_each(tm: TimerManager) -> None:
    """every().then() fires the chained callback after each repetition."""
    order: list[str] = []

    tm.every(0.5, lambda: order.append("A")).then(
        lambda: order.append("B"), 0.1,
    )

    tm.update(0.5)  # A fires
    assert order == ["A"]

    tm.update(0.1)  # B fires
    assert order == ["A", "B"]

    tm.update(0.4)  # second A fires (0.5 interval reset)
    assert order == ["A", "B", "A"]

    tm.update(0.1)  # second B fires
    assert order == ["A", "B", "A", "B"]


def test_cancel_repeating_timer_chain(tm: TimerManager) -> None:
    """Cancelling a repeating handle stops repeats and pending children."""
    order: list[str] = []

    handle = tm.every(0.5, lambda: order.append("A")).then(
        lambda: order.append("B"), 0.1,
    )

    tm.update(0.5)  # A fires, B scheduled
    assert order == ["A"]

    tm.cancel(handle)  # cancel everything

    tm.update(0.1)  # B should not fire
    tm.update(0.5)  # no more A
    assert order == ["A"]


# ------------------------------------------------------------------
# Handle API
# ------------------------------------------------------------------


def test_then_returns_chainable_handle(tm: TimerManager) -> None:
    """.then() returns the same handle for fluent chaining."""
    h1 = tm.after(1.0, lambda: None)
    h2 = h1.then(lambda: None, 0.5)

    assert h2 is h1
    assert isinstance(h2, TimerHandle)


# ------------------------------------------------------------------
# Edge cases: self-cancellation, creating timers, cancel_all
# ------------------------------------------------------------------


def test_timer_callback_cancels_itself(game: Game) -> None:
    """Timer callback that calls cancel on itself does not crash."""
    fired = []

    def cb() -> None:
        fired.append(True)
        game.cancel(handle)

    handle = game.after(0.0, cb)
    game.tick(dt=0.016)

    assert len(fired) == 1
    assert len(game._timer_manager._timers) == 0


def test_timer_callback_creates_new_timers(game: Game) -> None:
    """Timer callback that schedules new timers; new timers fire on subsequent updates."""
    fired = []

    def cb() -> None:
        fired.append("first")
        game.after(0.0, lambda: fired.append("second"))

    game.after(0.0, cb)
    game.tick(dt=0.016)

    assert fired == ["first"]
    game.tick(dt=0.016)
    assert fired == ["first", "second"]


def test_timer_callback_calls_cancel_all(game: Game) -> None:
    """Timer callback that calls cancel_all does not crash."""
    fired = []

    def cb() -> None:
        fired.append(True)
        game._timer_manager.cancel_all()

    game.after(0.0, cb)
    game.tick(dt=0.016)

    assert len(fired) == 1
    assert len(game._timer_manager._timers) == 0


def test_timer_then_after_fired_is_noop(game: Game) -> None:
    """TimerHandle.then() after timer already fired is a no-op; chained callback never runs."""
    fired = []

    handle = game.after(0.0, lambda: fired.append("main"))
    game.tick(dt=0.016)
    assert fired == ["main"]

    handle.then(lambda: fired.append("chained"), 0.0)
    game.tick(dt=0.016)
    game.tick(dt=0.016)

    assert fired == ["main"]


# ------------------------------------------------------------------
# dt edge cases (negative, NaN, Inf)
# ------------------------------------------------------------------


def test_timer_update_negative_dt(game: Game) -> None:
    """Timer update with negative dt: remaining increases (timer delays)."""
    fired = []

    game.after(0.1, lambda: fired.append(True))
    game._timer_manager.update(dt=-0.05)
    game._timer_manager.update(dt=0.2)

    assert len(fired) == 1


def test_timer_update_nan_dt_skipped(game: Game) -> None:
    """Timer update with NaN dt returns immediately; timer state unchanged; next valid dt fires."""
    fired = []

    game.after(0.0, lambda: fired.append(True))
    game._timer_manager.update(dt=float("nan"))  # no-op
    game._timer_manager.update(dt=0.016)

    assert fired == [True]


def test_timer_update_inf_dt_skipped(game: Game) -> None:
    """Timer update with Inf dt returns immediately (non-finite); next valid dt fires."""
    fired = []

    game.after(1.0, lambda: fired.append(True))
    game._timer_manager.update(dt=float("inf"))  # no-op
    assert fired == []
    game._timer_manager.update(dt=1.0)
    assert fired == [True]
