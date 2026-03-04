"""Tests for AnimationDef, AnimationPlayer, and Sprite animation integration."""

from pathlib import Path

import pytest

from saga2d import Game, Sprite
from saga2d.animation import AnimationDef, AnimationPlayer
from saga2d.assets import AssetManager
from saga2d.backends.mock_backend import MockBackend
from saga2d.rendering.layers import SpriteAnchor


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

    def test_importable_from_saga2d(self) -> None:
        from saga2d import AnimationDef as AD
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
        # 0.25 / 0.1 = 2.5 frames -> advance by 2 (to index 2), 0.05 remainder
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
        player.update(0.1)   # -> h1
        result = player.update(0.1)  # -> h0 (wrap)
        assert result == "h0"
        assert player.frame_index == 0

    def test_stays_playing_after_wrap(self) -> None:
        player = AnimationPlayer(
            frames=["h0", "h1"],
            frame_duration=0.1,
            loop=True,
        )
        player.update(0.1)   # -> h1
        player.update(0.1)   # -> h0
        assert player.is_playing is True
        assert player.is_complete is False

    def test_multiple_loops(self) -> None:
        """Can loop through the entire animation multiple times."""
        player = AnimationPlayer(
            frames=["h0", "h1"],
            frame_duration=0.1,
            loop=True,
        )
        # 5 frame durations = 2.5 loops through 2 frames -> index 1
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
        player.update(0.1)   # -> h1
        player.update(0.1)   # -> h2
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
        player.update(0.1)   # -> h1
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
        player.update(0.1)   # -> h1
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
        # Frame tried to advance past index 0 -> clamped to 0, finished
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
        player.update(0.01)  # 10 frames -> finishes (only 3 frames)
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


# ==================================================================
# Sprite animation integration — fixtures and helpers
# ==================================================================


@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    """Temp asset dir with walk (4 frames) and idle (2 frames) animations."""
    images = tmp_path / "images" / "sprites"
    images.mkdir(parents=True)
    # Static image for sprite creation.
    (images / "knight.png").write_bytes(b"png")
    # Walk animation: 4 frames.
    for i in range(1, 5):
        (images / f"walk_{i:02d}.png").write_bytes(b"png")
    # Idle animation: 2 frames.
    (images / "idle_01.png").write_bytes(b"png")
    (images / "idle_02.png").write_bytes(b"png")
    # Attack animation: 3 frames.
    (images / "attack_01.png").write_bytes(b"png")
    (images / "attack_02.png").write_bytes(b"png")
    (images / "attack_03.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def game(asset_dir: Path) -> Game:
    g = Game("Test", backend="mock", resolution=(800, 600))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    return g


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


def _walk_anim() -> AnimationDef:
    return AnimationDef(
        frames=[
            "sprites/walk_01",
            "sprites/walk_02",
            "sprites/walk_03",
            "sprites/walk_04",
        ],
        frame_duration=0.1,
        loop=True,
    )


def _idle_anim() -> AnimationDef:
    return AnimationDef(
        frames=["sprites/idle_01", "sprites/idle_02"],
        frame_duration=0.2,
        loop=True,
    )


def _attack_anim() -> AnimationDef:
    return AnimationDef(
        frames=[
            "sprites/attack_01",
            "sprites/attack_02",
            "sprites/attack_03",
        ],
        frame_duration=0.1,
        loop=False,
    )


# ==================================================================
# Sprite — play() basics
# ==================================================================


def test_play_sets_first_frame_image(game: Game, backend: MockBackend) -> None:
    """play() immediately pushes the first frame's image to the backend."""
    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    walk = _walk_anim()
    sprite.play(walk)

    record = backend.sprites[sprite.sprite_id]
    expected_handle = game.assets.image("sprites/walk_01")
    assert record["image"] == expected_handle


def test_play_registers_for_auto_update(game: Game) -> None:
    """play() adds the sprite to game._animated_sprites."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    assert sprite not in game._animated_sprites

    sprite.play(_walk_anim())
    assert sprite in game._animated_sprites


def test_play_with_prefix_string(game: Game, backend: MockBackend) -> None:
    """play() works with AnimationDef using a prefix string."""
    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    anim = AnimationDef(frames="sprites/walk", frame_duration=0.1, loop=True)
    sprite.play(anim)

    record = backend.sprites[sprite.sprite_id]
    expected_handle = game.assets.image("sprites/walk_01")
    assert record["image"] == expected_handle


# ==================================================================
# Sprite — frame advancement via update_animation
# ==================================================================


def test_frame_advances_after_duration(game: Game, backend: MockBackend) -> None:
    """After frame_duration seconds, the displayed frame changes."""
    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    sprite.play(_walk_anim())

    sprite.update_animation(0.1)

    record = backend.sprites[sprite.sprite_id]
    expected = game.assets.image("sprites/walk_02")
    assert record["image"] == expected


def test_no_advance_before_duration(game: Game, backend: MockBackend) -> None:
    """Frame stays the same when not enough time has elapsed."""
    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    sprite.play(_walk_anim())

    sprite.update_animation(0.05)

    record = backend.sprites[sprite.sprite_id]
    expected = game.assets.image("sprites/walk_01")
    assert record["image"] == expected


# ==================================================================
# Sprite — looping
# ==================================================================


def test_looping_cycles_back_to_first_frame(
    game: Game, backend: MockBackend,
) -> None:
    """After the last frame, a looping animation wraps to frame 0."""
    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    walk = _walk_anim()  # 4 frames x 0.1s
    sprite.play(walk)

    # Advance through all 4 frames and wrap.
    sprite.update_animation(0.1)  # -> frame 1 (walk_02)
    sprite.update_animation(0.1)  # -> frame 2 (walk_03)
    sprite.update_animation(0.1)  # -> frame 3 (walk_04)
    sprite.update_animation(0.1)  # -> frame 0 (walk_01, wrap)

    record = backend.sprites[sprite.sprite_id]
    expected = game.assets.image("sprites/walk_01")
    assert record["image"] == expected


# ==================================================================
# Sprite — one-shot (non-looping) with on_complete
# ==================================================================


def test_oneshot_completes_after_correct_time(
    game: Game, backend: MockBackend,
) -> None:
    """A 3-frame x 0.1s non-looping animation finishes at 0.3s."""
    attack = _attack_anim()  # 3 frames x 0.1s, loop=False
    completed = []

    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    sprite.play(attack, on_complete=lambda: completed.append(True))

    # Frame 0 -> 1.
    sprite.update_animation(0.1)
    assert len(completed) == 0
    # Frame 1 -> 2.
    sprite.update_animation(0.1)
    assert len(completed) == 0
    # Frame 2 -> finish (stays on frame 2, fires callback).
    sprite.update_animation(0.1)
    assert len(completed) == 1

    record = backend.sprites[sprite.sprite_id]
    expected = game.assets.image("sprites/attack_03")
    assert record["image"] == expected


def test_oneshot_stays_on_last_frame(game: Game, backend: MockBackend) -> None:
    """After finishing, further updates don't change the frame."""
    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    sprite.play(_attack_anim())

    # Run through all frames + extra.
    for _ in range(10):
        sprite.update_animation(0.1)

    record = backend.sprites[sprite.sprite_id]
    expected = game.assets.image("sprites/attack_03")
    assert record["image"] == expected


# ==================================================================
# Sprite — play() interrupts current animation
# ==================================================================


def test_play_interrupts_current(game: Game, backend: MockBackend) -> None:
    """Calling play() mid-animation replaces the current animation."""
    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    sprite.play(_walk_anim())
    sprite.update_animation(0.1)  # advance walk to frame 1

    # Interrupt with attack.
    sprite.play(_attack_anim())

    record = backend.sprites[sprite.sprite_id]
    expected = game.assets.image("sprites/attack_01")
    assert record["image"] == expected


def test_play_clears_queue(game: Game) -> None:
    """play() clears any queued animations."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.play(_attack_anim())
    sprite.queue(_idle_anim())
    sprite.queue(_walk_anim())

    # play() replaces everything.
    sprite.play(_walk_anim())
    assert len(sprite._anim_queue) == 0


# ==================================================================
# Sprite — queue()
# ==================================================================


def test_queue_plays_after_current_finishes(
    game: Game, backend: MockBackend,
) -> None:
    """Queued animation starts after the current one-shot finishes."""
    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    attack = _attack_anim()  # 3 frames x 0.1s, loop=False
    idle = _idle_anim()

    sprite.play(attack)
    sprite.queue(idle)

    # Play through attack: frames 0->1->2->finish -> idle starts.
    sprite.update_animation(0.1)  # attack frame 1
    sprite.update_animation(0.1)  # attack frame 2
    sprite.update_animation(0.1)  # attack finish -> idle starts at frame 0

    record = backend.sprites[sprite.sprite_id]
    expected = game.assets.image("sprites/idle_01")
    assert record["image"] == expected


def test_queue_when_nothing_playing_starts_immediately(
    game: Game, backend: MockBackend,
) -> None:
    """queue() with no current animation starts immediately (like play)."""
    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    sprite.queue(_walk_anim())

    record = backend.sprites[sprite.sprite_id]
    expected = game.assets.image("sprites/walk_01")
    assert record["image"] == expected


def test_queue_chain_three_animations(
    game: Game, backend: MockBackend,
) -> None:
    """Queue multiple animations: attack -> idle starts after attack completes."""
    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    attack = _attack_anim()  # 3 frames, loop=False
    idle = _idle_anim()      # loop=True

    callback_fired = []
    sprite.play(attack, on_complete=lambda: callback_fired.append("attack"))
    sprite.queue(idle, on_complete=lambda: callback_fired.append("idle"))

    # Play through attack.
    sprite.update_animation(0.1)  # attack frame 1
    sprite.update_animation(0.1)  # attack frame 2
    sprite.update_animation(0.1)  # attack finish -> callback -> idle starts

    # Attack callback should have fired.
    assert "attack" in callback_fired

    # Idle should now be playing.
    record = backend.sprites[sprite.sprite_id]
    expected = game.assets.image("sprites/idle_01")
    assert record["image"] == expected


# ==================================================================
# Sprite — stop_animation()
# ==================================================================


def test_stop_animation_stops_playback(
    game: Game, backend: MockBackend,
) -> None:
    """stop_animation() stops the animation; frame stays as-is."""
    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    sprite.play(_walk_anim())
    sprite.update_animation(0.1)  # -> walk_02

    sprite.stop_animation()

    # Further updates don't change the frame.
    sprite.update_animation(0.5)
    record = backend.sprites[sprite.sprite_id]
    expected = game.assets.image("sprites/walk_02")
    assert record["image"] == expected


def test_stop_animation_clears_queue(game: Game) -> None:
    """stop_animation() clears the animation queue."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.play(_attack_anim())
    sprite.queue(_idle_anim())

    sprite.stop_animation()
    assert len(sprite._anim_queue) == 0


def test_stop_animation_deregisters(game: Game) -> None:
    """stop_animation() removes the sprite from game._animated_sprites."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.play(_walk_anim())
    assert sprite in game._animated_sprites

    sprite.stop_animation()
    assert sprite not in game._animated_sprites


# ==================================================================
# Sprite — remove() clears animation
# ==================================================================


def test_remove_deregisters_animation(game: Game) -> None:
    """remove() stops animation and deregisters from auto-update."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.play(_walk_anim())
    assert sprite in game._animated_sprites

    sprite.remove()
    assert sprite not in game._animated_sprites


def test_play_on_removed_sprite_is_noop(game: Game) -> None:
    """play() on a removed sprite does nothing."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.remove()
    sprite.play(_walk_anim())  # should not raise
    assert sprite not in game._animated_sprites


# ==================================================================
# Sprite — automatic update via game.tick()
# ==================================================================


def test_game_tick_advances_animation(game: Game, backend: MockBackend) -> None:
    """game.tick(dt) automatically advances sprite animation."""
    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    sprite.play(_walk_anim())

    # tick with dt=0.1 should advance to walk_02.
    game.tick(dt=0.1)

    record = backend.sprites[sprite.sprite_id]
    expected = game.assets.image("sprites/walk_02")
    assert record["image"] == expected


def test_game_tick_multiple_sprites(game: Game, backend: MockBackend) -> None:
    """game.tick() updates all animated sprites."""
    s1 = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    s2 = Sprite(
        "sprites/knight", position=(200, 200), anchor=SpriteAnchor.TOP_LEFT,
    )
    s1.play(_walk_anim())
    s2.play(_attack_anim())

    game.tick(dt=0.1)

    r1 = backend.sprites[s1.sprite_id]
    r2 = backend.sprites[s2.sprite_id]
    assert r1["image"] == game.assets.image("sprites/walk_02")
    assert r2["image"] == game.assets.image("sprites/attack_02")


def test_game_tick_oneshot_fires_callback(game: Game) -> None:
    """on_complete fires when animation finishes during game.tick()."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    fired = []
    sprite.play(_attack_anim(), on_complete=lambda: fired.append(True))

    # 3 frames x 0.1s each -- need 3 ticks to finish.
    game.tick(dt=0.1)
    game.tick(dt=0.1)
    game.tick(dt=0.1)

    assert len(fired) == 1
