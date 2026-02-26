"""Adversarial tests for scene stack re-entrancy and sprite lifecycle.

Tests framework behavior when callbacks trigger stack ops or sprite mutations
during sensitive phases. All tests use MockBackend (headless).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from easygame import Camera, Do, Game, Scene, Sequence, Sprite, tween
from easygame.assets import AssetManager
from easygame.backends.mock_backend import MockBackend
from easygame.input import InputEvent
from easygame.ui import Anchor, Component
from easygame.util.fsm import StateMachine


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


# ==================================================================
# Scene stack re-entrancy
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

        # replace(replacement) then pop() → top becomes replacement, then
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

        # push(overlay) → [base, overlay]; pop() → [base].
        assert len(game._scene_stack._stack) == 1
        assert game._scene_stack.top() is base


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
# Audio
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
        # Target center (500, 400) → top-left (100, 100)
        assert cam.x == 100.0
        assert cam.y == 100.0

    def test_world_bounds_inverted_no_crash(self, game: Game) -> None:
        """World bounds with left > right — _clamp may produce odd values.
        Framework must not crash."""
        cam = Camera((800, 600), world_bounds=(1000, 0, 500, 1000))
        cam.center_on(750, 500)
        # max_x = 500 - 800 = -300; max(left, min(x, max_x)) = max(1000, min(x, -300))
        # For any x, min(x, -300) <= -300, so max(1000, -300) = 1000.
        # _x gets clamped to 1000. No crash.
        assert cam.x == 1000.0


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
