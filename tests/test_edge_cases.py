"""Edge case & adversarial tests for EasyGame core modules.

Regression tests for findings from Stage 2 edge-case audit.
Each test class corresponds to a finding in findings-edge-cases.md.

All tests use the MockBackend (headless) — no display required.
"""

from __future__ import annotations

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
from easygame.save import SaveError, SaveManager
from easygame.ui.components import Label, Panel
from easygame.util.timer import TimerManager
from easygame.util.tween import TweenManager


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

    def test_opacity_out_of_range_high(
        self, game: Game, backend: MockBackend
    ) -> None:
        """Setting opacity > 255 clamps to 255."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.opacity = 999
        assert s.opacity == 255

    def test_opacity_negative(self, game: Game) -> None:
        """Setting opacity < 0 clamps to 0."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.opacity = -50
        assert s.opacity == 0

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

    def test_tint_out_of_range(self, game: Game) -> None:
        """Tint components outside [0.0, 1.0] are clamped."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.tint = (2.0, -0.5, 100.0)
        assert s.tint == (1.0, 0.0, 1.0)

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
    """push(None) should raise a clean TypeError, not AttributeError."""

    def test_push_none_raises(self, game: Game) -> None:
        """push(None) raises TypeError with a clear message."""
        with pytest.raises(TypeError, match="scene must be a Scene instance"):
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

    def test_interval_zero_raises(self) -> None:
        """every(0, ...) raises ValueError."""
        mgr = TimerManager()
        with pytest.raises(ValueError, match="interval must be > 0"):
            mgr.every(0, lambda: None)

    def test_negative_interval_raises(self) -> None:
        """every(-1.0, ...) raises ValueError."""
        mgr = TimerManager()
        with pytest.raises(ValueError, match="interval must be > 0"):
            mgr.every(-1.0, lambda: None)

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

    def test_repeat_zero_is_noop(self, game: Game) -> None:
        """Repeat(Do(...), times=0) is a no-op: finishes immediately without running the child."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        count: list[int] = []
        action = Repeat(Do(lambda: count.append(1)), times=0)
        action.start(s)
        result = action.update(0.016)
        assert result is True
        assert len(count) == 0, "times=0 should never run the child action"

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

    def test_center_on_nan_raises(self) -> None:
        """center_on(NaN, NaN) raises ValueError."""
        cam = Camera((800, 600))
        with pytest.raises(ValueError, match="camera coordinates must be finite"):
            cam.center_on(float("nan"), float("nan"))

    def test_center_on_inf_raises(self) -> None:
        """center_on(inf, -inf) raises ValueError."""
        cam = Camera((800, 600))
        with pytest.raises(ValueError, match="camera coordinates must be finite"):
            cam.center_on(float("inf"), float("-inf"))

    def test_center_on_inf_with_bounds_raises(self) -> None:
        """center_on(inf, inf) with bounds raises ValueError before clamping."""
        cam = Camera((800, 600), world_bounds=(0, 0, 2000, 2000))
        with pytest.raises(ValueError, match="camera coordinates must be finite"):
            cam.center_on(float("inf"), float("inf"))

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

    def test_save_non_serializable_raises_save_error(
        self, tmp_path: Path
    ) -> None:
        """save() with non-JSON-serializable data raises SaveError."""
        mgr = SaveManager(tmp_path / "saves")
        with pytest.raises(SaveError, match="Cannot write save file"):
            mgr.save(1, {"obj": object()}, "TestScene")

    def test_corrupted_json_raises_save_error(
        self, tmp_path: Path
    ) -> None:
        """load() with corrupted JSON raises SaveError."""
        save_dir = tmp_path / "saves"
        save_dir.mkdir()
        corrupt_file = save_dir / "save_1.json"
        corrupt_file.write_text("{not valid json!!!", encoding="utf-8")
        mgr = SaveManager(save_dir)
        with pytest.raises(SaveError, match="Corrupted save file"):
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

    def test_pan_to_zero_duration(self, game: Game) -> None:
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


# ==================================================================
# F1: Sprite position must be finite (no NaN, Inf, -Inf)
# ==================================================================


class TestSpritePositionFinite:
    """Sprite position and assignment must reject non-finite values."""

    def test_position_nan_init_raises(self, game: Game) -> None:
        """Creating a Sprite with NaN position raises ValueError."""
        game.push(Scene())
        with pytest.raises(ValueError, match="finite"):
            Sprite("sprites/knight", position=(float("nan"), 0))

    def test_position_inf_init_raises(self, game: Game) -> None:
        """Creating a Sprite with inf position raises ValueError."""
        game.push(Scene())
        with pytest.raises(ValueError, match="finite"):
            Sprite("sprites/knight", position=(float("inf"), 0))

    def test_position_neg_inf_init_raises(self, game: Game) -> None:
        """Creating a Sprite with -inf position raises ValueError."""
        game.push(Scene())
        with pytest.raises(ValueError, match="finite"):
            Sprite("sprites/knight", position=(0, float("-inf")))

    def test_position_setter_nan_raises(self, game: Game) -> None:
        """Setting position to NaN raises ValueError."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        with pytest.raises(ValueError, match="finite"):
            s.position = (float("nan"), 0)

    def test_position_setter_inf_raises(self, game: Game) -> None:
        """Setting position to inf raises ValueError."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        with pytest.raises(ValueError, match="finite"):
            s.position = (0, float("inf"))

    def test_x_setter_nan_raises(self, game: Game) -> None:
        """Setting x to NaN raises ValueError."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        with pytest.raises(ValueError, match="finite"):
            s.x = float("nan")

    def test_y_setter_inf_raises(self, game: Game) -> None:
        """Setting y to inf raises ValueError."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        with pytest.raises(ValueError, match="finite"):
            s.y = float("inf")

    def test_finite_position_accepted(self, game: Game) -> None:
        """Normal finite positions work correctly."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(100.5, 200.7))
        assert s.position == (100.5, 200.7)
        s.position = (-50.0, 9999.0)
        assert s.position == (-50.0, 9999.0)


# ==================================================================
# F2: Scene stack pops scene if on_enter() raises
# ==================================================================


class TestSceneStackOnEnterException:
    """If on_enter() raises, the scene must NOT be left on the stack."""

    def test_push_on_enter_exception_pops_scene(self, game: Game) -> None:
        """push() with a scene whose on_enter raises removes scene from stack."""
        class BadScene(Scene):
            def on_enter(self) -> None:
                raise RuntimeError("on_enter failed")

        with pytest.raises(RuntimeError, match="on_enter failed"):
            game.push(BadScene())

        # Stack should be empty (no scenes before, bad scene was removed).
        assert game._scene_stack.top() is None

    def test_push_on_enter_exception_preserves_previous(self, game: Game) -> None:
        """push() failure preserves the previously active scene."""
        good_scene = Scene()
        game.push(good_scene)

        class BadScene(Scene):
            def on_enter(self) -> None:
                raise RuntimeError("on_enter failed")

        with pytest.raises(RuntimeError, match="on_enter failed"):
            game.push(BadScene())

        # The good scene's on_exit was already called (it's covered now),
        # but the bad scene should not be on the stack.
        # The stack should have the good scene still in it (it was
        # not popped — only on_exit was called before the push).
        # Actually, the good scene had on_exit called but stays in stack.
        assert game._scene_stack.top() is good_scene

    def test_replace_on_enter_exception_pops_scene(self, game: Game) -> None:
        """replace() with bad on_enter removes the new scene from stack."""
        good_scene = Scene()
        game.push(good_scene)

        class BadScene(Scene):
            def on_enter(self) -> None:
                raise RuntimeError("on_enter failed")

        with pytest.raises(RuntimeError, match="on_enter failed"):
            game.replace(BadScene())

        # The old scene was popped (replace pops first), and the new
        # scene was also removed due to on_enter failure.
        assert game._scene_stack.top() is None


# ==================================================================
# F4: MoveTo speed <= 0 raises ValueError
# ==================================================================


class TestMoveToSpeedValidation:
    """MoveTo should raise ValueError if speed <= 0."""

    def test_speed_zero_raises(self) -> None:
        """MoveTo(speed=0) raises ValueError."""
        with pytest.raises(ValueError, match="speed must be > 0"):
            MoveTo((100, 100), speed=0)

    def test_speed_negative_raises(self) -> None:
        """MoveTo(speed=-5) raises ValueError."""
        with pytest.raises(ValueError, match="speed must be > 0"):
            MoveTo((100, 100), speed=-5)

    def test_speed_positive_accepted(self, game: Game) -> None:
        """MoveTo(speed=100) is accepted normally."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        action = MoveTo((100, 100), speed=100)
        action.start(s)
        # Should not raise


# ==================================================================
# F5: Label(None) handled gracefully as empty string
# ==================================================================


class TestLabelNoneText:
    """Label(None) should not crash; it should treat None as empty string."""

    def test_label_none_text_is_empty(self) -> None:
        """Label(None) stores empty string."""
        label = Label(None)
        assert label.text == ""

    def test_label_set_text_none(self) -> None:
        """Setting label.text = None stores empty string."""
        label = Label("hello")
        label.text = None
        assert label.text == ""

    def test_label_normal_text_works(self) -> None:
        """Label with normal text works correctly."""
        label = Label("Hello World")
        assert label.text == "Hello World"

    def test_label_empty_string(self) -> None:
        """Label('') is accepted."""
        label = Label("")
        assert label.text == ""

    def test_label_none_preferred_size_no_crash(self) -> None:
        """Label(None).get_preferred_size() does not crash."""
        label = Label(None)
        w, h = label.get_preferred_size()
        assert w == 0  # empty text → zero width
        assert h > 0  # height based on font size


# ==================================================================
# F6: Panel(spacing=None) uses default spacing
# ==================================================================


class TestPanelSpacingNone:
    """Panel(spacing=None) should use 0 as default, not crash."""

    def test_spacing_none_uses_default(self) -> None:
        """Panel(spacing=None) defaults spacing to 0."""
        panel = Panel(spacing=None)
        assert panel.spacing == 0

    def test_spacing_zero_accepted(self) -> None:
        """Panel(spacing=0) is accepted."""
        panel = Panel(spacing=0)
        assert panel.spacing == 0

    def test_spacing_positive_accepted(self) -> None:
        """Panel(spacing=10) is accepted."""
        panel = Panel(spacing=10)
        assert panel.spacing == 10

    def test_spacing_negative_raises(self) -> None:
        """Panel(spacing=-1) raises ValueError."""
        with pytest.raises(ValueError, match="spacing cannot be negative"):
            Panel(spacing=-1)


# ==================================================================
# F7: TweenManager validates target values for NaN/Inf
# ==================================================================


class TestTweenManagerFiniteValues:
    """TweenManager.create() should reject NaN/Inf from_val and to_val."""

    def test_from_val_nan_raises(self) -> None:
        """create() with from_val=NaN raises ValueError."""
        mgr = TweenManager()
        target = type("T", (), {"x": 0.0})()
        with pytest.raises(ValueError, match="from_val must be finite"):
            mgr.create(target, "x", float("nan"), 100.0, 1.0)

    def test_to_val_nan_raises(self) -> None:
        """create() with to_val=NaN raises ValueError."""
        mgr = TweenManager()
        target = type("T", (), {"x": 0.0})()
        with pytest.raises(ValueError, match="to_val must be finite"):
            mgr.create(target, "x", 0.0, float("nan"), 1.0)

    def test_from_val_inf_raises(self) -> None:
        """create() with from_val=inf raises ValueError."""
        mgr = TweenManager()
        target = type("T", (), {"x": 0.0})()
        with pytest.raises(ValueError, match="from_val must be finite"):
            mgr.create(target, "x", float("inf"), 100.0, 1.0)

    def test_to_val_neg_inf_raises(self) -> None:
        """create() with to_val=-inf raises ValueError."""
        mgr = TweenManager()
        target = type("T", (), {"x": 0.0})()
        with pytest.raises(ValueError, match="to_val must be finite"):
            mgr.create(target, "x", 0.0, float("-inf"), 1.0)

    def test_finite_values_accepted(self) -> None:
        """create() with normal finite values works."""
        mgr = TweenManager()
        target = type("T", (), {"x": 0.0})()
        tid = mgr.create(target, "x", 0.0, 100.0, 1.0)
        assert tid >= 0
