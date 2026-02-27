"""Tests for TweenManager, tween(), Sprite.move_to(), and tween edge cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from easygame import Game, Sprite, Ease, tween
from easygame.assets import AssetManager
from easygame.rendering.layers import SpriteAnchor
from easygame.util.tween import TweenManager


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    """Temp asset dir with knight.png."""
    images = tmp_path / "images" / "sprites"
    images.mkdir(parents=True)
    (images / "knight.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def game(asset_dir: Path) -> Game:
    g = Game("Test", backend="mock", resolution=(800, 600))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    return g


class Box:
    """Simple target for tweens with a numeric property."""

    def __init__(self, value: float = 0.0) -> None:
        self.x = value


# ------------------------------------------------------------------
# tween() basics
# ------------------------------------------------------------------


def test_tween_reaches_target_after_duration(game: Game) -> None:
    """tween() reaches target value after duration."""
    obj = type("Obj", (), {"val": 0.0})()
    tid = tween(obj, "val", 0.0, 100.0, 0.5)

    game.tick(dt=0.25)
    assert 0 < obj.val < 100
    game.tick(dt=0.25)
    assert obj.val == 100.0

    game.cancel_tween(tid)


def test_tween_on_complete_fires_once(game: Game) -> None:
    """on_complete fires exactly once when tween finishes."""
    obj = type("Obj", (), {"val": 0.0})()
    fired = []
    tween(obj, "val", 0.0, 1.0, 0.2, on_complete=lambda: fired.append(True))

    game.tick(dt=0.1)
    assert len(fired) == 0
    game.tick(dt=0.1)
    assert len(fired) == 1
    game.tick(dt=0.5)
    assert len(fired) == 1


def test_tween_cancel_stops_at_current_value(game: Game) -> None:
    """cancel_tween() stops interpolation at current value."""
    obj = type("Obj", (), {"val": 0.0})()
    tid = tween(obj, "val", 0.0, 100.0, 1.0)

    game.tick(dt=0.3)
    mid_val = obj.val
    game.cancel_tween(tid)
    game.tick(dt=1.0)
    assert obj.val == mid_val


def test_tween_ease_linear_at_half(game: Game) -> None:
    """Linear ease: 50% progress = 50% value."""
    obj = type("Obj", (), {"val": 0.0})()
    tween(obj, "val", 0.0, 100.0, 0.4, ease=Ease.LINEAR)

    game.tick(dt=0.2)
    assert abs(obj.val - 50.0) < 1.0


def test_tween_ease_in_at_half(game: Game) -> None:
    """Ease-in: 50% progress < 50% value (slow start)."""
    obj = type("Obj", (), {"val": 0.0})()
    tween(obj, "val", 0.0, 100.0, 0.4, ease=Ease.EASE_IN)

    game.tick(dt=0.2)
    assert obj.val < 50.0


def test_tween_ease_out_at_half(game: Game) -> None:
    """Ease-out: 50% progress > 50% value (slow end)."""
    obj = type("Obj", (), {"val": 0.0})()
    tween(obj, "val", 0.0, 100.0, 0.4, ease=Ease.EASE_OUT)

    game.tick(dt=0.2)
    assert obj.val > 50.0


def test_tween_sprite_x_updates_backend(game: Game) -> None:
    """Tweening sprite.x updates backend position."""
    sprite = Sprite(
        "sprites/knight", position=(100, 200), anchor=SpriteAnchor.TOP_LEFT,
    )
    tween(sprite, "x", 100.0, 300.0, 0.5)

    game.tick(dt=0.25)
    assert 100 < sprite.x < 300
    record = game.backend.sprites[sprite.sprite_id]
    assert 100 < record["x"] < 300


def test_tween_no_game_raises(game: Game) -> None:
    """tween() before Game raises RuntimeError."""
    import easygame.util.tween as tween_mod

    old = tween_mod._tween_manager
    tween_mod._tween_manager = None
    try:
        obj = type("Obj", (), {"val": 0.0})()
        with pytest.raises(RuntimeError, match="No active Game"):
            tween(obj, "val", 0.0, 1.0, 0.5)
    finally:
        tween_mod._tween_manager = old


# ------------------------------------------------------------------
# Sprite.move_to()
# ------------------------------------------------------------------


def test_move_to_reaches_target(game: Game) -> None:
    """Sprite reaches target position after distance/speed seconds."""
    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    # Distance = 300, speed = 100 -> duration = 3s
    sprite.move_to((400, 100), speed=100.0)

    game.tick(dt=1.0)
    assert 100 < sprite.x < 400
    game.tick(dt=1.0)
    assert 200 < sprite.x < 400
    game.tick(dt=1.0)
    assert sprite.x == 400.0
    assert sprite.y == 100.0


def test_move_to_on_arrive_fires(game: Game) -> None:
    """on_arrive fires when movement completes."""
    sprite = Sprite(
        "sprites/knight", position=(0, 0), anchor=SpriteAnchor.TOP_LEFT,
    )
    arrived = []
    sprite.move_to((100, 0), speed=100.0, on_arrive=lambda: arrived.append(True))

    game.tick(dt=0.5)  # Halfway
    assert len(arrived) == 0
    game.tick(dt=0.5)  # Finish (duration=1.0)
    assert len(arrived) == 1


def test_move_to_zero_distance_fires_immediately(game: Game) -> None:
    """Zero distance fires on_arrive immediately."""
    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    arrived = []
    sprite.move_to((100, 100), speed=100.0, on_arrive=lambda: arrived.append(True))

    assert len(arrived) == 1
    assert sprite.x == 100
    assert sprite.y == 100


def test_move_to_cancels_previous(game: Game) -> None:
    """New move_to cancels previous movement."""
    sprite = Sprite(
        "sprites/knight", position=(0, 0), anchor=SpriteAnchor.TOP_LEFT,
    )
    arrived_first = []
    arrived_second = []
    sprite.move_to((200, 0), speed=100.0, on_arrive=lambda: arrived_first.append(1))
    sprite.move_to((50, 0), speed=100.0, on_arrive=lambda: arrived_second.append(1))

    game.tick(dt=0.2)  # Moving to 50 (duration 0.5s), not yet there
    assert len(arrived_first) == 0
    assert len(arrived_second) == 0
    game.tick(dt=0.4)  # Finish move to 50
    assert len(arrived_first) == 0
    assert len(arrived_second) == 1
    assert sprite.x == 50.0


def test_move_to_on_removed_sprite_is_noop(game: Game) -> None:
    """move_to on removed sprite is no-op."""
    sprite = Sprite(
        "sprites/knight", position=(100, 100), anchor=SpriteAnchor.TOP_LEFT,
    )
    sprite.remove()
    sprite.move_to((200, 200), speed=100.0)  # Should not raise


def test_remove_cancels_move_tweens(game: Game) -> None:
    """Sprite.remove() cancels active move tweens."""
    sprite = Sprite(
        "sprites/knight", position=(0, 0), anchor=SpriteAnchor.TOP_LEFT,
    )
    arrived = []
    sprite.move_to((100, 0), speed=10.0, on_arrive=lambda: arrived.append(1))
    sprite.remove()

    game.tick(dt=20.0)  # Would have completed
    assert len(arrived) == 0


# ------------------------------------------------------------------
# Tween edge cases: duration=0, from==to
# ------------------------------------------------------------------


def test_tween_duration_zero_completes_on_next_update(game: Game) -> None:
    """Tween with duration=0 completes on the next update."""
    box = Box(100.0)
    completed = []

    tween(box, "x", 100.0, 200.0, 0.0, on_complete=lambda: completed.append(True))
    assert box.x == 100.0

    game._tween_manager.update(dt=0.016)

    assert box.x == 200.0
    assert completed == [True]


def test_tween_from_val_equals_to_val(game: Game) -> None:
    """Tween with from_val == to_val completes normally; value stays constant."""
    box = Box(50.0)
    completed = []

    tween(box, "x", 50.0, 50.0, 0.1, on_complete=lambda: completed.append(True))

    game._tween_manager.update(dt=0.05)
    assert box.x == 50.0
    assert completed == []

    game._tween_manager.update(dt=0.06)
    assert box.x == 50.0
    assert completed == [True]


# ------------------------------------------------------------------
# Tween callback interactions
# ------------------------------------------------------------------


def test_tween_on_complete_creates_new_tween(game: Game) -> None:
    """Tween on_complete that creates a new tween; new tween runs on subsequent updates."""
    box = Box(0.0)
    completed = []

    def first_done() -> None:
        completed.append("first")
        tween(box, "x", 100.0, 200.0, 0.0, on_complete=lambda: completed.append("second"))

    tween(box, "x", 0.0, 100.0, 0.0, on_complete=first_done)

    game._tween_manager.update(dt=0.016)
    assert completed == ["first"]
    assert box.x == 100.0

    game._tween_manager.update(dt=0.016)
    assert completed == ["first", "second"]
    assert box.x == 200.0


def test_tween_on_complete_cancels_other_tween(game: Game) -> None:
    """Tween on_complete that cancels another tween does not crash."""
    box = Box(0.0)
    tid2 = [None]

    tid1 = tween(
        box,
        "x",
        0.0,
        100.0,
        0.0,
        on_complete=lambda: game.cancel_tween(tid2[0]),
    )
    tid2[0] = tween(box, "x", 50.0, 150.0, 1.0)

    game._tween_manager.update(dt=0.016)

    assert box.x == 100.0
    assert tid2[0] not in game._tween_manager._tweens


# ------------------------------------------------------------------
# Tween dt edge cases: negative, NaN, Inf
# ------------------------------------------------------------------


def test_tween_update_negative_dt(game: Game) -> None:
    """Tween update with negative dt: elapsed can decrease."""
    box = Box(0.0)

    tween(box, "x", 0.0, 100.0, 1.0)
    game._tween_manager.update(dt=0.5)
    assert 0 < box.x < 100

    game._tween_manager.update(dt=-0.3)
    game._tween_manager.update(dt=0.9)
    assert box.x == 100.0


def test_tween_update_nan_dt_skipped(game: Game) -> None:
    """Tween update with NaN dt returns immediately; tween state unchanged; next valid dt advances."""
    box = Box(0.0)
    completed = []

    tween(box, "x", 0.0, 100.0, 1.0, on_complete=lambda: completed.append(True))
    game._tween_manager.update(dt=float("nan"))  # no-op
    assert box.x == 0.0
    assert completed == []

    game._tween_manager.update(dt=1.0)
    assert box.x == 100.0
    assert completed == [True]


def test_tween_update_inf_dt_skipped(game: Game) -> None:
    """Tween update with Inf dt returns immediately (non-finite); next valid dt completes."""
    box = Box(0.0)
    completed = []

    tween(box, "x", 0.0, 100.0, 1.0, on_complete=lambda: completed.append(True))
    game._tween_manager.update(dt=float("inf"))  # no-op
    assert box.x == 0.0
    assert completed == []
    game._tween_manager.update(dt=1.0)
    assert box.x == 100.0
    assert completed == [True]


# ------------------------------------------------------------------
# Tween input validation: NaN/Inf rejection for from_val and to_val
# ------------------------------------------------------------------


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
