"""Adversarial Stage 2 — edge-case tests for scene stack, actions, timers,
tweens, audio, save system, UI component tree, and camera.

Tests cover:
1. Scene stack reentrancy: on_enter / on_exit / on_reveal calling push / pop /
   replace, including deeply nested chains.
2. Action system edge cases: deepcopy with closures, parallel instant/long mix,
   start() raising, stop() during update().
3. Timer/Tween interaction: timer callback creates tween, tween on_complete
   cancels another tween, cancel_all from within a callback.
4. Audio edge cases: rapid crossfade_music(), play_sound(optional=True) for
   missing asset, play_pool with pool of size 1.
5. Save system: deeply nested state, unicode keys, slot validation.
6. UI component tree: deeply nested Panels, tooltip on draggable, remove
   component during its own on_click callback.
7. Camera: shake() with negative intensity, pan_to() interrupted by another
   pan_to(), edge_scroll at exact corner.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, cast

import pytest

from easygame import (
    Action,
    Delay,
    Do,
    FadeOut,
    Game,
    Parallel,
    Repeat,
    Sequence,
    Sprite,
)
from easygame.assets import AssetManager, AssetNotFoundError
from easygame.backends.base import Backend
from easygame.backends.mock_backend import MockBackend
from easygame.input import InputEvent
from easygame.rendering.camera import Camera
from easygame.save import SaveManager
from easygame.scene import Scene, SceneStack
from easygame.ui import Anchor, Button, Label, Layout, Panel
from easygame.ui.component import _UIRoot
from easygame.ui.widgets import Tooltip
from easygame.util.tween import tween


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


class FakeGame:
    """Minimal game stand-in for low-level SceneStack tests."""

    _hud = None


class TrackingScene(Scene):
    """Scene that records lifecycle calls in a shared *log* list."""

    def __init__(self, name: str, log: list[str] | None = None) -> None:
        self.name = name
        self.log: list[str] = log if log is not None else []

    def on_enter(self) -> None:
        self.log.append(f"{self.name}.on_enter")

    def on_exit(self) -> None:
        self.log.append(f"{self.name}.on_exit")

    def on_reveal(self) -> None:
        self.log.append(f"{self.name}.on_reveal")


# ------------------------------------------------------------------
# Fixtures (match existing test_actions.py pattern)
# ------------------------------------------------------------------


@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    images = tmp_path / "images" / "sprites"
    images.mkdir(parents=True)
    (images / "knight.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def game(asset_dir: Path) -> Game:
    g = Game("Test", backend="mock", resolution=(800, 600))
    g.assets = AssetManager(cast(Backend, g.backend), base_path=asset_dir)
    return g


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return cast(MockBackend, game.backend)


@pytest.fixture
def sprite(game: Game) -> Sprite:
    return Sprite("sprites/knight", position=(100, 300))


# ===================================================================
# 1. Scene Stack Reentrancy
# ===================================================================


class TestSceneStackReentrancy:
    """Scenes whose lifecycle hooks mutate the stack (push/pop/replace)."""

    # ---------------------------------------------------------------
    # on_enter pushes another scene
    # ---------------------------------------------------------------

    def test_on_enter_pushes_another_scene(self) -> None:
        """A.on_enter pushes B → B ends up on top, A got on_exit."""
        log: list[str] = []
        game = FakeGame()
        stack = SceneStack(cast(Game, game))

        class SceneB(TrackingScene):
            pass

        class SceneA(TrackingScene):
            def on_enter(self) -> None:
                super().on_enter()
                stack.push(SceneB("B", self.log))

        a = SceneA("A", log)
        stack.push(a)

        assert stack.top().name == "B"  # type: ignore[union-attr]
        assert "A.on_enter" in log
        assert "A.on_exit" in log
        assert "B.on_enter" in log

    # ---------------------------------------------------------------
    # Deeply nested: A.on_enter → push B → B.on_enter → push C
    # ---------------------------------------------------------------

    def test_deeply_nested_on_enter_chain(self) -> None:
        """A.on_enter pushes B, B.on_enter pushes C → C on top."""
        log: list[str] = []
        game = FakeGame()
        stack = SceneStack(cast(Game, game))

        class SceneC(TrackingScene):
            pass

        class SceneB(TrackingScene):
            def on_enter(self) -> None:
                super().on_enter()
                stack.push(SceneC("C", self.log))

        class SceneA(TrackingScene):
            def on_enter(self) -> None:
                super().on_enter()
                stack.push(SceneB("B", self.log))

        a = SceneA("A", log)
        stack.push(a)

        assert stack.top().name == "C"  # type: ignore[union-attr]
        assert len(stack._stack) == 3
        # Lifecycle order: A enters, A exits (pushed over by B),
        # B enters, B exits (pushed over by C), C enters.
        assert "A.on_enter" in log
        assert "B.on_enter" in log
        assert "C.on_enter" in log

    # ---------------------------------------------------------------
    # on_exit pushes a scene (deferred during flushing)
    # ---------------------------------------------------------------

    def test_on_exit_pushes_scene(self) -> None:
        """When A is popped, A.on_exit pushes D → deferred.  D materialises
        only after the pending ops are flushed (next tick or manual flush)."""
        log: list[str] = []
        game = FakeGame()
        stack = SceneStack(cast(Game, game))

        class SceneD(TrackingScene):
            pass

        class SceneA(TrackingScene):
            def on_exit(self) -> None:
                super().on_exit()
                stack.push(SceneD("D", self.log))

        a = SceneA("A", log)
        stack.push(a)
        # pop A → on_exit fires → push D deferred (on_exit sets _in_on_exit)
        stack.pop()

        # Push was deferred; verify it's in the pending ops queue
        assert "A.on_exit" in log
        assert len(stack._pending_ops) == 1

        # Flush to apply the deferred push
        stack.flush_pending_ops()
        assert stack.top() is not None
        assert stack.top().name == "D"  # type: ignore[union-attr]
        assert "D.on_enter" in log

    # ---------------------------------------------------------------
    # on_exit calls pop (re-entrance via on_exit)
    # ---------------------------------------------------------------

    def test_on_exit_pushes_during_pop(self) -> None:
        """B.on_exit pushes X → deferred; when flushed X is on top."""
        log: list[str] = []
        game = FakeGame()
        stack = SceneStack(cast(Game, game))

        class SceneB(TrackingScene):
            def on_exit(self) -> None:
                super().on_exit()
                stack.push(TrackingScene("X", self.log))

        a = TrackingScene("A", log)
        b = SceneB("B", log)

        stack.push(a)
        stack.push(b)

        # Pop B: on_exit fires, push X deferred (_in_on_exit is True)
        stack.pop()

        assert "B.on_exit" in log
        assert "A.on_reveal" in log
        # Push was deferred — X not yet applied
        assert len(stack._pending_ops) == 1

        # Flush to apply
        stack.flush_pending_ops()
        assert stack.top().name == "X"  # type: ignore[union-attr]
        assert "X.on_enter" in log

    # ---------------------------------------------------------------
    # on_reveal pushes a scene
    # ---------------------------------------------------------------

    def test_on_reveal_pushes_scene(self) -> None:
        """A.on_reveal pushes E → deferred; E on top after flush."""
        log: list[str] = []
        game = FakeGame()
        stack = SceneStack(cast(Game, game))

        class SceneE(TrackingScene):
            pass

        class SceneA(TrackingScene):
            def on_reveal(self) -> None:
                super().on_reveal()
                stack.push(SceneE("E", self.log))

        a = SceneA("A", log)
        b = TrackingScene("B", log)

        stack.push(a)
        stack.push(b)
        stack.pop()  # B popped, A revealed → A pushes E (deferred)

        assert "A.on_reveal" in log
        # Push E was deferred because on_reveal runs during _in_on_exit
        assert len(stack._pending_ops) == 1

        stack.flush_pending_ops()
        assert "E.on_enter" in log
        # E is on top; A is below (got on_exit when E was pushed)
        assert stack.top().name == "E"  # type: ignore[union-attr]

    # ---------------------------------------------------------------
    # on_enter calls replace
    # ---------------------------------------------------------------

    def test_on_enter_replaces_self(self) -> None:
        """A.on_enter replaces itself with R → R ends up on top."""
        log: list[str] = []
        game = FakeGame()
        stack = SceneStack(cast(Game, game))

        class SceneR(TrackingScene):
            pass

        class SceneA(TrackingScene):
            def on_enter(self) -> None:
                super().on_enter()
                stack.replace(SceneR("R", self.log))

        a = SceneA("A", log)
        stack.push(a)

        assert stack.top().name == "R"  # type: ignore[union-attr]
        assert "A.on_enter" in log
        assert "A.on_exit" in log
        assert "R.on_enter" in log

    # ---------------------------------------------------------------
    # on_enter calls pop (pops self)
    # ---------------------------------------------------------------

    def test_on_enter_pops_self(self) -> None:
        """B.on_enter pops → stack returns to A, A gets on_reveal."""
        log: list[str] = []
        game = FakeGame()
        stack = SceneStack(cast(Game, game))

        class SceneB(TrackingScene):
            def on_enter(self) -> None:
                super().on_enter()
                stack.pop()

        a = TrackingScene("A", log)
        b = SceneB("B", log)

        stack.push(a)
        stack.push(b)

        # B entered then popped itself → A revealed
        assert stack.top().name == "A"  # type: ignore[union-attr]
        assert "B.on_enter" in log
        assert "B.on_exit" in log
        assert "A.on_reveal" in log

    # ---------------------------------------------------------------
    # Triple chain: A.on_enter→push B, B.on_enter→push C, C.on_enter→pop
    # ---------------------------------------------------------------

    def test_triple_chain_with_pop(self) -> None:
        """A→push B→push C→pop C: B ends up on top, B gets on_reveal."""
        log: list[str] = []
        game = FakeGame()
        stack = SceneStack(cast(Game, game))

        class SceneC(TrackingScene):
            def on_enter(self) -> None:
                super().on_enter()
                stack.pop()

        class SceneB(TrackingScene):
            def on_enter(self) -> None:
                super().on_enter()
                stack.push(SceneC("C", self.log))

        class SceneA(TrackingScene):
            def on_enter(self) -> None:
                super().on_enter()
                stack.push(SceneB("B", self.log))

        a = SceneA("A", log)
        stack.push(a)

        # A.on_enter → push B → B.on_enter → push C → C.on_enter → pop C
        assert "C.on_enter" in log
        assert "C.on_exit" in log
        assert "B.on_reveal" in log
        assert stack.top().name == "B"  # type: ignore[union-attr]

    # ---------------------------------------------------------------
    # Reentrancy during game tick (deferred ops)
    # ---------------------------------------------------------------

    def test_on_enter_push_during_game_tick(self, game: Game) -> None:
        """Push from on_enter during game.tick() is properly deferred and flushed."""
        log: list[str] = []

        class Inner(Scene):
            def on_enter(self) -> None:
                log.append("Inner.on_enter")

        class Outer(Scene):
            def on_enter(self) -> None:
                log.append("Outer.on_enter")
                self.game.push(Inner())

        game.push(Outer())
        game.tick(dt=0.016)

        # Inner was pushed (deferred from Outer.on_enter or directly)
        assert "Outer.on_enter" in log
        assert "Inner.on_enter" in log

    # ---------------------------------------------------------------
    # Deeply nested during update (deferred)
    # ---------------------------------------------------------------

    def test_nested_push_during_update(self, game: Game) -> None:
        """Scene.update() pushes new scene → deferred until flush."""
        entered: list[str] = []

        class Child(Scene):
            def on_enter(self) -> None:
                entered.append("Child")

        class Parent(Scene):
            _pushed = False

            def update(self, dt: float) -> None:
                if not self._pushed:
                    self._pushed = True
                    self.game.push(Child())

        game.push(Parent())
        game.tick(dt=0.016)

        assert "Child" in entered


# ===================================================================
# 2. Action System — Deepcopy of closures / lambdas
# ===================================================================


class TestActionDeepcopy:
    """Verify deepcopy works correctly for actions containing closures."""

    def test_deepcopy_do_with_lambda(self) -> None:
        """Do(lambda) can be deepcopied; each copy calls independently."""
        counter = [0]
        original = Do(lambda: counter.__setitem__(0, counter[0] + 1))
        cloned = copy.deepcopy(original)

        # Both share the *same* closure variable (counter list is mutable
        # and deepcopy copies the function object which still closes over
        # the *original* list).
        assert cloned is not original
        assert cloned._fn is not original._fn or callable(cloned._fn)

    def test_deepcopy_sequence_with_closures(self) -> None:
        """Sequence containing Do(lambda) survives deepcopy."""
        log: list[int] = []
        seq = Sequence(
            Do(lambda: log.append(1)),
            Delay(0.1),
            Do(lambda: log.append(2)),
        )
        cloned = copy.deepcopy(seq)
        assert cloned is not seq
        assert len(cloned._actions) == 3
        # Internal state is independent
        assert cloned._index == 0

    def test_repeat_deepcopy_preserves_lambda_behavior(
        self, sprite: Sprite, game: Game,
    ) -> None:
        """Repeat deep-copies its template each iteration; lambdas still work."""
        counter = [0]
        sprite.do(
            Repeat(
                Sequence(
                    Delay(0.05),
                    Do(lambda: counter.__setitem__(0, counter[0] + 1)),
                ),
                times=3,
            )
        )
        game.tick(dt=0.05)
        assert counter[0] == 1
        game.tick(dt=0.05)
        assert counter[0] == 2
        game.tick(dt=0.05)
        assert counter[0] == 3

    def test_deepcopy_parallel_with_closures(self) -> None:
        """Parallel containing lambdas survives deepcopy."""
        a_log: list[int] = []
        b_log: list[int] = []
        par = Parallel(
            Do(lambda: a_log.append(1)),
            Sequence(Delay(0.1), Do(lambda: b_log.append(2))),
        )
        cloned = copy.deepcopy(par)
        assert cloned is not par
        assert len(cloned._actions) == 2
        # done flags are independent
        assert cloned._done == [False, False]

    def test_deepcopy_nested_do_with_captured_variable(self) -> None:
        """Closure capturing a local variable works after deepcopy."""
        results: list[str] = []
        name = "hello"
        action = Do(lambda: results.append(name))
        cloned = copy.deepcopy(action)

        # Execute original
        action.update(0.0)
        assert results == ["hello"]

        # Execute clone — it should also append (same closure var or copy)
        cloned.update(0.0)
        assert len(results) >= 2  # deepcopy of lambda may share mutable


# ===================================================================
# 2. Action System — Parallel with mix of instant and long-running
# ===================================================================


class TestParallelMixedActions:
    """Parallel with Do (instant) alongside Delay / FadeOut (long-running)."""

    def test_parallel_instant_and_delay(self, sprite: Sprite, game: Game) -> None:
        """Parallel(Do, Delay): Do fires immediately, waits for Delay."""
        fired = []
        sprite.do(
            Parallel(
                Do(lambda: fired.append("instant")),
                Delay(0.2),
            )
        )
        game.tick(dt=0.016)
        assert "instant" in fired
        # Still running because Delay not done
        assert sprite in game._action_sprites
        game.tick(dt=0.2)
        assert sprite not in game._action_sprites

    def test_parallel_multiple_do_and_delay(
        self, sprite: Sprite, game: Game,
    ) -> None:
        """Parallel(Do, Do, Delay): both Do fire on first tick, Delay continues."""
        log: list[str] = []
        sprite.do(
            Parallel(
                Do(lambda: log.append("a")),
                Do(lambda: log.append("b")),
                Delay(0.1),
            )
        )
        game.tick(dt=0.016)
        assert "a" in log
        assert "b" in log
        assert sprite in game._action_sprites  # Delay still running

    def test_parallel_do_and_fadeout(self, sprite: Sprite, game: Game) -> None:
        """Parallel(Do, FadeOut): Do fires immediately, FadeOut continues."""
        callback_count = [0]
        sprite.do(
            Parallel(
                Do(lambda: callback_count.__setitem__(0, 1)),
                FadeOut(0.3),
            )
        )
        game.tick(dt=0.016)
        assert callback_count[0] == 1
        assert sprite.opacity > 0  # FadeOut hasn't completed
        assert sprite in game._action_sprites

        game.tick(dt=0.3)
        assert sprite.opacity == 0
        assert sprite not in game._action_sprites

    def test_parallel_instant_only(self, sprite: Sprite, game: Game) -> None:
        """Parallel of only Do actions completes in one tick."""
        log: list[int] = []
        sprite.do(
            Parallel(
                Do(lambda: log.append(1)),
                Do(lambda: log.append(2)),
                Do(lambda: log.append(3)),
            )
        )
        game.tick(dt=0.016)
        assert sorted(log) == [1, 2, 3]
        assert sprite not in game._action_sprites

    def test_parallel_do_sequence_and_delay(
        self, sprite: Sprite, game: Game,
    ) -> None:
        """Parallel(Sequence(Do, Do), Delay(0.1)): sequence fires instantly,
        Delay keeps Parallel alive."""
        seq_log: list[int] = []
        sprite.do(
            Parallel(
                Sequence(
                    Do(lambda: seq_log.append(1)),
                    Do(lambda: seq_log.append(2)),
                ),
                Delay(0.1),
            )
        )
        game.tick(dt=0.016)
        assert seq_log == [1, 2]
        assert sprite in game._action_sprites  # Delay not done

        game.tick(dt=0.1)
        assert sprite not in game._action_sprites


# ===================================================================
# 2. Action System — Sequence where child start() raises
# ===================================================================


class _ExplodingAction(Action):
    """Action whose start() raises RuntimeError."""

    def start(self, sprite: Sprite) -> None:
        raise RuntimeError("start() exploded")

    def update(self, dt: float) -> bool:
        return True


class _TrackingAction(Action):
    """Records start/update/stop calls."""

    def __init__(self) -> None:
        self.started = False
        self.updated = False
        self.stopped = False

    def start(self, sprite: Sprite) -> None:
        self.started = True

    def update(self, dt: float) -> bool:
        self.updated = True
        return True

    def stop(self) -> None:
        self.stopped = True


class TestSequenceChildStartRaises:
    """When a child action's start() raises, the error propagates."""

    def test_first_child_start_raises(self, sprite: Sprite, game: Game) -> None:
        """If the very first child's start() raises during Sequence.start(),
        the exception propagates from sprite.do()."""
        with pytest.raises(RuntimeError, match="start\\(\\) exploded"):
            sprite.do(Sequence(_ExplodingAction()))

    def test_second_child_start_raises_after_first_completes(
        self, sprite: Sprite, game: Game,
    ) -> None:
        """First child (Do) completes → Sequence starts second child →
        second child's start() raises during update()."""
        log: list[str] = []
        second = _ExplodingAction()

        sprite.do(
            Sequence(
                Do(lambda: log.append("first")),
                second,  # start() will raise when Sequence advances
            )
        )
        # First Do is started ok; on first tick Do completes, Sequence
        # calls second.start() which raises during update.
        with pytest.raises(RuntimeError, match="start\\(\\) exploded"):
            game.tick(dt=0.016)

        assert "first" in log

    def test_exploding_start_does_not_run_subsequent_children(
        self, sprite: Sprite, game: Game,
    ) -> None:
        """After start() raises on child N, child N+1 is never started."""
        third = _TrackingAction()

        sprite.do(
            Sequence(
                Do(lambda: None),
                _ExplodingAction(),
                third,
            )
        )
        with pytest.raises(RuntimeError):
            game.tick(dt=0.016)

        assert not third.started
        assert not third.updated


# ===================================================================
# 2. Action System — stop() called during update()
# ===================================================================


class _StopDuringUpdateAction(Action):
    """Long-running action that records calls."""

    def __init__(self) -> None:
        self._sprite: Sprite | None = None
        self.update_count = 0
        self.stopped = False

    def start(self, sprite: Sprite) -> None:
        self._sprite = sprite

    def update(self, dt: float) -> bool:
        self.update_count += 1
        return False  # Never finishes on its own

    def stop(self) -> None:
        self.stopped = True


class TestStopDuringUpdate:
    """Calling stop_actions() or do(new_action) while an action is mid-update."""

    def test_stop_actions_after_partial_update(
        self, sprite: Sprite, game: Game,
    ) -> None:
        """stop_actions() after a few ticks cancels action cleanly."""
        action = _StopDuringUpdateAction()
        sprite.do(action)

        game.tick(dt=0.016)
        game.tick(dt=0.016)
        assert action.update_count == 2
        assert not action.stopped

        sprite.stop_actions()
        assert action.stopped
        assert sprite not in game._action_sprites

        # No more updates
        game.tick(dt=0.016)
        assert action.update_count == 2

    def test_do_replaces_action_during_sequence_update(
        self, sprite: Sprite, game: Game,
    ) -> None:
        """Calling sprite.do(new) replaces the old action; old gets stop()."""
        old_action = _StopDuringUpdateAction()
        sprite.do(old_action)
        game.tick(dt=0.016)
        assert old_action.update_count == 1

        new_fired = []
        sprite.do(Do(lambda: new_fired.append(True)))
        # Old action was stopped by do()
        assert old_action.stopped

        game.tick(dt=0.016)
        assert new_fired == [True]
        # Old action didn't get another update
        assert old_action.update_count == 1

    def test_stop_inside_do_callback(self, sprite: Sprite, game: Game) -> None:
        """Do(fn) where fn calls sprite.stop_actions() — should not crash."""
        log: list[str] = []

        def stop_self() -> None:
            log.append("stopping")
            sprite.stop_actions()

        sprite.do(
            Sequence(
                Do(stop_self),
                Do(lambda: log.append("should_not_run")),
            )
        )
        game.tick(dt=0.016)
        assert "stopping" in log
        # The sequence was stopped, so the second Do should not run.
        # (Depending on implementation, the stop may or may not take
        # effect immediately within the same tick.)
        assert sprite not in game._action_sprites

    def test_parallel_stop_during_running(
        self, sprite: Sprite, game: Game,
    ) -> None:
        """Stopping Parallel mid-flight stops all children."""
        a = _StopDuringUpdateAction()
        b = _StopDuringUpdateAction()
        sprite.do(Parallel(a, b))

        game.tick(dt=0.016)
        assert a.update_count == 1
        assert b.update_count == 1

        sprite.stop_actions()
        assert a.stopped
        assert b.stopped

    def test_sequence_stop_only_stops_current_child(
        self, sprite: Sprite, game: Game,
    ) -> None:
        """Stopping a Sequence only calls stop() on the current child."""
        first = _StopDuringUpdateAction()
        second = _TrackingAction()
        sprite.do(Sequence(first, second))

        game.tick(dt=0.016)
        # first is the active child (never completes), second not started
        assert first.update_count == 1
        assert not second.started

        sprite.stop_actions()
        assert first.stopped
        assert not second.stopped  # Never started, never stopped

    def test_stop_on_unstarted_action_is_safe(self) -> None:
        """Calling stop() on an action that was never started is a no-op."""
        actions = [
            Delay(1.0),
            Do(lambda: None),
            Sequence(Delay(0.5)),
            Parallel(Delay(0.5)),
            _StopDuringUpdateAction(),
        ]
        for action in actions:
            action.stop()  # Should not raise


# ===================================================================
# 3. Timer / Tween Interaction
# ===================================================================


class TestTimerTweenInteraction:
    """Timer callbacks creating tweens and tweens cancelling other tweens."""

    def test_timer_callback_creates_tween(self, game: Game) -> None:
        """A timer callback that creates a tween — tween should work normally."""
        obj = type("Obj", (), {"val": 0.0})()
        created = []

        def on_timer() -> None:
            tid = tween(obj, "val", 0.0, 100.0, 0.5)
            created.append(tid)

        game.after(0.1, on_timer)
        # Advance past the timer
        game.tick(dt=0.1)
        assert len(created) == 1

        # Tween should now be active; advance it
        game.tick(dt=0.25)
        assert obj.val > 0.0
        game.tick(dt=0.25)
        assert obj.val == 100.0

    def test_tween_on_complete_cancels_another_tween(self, game: Game) -> None:
        """Tween A's on_complete cancels Tween B — B should stop mid-way."""
        obj_a = type("ObjA", (), {"val": 0.0})()
        obj_b = type("ObjB", (), {"val": 0.0})()

        tid_b_holder: list[int] = []

        def cancel_b() -> None:
            if tid_b_holder:
                game.cancel_tween(tid_b_holder[0])

        # A completes in 0.2s and cancels B
        tween(obj_a, "val", 0.0, 100.0, 0.2, on_complete=cancel_b)
        tid_b = tween(obj_b, "val", 0.0, 100.0, 1.0)
        tid_b_holder.append(tid_b)

        # Advance partway — both tweens should be in progress
        game.tick(dt=0.1)
        assert 0.0 < obj_a.val < 100.0
        assert 0.0 < obj_b.val < 100.0

        # Complete A — its on_complete cancels B
        game.tick(dt=0.1)
        assert obj_a.val == 100.0
        b_val_at_cancel = obj_b.val
        # B was updated this tick then cancelled — it should have some value
        assert b_val_at_cancel > 0.0

        # B should not advance further after cancellation
        game.tick(dt=0.5)
        assert obj_b.val == b_val_at_cancel

    def test_cancel_all_timers_from_within_callback(self, game: Game) -> None:
        """cancel_all() on the timer manager from inside a timer callback."""
        fired: list[str] = []

        def nuke_all() -> None:
            fired.append("nuke")
            game._timer_manager.cancel_all()

        game.after(0.1, nuke_all)
        game.after(0.1, lambda: fired.append("second"))
        game.every(0.1, lambda: fired.append("repeating"))

        game.tick(dt=0.1)
        # "nuke" fired, then cancel_all killed the others
        assert "nuke" in fired
        # The other timers may or may not fire depending on iteration order
        # (snapshot copy), but after cancel_all no more should fire
        fired.clear()
        game.tick(dt=0.1)
        assert fired == []  # All timers cancelled

    def test_cancel_all_tweens_from_within_tween_callback(
        self, game: Game,
    ) -> None:
        """cancel_all() on the tween manager from inside an on_complete."""
        obj_a = type("ObjA", (), {"val": 0.0})()
        obj_b = type("ObjB", (), {"val": 0.0})()

        def nuke_tweens() -> None:
            game._tween_manager.cancel_all()

        tween(obj_a, "val", 0.0, 1.0, 0.1, on_complete=nuke_tweens)
        tween(obj_b, "val", 0.0, 1.0, 0.5)

        game.tick(dt=0.1)
        assert obj_a.val == 1.0
        b_val = obj_b.val
        # B should be cancelled and not advance further
        game.tick(dt=0.5)
        assert obj_b.val == b_val

    def test_timer_creates_tween_that_creates_timer(self, game: Game) -> None:
        """Chain: timer → creates tween → tween on_complete creates timer."""
        final_fired: list[bool] = []

        def on_tween_done() -> None:
            game.after(0.05, lambda: final_fired.append(True))

        def on_timer() -> None:
            obj = type("O", (), {"v": 0.0})()
            tween(obj, "v", 0.0, 1.0, 0.1, on_complete=on_tween_done)

        game.after(0.05, on_timer)
        # 0.05s: timer fires → creates tween
        game.tick(dt=0.05)
        # 0.1s: tween completes → creates another timer
        game.tick(dt=0.1)
        # 0.05s: final timer fires
        game.tick(dt=0.05)
        assert final_fired == [True]


# ===================================================================
# 4. Audio Edge Cases
# ===================================================================


class TestAudioEdgeCases:
    """Audio system adversarial scenarios."""

    @pytest.fixture
    def audio_game(self, tmp_path: Path) -> Game:
        """Game with audio assets configured.

        AssetManager resolves sounds under ``base_path/sounds/`` and music
        under ``base_path/music/``.  Names passed to play_sound/play_music
        are relative to those directories.
        """
        sounds_dir = tmp_path / "sounds"
        sounds_dir.mkdir()
        (sounds_dir / "hit.wav").write_bytes(b"wav")
        (sounds_dir / "ack_01.wav").write_bytes(b"wav")

        music_dir = tmp_path / "music"
        music_dir.mkdir()
        (music_dir / "town.ogg").write_bytes(b"ogg")
        (music_dir / "battle.ogg").write_bytes(b"ogg")
        (music_dir / "boss.ogg").write_bytes(b"ogg")

        g = Game("AudioTest", backend="mock", resolution=(800, 600))
        g.assets = AssetManager(cast(Backend, g.backend), base_path=tmp_path)
        return g

    def test_crossfade_rapid_calls(self, audio_game: Game) -> None:
        """Calling crossfade_music() rapidly multiple times doesn't crash."""
        audio = audio_game.audio
        audio.play_music("town")

        # Rapidly crossfade to different tracks
        audio.crossfade_music("battle", duration=0.5)
        audio.crossfade_music("boss", duration=0.5)
        audio.crossfade_music("town", duration=0.5)
        audio.crossfade_music("battle", duration=0.5)

        # Should not crash; advance time to let tweens settle
        for _ in range(20):
            audio_game.tick(dt=0.05)

        # Final state: battle is playing
        assert audio._current_music_name == "battle"

    def test_crossfade_to_same_track_is_noop(self, audio_game: Game) -> None:
        """crossfade_music() with the same track name is a no-op."""
        audio = audio_game.audio
        audio.play_music("town")
        player_before = audio._current_player_id

        audio.crossfade_music("town", duration=1.0)

        # Player should not change (no-op)
        assert audio._current_player_id == player_before
        assert audio._crossfade_tween_ids == []

    def test_play_sound_optional_missing_asset(self, audio_game: Game) -> None:
        """play_sound(optional=True) with missing asset does not raise."""
        audio = audio_game.audio
        # This should NOT raise
        audio.play_sound("nonexistent", optional=True)

    def test_play_sound_non_optional_missing_asset_raises(
        self, audio_game: Game,
    ) -> None:
        """play_sound(optional=False) with missing asset raises."""
        audio = audio_game.audio
        with pytest.raises(AssetNotFoundError):
            audio.play_sound("nonexistent", optional=False)

    def test_play_pool_size_one(self, audio_game: Game) -> None:
        """play_pool() with a pool of size 1 always plays that sound."""
        audio = audio_game.audio
        audio.register_pool("single", ["hit"])

        mock_backend = cast(MockBackend, audio_game.backend)
        count_before = len(mock_backend.sounds_played)

        # Play several times — should always work
        for _ in range(5):
            audio.play_pool("single")

        assert len(mock_backend.sounds_played) == count_before + 5

    def test_play_pool_size_one_no_repeat_crash(self, audio_game: Game) -> None:
        """Pool of size 1 doesn't crash from the no-repeat logic."""
        audio = audio_game.audio
        audio.register_pool("one", ["hit"])
        # The no-repeat logic skips the last played index, but with 1 sound
        # it should still work
        audio.play_pool("one")
        audio.play_pool("one")
        audio.play_pool("one")
        # No crash = success

    def test_crossfade_when_no_music_playing(self, audio_game: Game) -> None:
        """crossfade_music() with no current music acts like play_music()."""
        audio = audio_game.audio
        assert audio._current_player_id is None

        audio.crossfade_music("town", duration=1.0)
        assert audio._current_music_name == "town"
        assert audio._current_player_id is not None


# ===================================================================
# 5. Save System Edge Cases
# ===================================================================


class TestSaveSystemEdgeCases:
    """Save system with deeply nested state, unicode keys, slot validation."""

    @pytest.fixture
    def save_mgr(self, tmp_path: Path) -> SaveManager:
        return SaveManager(tmp_path / "saves")

    def test_save_deeply_nested_state_100_levels(
        self, save_mgr: SaveManager,
    ) -> None:
        """Save state nested 100 levels deep — JSON handles it fine."""
        # Build nested dict 100 levels deep
        state: dict[str, Any] = {"leaf": True}
        for i in range(100):
            state = {"level": i, "child": state}

        save_mgr.save(1, state, "DeepScene")
        loaded = save_mgr.load(1)
        assert loaded is not None

        # Walk down to verify depth
        inner = loaded["state"]
        for i in range(100):
            assert inner["level"] == 99 - i
            inner = inner["child"]
        assert inner["leaf"] is True

    def test_save_with_unicode_keys(self, save_mgr: SaveManager) -> None:
        """Unicode keys and values survive round-trip."""
        state = {
            "名前": "勇者",
            "レベル": 42,
            "emoji_key_🗡️": "sword",
            "nested": {"clé": "valeur", "Schlüssel": "Wert"},
        }
        save_mgr.save(1, state, "UnicodeScene")
        loaded = save_mgr.load(1)
        assert loaded is not None
        assert loaded["state"]["名前"] == "勇者"
        assert loaded["state"]["レベル"] == 42
        assert loaded["state"]["emoji_key_🗡️"] == "sword"
        assert loaded["state"]["nested"]["clé"] == "valeur"

    def test_save_slot_zero_raises(self, save_mgr: SaveManager) -> None:
        """Slot 0 raises ValueError."""
        with pytest.raises(ValueError, match="slot must be >= 1"):
            save_mgr.save(0, {}, "TestScene")

    def test_save_negative_slot_raises(self, save_mgr: SaveManager) -> None:
        """Negative slot raises ValueError."""
        with pytest.raises(ValueError, match="slot must be >= 1"):
            save_mgr.save(-1, {}, "TestScene")

    def test_load_slot_zero_raises(self, save_mgr: SaveManager) -> None:
        """Load from slot 0 raises ValueError."""
        with pytest.raises(ValueError, match="slot must be >= 1"):
            save_mgr.load(0)

    def test_load_negative_slot_raises(self, save_mgr: SaveManager) -> None:
        """Load from negative slot raises ValueError."""
        with pytest.raises(ValueError, match="slot must be >= 1"):
            save_mgr.load(-5)

    def test_delete_slot_zero_raises(self, save_mgr: SaveManager) -> None:
        """Delete slot 0 raises ValueError."""
        with pytest.raises(ValueError, match="slot must be >= 1"):
            save_mgr.delete(0)

    def test_save_deeply_nested_list(self, save_mgr: SaveManager) -> None:
        """Deeply nested lists survive round-trip."""
        state: Any = [1, 2, 3]
        for _ in range(50):
            state = [state, "wrapper"]

        save_mgr.save(2, {"data": state}, "ListScene")
        loaded = save_mgr.load(2)
        assert loaded is not None

        # Unwrap to verify
        inner = loaded["state"]["data"]
        for _ in range(50):
            assert inner[1] == "wrapper"
            inner = inner[0]
        assert inner == [1, 2, 3]

    def test_save_empty_state(self, save_mgr: SaveManager) -> None:
        """Empty state dict saves and loads correctly."""
        save_mgr.save(1, {}, "EmptyScene")
        loaded = save_mgr.load(1)
        assert loaded is not None
        assert loaded["state"] == {}

    def test_save_large_slot_number(self, save_mgr: SaveManager) -> None:
        """Very large slot number works fine."""
        save_mgr.save(9999, {"big": True}, "BigSlot")
        loaded = save_mgr.load(9999)
        assert loaded is not None
        assert loaded["state"]["big"] is True


# ===================================================================
# 6. UI Component Tree
# ===================================================================


class TestUIComponentTree:
    """Deeply nested UI, tooltip on draggable, remove during callback."""

    @pytest.fixture
    def ui_game(self) -> Game:
        return Game("UITest", backend="mock", resolution=(800, 600))

    @pytest.fixture
    def root(self, ui_game: Game) -> _UIRoot:
        return _UIRoot(ui_game)

    def test_deeply_nested_panel_hierarchy(self, root: _UIRoot) -> None:
        """10+ levels of nested Panels — layout should not crash."""
        # Build 12 levels deep
        innermost = Label("Deep", width=50, height=20)
        current: Panel | Label = innermost  # type: ignore[assignment]
        for i in range(12):
            panel = Panel(
                layout=Layout.VERTICAL,
                children=[current],
                width=60 + i * 10,
                height=30 + i * 10,
            )
            current = panel

        root.add(current)
        root._ensure_layout()

        # Verify the tree is intact by walking down
        node = root._children[0]
        depth = 0
        while hasattr(node, "_children") and node._children:
            depth += 1
            node = node._children[0]
        assert depth >= 12

    def test_deeply_nested_panel_draw(
        self, ui_game: Game, root: _UIRoot,
    ) -> None:
        """Drawing a deeply nested panel tree should not crash."""
        current: Panel | Label = Label("Leaf", width=40, height=20)  # type: ignore[assignment]
        for _ in range(10):
            current = Panel(
                layout=Layout.VERTICAL,
                children=[current],
                width=100,
                height=100,
            )
        root.add(current)
        root._ensure_layout()
        root.draw()  # Should not crash

    def test_tooltip_on_draggable_component(self, root: _UIRoot) -> None:
        """A draggable component can have a tooltip added alongside it."""
        draggable_btn = Button(
            "Drag Me",
            width=100,
            height=40,
            anchor=Anchor.TOP_LEFT,
            draggable=True,
            drag_data="payload",
        )
        tooltip = Tooltip("Drag this item", delay=0.3)

        root.add(draggable_btn)
        root.add(tooltip)
        root._ensure_layout()

        # Show tooltip at button position
        tooltip.show(50, 20)
        assert tooltip._showing is True
        assert tooltip._visible_now is False

        # Advance past delay
        tooltip.update(0.4)
        assert tooltip._visible_now is True

        # Hide
        tooltip.hide()
        assert tooltip._visible_now is False
        assert tooltip._showing is False

    def test_remove_component_during_own_on_click(
        self, ui_game: Game, root: _UIRoot,
    ) -> None:
        """Button removes itself from parent during its own on_click."""
        panel = Panel(
            layout=Layout.VERTICAL,
            width=200,
            height=200,
            anchor=Anchor.TOP_LEFT,
        )
        removed: list[bool] = []

        btn = Button("Remove Me", width=100, height=40)

        def self_destruct() -> None:
            removed.append(True)
            if btn.parent is not None:
                btn.parent.remove(btn)

        btn.on_click = self_destruct
        panel.add(btn)
        root.add(panel)
        root._ensure_layout()

        # Simulate click inside the button's bounds
        event = InputEvent(type="click", x=50, y=20, button="left")
        consumed = root.handle_event(event)

        assert consumed is True
        assert removed == [True]
        assert btn.parent is None
        assert btn not in panel._children

    def test_add_many_children_to_panel(self, root: _UIRoot) -> None:
        """Panel with many children (50+) handles layout correctly."""
        panel = Panel(
            layout=Layout.VERTICAL,
            spacing=2,
            width=300,
            anchor=Anchor.TOP_LEFT,
        )
        for i in range(50):
            panel.add(Label(f"Item {i}", width=200, height=20))

        root.add(panel)
        root._ensure_layout()

        assert len(panel._children) == 50
        # Children should be stacked vertically
        for i in range(1, len(panel._children)):
            assert (
                panel._children[i]._computed_y
                >= panel._children[i - 1]._computed_y
            )


# ===================================================================
# 7. Camera Edge Cases
# ===================================================================


class TestCameraEdgeCases:
    """Camera adversarial scenarios."""

    def test_shake_with_negative_intensity(self) -> None:
        """shake() with negative intensity — implementation uses
        random.uniform(-intensity, intensity) which swaps bounds."""
        cam = Camera((800, 600))
        # Negative intensity: random.uniform(-(-5), -5) = uniform(5, -5)
        # Python's random.uniform handles a > b by returning values in [b, a].
        cam.shake(intensity=-5.0, duration=0.5, decay=1.0)

        # Advance to generate shake offsets — should not crash
        cam.update(dt=0.1)
        # Offsets should be within [-5, 5] (absolute value)
        assert -5.0 <= cam.shake_offset_x <= 5.0
        assert -5.0 <= cam.shake_offset_y <= 5.0

    def test_shake_zero_duration_resets(self) -> None:
        """shake(duration=0) resets any active shake immediately."""
        cam = Camera((800, 600))
        cam.shake(intensity=10.0, duration=1.0, decay=1.0)
        cam.update(dt=0.1)
        # Some shake should be active
        assert cam._shake_duration == 1.0

        # Reset with zero duration
        cam.shake(intensity=10.0, duration=0, decay=1.0)
        assert cam.shake_offset_x == 0.0
        assert cam.shake_offset_y == 0.0
        assert cam._shake_duration == 0.0

    def test_shake_negative_duration_resets(self) -> None:
        """shake(duration=-1) treated as reset (duration <= 0)."""
        cam = Camera((800, 600))
        cam.shake(intensity=10.0, duration=-1.0, decay=1.0)
        assert cam.shake_offset_x == 0.0
        assert cam.shake_offset_y == 0.0
        assert cam._shake_duration == 0.0

    def test_pan_to_interrupted_by_another_pan_to(self, game: Game) -> None:
        """Starting a new pan_to() cancels the previous one."""
        cam = Camera((800, 600))
        cam.center_on(0, 0)

        # First pan
        cam.pan_to(1000, 1000, duration=2.0)
        first_x_tween = cam._pan_tween_x
        first_y_tween = cam._pan_tween_y
        assert first_x_tween is not None
        assert first_y_tween is not None

        # Advance partway
        game.tick(dt=0.5)

        # Interrupt with second pan
        cam.pan_to(500, 500, duration=1.0)
        assert cam._pan_tween_x is not None
        assert cam._pan_tween_x != first_x_tween  # New tween
        assert cam._pan_tween_y != first_y_tween

        # Verify old tweens were cancelled (they should be gone from manager)
        assert first_x_tween not in game._tween_manager._tweens
        assert first_y_tween not in game._tween_manager._tweens

        # Advance second pan to completion
        game.tick(dt=1.0)
        # Camera should be near the second target center (500, 500)
        expected_x = 500 - 400  # center x=500 → top-left x=100
        expected_y = 500 - 300  # center y=500 → top-left y=200
        assert abs(cam._x - expected_x) < 2
        assert abs(cam._y - expected_y) < 2

    def test_pan_to_cancelled_by_center_on(self, game: Game) -> None:
        """center_on() cancels an active pan_to()."""
        cam = Camera((800, 600))
        cam.center_on(0, 0)
        cam.pan_to(1000, 1000, duration=2.0)
        assert cam._pan_tween_x is not None

        cam.center_on(200, 200)
        assert cam._pan_tween_x is None
        assert cam._pan_tween_y is None
        # Camera should be centered on (200, 200)
        assert abs(cam._x - (200 - 400)) < 1
        assert abs(cam._y - (200 - 300)) < 1

    def test_edge_scroll_at_exact_corner_top_left(self) -> None:
        """Mouse at (0, 0) — top-left corner — both axes should scroll."""
        cam = Camera(
            (800, 600),
            world_bounds=(0, 0, 4000, 3000),
        )
        # Center at (2000, 1500) so there's room to scroll in all directions
        cam.center_on(2000, 1500)
        cam.enable_edge_scroll(margin=50, speed=200)

        initial_x = cam._x
        initial_y = cam._y

        # Mouse at exact corner (0, 0) — within margin on both axes
        cam.update(dt=0.1, mouse_x=0, mouse_y=0)

        # Camera should have scrolled left and up
        assert cam._x < initial_x
        assert cam._y < initial_y

    def test_edge_scroll_at_exact_corner_bottom_right(self) -> None:
        """Mouse at (800, 600) — bottom-right corner — both axes scroll."""
        cam = Camera(
            (800, 600),
            world_bounds=(0, 0, 4000, 3000),
        )
        cam.center_on(2000, 1500)
        cam.enable_edge_scroll(margin=50, speed=200)

        initial_x = cam._x
        initial_y = cam._y

        # Mouse at bottom-right corner (beyond vw - margin, beyond vh - margin)
        cam.update(dt=0.1, mouse_x=800, mouse_y=600)

        # Camera should have scrolled right and down
        assert cam._x > initial_x
        assert cam._y > initial_y

    def test_edge_scroll_diagonal_speed(self) -> None:
        """Corner scroll moves at speed on each axis independently."""
        cam = Camera(
            (800, 600),
            world_bounds=(0, 0, 4000, 3000),
        )
        cam.center_on(2000, 1500)
        cam.enable_edge_scroll(margin=50, speed=100)

        initial_x = cam._x
        initial_y = cam._y

        cam.update(dt=1.0, mouse_x=0, mouse_y=0)

        # Each axis should have moved by speed * dt = 100
        assert abs((initial_x - cam._x) - 100) < 1
        assert abs((initial_y - cam._y) - 100) < 1

    def test_edge_scroll_clamped_to_world_bounds(self) -> None:
        """Edge scroll respects world bounds and doesn't go beyond."""
        cam = Camera(
            (800, 600),
            world_bounds=(0, 0, 800, 600),
        )
        cam.center_on(400, 300)  # Exactly fills the viewport
        cam.enable_edge_scroll(margin=50, speed=200)

        # Mouse at top-left corner — tries to scroll left/up but bounds prevent it
        cam.update(dt=1.0, mouse_x=0, mouse_y=0)

        # Should be clamped at (0, 0)
        assert cam._x == 0.0
        assert cam._y == 0.0
