"""Edge-case tests for TimerManager and TweenManager."""

import math

import pytest

from easygame import Game, tween


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def game() -> Game:
    """Game with mock backend (provides timer and tween managers)."""
    g = Game("Test", backend="mock", resolution=(800, 600))
    yield g
    g._teardown()


class Box:
    """Simple target for tweens with a numeric property."""

    def __init__(self, value: float = 0.0) -> None:
        self.x = value


# ------------------------------------------------------------------
# 1. Timer callback that cancels itself
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


# ------------------------------------------------------------------
# 2. Timer callback that creates new timers
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# 3. Timer callback that calls cancel_all
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# 4. TimerHandle.then() after timer already fired
# ------------------------------------------------------------------


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
# 5 & 9. Tween with duration=0
# ------------------------------------------------------------------


def test_tween_duration_zero_completes_on_next_update(game: Game) -> None:
    """Tween with duration=0 completes on the next update."""
    box = Box(100.0)
    completed = []

    tween(box, "x", 100.0, 200.0, 0.0, on_complete=lambda: completed.append(True))
    assert box.x == 100.0

    game._tween_manager.update(dt=0.016)

    assert box.x == 200.0
    assert completed == [True]


# ------------------------------------------------------------------
# 6. Tween with from_val == to_val
# ------------------------------------------------------------------


def test_tween_from_val_equals_to_val(game: Game) -> None:
    """Tween with from_val == to_val completes normally; value stays constant."""
    box = Box(50.0)
    completed = []

    tween(box, "x", 50.0, 50.0, 0.1, on_complete=lambda: completed.append(True))

    game._tween_manager.update(dt=0.05)
    assert box.x == 50.0
    assert completed == []

    game._tween_manager.update(dt=0.06)
    assert box.x == 50.0
    assert completed == [True]


# ------------------------------------------------------------------
# 7. Tween on_complete that creates new tweens or cancels tweens
# ------------------------------------------------------------------


def test_tween_on_complete_creates_new_tween(game: Game) -> None:
    """Tween on_complete that creates a new tween; new tween runs on subsequent updates."""
    box = Box(0.0)
    completed = []

    def first_done() -> None:
        completed.append("first")
        tween(box, "x", 100.0, 200.0, 0.0, on_complete=lambda: completed.append("second"))

    tween(box, "x", 0.0, 100.0, 0.0, on_complete=first_done)

    game._tween_manager.update(dt=0.016)
    assert completed == ["first"]
    assert box.x == 100.0

    game._tween_manager.update(dt=0.016)
    assert completed == ["first", "second"]
    assert box.x == 200.0


def test_tween_on_complete_cancels_other_tween(game: Game) -> None:
    """Tween on_complete that cancels another tween does not crash."""
    box = Box(0.0)
    tid2 = [None]

    tid1 = tween(
        box,
        "x",
        0.0,
        100.0,
        0.0,
        on_complete=lambda: game.cancel_tween(tid2[0]),
    )
    tid2[0] = tween(box, "x", 50.0, 150.0, 1.0)

    game._tween_manager.update(dt=0.016)

    assert box.x == 100.0
    assert tid2[0] not in game._tween_manager._tweens


# ------------------------------------------------------------------
# 8. dt edge cases for both
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


def test_tween_update_negative_dt(game: Game) -> None:
    """Tween update with negative dt: elapsed can decrease."""
    box = Box(0.0)

    tween(box, "x", 0.0, 100.0, 1.0)
    game._tween_manager.update(dt=0.5)
    assert 0 < box.x < 100

    game._tween_manager.update(dt=-0.3)
    game._tween_manager.update(dt=0.9)
    assert box.x == 100.0


def test_tween_update_nan_dt_skipped(game: Game) -> None:
    """Tween update with NaN dt returns immediately; tween state unchanged; next valid dt advances."""
    box = Box(0.0)
    completed = []

    tween(box, "x", 0.0, 100.0, 1.0, on_complete=lambda: completed.append(True))
    game._tween_manager.update(dt=float("nan"))  # no-op
    assert box.x == 0.0
    assert completed == []

    game._tween_manager.update(dt=1.0)
    assert box.x == 100.0
    assert completed == [True]


def test_tween_update_inf_dt_skipped(game: Game) -> None:
    """Tween update with Inf dt returns immediately (non-finite); next valid dt completes."""
    box = Box(0.0)
    completed = []

    tween(box, "x", 0.0, 100.0, 1.0, on_complete=lambda: completed.append(True))
    game._tween_manager.update(dt=float("inf"))  # no-op
    assert box.x == 0.0
    assert completed == []
    game._tween_manager.update(dt=1.0)
    assert box.x == 100.0
    assert completed == [True]
