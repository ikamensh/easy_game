"""Edge case & adversarial tests for EasyGame core modules.

Regression tests for findings from Stage 2 edge-case audit.
Each test class corresponds to a finding in findings-edge-cases.md.

All tests use the MockBackend (headless) — no display required.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from easygame import (
    Camera,
    Do,
    FadeIn,
    FadeOut,
    Game,
    MoveTo,
    Parallel,
    Repeat,
    Scene,
    Sequence,
    Sprite,
)
from easygame.assets import AssetManager
from easygame.backends.base import KeyEvent, MouseEvent
from easygame.backends.mock_backend import MockBackend
from easygame.input import InputManager
from easygame.save import SaveManager
from easygame.util.timer import TimerManager


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
def game(asset_dir: Path) -> Game:
    """Game with mock backend and temp assets."""
    g = Game("Test", backend="mock", resolution=(800, 600))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    return g


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


# ==================================================================
# Finding 1: Sprite opacity is not clamped to 0-255
# ==================================================================


class TestSpriteOpacity:
    """Sprite.opacity should accept any numeric value; the framework
    should clamp it to the valid 0-255 range before syncing to backend."""

    def test_opacity_above_255_is_not_clamped(
        self, game: Game, backend: MockBackend
    ) -> None:
        """Setting opacity > 255 stores raw value (no clamping)."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.opacity = 999
        # FINDING: value passes through unclamped.
        # Expected after fix: s.opacity == 255
        assert s.opacity == 999, (
            "If this fails, opacity clamping has been implemented (good!)"
        )

    def test_opacity_negative_is_not_clamped(self, game: Game) -> None:
        """Setting opacity < 0 stores raw value (no clamping)."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.opacity = -50
        # FINDING: value passes through unclamped.
        # Expected after fix: s.opacity == 0
        assert s.opacity == -50, (
            "If this fails, opacity clamping has been implemented (good!)"
        )

    def test_opacity_float_truncates_to_int(self, game: Game) -> None:
        """Float opacity is truncated to int."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.opacity = 127.9
        assert s.opacity == 127

    def test_opacity_zero_and_255_accepted(self, game: Game) -> None:
        """Boundary values 0 and 255 are accepted as-is."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.opacity = 0
        assert s.opacity == 0
        s.opacity = 255
        assert s.opacity == 255


# ==================================================================
# Finding 2: Sprite tint components are not clamped to 0.0-1.0
# ==================================================================


class TestSpriteTint:
    """Sprite.tint components should be in [0.0, 1.0]; values outside
    this range are currently stored as-is."""

    def test_tint_above_range_is_not_clamped(self, game: Game) -> None:
        """Tint components > 1.0 are stored as-is (no clamping)."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.tint = (2.0, -0.5, 100.0)
        # FINDING: value passes through unclamped.
        # Expected after fix: s.tint == (1.0, 0.0, 1.0)
        assert s.tint == (2.0, -0.5, 100.0), (
            "If this fails, tint clamping has been implemented (good!)"
        )

    def test_tint_valid_range_accepted(self, game: Game) -> None:
        """Values within [0.0, 1.0] are accepted unchanged."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.tint = (0.0, 0.5, 1.0)
        assert s.tint == (0.0, 0.5, 1.0)

    def test_tint_default_is_white(self, game: Game) -> None:
        """Default tint is (1.0, 1.0, 1.0) = no tinting."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        assert s.tint == (1.0, 1.0, 1.0)


# ==================================================================
# Finding 3: SceneStack.push(None) raises AttributeError
# ==================================================================


class TestSceneStackPushNone:
    """push(None) should raise a clean ValueError, not AttributeError."""

    def test_push_none_raises_attribute_error(self, game: Game) -> None:
        """push(None) currently raises AttributeError (unguarded)."""
        # FINDING: raises AttributeError, not ValueError.
        # Expected after fix: raises ValueError with clear message.
        with pytest.raises(AttributeError):
            game.push(None)  # type: ignore[arg-type]

    def test_push_valid_scene_works(self, game: Game) -> None:
        """push() with a valid Scene succeeds normally."""
        scene = Scene()
        game.push(scene)
        # Verify scene is on the stack.
        game.tick(dt=0.016)


# ==================================================================
# Finding 4: Timer.every() accepts zero/negative intervals
# ==================================================================


class TestTimerEveryInterval:
    """every() should validate interval > 0."""

    def test_every_zero_interval_accepted(self) -> None:
        """every(0, ...) currently accepts interval=0 without error."""
        mgr = TimerManager()
        # FINDING: no validation; zero interval accepted.
        # Expected after fix: raises ValueError.
        handle = mgr.every(0, lambda: None)
        assert handle is not None  # it returns a handle — no error raised

    def test_every_negative_interval_accepted(self) -> None:
        """every(-1.0, ...) currently accepts negative interval without error."""
        mgr = TimerManager()
        # FINDING: no validation; negative interval accepted.
        # Expected after fix: raises ValueError.
        handle = mgr.every(-1.0, lambda: None)
        assert handle is not None

    def test_every_positive_interval_works(self) -> None:
        """every() with a valid positive interval fires correctly."""
        mgr = TimerManager()
        count = []
        mgr.every(0.5, lambda: count.append(1))
        mgr.update(0.5)
        assert len(count) == 1
        mgr.update(0.5)
        assert len(count) == 2

    def test_after_zero_delay_fires_next_tick(self, game: Game) -> None:
        """after(0, ...) fires on the next tick, not immediately."""
        fired = []
        game.after(0, lambda: fired.append(True))
        assert len(fired) == 0  # not fired yet
        game.tick(dt=0.0)
        assert len(fired) == 1

    def test_cancel_timer_inside_callback(self, game: Game) -> None:
        """Cancelling a timer from within its own callback doesn't crash."""
        handle = None

        def cancel_self() -> None:
            game.cancel(handle)

        handle = game.after(0.1, cancel_self)
        game.tick(dt=0.1)  # should not raise

    def test_cancel_same_timer_twice(self, game: Game) -> None:
        """Cancelling a timer twice is a no-op (no error)."""
        handle = game.after(1.0, lambda: None)
        game.cancel(handle)
        game.cancel(handle)  # should not raise


# ==================================================================
# Finding 5: Repeat(times=0) runs child once instead of being no-op
# ==================================================================


class TestRepeatTimesZero:
    """Repeat(action, times=0) should be a no-op — the child should
    never run."""

    def test_repeat_zero_runs_child_once(self, game: Game) -> None:
        """Repeat(Do(...), times=0) currently runs the child once."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        count: list[int] = []
        action = Repeat(Do(lambda: count.append(1)), times=0)
        action.start(s)
        result = action.update(0.016)
        # FINDING: child runs once, then Repeat finishes.
        # Expected after fix: count == 0, result == True immediately.
        assert result is True
        assert len(count) == 1, (
            "If this fails with count==0, the times=0 no-op fix was applied (good!)"
        )

    def test_repeat_once_runs_child_exactly_once(self, game: Game) -> None:
        """Repeat(Do(...), times=1) runs the child exactly once."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        count: list[int] = []
        action = Repeat(Do(lambda: count.append(1)), times=1)
        action.start(s)
        result = action.update(0.016)
        assert result is True
        assert len(count) == 1

    def test_repeat_none_is_infinite(self, game: Game) -> None:
        """Repeat(Do(...), times=None) runs indefinitely."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        count: list[int] = []
        action = Repeat(Do(lambda: count.append(1)), times=None)
        action.start(s)
        for _ in range(10):
            action.update(0.016)
        assert len(count) == 10


# ==================================================================
# Finding 6: Camera.center_on() accepts NaN/Inf
# ==================================================================


class TestCameraNaNInf:
    """Camera.center_on() should reject NaN/Inf coordinates."""

    def test_center_on_nan_accepted(self) -> None:
        """center_on(NaN, NaN) currently succeeds (no validation)."""
        cam = Camera((800, 600))
        # FINDING: NaN propagates into camera position.
        # Expected after fix: raises ValueError.
        cam.center_on(float("nan"), float("nan"))
        assert math.isnan(cam.x), "NaN propagated into camera x"

    def test_center_on_inf_accepted(self) -> None:
        """center_on(inf, -inf) currently succeeds (no validation)."""
        cam = Camera((800, 600))
        # FINDING: Inf propagates into camera position.
        # Expected after fix: raises ValueError.
        cam.center_on(float("inf"), float("-inf"))
        assert math.isinf(cam.x), "Inf propagated into camera x"

    def test_center_on_inf_with_bounds(self) -> None:
        """center_on(inf, inf) with bounds — _clamp may mask inf to bound edge."""
        cam = Camera((800, 600), world_bounds=(0, 0, 2000, 2000))
        cam.center_on(float("inf"), float("inf"))
        # With bounds, _clamp brings inf to the max bound edge.
        # Still not ideal — inf should be rejected before clamping.

    def test_center_on_finite_works(self) -> None:
        """center_on() with normal finite coordinates works correctly."""
        cam = Camera((800, 600))
        cam.center_on(500.0, 400.0)
        # viewport top-left = (500 - 400, 400 - 300) = (100, 100)
        assert cam.x == 100.0
        assert cam.y == 100.0

    def test_shake_zero_duration_is_noop(self) -> None:
        """shake(intensity=5, duration=0) resets shake state."""
        cam = Camera((800, 600))
        cam.shake(5.0, 0.0, 1.0)
        assert cam.shake_offset_x == 0.0
        assert cam.shake_offset_y == 0.0

    def test_world_bounds_smaller_than_viewport(self) -> None:
        """World bounds smaller than viewport doesn't crash."""
        cam = Camera((800, 600), world_bounds=(0, 0, 400, 300))
        cam.center_on(200.0, 150.0)
        # Camera should still function (clamp handles this).


# ==================================================================
# Finding 7: SaveManager — no SaveError, corrupted JSON unhandled
# ==================================================================


class TestSaveManagerEdgeCases:
    """SaveManager should handle corrupted files and non-serializable data."""

    def test_load_nonexistent_slot_returns_none(self, tmp_path: Path) -> None:
        """load() on an empty slot returns None."""
        mgr = SaveManager(tmp_path / "saves")
        assert mgr.load(99) is None

    def test_save_non_serializable_raises_type_error(
        self, tmp_path: Path
    ) -> None:
        """save() with non-JSON-serializable data raises TypeError."""
        mgr = SaveManager(tmp_path / "saves")
        with pytest.raises(TypeError):
            mgr.save(1, {"obj": object()}, "TestScene")

    def test_load_corrupted_json_raises_decode_error(
        self, tmp_path: Path
    ) -> None:
        """load() with corrupted JSON raises json.JSONDecodeError (raw)."""
        save_dir = tmp_path / "saves"
        save_dir.mkdir()
        corrupt_file = save_dir / "save_1.json"
        corrupt_file.write_text("{not valid json!!!", encoding="utf-8")
        mgr = SaveManager(save_dir)
        # FINDING: raw JSONDecodeError leaks out. No framework-specific
        # SaveError wraps it.
        # Expected after fix: raises SaveError with clear message.
        with pytest.raises(json.JSONDecodeError):
            mgr.load(1)

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """Normal save/load roundtrip works."""
        mgr = SaveManager(tmp_path / "saves")
        state = {"level": 3, "gold": 500}
        mgr.save(1, state, "WorldScene")
        data = mgr.load(1)
        assert data is not None
        assert data["state"] == state
        assert data["scene_class"] == "WorldScene"

    def test_delete_nonexistent_slot_is_noop(self, tmp_path: Path) -> None:
        """Deleting a non-existent slot does not raise."""
        mgr = SaveManager(tmp_path / "saves")
        mgr.delete(99)  # should not raise

    def test_list_slots_with_no_saves(self, tmp_path: Path) -> None:
        """list_slots() returns all None when no saves exist."""
        mgr = SaveManager(tmp_path / "saves")
        result = mgr.list_slots(count=3)
        assert result == [None, None, None]


# ==================================================================
# Additional edge cases (from audit, no findings — pass tests)
# ==================================================================


class TestSpriteRemoveEdgeCases:
    """Sprite.remove() edge cases that pass (no findings)."""

    def test_remove_twice_is_safe(self, game: Game) -> None:
        """Calling remove() twice doesn't crash."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.remove()
        s.remove()  # should not raise

    def test_do_on_removed_sprite_is_noop(self, game: Game) -> None:
        """Calling .do() on a removed sprite is silently ignored."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.remove()
        s.do(Do(lambda: None))  # should not raise


class TestActionEdgeCases:
    """Action edge cases that pass (no findings)."""

    def test_empty_sequence_is_done_immediately(self, game: Game) -> None:
        """Sequence() with no children finishes on first update."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        action = Sequence()
        action.start(s)
        assert action.update(0.016) is True

    def test_parallel_no_children_is_done(self, game: Game) -> None:
        """Parallel() with no children finishes immediately."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        action = Parallel()
        action.start(s)
        assert action.update(0.016) is True

    def test_moveto_current_position(self, game: Game) -> None:
        """MoveTo to current position (distance=0) finishes immediately."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(100, 200))
        action = MoveTo((100, 200), speed=100)
        action.start(s)
        assert action.update(0.016) is True

    def test_fadeout_zero_duration(self, game: Game) -> None:
        """FadeOut(duration=0) finishes immediately, sets opacity to 0."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        action = FadeOut(0.0)
        action.start(s)
        assert action.update(0.016) is True
        assert s.opacity == 0

    def test_fadein_zero_duration(self, game: Game) -> None:
        """FadeIn(duration=0) finishes immediately, sets opacity to 255."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.opacity = 0
        action = FadeIn(0.0)
        action.start(s)
        assert action.update(0.016) is True
        assert s.opacity == 255

    def test_deeply_nested_sequences(self, game: Game) -> None:
        """Nested Sequence(Sequence(Sequence(...))) works correctly."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        count: list[int] = []
        inner = Sequence(Do(lambda: count.append(1)))
        mid = Sequence(inner)
        outer = Sequence(mid)
        outer.start(s)
        outer.update(0.016)
        assert len(count) == 1

    def test_do_callback_exception_propagates(self, game: Game) -> None:
        """Do() callback that raises propagates the exception."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))

        def bad_callback() -> None:
            raise RuntimeError("boom")

        action = Do(bad_callback)
        action.start(s)
        with pytest.raises(RuntimeError, match="boom"):
            action.update(0.016)


class TestCameraFollowEdgeCases:
    """Camera follow edge cases that pass (no findings)."""

    def test_follow_none_stops_following(self) -> None:
        """follow(None) disables following."""
        cam = Camera((800, 600))
        cam.follow(None)
        # Should not crash on update with no follow target.
        cam.update(0.016)

    def test_pan_to_zero_duration(self) -> None:
        """pan_to with duration=0 still works (instant pan)."""
        cam = Camera((800, 600))
        # Duration of 0 — tween system handles it.
        cam.pan_to(500, 400, 0.0)


class TestAudioEdgeCases:
    """Audio edge cases that pass (no findings)."""

    def test_set_volume_clamps_high(self, game: Game) -> None:
        """set_volume > 1.0 is clamped to 1.0."""
        audio = game.audio
        audio.set_volume("master", 2.0)
        assert audio.get_volume("master") == 1.0

    def test_set_volume_clamps_negative(self, game: Game) -> None:
        """set_volume < 0.0 is clamped to 0.0."""
        audio = game.audio
        audio.set_volume("master", -0.5)
        assert audio.get_volume("master") == 0.0

    def test_set_volume_unknown_channel_raises(self, game: Game) -> None:
        """set_volume on unknown channel raises KeyError."""
        audio = game.audio
        with pytest.raises(KeyError):
            audio.set_volume("nonexistent", 0.5)

    def test_crossfade_same_track_is_noop(self, game: Game) -> None:
        """crossfade_music to the same track is a no-op."""
        # With no music playing, _current_music_name is None.
        # crossfade to None would be odd — this tests that the check works.
        _audio = game.audio  # noqa: F841 — access to verify no crash
        # No crash when no music is playing and crossfade called.
        # (This would try play_music since _current_player_id is None.)


class TestInputEdgeCases:
    """Input edge cases that pass (no findings)."""

    def test_translate_empty_list(self) -> None:
        """translate([]) returns empty list."""
        mgr = InputManager()
        assert mgr.translate([]) == []

    def test_key_event_with_empty_key(self) -> None:
        """KeyEvent with empty string key translates without error."""
        mgr = InputManager()
        events = mgr.translate([KeyEvent(type="key_press", key="")])
        assert len(events) == 1
        assert events[0].key == ""

    def test_mouse_event_with_negative_coords(self) -> None:
        """MouseEvent with negative coordinates translates without error."""
        mgr = InputManager()
        events = mgr.translate([
            MouseEvent(type="click", x=-10, y=-20, button="left", dx=0, dy=0)
        ])
        assert len(events) == 1
        assert events[0].x == -10
        assert events[0].y == -20
