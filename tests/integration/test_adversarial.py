"""Adversarial tests for scene stack re-entrancy, sprite lifecycle, actions,
timers, tweens, audio, save system, UI component tree, camera, and FSM.

Tests framework behavior when callbacks trigger stack ops, sprite mutations,
or other sensitive operations during update phases. All tests use MockBackend
(headless).

Merged from test_adversarial.py (Stage 1) and test_adversarial_stage_2.py
(Stage 2), with duplicates removed.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, cast

import pytest

from easygame import (
    Action,
    Camera,
    Delay,
    Do,
    FadeOut,
    Game,
    Parallel,
    Repeat,
    Scene,
    Sequence,
    Sprite,
    tween,
)
from easygame.assets import AssetManager, AssetNotFoundError
from easygame.backends.base import Backend
from easygame.backends.mock_backend import MockBackend
from easygame.input import InputEvent
from easygame.save import SaveManager
from easygame.scene import SceneStack
from easygame.ui import Anchor, Button, Component, Label, Layout, Panel
from easygame.ui.component import _UIRoot
from easygame.ui.widgets import Tooltip
from easygame.util.fsm import StateMachine


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
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    """Temp asset dir with a test image."""
    images = tmp_path / "images" / "sprites"
    images.mkdir(parents=True)
    (images / "knight.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def asset_dir_with_audio(tmp_path: Path) -> Path:
    """Temp asset dir with images, sounds, and music for audio tests."""
    images = tmp_path / "images" / "sprites"
    images.mkdir(parents=True)
    (images / "knight.png").write_bytes(b"png")
    sounds = tmp_path / "sounds"
    sounds.mkdir()
    (sounds / "click.wav").write_bytes(b"wav")
    music = tmp_path / "music"
    music.mkdir()
    (music / "exploration.ogg").write_bytes(b"ogg")
    (music / "battle.ogg").write_bytes(b"ogg")
    return tmp_path


@pytest.fixture
def game(asset_dir: Path) -> Game:
    """Game with mock backend and temp assets."""
    g = Game("Test", backend="mock", resolution=(800, 600))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    return g


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


@pytest.fixture
def sprite(game: Game) -> Sprite:
    return Sprite("sprites/knight", position=(100, 300))


# ==================================================================
# Scene stack re-entrancy (Stage 1 — original)
# ==================================================================


class TestSceneStackReentrancy:
    """Scene stack behavior when lifecycle hooks or update() trigger
    push/pop/replace during the same tick."""

    def test_on_enter_pushes_another_scene(self, game: Game) -> None:
        """on_enter() calling game.push() applies immediately; stack ends
        with [base, overlay] and no crash."""
        overlay = Scene()
        base = Scene()

        def base_on_enter() -> None:
            game.push(overlay)

        base.on_enter = base_on_enter  # type: ignore[method-assign]

        game.push(base)

        # After push(base): base.on_enter runs, which pushes overlay.
        # So stack should be [base, overlay], overlay is top.
        top = game._scene_stack.top()
        assert top is overlay
        assert len(game._scene_stack._stack) == 2
        assert game._scene_stack._stack[0] is base
        assert game._scene_stack._stack[1] is overlay

    def test_on_exit_calls_pop_no_recursion(self, game: Game) -> None:
        """on_exit() calling game.pop() defers the nested pop — no RecursionError."""
        base = Scene()
        middle = Scene()
        top_scene = Scene()

        def top_on_exit() -> None:
            game.pop()

        top_scene.on_exit = top_on_exit  # type: ignore[method-assign]

        game.push(base)
        game.push(middle)
        game.push(top_scene)

        # Must not raise RecursionError; nested pop is deferred.
        game.pop()
        # First pop removed top_scene; deferred pop removed middle.
        game.tick(dt=0.016)  # flush deferred ops
        assert len(game._scene_stack._stack) == 1
        assert game._scene_stack.top() is base

    def test_update_calls_replace_then_pop_same_tick(self, game: Game) -> None:
        """update() calling replace() then pop() — both deferred, executed
        in order during flush. Final stack loses top and replacement."""
        base = Scene()
        original_top = Scene()
        replacement = Scene()

        def original_update(dt: float) -> None:
            game.replace(replacement)
            game.pop()

        original_top.update = original_update  # type: ignore[method-assign]

        game.push(base)
        game.push(original_top)

        game.tick(dt=0.016)

        # replace(replacement) then pop() -> top becomes replacement, then
        # we pop it. Stack should be [base] only.
        assert len(game._scene_stack._stack) == 1
        assert game._scene_stack.top() is base

    def test_update_calls_push_then_pop_same_tick(self, game: Game) -> None:
        """update() calling push() then pop() — deferred ops run in order.
        Net effect: push overlay, then pop it; stack unchanged from before."""
        base = Scene()
        overlay = Scene()

        def base_update(dt: float) -> None:
            game.push(overlay)
            game.pop()

        base.update = base_update  # type: ignore[method-assign]

        game.push(base)
        game.tick(dt=0.016)

        # push(overlay) -> [base, overlay]; pop() -> [base].
        assert len(game._scene_stack._stack) == 1
        assert game._scene_stack.top() is base


# ==================================================================
# Scene stack re-entrancy — Advanced (Stage 2)
# ==================================================================


class TestSceneStackReentrancyAdvanced:
    """Advanced scene stack reentrancy: deeply nested chains, on_exit push,
    on_reveal push, on_enter replace/pop, triple chains, game tick deferral."""

    def test_deeply_nested_on_enter_chain(self) -> None:
        """A.on_enter pushes B, B.on_enter pushes C -> C on top."""
        log: list[str] = []
        fake_game = FakeGame()
        stack = SceneStack(cast(Game, fake_game))

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
        assert "A.on_enter" in log
        assert "B.on_enter" in log
        assert "C.on_enter" in log

    def test_on_exit_pushes_scene(self) -> None:
        """When A is popped, A.on_exit pushes D -> deferred. D materialises
        only after the pending ops are flushed (next tick or manual flush)."""
        log: list[str] = []
        fake_game = FakeGame()
        stack = SceneStack(cast(Game, fake_game))

        class SceneD(TrackingScene):
            pass

        class SceneA(TrackingScene):
            def on_exit(self) -> None:
                super().on_exit()
                stack.push(SceneD("D", self.log))

        a = SceneA("A", log)
        stack.push(a)
        stack.pop()

        assert "A.on_exit" in log
        assert len(stack._pending_ops) == 1

        stack.flush_pending_ops()
        assert stack.top() is not None
        assert stack.top().name == "D"  # type: ignore[union-attr]
        assert "D.on_enter" in log

    def test_on_exit_pushes_during_pop(self) -> None:
        """B.on_exit pushes X -> deferred; when flushed X is on top."""
        log: list[str] = []
        fake_game = FakeGame()
        stack = SceneStack(cast(Game, fake_game))

        class SceneB(TrackingScene):
            def on_exit(self) -> None:
                super().on_exit()
                stack.push(TrackingScene("X", self.log))

        a = TrackingScene("A", log)
        b = SceneB("B", log)

        stack.push(a)
        stack.push(b)

        stack.pop()

        assert "B.on_exit" in log
        assert "A.on_reveal" in log
        assert len(stack._pending_ops) == 1

        stack.flush_pending_ops()
        assert stack.top().name == "X"  # type: ignore[union-attr]
        assert "X.on_enter" in log

    def test_on_reveal_pushes_scene(self) -> None:
        """A.on_reveal pushes E -> deferred; E on top after flush."""
        log: list[str] = []
        fake_game = FakeGame()
        stack = SceneStack(cast(Game, fake_game))

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
        stack.pop()

        assert "A.on_reveal" in log
        assert len(stack._pending_ops) == 1

        stack.flush_pending_ops()
        assert "E.on_enter" in log
        assert stack.top().name == "E"  # type: ignore[union-attr]

    def test_on_enter_replaces_self(self) -> None:
        """A.on_enter replaces itself with R -> R ends up on top."""
        log: list[str] = []
        fake_game = FakeGame()
        stack = SceneStack(cast(Game, fake_game))

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

    def test_on_enter_pops_self(self) -> None:
        """B.on_enter pops -> stack returns to A, A gets on_reveal."""
        log: list[str] = []
        fake_game = FakeGame()
        stack = SceneStack(cast(Game, fake_game))

        class SceneB(TrackingScene):
            def on_enter(self) -> None:
                super().on_enter()
                stack.pop()

        a = TrackingScene("A", log)
        b = SceneB("B", log)

        stack.push(a)
        stack.push(b)

        assert stack.top().name == "A"  # type: ignore[union-attr]
        assert "B.on_enter" in log
        assert "B.on_exit" in log
        assert "A.on_reveal" in log

    def test_triple_chain_with_pop(self) -> None:
        """A->push B->push C->pop C: B ends up on top, B gets on_reveal."""
        log: list[str] = []
        fake_game = FakeGame()
        stack = SceneStack(cast(Game, fake_game))

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

        assert "C.on_enter" in log
        assert "C.on_exit" in log
        assert "B.on_reveal" in log
        assert stack.top().name == "B"  # type: ignore[union-attr]

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

        assert "Outer.on_enter" in log
        assert "Inner.on_enter" in log

    def test_nested_push_during_update(self, game: Game) -> None:
        """Scene.update() pushes new scene -> deferred until flush."""
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


# ==================================================================
# Sprite lifecycle
# ==================================================================


class TestSpriteLifecycleAdversarial:
    """Sprite behavior when actions mutate sprites during update_action."""

    def test_sprite_removed_in_do_callback(self, game: Game) -> None:
        """Do() callback that removes its own sprite — must not crash.
        Action completes; sprite is removed and deregistered."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        removed = []

        def remove_self() -> None:
            s.remove()
            removed.append(True)

        s.do(Do(remove_self))

        game.tick(dt=0.016)

        assert len(removed) == 1
        assert s.is_removed
        assert s not in game._action_sprites

    def test_sprite_do_during_own_update_action(self, game: Game) -> None:
        """sprite.do() called from within its own action's callback during
        update_action — must not crash. New action may or may not run
        depending on implementation."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        callback_called = []
        new_action_started = []

        def callback() -> None:
            callback_called.append(True)
            s.do(Do(lambda: new_action_started.append(True)))

        s.do(Sequence(Do(callback), Do(lambda: None)))

        game.tick(dt=0.016)

        assert len(callback_called) == 1
        # Framework must not crash. New action behavior is implementation-defined.
        assert not s.is_removed

    def test_sprite_do_on_other_sprite_during_update_action(
        self, game: Game
    ) -> None:
        """sprite_b.do() called from sprite_a's action callback — adds B to
        action set; iteration is over a copy so no mutation during iter.
        B's Do completes in one update but B is processed same frame."""
        game.push(Scene())
        a = Sprite("sprites/knight", position=(0, 0))
        b = Sprite("sprites/knight", position=(100, 100))

        def a_callback() -> None:
            b.do(Do(lambda: None))

        a.do(Do(a_callback))

        game.tick(dt=0.016)

        # A's action completes. B was added during A's update; iteration uses
        # a copy so B is not processed this frame (stays in _action_sprites).
        # No crash; both sprites intact.
        assert not a.is_removed
        assert not b.is_removed
        assert a not in game._action_sprites


# ==================================================================
# Action system — Deepcopy of closures / lambdas (Stage 2)
# ==================================================================


class TestActionDeepcopy:
    """Verify deepcopy works correctly for actions containing closures."""

    def test_deepcopy_do_with_lambda(self) -> None:
        """Do(lambda) can be deepcopied; each copy calls independently."""
        counter = [0]
        original = Do(lambda: counter.__setitem__(0, counter[0] + 1))
        cloned = copy.deepcopy(original)

        assert cloned is not original
        assert callable(cloned._fn)

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
        assert len(results) == 2


# ==================================================================
# Action system — Parallel with mix of instant and long-running (Stage 2)
# ==================================================================


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


# ==================================================================
# Action system — Sequence where child start() raises (Stage 2)
# ==================================================================


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
        """First child (Do) completes -> Sequence starts second child ->
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


# ==================================================================
# Action system — stop() called during update() (Stage 2)
# ==================================================================


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


# ==================================================================
# Timer chains
# ==================================================================


class TestTimerChainAdversarial:
    """Timer .then() chain edge cases."""

    def test_then_callback_cancels_parent_handle(self, game: Game) -> None:
        """Parent callback cancels its own handle — then-chain never runs."""
        order = []

        def parent_cb() -> None:
            order.append("parent")
            game.cancel(handle)

        def then_cb() -> None:
            order.append("then")

        handle = game.after(0.0, parent_cb)
        handle.then(then_cb, 0.0)

        game.tick(dt=0.016)
        game.tick(dt=0.016)

        assert order == ["parent"]
        assert "then" not in order

    def test_then_callback_throws_is_caught_and_removed(self, game: Game) -> None:
        """then() callback that raises is caught, logged, and the timer removed."""
        def parent_cb() -> None:
            pass

        def then_cb() -> None:
            raise ValueError("then callback failed")

        handle = game.after(0.0, parent_cb)
        handle.then(then_cb, 0.0)

        game.tick(dt=0.016)
        # The then-chain fires on the next tick.  The exception is caught
        # and logged, not propagated.
        game.tick(dt=0.016)  # should NOT raise
        # Timer should have been removed.
        assert len(game._timer_manager._timers) == 0


# ==================================================================
# Timer / Tween interaction (Stage 2)
# ==================================================================


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
        assert "nuke" in fired
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
        """Chain: timer -> creates tween -> tween on_complete creates timer."""
        final_fired: list[bool] = []

        def on_tween_done() -> None:
            game.after(0.05, lambda: final_fired.append(True))

        def on_timer() -> None:
            obj = type("O", (), {"v": 0.0})()
            tween(obj, "v", 0.0, 1.0, 0.1, on_complete=on_tween_done)

        game.after(0.05, on_timer)
        # 0.05s: timer fires -> creates tween
        game.tick(dt=0.05)
        # 0.1s: tween completes -> creates another timer
        game.tick(dt=0.1)
        # 0.05s: final timer fires
        game.tick(dt=0.05)
        assert final_fired == [True]


# ==================================================================
# Tweens
# ==================================================================


class TestTweenAdversarial:
    """Tween edge cases: duration=0, missing property, cancel_by_target,
    overlapping tweens on same property."""

    def test_tween_duration_zero_completes_immediately(
        self, game: Game
    ) -> None:
        """duration=0 completes on first update; sets to_val, fires on_complete."""
        obj = type("Obj", (), {"val": 0.0})()
        fired = []
        tween(obj, "val", 0.0, 100.0, 0.0, on_complete=lambda: fired.append(True))

        game.tick(dt=0.016)

        assert obj.val == 100.0
        assert len(fired) == 1

    def test_tween_property_does_not_exist_raises(self, game: Game) -> None:
        """Tweening a property that doesn't exist on target raises AttributeError at creation."""
        class Slotted:
            __slots__ = ("x",)
            def __init__(self) -> None:
                self.x = 0.0

        obj = Slotted()
        with pytest.raises(AttributeError, match="has no attribute 'y'"):
            tween(obj, "y", 0.0, 1.0, 0.5)

    def test_cancel_by_target_when_no_tweens_no_crash(
        self, game: Game
    ) -> None:
        """cancel_by_target() on object with no active tweens is a no-op."""
        obj = type("Obj", (), {"val": 0.0})()
        game._tween_manager.cancel_by_target(obj)  # should not raise

    def test_two_tweens_same_property_last_wins(self, game: Game) -> None:
        """Two tweens on same target+property: both run; last in iteration wins.
        Second tween (created later) overwrites first each frame."""
        obj = type("Obj", (), {"val": 0.0})()
        tween(obj, "val", 0.0, 100.0, 1.0)   # first: 0 -> 100
        tween(obj, "val", 0.0, 200.0, 1.0)   # second: 0 -> 200

        game.tick(dt=0.5)

        # Both run; second overwrites. At t=0.5: first would give 50, second 100.
        # Second runs last, so val should be 100.
        assert obj.val == 100.0


# ==================================================================
# Audio (Stage 1 — original)
# ==================================================================


@pytest.fixture
def game_with_audio(asset_dir_with_audio: Path) -> Game:
    """Game with mock backend and temp assets including sounds/music."""
    g = Game("Test", backend="mock", resolution=(800, 600))
    g.assets = AssetManager(g.backend, base_path=asset_dir_with_audio)
    return g


class TestAudioAdversarial:
    """Audio edge cases: unknown channel, unregistered pool, empty pool,
    optional missing asset, crossfade during crossfade."""

    def test_set_volume_unknown_channel_raises(
        self, game_with_audio: Game
    ) -> None:
        """set_volume with unknown channel raises KeyError."""
        with pytest.raises(KeyError, match="Unknown audio channel"):
            game_with_audio.audio.set_volume("nonexistent", 0.5)

    def test_get_volume_unknown_channel_raises(
        self, game_with_audio: Game
    ) -> None:
        """get_volume with unknown channel raises KeyError."""
        with pytest.raises(KeyError, match="Unknown audio channel"):
            game_with_audio.audio.get_volume("invalid")

    def test_play_pool_unregistered_raises(
        self, game_with_audio: Game
    ) -> None:
        """play_pool with unregistered pool raises KeyError."""
        with pytest.raises(KeyError):
            game_with_audio.audio.play_pool("never_registered")

    def test_play_pool_empty_pool_no_crash(
        self, game_with_audio: Game
    ) -> None:
        """play_pool with empty registered pool returns without playing."""
        game_with_audio.audio.register_pool("empty", [])
        game_with_audio.audio.play_pool("empty")  # should not raise

    def test_play_sound_optional_missing_asset_no_crash(
        self, game_with_audio: Game
    ) -> None:
        """play_sound with optional=True and missing asset returns None."""
        result = game_with_audio.audio.play_sound(
            "nonexistent_sound", optional=True
        )
        assert result is None

    def test_crossfade_during_crossfade_no_crash(
        self, game_with_audio: Game
    ) -> None:
        """crossfade_music during an active crossfade cancels previous, starts new."""
        game_with_audio.audio.play_music("exploration")
        game_with_audio.audio.crossfade_music("battle", duration=1.0)
        game_with_audio.audio.crossfade_music("exploration", duration=0.5)
        game_with_audio.tick(dt=0.016)
        # No crash; second crossfade replaced the first.


# ==================================================================
# Audio edge cases (Stage 2)
# ==================================================================


class TestAudioEdgeCases:
    """Audio system adversarial scenarios (Stage 2)."""

    @pytest.fixture
    def audio_game(self, tmp_path: Path) -> Game:
        """Game with audio assets configured."""
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


# ==================================================================
# Camera
# ==================================================================


class TestCameraAdversarial:
    """Camera edge cases: follow removed sprite, pan_to NaN/Inf,
    pan_to duration=0, world_bounds edge cases."""

    def test_follow_removed_sprite_no_crash(self, game: Game) -> None:
        """update() with follow target that was removed clears follow, no crash."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(100, 100))
        cam = Camera((800, 600))
        cam.follow(s)
        s.remove()
        cam.update(0.016)  # should not crash; clears _follow_target
        assert cam._follow_target is None

    def test_pan_to_nan_raises_value_error(self, game: Game) -> None:
        """pan_to with NaN coordinates raises ValueError."""
        cam = Camera((800, 600))
        with pytest.raises(ValueError, match="finite"):
            cam.pan_to(float("nan"), float("nan"), 0.5)

    def test_pan_to_duration_zero_instant(self, game: Game) -> None:
        """pan_to with duration=0 completes immediately."""
        cam = Camera((800, 600))
        cam.center_on(100, 100)
        cam.pan_to(500, 400, 0.0)
        game.tick(dt=0.016)
        # Target center (500, 400) -> top-left (100, 100)
        assert cam.x == 100.0
        assert cam.y == 100.0

    def test_world_bounds_inverted_no_crash(self, game: Game) -> None:
        """World bounds with left > right — _clamp may produce odd values.
        Framework must not crash."""
        cam = Camera((800, 600), world_bounds=(1000, 0, 500, 1000))
        cam.center_on(750, 500)
        assert cam.x == 1000.0


# ==================================================================
# Camera edge cases (Stage 2)
# ==================================================================


class TestCameraEdgeCases:
    """Camera adversarial scenarios (Stage 2)."""

    def test_shake_with_negative_intensity(self) -> None:
        """shake() with negative intensity — random.uniform handles swapped bounds."""
        cam = Camera((800, 600))
        cam.shake(intensity=-5.0, duration=0.5, decay=1.0)

        cam.update(dt=0.1)
        assert -5.0 <= cam.shake_offset_x <= 5.0
        assert -5.0 <= cam.shake_offset_y <= 5.0

    def test_shake_zero_duration_resets(self) -> None:
        """shake(duration=0) resets any active shake immediately."""
        cam = Camera((800, 600))
        cam.shake(intensity=10.0, duration=1.0, decay=1.0)
        cam.update(dt=0.1)
        assert cam._shake_duration == 1.0

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

        cam.pan_to(1000, 1000, duration=2.0)
        first_x_tween = cam._pan_tween_x
        first_y_tween = cam._pan_tween_y
        assert first_x_tween is not None
        assert first_y_tween is not None

        game.tick(dt=0.5)

        cam.pan_to(500, 500, duration=1.0)
        assert cam._pan_tween_x is not None
        assert cam._pan_tween_x != first_x_tween  # New tween
        assert cam._pan_tween_y != first_y_tween

        assert first_x_tween not in game._tween_manager._tweens
        assert first_y_tween not in game._tween_manager._tweens

        game.tick(dt=1.0)
        expected_x = 500 - 400
        expected_y = 500 - 300
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
        assert abs(cam._x - (200 - 400)) < 1
        assert abs(cam._y - (200 - 300)) < 1

    def test_edge_scroll_at_exact_corner_top_left(self) -> None:
        """Mouse at (0, 0) — top-left corner — both axes should scroll."""
        cam = Camera(
            (800, 600),
            world_bounds=(0, 0, 4000, 3000),
        )
        cam.center_on(2000, 1500)
        cam.enable_edge_scroll(margin=50, speed=200)

        initial_x = cam._x
        initial_y = cam._y

        cam.update(dt=0.1, mouse_x=0, mouse_y=0)

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

        cam.update(dt=0.1, mouse_x=800, mouse_y=600)

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

        assert abs((initial_x - cam._x) - 100) < 1
        assert abs((initial_y - cam._y) - 100) < 1

    def test_edge_scroll_clamped_to_world_bounds(self) -> None:
        """Edge scroll respects world bounds and doesn't go beyond."""
        cam = Camera(
            (800, 600),
            world_bounds=(0, 0, 800, 600),
        )
        cam.center_on(400, 300)
        cam.enable_edge_scroll(margin=50, speed=200)

        cam.update(dt=1.0, mouse_x=0, mouse_y=0)

        assert cam._x == 0.0
        assert cam._y == 0.0


# ==================================================================
# UI Component
# ==================================================================


class TestUIComponentAdversarial:
    """UI Component edge cases: add self, add None, remove non-child,
    compute_layout zero bounds, draggable with _game=None."""

    def test_add_self_as_child_raises_value_error(self, game: Game) -> None:
        """add(self) raises ValueError to prevent cycle."""
        game.push(Scene())
        root = game._scene_stack.top().ui  # type: ignore[union-attr]
        panel = Component(width=100, height=100)
        root.add(panel)
        with pytest.raises(ValueError, match="Cannot add component to itself"):
            panel.add(panel)

    def test_negative_dimensions_raise_value_error(self) -> None:
        """Component with negative width/height/margin raises ValueError."""
        with pytest.raises(ValueError, match="width cannot be negative"):
            Component(width=-10, height=50)
        with pytest.raises(ValueError, match="height cannot be negative"):
            Component(width=50, height=-10)
        with pytest.raises(ValueError, match="margin cannot be negative"):
            Component(width=50, height=50, margin=-5)

    def test_remove_non_child_no_crash(self, game: Game) -> None:
        """remove(child) when child is not in _children is a no-op."""
        game.push(Scene())
        root = game._scene_stack.top().ui  # type: ignore[union-attr]
        a = Component(width=50, height=50)
        b = Component(width=50, height=50)
        root.add(a)
        root.remove(b)  # b was never added
        assert a in root._children

    def test_compute_layout_zero_bounds_no_crash(self, game: Game) -> None:
        """compute_layout(0,0,0,0) with zero-sized parent — no crash."""
        comp = Component(width=100, height=100, anchor=Anchor.CENTER)
        comp.compute_layout(0, 0, 0, 0)
        assert comp._layout_dirty is False

    def test_handle_event_draggable_no_game_skips_drag(
        self, game: Game
    ) -> None:
        """Draggable component with _game=None does not crash on click."""
        comp = Component(width=100, height=100, draggable=True)
        comp._game = None
        comp._computed_x = 50
        comp._computed_y = 50
        comp._computed_w = 100
        comp._computed_h = 100
        evt = InputEvent(type="click", x=100, y=100, button="left")
        result = comp.handle_event(evt)
        # No crash; drag not started (no _game), falls through to on_event.
        assert result is False


# ==================================================================
# UI Component tree (Stage 2)
# ==================================================================


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

        tooltip.show(50, 20)
        assert tooltip._showing is True
        assert tooltip._visible_now is False

        tooltip.update(0.4)
        assert tooltip._visible_now is True

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
        for i in range(1, len(panel._children)):
            assert (
                panel._children[i]._computed_y
                >= panel._children[i - 1]._computed_y
            )


# ==================================================================
# Save system (Stage 2)
# ==================================================================


class TestSaveSystemEdgeCases:
    """Save system with deeply nested state, unicode keys, slot validation."""

    @pytest.fixture
    def save_mgr(self, tmp_path: Path) -> SaveManager:
        return SaveManager(tmp_path / "saves")

    def test_save_deeply_nested_state_100_levels(
        self, save_mgr: SaveManager,
    ) -> None:
        """Save state nested 100 levels deep — JSON handles it fine."""
        state: dict[str, Any] = {"leaf": True}
        for i in range(100):
            state = {"level": i, "child": state}

        save_mgr.save(1, state, "DeepScene")
        loaded = save_mgr.load(1)
        assert loaded is not None

        inner = loaded["state"]
        for i in range(100):
            assert inner["level"] == 99 - i
            inner = inner["child"]
        assert inner["leaf"] is True

    def test_save_with_unicode_keys(self, save_mgr: SaveManager) -> None:
        """Unicode keys and values survive round-trip."""
        state = {
            "\u540d\u524d": "\u52c7\u8005",
            "\u30ec\u30d9\u30eb": 42,
            "emoji_key_\U0001f5e1\ufe0f": "sword",
            "nested": {"cl\u00e9": "valeur", "Schl\u00fcssel": "Wert"},
        }
        save_mgr.save(1, state, "UnicodeScene")
        loaded = save_mgr.load(1)
        assert loaded is not None
        assert loaded["state"]["\u540d\u524d"] == "\u52c7\u8005"
        assert loaded["state"]["\u30ec\u30d9\u30eb"] == 42
        assert loaded["state"]["emoji_key_\U0001f5e1\ufe0f"] == "sword"
        assert loaded["state"]["nested"]["cl\u00e9"] == "valeur"

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


# ==================================================================
# FSM
# ==================================================================


class TestFSMAdversarial:
    """FSM edge cases: trigger unknown event, on_exit triggers event,
    on_enter raises, empty states."""

    def test_trigger_unknown_event_returns_false(self) -> None:
        """trigger(event) with no transition for event returns False."""
        fsm = StateMachine(
            states=["idle", "walking"],
            initial="idle",
            transitions={"idle": {"move": "walking"}},
        )
        assert fsm.trigger("attack") is False
        assert fsm.state == "idle"

    def test_on_exit_triggers_event_reentrancy(self) -> None:
        """on_exit callback that calls trigger() — re-entrancy; must not crash.
        Inner trigger uses event with no transition from current state."""
        order = []

        def exit_walking() -> None:
            order.append("exit_walking")
            fsm.trigger("move")  # no transition from walking; returns False

        fsm = StateMachine(
            states=["idle", "walking"],
            initial="walking",
            transitions={
                "idle": {"move": "walking"},
                "walking": {"arrive": "idle"},
            },
            on_exit={"walking": exit_walking},
            on_enter={"idle": lambda: order.append("enter_idle")},
        )
        fsm.trigger("arrive")
        assert fsm.state == "idle"
        assert "exit_walking" in order

    def test_on_enter_raises_propagates(self) -> None:
        """on_enter callback that raises propagates the exception."""
        def raise_boom() -> None:
            raise ValueError("boom")

        fsm = StateMachine(
            states=["idle", "walking"],
            initial="idle",
            transitions={"idle": {"move": "walking"}},
            on_enter={"walking": raise_boom},
        )
        with pytest.raises(ValueError, match="boom"):
            fsm.trigger("move")

    def test_empty_states_raises(self) -> None:
        """Initial state not in empty states raises ValueError."""
        with pytest.raises(ValueError, match="Initial state 'idle' not in states"):
            StateMachine(states=[], initial="idle")
