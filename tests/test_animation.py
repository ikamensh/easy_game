"""Tests for AnimationDef and AnimationPlayer."""

import pytest

from easygame.animation import AnimationDef, AnimationPlayer


# ==================================================================
# AnimationDef
# ==================================================================


class TestAnimationDef:
    """AnimationDef stores frames, frame_duration, and loop flag."""

    def test_explicit_frames_list(self) -> None:
        anim = AnimationDef(
            frames=["walk_01", "walk_02", "walk_03"],
            frame_duration=0.15,
            loop=True,
        )
        assert anim.frames == ["walk_01", "walk_02", "walk_03"]
        assert anim.frame_duration == 0.15
        assert anim.loop is True

    def test_prefix_string(self) -> None:
        anim = AnimationDef(frames="sprites/walk", frame_duration=0.1)
        assert anim.frames == "sprites/walk"

    def test_defaults(self) -> None:
        anim = AnimationDef(frames=["a", "b"])
        assert anim.frame_duration == 0.15
        assert anim.loop is True

    def test_loop_false(self) -> None:
        anim = AnimationDef(frames=["a", "b"], loop=False)
        assert anim.loop is False

    def test_repr_list_frames(self) -> None:
        anim = AnimationDef(frames=["a", "b", "c"])
        r = repr(anim)
        assert "3 frames" in r
        assert "loop=True" in r

    def test_repr_prefix(self) -> None:
        anim = AnimationDef(frames="sprites/walk")
        r = repr(anim)
        assert "sprites/walk" in r

    def test_importable_from_easygame(self) -> None:
        from easygame import AnimationDef as AD
        assert AD is AnimationDef


# ==================================================================
# AnimationPlayer — construction
# ==================================================================


class TestAnimationPlayerConstruction:
    """AnimationPlayer requires resolved handles and valid config."""

    def test_empty_frames_raises(self) -> None:
        with pytest.raises(ValueError, match="zero frames"):
            AnimationPlayer(frames=[], frame_duration=0.1, loop=True)

    def test_initial_state(self) -> None:
        player = AnimationPlayer(
            frames=["h0", "h1", "h2"],
            frame_duration=0.1,
            loop=True,
        )
        assert player.current_frame == "h0"
        assert player.frame_index == 0
        assert player.is_playing is True
        assert player.is_complete is False


# ==================================================================
# AnimationPlayer — frame advancement
# ==================================================================


class TestAnimationPlayerUpdate:
    """update(dt) advances frames and returns new handle or None."""

    def test_no_advance_before_duration(self) -> None:
        """update returns None when not enough time has elapsed."""
        player = AnimationPlayer(
            frames=["h0", "h1", "h2"],
            frame_duration=0.1,
            loop=True,
        )
        result = player.update(0.05)
        assert result is None
        assert player.current_frame == "h0"

    def test_advance_to_second_frame(self) -> None:
        """After frame_duration, advances to frame 1."""
        player = AnimationPlayer(
            frames=["h0", "h1", "h2"],
            frame_duration=0.1,
            loop=True,
        )
        result = player.update(0.1)
        assert result == "h1"
        assert player.frame_index == 1

    def test_advance_multiple_frames_in_one_update(self) -> None:
        """A large dt can skip multiple frames."""
        player = AnimationPlayer(
            frames=["h0", "h1", "h2", "h3"],
            frame_duration=0.1,
            loop=True,
        )
        result = player.update(0.25)
        # 0.25 / 0.1 = 2.5 frames → advance by 2 (to index 2), 0.05 remainder
        assert result == "h2"
        assert player.frame_index == 2

    def test_accumulated_small_updates(self) -> None:
        """Multiple small updates accumulate to trigger a frame change."""
        player = AnimationPlayer(
            frames=["h0", "h1"],
            frame_duration=0.1,
            loop=True,
        )
        assert player.update(0.03) is None
        assert player.update(0.03) is None
        result = player.update(0.05)  # total: 0.11
        assert result == "h1"


# ==================================================================
# AnimationPlayer — looping
# ==================================================================


class TestAnimationPlayerLooping:
    """Looping animations wrap around to frame 0 after the last frame."""

    def test_wraps_to_first_frame(self) -> None:
        player = AnimationPlayer(
            frames=["h0", "h1"],
            frame_duration=0.1,
            loop=True,
        )
        player.update(0.1)   # → h1
        result = player.update(0.1)  # → h0 (wrap)
        assert result == "h0"
        assert player.frame_index == 0

    def test_stays_playing_after_wrap(self) -> None:
        player = AnimationPlayer(
            frames=["h0", "h1"],
            frame_duration=0.1,
            loop=True,
        )
        player.update(0.1)   # → h1
        player.update(0.1)   # → h0
        assert player.is_playing is True
        assert player.is_complete is False

    def test_multiple_loops(self) -> None:
        """Can loop through the entire animation multiple times."""
        player = AnimationPlayer(
            frames=["h0", "h1"],
            frame_duration=0.1,
            loop=True,
        )
        # 5 frame durations = 2.5 loops through 2 frames → index 1
        player.update(0.5)
        assert player.frame_index == 1
        assert player.is_playing is True

    def test_looping_never_fires_on_complete(self) -> None:
        callback_count = 0

        def on_done() -> None:
            nonlocal callback_count
            callback_count += 1

        player = AnimationPlayer(
            frames=["h0", "h1"],
            frame_duration=0.1,
            loop=True,
            on_complete=on_done,
        )
        # Run many loops
        for _ in range(20):
            player.update(0.1)
        assert callback_count == 0


# ==================================================================
# AnimationPlayer — non-looping (one-shot)
# ==================================================================


class TestAnimationPlayerOneShot:
    """Non-looping animations play once, fire on_complete, stay on last frame."""

    def test_finishes_after_last_frame(self) -> None:
        player = AnimationPlayer(
            frames=["h0", "h1", "h2"],
            frame_duration=0.1,
            loop=False,
        )
        player.update(0.1)   # → h1
        player.update(0.1)   # → h2
        player.update(0.1)   # stays on h2, finishes

        assert player.is_complete is True
        assert player.is_playing is False
        assert player.current_frame == "h2"

    def test_stays_on_last_frame(self) -> None:
        """After finishing, further updates return None and stay on last frame."""
        player = AnimationPlayer(
            frames=["h0", "h1"],
            frame_duration=0.1,
            loop=False,
        )
        player.update(0.1)   # → h1
        player.update(0.1)   # finishes

        result = player.update(0.1)
        assert result is None
        assert player.current_frame == "h1"

    def test_fires_on_complete_once(self) -> None:
        callback_count = 0

        def on_done() -> None:
            nonlocal callback_count
            callback_count += 1

        player = AnimationPlayer(
            frames=["h0", "h1"],
            frame_duration=0.1,
            loop=False,
            on_complete=on_done,
        )
        player.update(0.1)   # → h1
        player.update(0.1)   # finishes, fires callback
        player.update(0.1)   # no-op
        player.update(0.1)   # no-op

        assert callback_count == 1

    def test_on_complete_none_is_safe(self) -> None:
        """No crash when on_complete is None."""
        player = AnimationPlayer(
            frames=["h0", "h1"],
            frame_duration=0.1,
            loop=False,
        )
        player.update(0.1)
        player.update(0.1)  # finishes, no callback
        assert player.is_complete is True

    def test_single_frame_non_looping(self) -> None:
        """A single-frame non-looping animation finishes immediately on first advance."""
        callback_fired = False

        def on_done() -> None:
            nonlocal callback_fired
            callback_fired = True

        player = AnimationPlayer(
            frames=["h0"],
            frame_duration=0.1,
            loop=False,
            on_complete=on_done,
        )
        player.update(0.1)
        # Frame tried to advance past index 0 → clamped to 0, finished
        assert player.is_complete is True
        assert callback_fired is True
        assert player.current_frame == "h0"

    def test_large_dt_finishes_correctly(self) -> None:
        """A dt that spans the entire animation finishes cleanly."""
        player = AnimationPlayer(
            frames=["h0", "h1", "h2"],
            frame_duration=0.1,
            loop=False,
        )
        player.update(1.0)  # 10 frames worth, but only 3 frames
        assert player.is_complete is True
        assert player.current_frame == "h2"


# ==================================================================
# AnimationPlayer — edge cases
# ==================================================================


class TestAnimationPlayerEdgeCases:
    """Edge cases and special scenarios."""

    def test_zero_dt_returns_none(self) -> None:
        player = AnimationPlayer(
            frames=["h0", "h1"],
            frame_duration=0.1,
            loop=True,
        )
        assert player.update(0.0) is None

    def test_very_small_frame_duration(self) -> None:
        """Very small frame_duration still works correctly."""
        player = AnimationPlayer(
            frames=["h0", "h1", "h2"],
            frame_duration=0.001,
            loop=False,
        )
        player.update(0.01)  # 10 frames → finishes (only 3 frames)
        assert player.is_complete is True
        assert player.current_frame == "h2"

    def test_single_frame_looping(self) -> None:
        """Single-frame looping animation never finishes, stays on frame 0."""
        player = AnimationPlayer(
            frames=["h0"],
            frame_duration=0.1,
            loop=True,
        )
        player.update(0.5)
        assert player.is_playing is True
        assert player.current_frame == "h0"
