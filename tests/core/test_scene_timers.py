"""Tests for Scene timer ownership: after, every, cancel_timer, auto-cleanup."""

from __future__ import annotations

import pytest

from easygame import Game, Scene
from easygame.util.timer import TimerHandle


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def game() -> Game:
    return Game("Test", backend="mock", resolution=(800, 600))


# ------------------------------------------------------------------
# Scene.after() fires while scene is active
# ------------------------------------------------------------------


def test_scene_after_fires(game: Game) -> None:
    """Scene.after() fires callback after correct elapsed time."""
    fired: list[str] = []

    class TimerScene(Scene):
        def on_enter(self) -> None:
            self.after(0.3, lambda: fired.append("done"))

    game.push(TimerScene())

    game.tick(dt=0.1)
    assert len(fired) == 0
    game.tick(dt=0.1)
    assert len(fired) == 0
    game.tick(dt=0.1)
    assert len(fired) == 1
    assert fired[0] == "done"


def test_scene_after_returns_timer_id(game: Game) -> None:
    """Scene.after() returns a TimerHandle usable for cancellation."""
    scene = Scene()
    game.push(scene)

    handle = scene.after(1.0, lambda: None)

    assert isinstance(handle, TimerHandle)


def test_scene_after_zero_delay(game: Game) -> None:
    """Scene.after(0, ...) fires on next tick."""
    fired: list[bool] = []

    class TimerScene(Scene):
        def on_enter(self) -> None:
            self.after(0, lambda: fired.append(True))

    game.push(TimerScene())
    assert len(fired) == 0

    game.tick(dt=0.016)
    assert len(fired) == 1


def test_scene_after_removes_from_owned_set_on_fire(game: Game) -> None:
    """One-shot timer is removed from owned set after it fires naturally."""

    class TimerScene(Scene):
        def on_enter(self) -> None:
            self.tid = self.after(0.1, lambda: None)

    scene = TimerScene()
    game.push(scene)

    # Before firing
    assert scene.tid in scene._get_owned_timers()

    game.tick(dt=0.2)

    # After firing — no longer tracked
    assert scene.tid not in scene._get_owned_timers()


# ------------------------------------------------------------------
# Scene.every() fires while scene is active
# ------------------------------------------------------------------


def test_scene_every_fires_repeatedly(game: Game) -> None:
    """Scene.every() fires at correct intervals."""
    count: list[int] = []

    class TimerScene(Scene):
        def on_enter(self) -> None:
            self.every(0.2, lambda: count.append(1))

    game.push(TimerScene())

    game.tick(dt=0.2)
    assert len(count) == 1
    game.tick(dt=0.2)
    assert len(count) == 2
    game.tick(dt=0.2)
    assert len(count) == 3


def test_scene_every_returns_timer_id(game: Game) -> None:
    """Scene.every() returns a TimerHandle usable for cancellation."""
    scene = Scene()
    game.push(scene)

    handle = scene.every(1.0, lambda: None)

    assert isinstance(handle, TimerHandle)


# ------------------------------------------------------------------
# Auto-cancel on scene exit (pop)
# ------------------------------------------------------------------


def test_pop_cancels_after_timers(game: Game) -> None:
    """Popping a scene auto-cancels all Scene.after() timers."""
    fired: list[str] = []

    class TimerScene(Scene):
        def on_enter(self) -> None:
            self.after(0.5, lambda: fired.append("should not fire"))

    game.push(TimerScene())
    game.tick(dt=0.1)  # timer at 0.4s remaining
    game.pop()

    # Advance well past the timer's original deadline
    game.tick(dt=1.0)
    game.tick(dt=1.0)

    assert len(fired) == 0


def test_pop_cancels_every_timers(game: Game) -> None:
    """Popping a scene auto-cancels all Scene.every() timers."""
    count: list[int] = []

    class TimerScene(Scene):
        def on_enter(self) -> None:
            self.every(0.1, lambda: count.append(1))

    game.push(TimerScene())
    game.tick(dt=0.1)
    assert len(count) == 1  # fires once while scene is active

    game.pop()
    game.tick(dt=0.1)
    game.tick(dt=0.1)
    game.tick(dt=0.1)

    # Should not have fired again after scene exit
    assert len(count) == 1


def test_on_exit_runs_before_timer_cleanup(game: Game) -> None:
    """User's on_exit runs before owned timers are cancelled."""
    timers_in_on_exit: list[set[int]] = []

    class TimerScene(Scene):
        def on_enter(self) -> None:
            self.tid = self.after(5.0, lambda: None)

        def on_exit(self) -> None:
            # Timer should still be in the owned set during on_exit
            timers_in_on_exit.append(set(self._get_owned_timers()))

    game.push(TimerScene())
    game.pop()

    assert len(timers_in_on_exit) == 1
    # The timer ID should have been present during on_exit
    assert len(timers_in_on_exit[0]) == 1


# ------------------------------------------------------------------
# Auto-cancel on push (old scene exits)
# ------------------------------------------------------------------


def test_push_cancels_old_scene_timers(game: Game) -> None:
    """Pushing a new scene auto-cancels the old scene's timers."""
    fired: list[str] = []

    class TimerScene(Scene):
        def on_enter(self) -> None:
            self.after(0.5, lambda: fired.append("should not fire"))

    game.push(TimerScene())
    game.push(Scene())  # pushes over → old scene exits

    game.tick(dt=1.0)
    game.tick(dt=1.0)

    assert len(fired) == 0


# ------------------------------------------------------------------
# Auto-cancel on replace
# ------------------------------------------------------------------


def test_replace_cancels_old_scene_timers(game: Game) -> None:
    """Replacing a scene auto-cancels the old scene's timers."""
    fired: list[str] = []

    class TimerScene(Scene):
        def on_enter(self) -> None:
            self.after(0.5, lambda: fired.append("should not fire"))

    game.push(TimerScene())
    game.replace(Scene())

    game.tick(dt=1.0)
    game.tick(dt=1.0)

    assert len(fired) == 0


# ------------------------------------------------------------------
# Auto-cancel on clear_and_push
# ------------------------------------------------------------------


def test_clear_and_push_cancels_all_scene_timers(game: Game) -> None:
    """clear_and_push cancels timers from ALL cleared scenes."""
    fired: list[str] = []

    class TimerSceneA(Scene):
        def on_enter(self) -> None:
            self.after(0.5, lambda: fired.append("A"))

    class TimerSceneB(Scene):
        def on_enter(self) -> None:
            self.after(0.5, lambda: fired.append("B"))

    game.push(TimerSceneA())
    game.push(TimerSceneB())
    game.clear_and_push(Scene())

    game.tick(dt=1.0)
    game.tick(dt=1.0)

    assert len(fired) == 0


# ------------------------------------------------------------------
# Manual cancel via cancel_timer()
# ------------------------------------------------------------------


def test_cancel_timer_prevents_fire(game: Game) -> None:
    """cancel_timer() prevents the timer from firing."""
    fired: list[str] = []

    class TimerScene(Scene):
        def on_enter(self) -> None:
            self.tid = self.after(0.5, lambda: fired.append("nope"))

    scene = TimerScene()
    game.push(scene)
    game.tick(dt=0.2)

    scene.cancel_timer(scene.tid)

    game.tick(dt=0.5)
    game.tick(dt=0.5)

    assert len(fired) == 0


def test_cancel_timer_removes_from_owned_set(game: Game) -> None:
    """cancel_timer() deregisters the timer from the scene's owned set."""

    class TimerScene(Scene):
        def on_enter(self) -> None:
            self.tid = self.after(5.0, lambda: None)

    scene = TimerScene()
    game.push(scene)
    assert scene.tid in scene._get_owned_timers()

    scene.cancel_timer(scene.tid)

    assert scene.tid not in scene._get_owned_timers()


def test_cancel_timer_safe_on_fired_timer(game: Game) -> None:
    """cancel_timer() on an already-fired one-shot is a no-op."""

    class TimerScene(Scene):
        def on_enter(self) -> None:
            self.tid = self.after(0.1, lambda: None)

    scene = TimerScene()
    game.push(scene)
    game.tick(dt=0.2)  # timer fires

    scene.cancel_timer(scene.tid)  # should not raise


# ------------------------------------------------------------------
# Mixed after + every timers
# ------------------------------------------------------------------


def test_mixed_timers_auto_cancel(game: Game) -> None:
    """Both after() and every() timers are cancelled on scene exit."""
    fired_after: list[str] = []
    fired_every: list[str] = []

    class TimerScene(Scene):
        def on_enter(self) -> None:
            self.after(0.5, lambda: fired_after.append("after"))
            self.every(0.1, lambda: fired_every.append("every"))

    game.push(TimerScene())
    game.tick(dt=0.1)
    assert len(fired_every) == 1

    game.pop()

    # Advance well past all deadlines
    game.tick(dt=1.0)
    game.tick(dt=1.0)

    assert len(fired_after) == 0  # never fired
    assert len(fired_every) == 1  # only fired once while active


# ------------------------------------------------------------------
# Scene with no timers: cleanup is harmless
# ------------------------------------------------------------------


def test_scene_without_timers_exits_cleanly(game: Game) -> None:
    """A scene that never calls after/every exits without error."""
    game.push(Scene())
    game.pop()  # should not raise


# ------------------------------------------------------------------
# Deferred operations preserve timer cleanup semantics
# ------------------------------------------------------------------


def test_deferred_pop_cancels_timers(game: Game) -> None:
    """Deferred pop (during tick) still cancels owned timers."""
    fired: list[str] = []

    class TimerScene(Scene):
        def on_enter(self) -> None:
            self.after(0.5, lambda: fired.append("should not fire"))

        def update(self, dt: float) -> None:
            self.game.pop()

    game.push(TimerScene())
    game.tick(dt=0.016)

    game.tick(dt=1.0)
    game.tick(dt=1.0)

    assert len(fired) == 0


def test_multiple_timers_all_cancelled(game: Game) -> None:
    """Multiple timers (3 after + 2 every) are all cancelled on exit."""
    fired: list[str] = []

    class TimerScene(Scene):
        def on_enter(self) -> None:
            self.after(0.5, lambda: fired.append("a1"))
            self.after(1.0, lambda: fired.append("a2"))
            self.after(2.0, lambda: fired.append("a3"))
            self.every(0.3, lambda: fired.append("e1"))
            self.every(0.7, lambda: fired.append("e2"))

    game.push(TimerScene())
    game.pop()

    game.tick(dt=3.0)
    game.tick(dt=3.0)

    assert len(fired) == 0
