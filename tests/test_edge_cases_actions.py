"""Edge-case tests for composable Actions."""

import threading

from pathlib import Path

import pytest

from easygame import (
    Do,
    Game,
    MoveTo,
    Parallel,
    Repeat,
    Sequence,
    Sprite,
)
from easygame.actions import Action
from easygame.assets import AssetManager


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    """Temp asset dir with knight sprite."""
    images = tmp_path / "images" / "sprites"
    images.mkdir(parents=True)
    (images / "knight.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def game(asset_dir: Path) -> Game:
    g = Game("Test", backend="mock", resolution=(800, 600))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    yield g
    g._teardown()


@pytest.fixture
def sprite(game: Game) -> Sprite:
    return Sprite("sprites/knight", position=(100, 300))


# ------------------------------------------------------------------
# 1. Sequence() and Parallel() with no children
# ------------------------------------------------------------------


def test_sequence_empty_completes_immediately(sprite: Sprite) -> None:
    """Sequence() with no children completes immediately."""
    seq = Sequence()
    seq.start(sprite)
    assert seq.update(0.016) is True


def test_parallel_empty_completes_immediately(sprite: Sprite) -> None:
    """Parallel() with no children completes immediately."""
    par = Parallel()
    par.start(sprite)
    assert par.update(0.016) is True


# ------------------------------------------------------------------
# 2. Repeat(action, times=0) and Repeat(action, times=-1)
# ------------------------------------------------------------------


def test_repeat_times_zero_completes_immediately(sprite: Sprite) -> None:
    """Repeat(action, times=0) completes immediately without running action."""
    ran = []

    seq = Sequence(Do(lambda: ran.append(1)))
    rep = Repeat(seq, times=0)
    rep.start(sprite)
    assert rep.update(0.016) is True
    assert ran == []


def test_repeat_times_negative_completes_immediately(sprite: Sprite) -> None:
    """Repeat(action, times=-1) completes immediately (treated like times=0)."""
    ran = []

    seq = Sequence(Do(lambda: ran.append(1)))
    rep = Repeat(seq, times=-1)
    rep.start(sprite)
    assert rep.update(0.016) is True
    assert ran == []


# ------------------------------------------------------------------
# 3. Sequence with child that immediately finishes
# ------------------------------------------------------------------


def test_sequence_instant_children_chain_in_same_frame(sprite: Sprite) -> None:
    """Sequence with instant children (Do) runs all in same update."""
    order = []

    seq = Sequence(
        Do(lambda: order.append(1)),
        Do(lambda: order.append(2)),
        Do(lambda: order.append(3)),
    )
    seq.start(sprite)
    done = seq.update(0.016)

    assert done is True
    assert order == [1, 2, 3]


# ------------------------------------------------------------------
# 4. Deeply nested actions (100 levels)
# ------------------------------------------------------------------


def test_deeply_nested_sequence_100_levels(sprite: Sprite) -> None:
    """Sequence nested 100 levels deep completes without stack overflow."""
    order = []

    inner = Do(lambda: order.append(1))
    for _ in range(99):
        inner = Sequence(inner)

    seq = Sequence(inner)
    seq.start(sprite)
    done = seq.update(0.016)

    assert done is True
    assert order == [1]


# ------------------------------------------------------------------
# 5. MoveTo with NaN/Inf target position
# ------------------------------------------------------------------


def test_move_to_nan_target_raises_in_init(sprite: Sprite) -> None:
    """MoveTo with NaN target raises ValueError in __init__ (fail fast)."""
    with pytest.raises(ValueError, match="finite"):
        MoveTo((float("nan"), 300), speed=100)


def test_move_to_inf_target_raises_in_init(sprite: Sprite) -> None:
    """MoveTo with Inf target raises ValueError in __init__ (fail fast)."""
    with pytest.raises(ValueError, match="finite"):
        MoveTo((float("inf"), 300), speed=100)


# ------------------------------------------------------------------
# 6. MoveTo with extremely large speed
# ------------------------------------------------------------------


def test_move_to_extremely_large_speed(sprite: Sprite) -> None:
    """MoveTo with very large speed completes in one frame without error."""
    move = MoveTo((500, 400), speed=1e12)
    move.start(sprite)

    done = move.update(0.016)
    assert done is True
    assert sprite.position == (500, 400)


# ------------------------------------------------------------------
# 7. Repeat with non-Action child
# ------------------------------------------------------------------


def test_repeat_non_action_raises_in_init(sprite: Sprite) -> None:
    """Repeat with non-Action child raises TypeError in __init__."""
    with pytest.raises(TypeError, match="Action"):
        Repeat(123, times=1)


# ------------------------------------------------------------------
# 8. Repeat with action that cannot be deep-copied
# ------------------------------------------------------------------


def test_repeat_uncopyable_action_raises(sprite: Sprite) -> None:
    """Repeat with action containing uncopyable state (e.g. Lock) raises on deepcopy."""

    class ActionWithLock(Action):
        def __init__(self) -> None:
            self._lock = threading.Lock()

    rep = Repeat(ActionWithLock(), times=2)

    with pytest.raises((TypeError, AttributeError)):
        rep.start(sprite)
