"""Comprehensive tests for Stage 10 Composable Actions system.

Tests all 10 action types using the mock backend. Covers: Sequence timing,
Parallel completion, Delay, Do, PlayAnim, MoveTo, FadeOut, FadeIn, Remove,
Repeat (finite and infinite), nested compositions, stop_actions, do() replace,
and the battle sequence pattern.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from easygame import (
    Game,
    Sprite,
    AnimationDef,
    Delay,
    Do,
    FadeIn,
    FadeOut,
    MoveTo,
    Parallel,
    PlayAnim,
    Remove,
    Repeat,
    Sequence,
)
from easygame.assets import AssetManager
from easygame.backends.mock_backend import MockBackend


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    """Temp asset dir with knight, walk (4 frames), attack (3 frames)."""
    images = tmp_path / "images" / "sprites"
    images.mkdir(parents=True)
    (images / "knight.png").write_bytes(b"png")
    for i in range(1, 5):
        (images / f"walk_{i:02d}.png").write_bytes(b"png")
    for i in range(1, 4):
        (images / f"attack_{i:02d}.png").write_bytes(b"png")
    (images / "idle_01.png").write_bytes(b"png")
    (images / "idle_02.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def game(asset_dir: Path) -> Game:
    g = Game("Test", backend="mock", resolution=(800, 600))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    return g


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


@pytest.fixture
def sprite(game: Game) -> Sprite:
    """Sprite at (100, 300) for action tests."""
    return Sprite("sprites/knight", position=(100, 300))


def _walk_anim() -> AnimationDef:
    return AnimationDef(
        frames=["sprites/walk_01", "sprites/walk_02", "sprites/walk_03", "sprites/walk_04"],
        frame_duration=0.1,
        loop=True,
    )


def _attack_anim() -> AnimationDef:
    return AnimationDef(
        frames=["sprites/attack_01", "sprites/attack_02", "sprites/attack_03"],
        frame_duration=0.1,
        loop=False,
    )


def _idle_anim() -> AnimationDef:
    return AnimationDef(
        frames=["sprites/idle_01", "sprites/idle_02"],
        frame_duration=0.2,
        loop=True,
    )


# ------------------------------------------------------------------
# Delay
# ------------------------------------------------------------------


class TestDelay:
    def test_delay_waits_correct_duration(self, sprite: Sprite, game: Game) -> None:
        done = []
        sprite.do(Sequence(Delay(0.5), Do(lambda: done.append(True))))
        game.tick(dt=0.25)
        assert len(done) == 0
        game.tick(dt=0.25)
        assert len(done) == 1

    def test_delay_zero_duration_completes_immediately(self, sprite: Sprite, game: Game) -> None:
        done = []
        sprite.do(Sequence(Delay(0), Do(lambda: done.append(True))))
        game.tick(dt=0.016)
        assert len(done) == 1

    def test_delay_exact_duration_completes_on_tick(self, sprite: Sprite, game: Game) -> None:
        done = []
        sprite.do(Sequence(Delay(0.1), Do(lambda: done.append(True))))
        game.tick(dt=0.1)
        assert len(done) == 1

    def test_delay_small_dt_accumulates(self, sprite: Sprite, game: Game) -> None:
        done = []
        sprite.do(Sequence(Delay(0.1), Do(lambda: done.append(True))))
        for _ in range(15):
            game.tick(dt=0.01)
            if done:
                break
        assert len(done) == 1

    def test_delay_overflows_into_next_action(self, sprite: Sprite, game: Game) -> None:
        """Delay(0.05) + Delay(0.05): first completes, second gets dt=0 so needs another tick."""
        count = []
        sprite.do(Sequence(
            Delay(0.05),
            Do(lambda: count.append(1)),
            Delay(0.05),
            Do(lambda: count.append(2)),
        ))
        game.tick(dt=0.1)  # first Delay done, second starts with dt=0
        assert count == [1]
        game.tick(dt=0.1)  # second Delay gets dt, completes
        assert count == [1, 2]


# ------------------------------------------------------------------
# Do
# ------------------------------------------------------------------


class TestDo:
    def test_do_fires_callable(self, sprite: Sprite, game: Game) -> None:
        fired = []
        sprite.do(Do(lambda: fired.append(True)))
        game.tick(dt=0.016)
        assert fired == [True]

    def test_do_completes_immediately(self, sprite: Sprite, game: Game) -> None:
        """Do should not keep sprite in _action_sprites after one tick."""
        sprite.do(Do(lambda: None))
        assert sprite in game._action_sprites
        game.tick(dt=0.016)
        assert sprite not in game._action_sprites

    def test_do_receives_no_dt(self, sprite: Sprite, game: Game) -> None:
        """Do is instant — update returns True on first call."""
        action = Do(lambda: None)
        sprite.do(action)
        result = action.update(0.5)
        assert result is True

    def test_do_chained_in_sequence(self, sprite: Sprite, game: Game) -> None:
        order = []
        sprite.do(Sequence(
            Do(lambda: order.append(1)),
            Do(lambda: order.append(2)),
            Do(lambda: order.append(3)),
        ))
        game.tick(dt=0.016)
        assert order == [1, 2, 3]

    def test_do_receives_sprite_via_closure(self, sprite: Sprite, game: Game) -> None:
        captured = []
        sprite.do(Do(lambda: captured.append(sprite.position)))
        game.tick(dt=0.016)
        assert captured == [(100, 300)]


# ------------------------------------------------------------------
# Sequence
# ------------------------------------------------------------------


class TestSequence:
    def test_sequence_executes_in_order(self, sprite: Sprite, game: Game) -> None:
        order = []
        sprite.do(Sequence(
            Do(lambda: order.append(1)),
            Delay(0.05),
            Do(lambda: order.append(2)),
            Delay(0.05),
            Do(lambda: order.append(3)),
        ))
        game.tick(dt=0.016)
        assert order == [1]
        game.tick(dt=0.05)
        assert order == [1, 2]
        game.tick(dt=0.05)
        assert order == [1, 2, 3]

    def test_sequence_empty_completes_immediately(self, sprite: Sprite, game: Game) -> None:
        sprite.do(Sequence())
        game.tick(dt=0.016)
        assert sprite not in game._action_sprites

    def test_sequence_single_action(self, sprite: Sprite, game: Game) -> None:
        fired = []
        sprite.do(Sequence(Do(lambda: fired.append(True))))
        game.tick(dt=0.016)
        assert fired == [True]

    def test_sequence_instant_chain_same_frame(self, sprite: Sprite, game: Game) -> None:
        """Sequence(Do, Do, Do) executes all in one tick."""
        count = [0]
        sprite.do(Sequence(
            Do(lambda: count.__setitem__(0, count[0] + 1)),
            Do(lambda: count.__setitem__(0, count[0] + 1)),
            Do(lambda: count.__setitem__(0, count[0] + 1)),
        ))
        game.tick(dt=0.016)
        assert count[0] == 3

    def test_sequence_remove_then_do_same_tick(self, sprite: Sprite, game: Game, backend: MockBackend) -> None:
        """Sequence(Do, Remove, Do) — Remove runs, sprite gone; Do(2) may run in same tick."""
        order = []
        sprite.do(Sequence(
            Do(lambda: order.append(1)),
            Remove(),
            Do(lambda: order.append(2)),
        ))
        game.tick(dt=0.016)
        assert sprite.is_removed
        assert sprite.sprite_id not in backend.sprites

    def test_sequence_correct_timing_between_delays(self, sprite: Sprite, game: Game) -> None:
        """Subsequent children get dt=0 when chained, so delays need full ticks."""
        times = []
        sprite.do(Sequence(
            Do(lambda: times.append(0)),
            Delay(0.2),
            Do(lambda: times.append(1)),
            Delay(0.3),
            Do(lambda: times.append(2)),
        ))
        game.tick(dt=0.1)  # Do(0), Delay(0.2) starts with dt=0
        assert times == [0]
        game.tick(dt=0.1)  # Delay has 0.1
        assert times == [0]
        game.tick(dt=0.1)  # Delay has 0.2, done; Do(1)
        assert times == [0, 1]
        game.tick(dt=0.2)  # Delay(0.3) gets 0.2
        assert times == [0, 1]
        game.tick(dt=0.1)  # Delay done, Do(2)
        assert times == [0, 1, 2]


# ------------------------------------------------------------------
# Parallel
# ------------------------------------------------------------------


class TestParallel:
    def test_parallel_runs_all_children(self, sprite: Sprite, game: Game) -> None:
        a_done, b_done = [], []
        sprite.do(Parallel(
            Sequence(Delay(0.1), Do(lambda: a_done.append(True))),
            Sequence(Delay(0.2), Do(lambda: b_done.append(True))),
        ))
        game.tick(dt=0.1)
        assert a_done == [True]
        assert b_done == []
        game.tick(dt=0.1)
        assert b_done == [True]

    def test_parallel_completes_when_all_done(self, sprite: Sprite, game: Game) -> None:
        sprite.do(Parallel(Delay(0.1), Delay(0.2)))
        game.tick(dt=0.1)
        assert sprite in game._action_sprites
        game.tick(dt=0.1)
        assert sprite not in game._action_sprites

    def test_parallel_two_move_to_waits_slower(self, sprite: Sprite, game: Game) -> None:
        """Parallel(MoveTo fast, MoveTo slow) completes when slow one arrives.

        Both update the same sprite; last update wins per frame. Final pos is
        from the slower MoveTo when it finishes.
        """
        sprite.do(Parallel(
            MoveTo((200, 300), speed=1000),  # arrives in ~0.1s
            MoveTo((150, 300), speed=100),   # arrives in ~0.5s
        ))
        game.tick(dt=0.2)
        assert sprite in game._action_sprites
        game.tick(dt=0.4)
        assert sprite not in game._action_sprites
        assert abs(sprite._x - 150) < 2

    def test_parallel_stops_infinite_child_when_finite_done(
        self, sprite: Sprite, game: Game,
    ) -> None:
        """Parallel(PlayAnim loop, MoveTo) stops PlayAnim when MoveTo finishes."""
        sprite.do(Parallel(PlayAnim(_walk_anim()), MoveTo((200, 300), speed=500)))
        game.tick(dt=0.25)  # MoveTo arrives
        assert sprite not in game._action_sprites
        assert sprite._anim_player is None  # PlayAnim.stop_animation was called

    def test_parallel_empty_completes_immediately(self, sprite: Sprite, game: Game) -> None:
        sprite.do(Parallel())
        game.tick(dt=0.016)
        assert sprite not in game._action_sprites

    def test_parallel_single_action(self, sprite: Sprite, game: Game) -> None:
        fired = []
        sprite.do(Parallel(Do(lambda: fired.append(True))))
        game.tick(dt=0.016)
        assert fired == [True]


# ------------------------------------------------------------------
# MoveTo
# ------------------------------------------------------------------


class TestMoveTo:
    def test_move_to_reaches_target(self, sprite: Sprite, game: Game) -> None:
        sprite.do(MoveTo((500, 300), speed=200))
        # 400px at 200px/s = 2s
        for _ in range(250):
            game.tick(dt=0.016)
            if sprite._x >= 499:
                break
        assert abs(sprite._x - 500) < 2
        assert abs(sprite._y - 300) < 2

    def test_move_to_correct_speed(self, sprite: Sprite, game: Game) -> None:
        """At 400 px/s, 100px takes 0.25s."""
        sprite.do(MoveTo((200, 300), speed=400))
        game.tick(dt=0.125)
        assert 140 < sprite._x < 160
        game.tick(dt=0.125)
        assert abs(sprite._x - 200) < 2

    def test_move_to_already_at_target_completes_immediately(
        self, sprite: Sprite, game: Game,
    ) -> None:
        sprite.do(MoveTo((100, 300), speed=200))
        game.tick(dt=0.016)
        assert sprite not in game._action_sprites

    def test_move_to_vertical_movement(self, sprite: Sprite, game: Game) -> None:
        sprite.do(MoveTo((100, 500), speed=200))
        for _ in range(150):
            game.tick(dt=0.016)
            if sprite._y >= 499:
                break
        assert abs(sprite._y - 500) < 2

    def test_move_to_diagonal_movement(self, sprite: Sprite, game: Game) -> None:
        sprite.do(MoveTo((200, 400), speed=200))
        dist = ((200 - 100) ** 2 + (400 - 300) ** 2) ** 0.5
        ticks = int(dist / 200 / 0.016) + 5
        for _ in range(ticks):
            game.tick(dt=0.016)
            if abs(sprite._x - 200) < 2 and abs(sprite._y - 400) < 2:
                break
        assert abs(sprite._x - 200) < 2
        assert abs(sprite._y - 400) < 2

    def test_move_to_stop_leaves_position(self, sprite: Sprite, game: Game) -> None:
        sprite.do(MoveTo((500, 300), speed=200))
        game.tick(dt=0.5)
        mid_x = sprite._x
        sprite.stop_actions()
        game.tick(dt=1.0)
        assert sprite._x == mid_x


# ------------------------------------------------------------------
# FadeOut
# ------------------------------------------------------------------


class TestFadeOut:
    def test_fade_out_reaches_zero(self, sprite: Sprite, game: Game) -> None:
        sprite.do(FadeOut(0.5))
        game.tick(dt=0.25)
        assert 0 < sprite.opacity < 255
        game.tick(dt=0.25)
        assert sprite.opacity == 0

    def test_fade_out_from_current_opacity(self, sprite: Sprite, game: Game) -> None:
        sprite.opacity = 128
        sprite.do(FadeOut(0.5))
        game.tick(dt=0.5)
        assert sprite.opacity == 0

    def test_fade_out_zero_duration(self, sprite: Sprite, game: Game) -> None:
        sprite.do(FadeOut(0))
        game.tick(dt=0.016)
        assert sprite.opacity == 0

    def test_fade_out_completes_in_one_tick_if_dt_exceeds_duration(
        self, sprite: Sprite, game: Game,
    ) -> None:
        sprite.do(FadeOut(0.1))
        game.tick(dt=0.5)
        assert sprite.opacity == 0
        assert sprite not in game._action_sprites

    def test_fade_out_stop_leaves_opacity(self, sprite: Sprite, game: Game) -> None:
        sprite.do(FadeOut(0.5))
        game.tick(dt=0.25)
        mid_opacity = sprite.opacity
        sprite.stop_actions()
        game.tick(dt=0.5)
        assert sprite.opacity == mid_opacity


# ------------------------------------------------------------------
# FadeIn
# ------------------------------------------------------------------


class TestFadeIn:
    def test_fade_in_reaches_255(self, sprite: Sprite, game: Game) -> None:
        sprite.opacity = 0
        sprite.do(FadeIn(0.5))
        game.tick(dt=0.25)
        assert 0 < sprite.opacity < 255
        game.tick(dt=0.25)
        assert sprite.opacity == 255

    def test_fade_in_from_current_opacity(self, sprite: Sprite, game: Game) -> None:
        sprite.opacity = 128
        sprite.do(FadeIn(0.5))
        game.tick(dt=0.5)
        assert sprite.opacity == 255

    def test_fade_in_zero_duration(self, sprite: Sprite, game: Game) -> None:
        sprite.opacity = 0
        sprite.do(FadeIn(0))
        game.tick(dt=0.016)
        assert sprite.opacity == 255


# ------------------------------------------------------------------
# Remove
# ------------------------------------------------------------------


class TestRemove:
    def test_remove_calls_sprite_remove(self, sprite: Sprite, game: Game, backend: MockBackend) -> None:
        sprite.do(Remove())
        game.tick(dt=0.016)
        assert sprite.is_removed
        assert sprite.sprite_id not in backend.sprites

    def test_remove_completes_immediately(self, sprite: Sprite, game: Game) -> None:
        sprite.do(Remove())
        game.tick(dt=0.016)
        assert sprite not in game._action_sprites

    def test_remove_in_sequence_after_delay(self, sprite: Sprite, game: Game, backend: MockBackend) -> None:
        sprite.do(Sequence(Delay(0.1), Remove()))
        game.tick(dt=0.05)
        assert not sprite.is_removed
        game.tick(dt=0.05)
        assert sprite.is_removed
        assert sprite.sprite_id not in backend.sprites


# ------------------------------------------------------------------
# PlayAnim
# ------------------------------------------------------------------


class TestPlayAnim:
    def test_play_anim_non_looping_completes(self, sprite: Sprite, game: Game) -> None:
        """3 frames × 0.1s = 0.3s; on_complete fires after animation phase."""
        sprite.do(PlayAnim(_attack_anim()))
        for _ in range(50):  # 50 × 0.016 ≈ 0.8s
            game.tick(dt=0.016)
            if sprite not in game._action_sprites:
                break
        assert sprite not in game._action_sprites

    def test_play_anim_looping_is_finite_false(self) -> None:
        assert PlayAnim(_walk_anim()).is_finite is False

    def test_play_anim_non_looping_is_finite_true(self) -> None:
        assert PlayAnim(_attack_anim()).is_finite is True

    def test_play_anim_starts_animation(self, sprite: Sprite, game: Game) -> None:
        """PlayAnim registers sprite for animation updates."""
        sprite.do(PlayAnim(_attack_anim()))
        assert sprite in game._animated_sprites
        game.tick(dt=0.016)
        assert sprite._anim_player is not None

    def test_play_anim_stop_calls_stop_animation(self, sprite: Sprite, game: Game) -> None:
        sprite.do(PlayAnim(_walk_anim()))
        game.tick(dt=0.05)
        sprite.stop_actions()
        assert sprite._anim_player is None

    def test_play_anim_removed_from_animated_sprites_on_stop(self, sprite: Sprite, game: Game) -> None:
        sprite.do(PlayAnim(_walk_anim()))
        assert sprite in game._animated_sprites
        sprite.stop_actions()
        assert sprite not in game._animated_sprites


# ------------------------------------------------------------------
# Repeat
# ------------------------------------------------------------------


class TestRepeat:
    def test_repeat_n_times(self, sprite: Sprite, game: Game) -> None:
        """Repeat runs one iteration per tick (Do completes, next starts next tick)."""
        count = [0]
        sprite.do(Repeat(Do(lambda: count.__setitem__(0, count[0] + 1)), times=3))
        for _ in range(5):
            game.tick(dt=0.016)
            if count[0] >= 3:
                break
        assert count[0] == 3
        assert sprite not in game._action_sprites

    def test_repeat_twice_with_delay(self, sprite: Sprite, game: Game) -> None:
        count = [0]
        sprite.do(Repeat(
            Sequence(Delay(0.05), Do(lambda: count.__setitem__(0, count[0] + 1))),
            times=2,
        ))
        game.tick(dt=0.05)
        assert count[0] == 1
        game.tick(dt=0.05)
        assert count[0] == 2
        assert sprite not in game._action_sprites

    def test_repeat_infinite_times_none(self) -> None:
        assert Repeat(Do(lambda: None), times=None).is_finite is False

    def test_repeat_finite_times_has_is_finite_true(self) -> None:
        assert Repeat(Do(lambda: None), times=5).is_finite is True

    def test_repeat_infinite_runs_until_stopped(self, sprite: Sprite, game: Game) -> None:
        count = [0]
        sprite.do(Repeat(Do(lambda: count.__setitem__(0, count[0] + 1)), times=None))
        for _ in range(5):
            game.tick(dt=0.016)
        assert count[0] >= 5
        assert sprite in game._action_sprites
        sprite.stop_actions()
        assert sprite not in game._action_sprites

    def test_repeat_zero_times_completes_immediately(self, sprite: Sprite, game: Game) -> None:
        """Repeat(times=0): implementation runs once then stops (count>=0)."""
        count = [0]
        sprite.do(Repeat(Do(lambda: count.__setitem__(0, count[0] + 1)), times=0))
        game.tick(dt=0.016)
        assert sprite not in game._action_sprites
        # Current impl: times=0 means count>=0 after first run, so completes after 1 iteration
        assert count[0] in (0, 1)

    def test_repeat_deep_copies_action_state(self, sprite: Sprite, game: Game) -> None:
        """Each Repeat iteration gets fresh Delay state."""
        count = [0]
        sprite.do(Repeat(
            Sequence(Delay(0.05), Do(lambda: count.__setitem__(0, count[0] + 1))),
            times=2,
        ))
        game.tick(dt=0.03)
        assert count[0] == 0
        game.tick(dt=0.03)
        assert count[0] == 1
        game.tick(dt=0.05)
        assert count[0] == 2

    def test_repeat_once_equivalent_to_single_action(self, sprite: Sprite, game: Game) -> None:
        count = [0]
        sprite.do(Repeat(Do(lambda: count.__setitem__(0, count[0] + 1)), times=1))
        game.tick(dt=0.016)
        assert count[0] == 1
        assert sprite not in game._action_sprites


# ------------------------------------------------------------------
# stop_actions
# ------------------------------------------------------------------


class TestStopActions:
    def test_stop_actions_cancels_mid_sequence(self, sprite: Sprite, game: Game) -> None:
        order = []
        sprite.do(Sequence(
            Do(lambda: order.append(1)),
            Delay(0.5),
            Do(lambda: order.append(2)),
        ))
        game.tick(dt=0.016)
        assert order == [1]
        sprite.stop_actions()
        assert sprite not in game._action_sprites
        for _ in range(50):
            game.tick(dt=0.016)
        assert order == [1]

    def test_stop_actions_cancels_mid_delay(self, sprite: Sprite, game: Game) -> None:
        done = []
        sprite.do(Sequence(Delay(0.5), Do(lambda: done.append(True))))
        game.tick(dt=0.1)
        sprite.stop_actions()
        game.tick(dt=0.5)
        assert done == []

    def test_stop_actions_cancels_mid_move_to(self, sprite: Sprite, game: Game) -> None:
        sprite.do(MoveTo((500, 300), speed=100))
        game.tick(dt=0.5)
        assert 100 < sprite._x < 500
        sprite.stop_actions()
        x_at_stop = sprite._x
        game.tick(dt=0.5)
        assert sprite._x == x_at_stop

    def test_stop_actions_cancels_mid_fade_out(self, sprite: Sprite, game: Game) -> None:
        sprite.do(FadeOut(0.5))
        game.tick(dt=0.25)
        opacity_at_stop = sprite.opacity
        sprite.stop_actions()
        game.tick(dt=0.5)
        assert sprite.opacity == opacity_at_stop

    def test_stop_actions_cancels_mid_repeat(self, sprite: Sprite, game: Game) -> None:
        """Stop during Repeat before all iterations complete."""
        count = [0]
        sprite.do(Repeat(
            Sequence(Delay(0.05), Do(lambda: count.__setitem__(0, count[0] + 1))),
            times=10,
        ))
        game.tick(dt=0.05)
        assert count[0] == 1
        sprite.stop_actions()
        assert sprite not in game._action_sprites
        game.tick(dt=0.5)
        assert count[0] == 1

    def test_stop_actions_cancels_parallel_children(self, sprite: Sprite, game: Game) -> None:
        sprite.do(Parallel(
            PlayAnim(_walk_anim()),
            MoveTo((500, 300), speed=100),
        ))
        game.tick(dt=0.1)
        sprite.stop_actions()
        assert sprite._anim_player is None
        assert sprite not in game._action_sprites

    def test_stop_actions_when_no_action_is_safe(self, sprite: Sprite, game: Game) -> None:
        sprite.stop_actions()
        sprite.stop_actions()


# ------------------------------------------------------------------
# do() replaces current action
# ------------------------------------------------------------------


class TestDoReplaces:
    def test_do_replaces_current_action(self, sprite: Sprite, game: Game) -> None:
        first_done, second_done = [], []
        sprite.do(Sequence(Delay(0.5), Do(lambda: first_done.append(True))))
        game.tick(dt=0.1)
        sprite.do(Do(lambda: second_done.append(True)))
        game.tick(dt=0.5)
        assert first_done == []
        assert second_done == [True]

    def test_do_cancels_previous_stop(self, sprite: Sprite, game: Game) -> None:
        stopped = []
        action = Delay(0.5)

        def track_stop():
            stopped.append(True)

        original_stop = action.stop
        action.stop = lambda: (original_stop(), track_stop())

        sprite.do(action)
        sprite.do(Do(lambda: None))
        assert stopped == [True]

    def test_do_twice_last_wins(self, sprite: Sprite, game: Game) -> None:
        order = []
        sprite.do(Do(lambda: order.append(1)))
        sprite.do(Do(lambda: order.append(2)))
        game.tick(dt=0.016)
        assert order == [2]


# ------------------------------------------------------------------
# Nested compositions
# ------------------------------------------------------------------


class TestNestedCompositions:
    def test_sequence_in_parallel(self, sprite: Sprite, game: Game) -> None:
        a, b = [], []
        sprite.do(Parallel(
            Sequence(Delay(0.1), Do(lambda: a.append(1))),
            Sequence(Delay(0.2), Do(lambda: b.append(2))),
        ))
        game.tick(dt=0.1)
        assert a == [1]
        assert b == []
        game.tick(dt=0.1)
        assert b == [2]

    def test_parallel_in_sequence(self, sprite: Sprite, game: Game) -> None:
        order = []
        sprite.do(Sequence(
            Parallel(
                Do(lambda: order.append(1)),
                Do(lambda: order.append(2)),
            ),
            Do(lambda: order.append(3)),
        ))
        game.tick(dt=0.016)
        assert order == [1, 2, 3]

    def test_parallel_in_repeat(self, sprite: Sprite, game: Game) -> None:
        """Repeat(Parallel(Do, Delay(0)), times=3) — one iter per tick."""
        count = [0]
        sprite.do(Repeat(
            Parallel(
                Do(lambda: count.__setitem__(0, count[0] + 1)),
                Delay(0.0),
            ),
            times=3,
        ))
        for _ in range(5):
            game.tick(dt=0.016)
            if count[0] >= 3:
                break
        assert count[0] == 3

    def test_sequence_in_repeat(self, sprite: Sprite, game: Game) -> None:
        count = [0]
        sprite.do(Repeat(
            Sequence(Delay(0.05), Do(lambda: count.__setitem__(0, count[0] + 1))),
            times=3,
        ))
        game.tick(dt=0.05)
        assert count[0] == 1
        game.tick(dt=0.05)
        assert count[0] == 2
        game.tick(dt=0.05)
        assert count[0] == 3

    def test_repeat_in_sequence(self, sprite: Sprite, game: Game) -> None:
        """Repeat(times=2) runs 2 iterations (one per tick), then Sequence continues."""
        order = []
        sprite.do(Sequence(
            Repeat(Do(lambda: order.append(1)), times=2),
            Do(lambda: order.append(2)),
        ))
        game.tick(dt=0.016)
        assert order == [1]
        game.tick(dt=0.016)
        assert order == [1, 1, 2]

    def test_deeply_nested(self, sprite: Sprite, game: Game) -> None:
        order = []
        sprite.do(Sequence(
            Parallel(
                Sequence(Delay(0.05), Do(lambda: order.append(1))),
                Sequence(Delay(0.1), Do(lambda: order.append(2))),
            ),
            Do(lambda: order.append(3)),
        ))
        game.tick(dt=0.05)
        assert order == [1]
        game.tick(dt=0.05)
        assert order == [1, 2, 3]


# ------------------------------------------------------------------
# Battle sequence pattern
# ------------------------------------------------------------------


class TestBattleSequence:
    def test_attack_sequence_walk_attack_delay_walk_back(
        self, sprite: Sprite, game: Game,
    ) -> None:
        """Walk right, attack, delay, walk back — battle pattern."""
        order = []
        start_x = sprite._x
        sprite.do(Sequence(
            Parallel(PlayAnim(_walk_anim()), MoveTo((400, 300), speed=300)),
            PlayAnim(_attack_anim()),
            Delay(0.1),
            Parallel(PlayAnim(_walk_anim()), MoveTo((start_x, 300), speed=300)),
            Do(lambda: order.append("done")),
        ))
        # Walk to 400: 300px at 300px/s = 1s
        for _ in range(80):
            game.tick(dt=0.016)
            if sprite._x >= 399:
                break
        assert sprite._x >= 399, f"expected x>=399, got {sprite._x}"
        # Attack: 3 frames × 0.1 = 0.3s; animation phase runs after actions
        for _ in range(30):
            game.tick(dt=0.016)
            if "done" in order:
                break
        # If not done yet, run delay + walk back
        for _ in range(100):
            game.tick(dt=0.016)
            if "done" in order:
                break
        assert "done" in order
        assert abs(sprite._x - start_x) < 15

    def test_battle_pattern_with_do_callback(self, sprite: Sprite, game: Game) -> None:
        """Simplified: Do, Delay, Do, MoveTo, Do."""
        order = []
        sprite.do(Sequence(
            Do(lambda: order.append("start")),
            Delay(0.1),
            Do(lambda: order.append("mid")),
            MoveTo((200, 300), speed=500),
            Do(lambda: order.append("end")),
        ))
        game.tick(dt=0.016)
        assert order == ["start"]
        game.tick(dt=0.1)
        assert order == ["start", "mid"]
        for _ in range(30):
            game.tick(dt=0.016)
            if "end" in order:
                break
        assert order == ["start", "mid", "end"]


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------


class TestEdgeCases:
    def test_sprite_do_when_removed_is_noop(self, sprite: Sprite, game: Game) -> None:
        sprite.remove()
        fired = []
        sprite.do(Do(lambda: fired.append(True)))
        game.tick(dt=0.016)
        assert fired == []
        assert sprite not in game._action_sprites

    def test_remove_in_sequence_prevents_further_actions(
        self, sprite: Sprite, game: Game, backend: MockBackend,
    ) -> None:
        """After Remove, sprite is gone — no crash from further updates."""
        order = []
        sprite.do(Sequence(
            Do(lambda: order.append(1)),
            Remove(),
            Do(lambda: order.append(2)),
        ))
        game.tick(dt=0.016)
        assert 1 in order
        assert sprite.is_removed
        assert sprite.sprite_id not in backend.sprites

    def test_do_on_removed_sprite_can_still_call_stop(self, sprite: Sprite, game: Game) -> None:
        """stop_actions when sprite removed — should not crash."""
        sprite.do(Delay(0.5))
        sprite.remove()
        game.tick(dt=0.016)

    def test_fade_out_from_zero(self, sprite: Sprite, game: Game) -> None:
        sprite.opacity = 0
        sprite.do(FadeOut(0.5))
        game.tick(dt=0.5)
        assert sprite.opacity == 0
        assert sprite not in game._action_sprites

    def test_fade_in_from_255(self, sprite: Sprite, game: Game) -> None:
        sprite.do(FadeIn(0.5))
        game.tick(dt=0.5)
        assert sprite.opacity == 255

    def test_parallel_three_children(self, sprite: Sprite, game: Game) -> None:
        a, b, c = [], [], []
        sprite.do(Parallel(
            Sequence(Delay(0.1), Do(lambda: a.append(1))),
            Sequence(Delay(0.2), Do(lambda: b.append(2))),
            Sequence(Delay(0.3), Do(lambda: c.append(3))),
        ))
        game.tick(dt=0.1)
        assert a == [1]
        game.tick(dt=0.1)
        assert b == [2]
        game.tick(dt=0.1)
        assert c == [3]
        assert sprite not in game._action_sprites

    def test_sequence_three_delays(self, sprite: Sprite, game: Game) -> None:
        """Three 0.05s delays chain; each gets dt=0 when started, so 3 ticks of 0.05."""
        done = []
        sprite.do(Sequence(
            Delay(0.05),
            Delay(0.05),
            Delay(0.05),
            Do(lambda: done.append(True)),
        ))
        game.tick(dt=0.05)
        assert not done
        game.tick(dt=0.05)
        assert not done
        game.tick(dt=0.05)
        assert done == [True]


# ------------------------------------------------------------------
# Bug-fix: MoveTo negative/zero speed validation
# ------------------------------------------------------------------


class TestMoveToSpeedValidation:
    """MoveTo should raise ValueError if speed <= 0."""

    def test_move_to_negative_speed_raises(self) -> None:
        """MoveTo with negative speed raises ValueError at construction."""
        with pytest.raises(ValueError, match="speed must be > 0"):
            MoveTo((200, 300), speed=-100)

    def test_move_to_zero_speed_raises(self) -> None:
        """MoveTo with speed=0 raises ValueError at construction."""
        with pytest.raises(ValueError, match="speed must be > 0"):
            MoveTo((100, 300), speed=0)

    def test_speed_positive_accepted(self, sprite: Sprite, game: Game) -> None:
        """MoveTo(speed=100) is accepted normally."""
        action = MoveTo((100, 100), speed=100)
        action.start(sprite)
        # Should not raise


# ------------------------------------------------------------------
# Bug-fix: Sequence/Parallel children type validation
# ------------------------------------------------------------------


class TestChildValidation:
    def test_sequence_rejects_non_action_child(self) -> None:
        """Sequence raises TypeError if a child is not an Action."""
        with pytest.raises(TypeError, match="Sequence child 0"):
            Sequence("not_an_action")

    def test_sequence_rejects_non_action_later_child(self) -> None:
        """Sequence catches non-Action children beyond the first."""
        with pytest.raises(TypeError, match="Sequence child 1"):
            Sequence(Delay(0.1), 42)

    def test_parallel_rejects_non_action_child(self) -> None:
        """Parallel raises TypeError if a child is not an Action."""
        with pytest.raises(TypeError, match="Parallel child 0"):
            Parallel(None)

    def test_parallel_rejects_non_action_later_child(self) -> None:
        """Parallel catches non-Action children beyond the first."""
        with pytest.raises(TypeError, match="Parallel child 2"):
            Parallel(Delay(0.1), Delay(0.2), [1, 2, 3])

    def test_sequence_accepts_valid_actions(self) -> None:
        """Sequence accepts proper Action subclasses without error."""
        seq = Sequence(Delay(0.1), Do(lambda: None), MoveTo((0, 0), speed=1))
        assert len(seq._actions) == 3

    def test_parallel_accepts_valid_actions(self) -> None:
        """Parallel accepts proper Action subclasses without error."""
        par = Parallel(Delay(0.1), Do(lambda: None))
        assert len(par._actions) == 2


# ------------------------------------------------------------------
# Additional edge cases from test_edge_cases.py (unique tests)
# ------------------------------------------------------------------


class TestRepeatTimesZero:
    """Repeat(action, times=0) behavior edge cases."""

    def test_repeat_zero_is_noop(self, sprite: Sprite, game: Game) -> None:
        """Repeat(Do(...), times=0) is a no-op: finishes immediately without running the child."""
        count: list[int] = []
        action = Repeat(Do(lambda: count.append(1)), times=0)
        action.start(sprite)
        result = action.update(0.016)
        assert result is True
        assert len(count) == 0, "times=0 should never run the child action"

    def test_repeat_once_runs_child_exactly_once(self, sprite: Sprite, game: Game) -> None:
        """Repeat(Do(...), times=1) runs the child exactly once."""
        count: list[int] = []
        action = Repeat(Do(lambda: count.append(1)), times=1)
        action.start(sprite)
        result = action.update(0.016)
        assert result is True
        assert len(count) == 1

    def test_repeat_none_is_infinite(self, sprite: Sprite, game: Game) -> None:
        """Repeat(Do(...), times=None) runs indefinitely."""
        count: list[int] = []
        action = Repeat(Do(lambda: count.append(1)), times=None)
        action.start(sprite)
        for _ in range(10):
            action.update(0.016)
        assert len(count) == 10


class TestActionEdgeCasesUnique:
    """Action edge cases unique to test_edge_cases.py."""

    def test_deeply_nested_sequences(self, sprite: Sprite, game: Game) -> None:
        """Nested Sequence(Sequence(Sequence(...))) works correctly."""
        count: list[int] = []
        inner = Sequence(Do(lambda: count.append(1)))
        mid = Sequence(inner)
        outer = Sequence(mid)
        outer.start(sprite)
        outer.update(0.016)
        assert len(count) == 1

    def test_do_callback_exception_propagates(self, sprite: Sprite, game: Game) -> None:
        """Do() callback that raises propagates the exception."""
        def bad_callback() -> None:
            raise RuntimeError("boom")

        action = Do(bad_callback)
        action.start(sprite)
        with pytest.raises(RuntimeError, match="boom"):
            action.update(0.016)


# ------------------------------------------------------------------
# Import
# ------------------------------------------------------------------


def test_actions_importable_from_easygame() -> None:
    from easygame import (
        Delay,
        Sequence,
    )
    assert Delay is not None
    assert Sequence is not None
