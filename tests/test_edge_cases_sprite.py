"""Edge-case tests for Sprite: teardown, removed sprite, NaN/Inf, lifecycle hooks."""

from pathlib import Path

import pytest

from easygame import Game, Scene, Sprite
from easygame.actions import Action
from easygame.assets import AssetManager
from easygame.backends.mock_backend import MockBackend
from easygame.rendering.layers import SpriteAnchor


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    """Create a temporary asset directory with test images."""
    images = tmp_path / "images"
    images.mkdir()
    sprites = images / "sprites"
    sprites.mkdir()
    (sprites / "knight.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def game(asset_dir: Path) -> Game:
    """Game with mock backend and assets."""
    g = Game("Test", backend="mock", resolution=(1920, 1080))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    yield g
    g._teardown()


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


# ------------------------------------------------------------------
# 1. Sprite creation after Game.quit() / teardown
# ------------------------------------------------------------------


def test_sprite_creation_after_teardown_raises_runtime_error(
    game: Game,
) -> None:
    """Creating a Sprite after _teardown() raises RuntimeError (no active Game)."""
    game._teardown()

    with pytest.raises(RuntimeError, match="No active Game"):
        Sprite("sprites/knight")


# ------------------------------------------------------------------
# 2. Sprite property setters on removed sprite
# ------------------------------------------------------------------


def test_setters_on_removed_sprite_do_not_sync_to_backend(
    game: Game, backend: MockBackend
) -> None:
    """Setting position, x, y, opacity, visible, tint on removed sprite does not sync."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.TOP_LEFT,
    )
    sid = sprite.sprite_id
    backend.update_sprite(sid, 999, 999, opacity=50, visible=False)

    sprite.remove()

    # These should not crash; _sync_to_backend returns early when _removed.
    sprite.position = (0, 0)
    sprite.x = 500
    sprite.y = 500
    sprite.opacity = 128
    sprite.visible = True
    sprite.tint = (0.5, 0.5, 0.5)

    # Backend state unchanged (sprite was removed, so backend no longer has it).
    assert sid not in backend.sprites


def test_setters_on_removed_sprite_update_internal_state(game: Game) -> None:
    """Removed sprite setters still update internal state (for consistency)."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.remove()

    sprite.position = (200, 300)
    sprite.opacity = 64

    assert sprite.position == (200, 300)
    assert sprite.x == 200
    assert sprite.y == 300
    assert sprite.opacity == 64


# ------------------------------------------------------------------
# 3. None, NaN/Inf position, x, y
# ------------------------------------------------------------------


def test_position_none_raises_value_error(game: Game) -> None:
    """Setting position to None raises ValueError with clear message."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.TOP_LEFT,
    )
    with pytest.raises(ValueError, match="cannot be None"):
        sprite.position = None  # type: ignore[assignment]


def test_position_nan_raises_value_error(game: Game) -> None:
    """Setting position to NaN raises ValueError."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.TOP_LEFT,
    )
    with pytest.raises(ValueError, match="finite"):
        sprite.position = (float("nan"), 200)


def test_position_inf_raises_value_error(game: Game) -> None:
    """Setting position to Inf raises ValueError."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.TOP_LEFT,
    )
    with pytest.raises(ValueError, match="finite"):
        sprite.position = (float("inf"), 200)


def test_x_nan_raises_value_error(game: Game) -> None:
    """Setting x to NaN raises ValueError."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.TOP_LEFT,
    )
    with pytest.raises(ValueError, match="finite"):
        sprite.x = float("nan")


def test_y_nan_raises_value_error(game: Game) -> None:
    """Setting y to NaN raises ValueError."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.TOP_LEFT,
    )
    with pytest.raises(ValueError, match="finite"):
        sprite.y = float("nan")


def test_constructor_position_nan_raises(game: Game) -> None:
    """Sprite constructor with NaN position raises ValueError."""
    with pytest.raises(ValueError, match="finite"):
        Sprite(
            "sprites/knight",
            position=(float("nan"), 100),
            anchor=SpriteAnchor.TOP_LEFT,
        )


# ------------------------------------------------------------------
# 4. NaN/Inf opacity (clamped to [0, 255])
# ------------------------------------------------------------------


def test_opacity_nan_clamped_to_zero(game: Game) -> None:
    """opacity=NaN is clamped to 0 (non-finite handled before int())."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.opacity = float("nan")
    assert sprite.opacity == 0


def test_opacity_inf_clamped_to_255(game: Game) -> None:
    """opacity=Inf is clamped to 255 (non-finite handled before int())."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.opacity = float("inf")
    assert sprite.opacity == 255


def test_tint_nan_clamped_by_min_max(game: Game, backend: MockBackend) -> None:
    """tint with NaN is clamped via min/max (Python 3.12+ returns non-NaN)."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.tint = (float("nan"), 0.5, float("nan"))

    # min(1, nan) and max(0, ...) behavior: NaN channel becomes 1.0 or 0.0
    assert all(
        isinstance(c, float) and 0.0 <= c <= 1.0 for c in sprite.tint
    )
    assert backend.sprites[sprite.sprite_id]["tint"] == sprite.tint


def test_tint_inf_clamped(game: Game, backend: MockBackend) -> None:
    """tint with Inf is clamped to [0, 1]."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.tint = (float("inf"), 0.0, float("-inf"))

    assert sprite.tint == (1.0, 0.0, 0.0)
    assert backend.sprites[sprite.sprite_id]["tint"] == (1.0, 0.0, 0.0)


# ------------------------------------------------------------------
# 5. sprite.do() on removed sprite
# ------------------------------------------------------------------


def test_do_on_removed_sprite_is_noop(game: Game) -> None:
    """sprite.do(action) on removed sprite returns immediately without registering."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.do(Action())
    sprite.remove()

    sprite.do(Action())  # should not crash

    assert sprite not in game._action_sprites


# ------------------------------------------------------------------
# 6. Sprite creation in on_reveal and on_exit
# ------------------------------------------------------------------


def test_sprite_creation_in_on_reveal(game: Game, backend: MockBackend) -> None:
    """Creating a Sprite in on_reveal works; sprite is valid and in backend."""
    created_sprite = None

    class SceneA(Scene):
        def on_reveal(self) -> None:
            nonlocal created_sprite
            created_sprite = Sprite("sprites/knight", position=(50, 50))

    class SceneB(Scene):
        def update(self, dt: float) -> None:
            self.game.pop()

    game.push(SceneA())
    game.push(SceneB())
    game.tick(dt=0.016)  # B.update pops; A gets on_reveal

    assert created_sprite is not None
    assert created_sprite.sprite_id in backend.sprites
    assert not created_sprite.is_removed


def test_sprite_creation_in_on_exit(game: Game, backend: MockBackend) -> None:
    """Creating a Sprite in on_exit works; sprite survives (unowned)."""
    created_sprite = None

    class SceneA(Scene):
        def on_exit(self) -> None:
            nonlocal created_sprite
            created_sprite = Sprite("sprites/knight", position=(75, 75))

    game.push(SceneA())
    game.pop()

    assert created_sprite is not None
    assert created_sprite.sprite_id in backend.sprites
    assert not created_sprite.is_removed
