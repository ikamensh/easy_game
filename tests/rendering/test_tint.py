"""Tests for Sprite tint: default value, getter/setter, backend sync, persistence, and edge cases."""

from pathlib import Path

import pytest

from easygame import Game, Scene, Sprite
from easygame.assets import AssetManager
from easygame.backends.mock_backend import MockBackend
from easygame.rendering.layers import SpriteAnchor


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    """Create a temporary asset directory with a test image."""
    images = tmp_path / "images"
    images.mkdir()
    sprites = images / "sprites"
    sprites.mkdir()
    (sprites / "knight.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def game(asset_dir: Path) -> Game:
    """Return a Game instance with assets pointing at the temp directory."""
    g = Game("Test", backend="mock", resolution=(1920, 1080))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    return g


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


# ------------------------------------------------------------------
# Default tint
# ------------------------------------------------------------------

def test_default_tint_is_white(game: Game) -> None:
    """A newly created sprite has tint (1.0, 1.0, 1.0) by default."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    assert sprite.tint == (1.0, 1.0, 1.0)


def test_default_tint_synced_to_backend(game: Game, backend: MockBackend) -> None:
    """The default tint (1.0, 1.0, 1.0) is recorded in the backend at creation."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    record = backend.sprites[sprite.sprite_id]
    assert record["tint"] == (1.0, 1.0, 1.0)


# ------------------------------------------------------------------
# Tint getter / setter
# ------------------------------------------------------------------

def test_tint_getter_returns_current_value(game: Game) -> None:
    """sprite.tint returns the value that was set."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.tint = (0.5, 0.3, 0.8)
    assert sprite.tint == (0.5, 0.3, 0.8)


# ------------------------------------------------------------------
# Backend sync on tint change
# ------------------------------------------------------------------

def test_set_tint_updates_backend(game: Game, backend: MockBackend) -> None:
    """Setting sprite.tint syncs the new value to the backend record."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.tint = (0.5, 0.2, 0.9)

    record = backend.sprites[sprite.sprite_id]
    assert record["tint"] == (0.5, 0.2, 0.9)


def test_set_tint_multiple_times(game: Game, backend: MockBackend) -> None:
    """Repeated tint changes each update the backend to the latest value."""
    sprite = Sprite("sprites/knight", position=(100, 100))

    sprite.tint = (1.0, 0.0, 0.0)
    assert backend.sprites[sprite.sprite_id]["tint"] == (1.0, 0.0, 0.0)

    sprite.tint = (0.0, 1.0, 0.0)
    assert backend.sprites[sprite.sprite_id]["tint"] == (0.0, 1.0, 0.0)

    sprite.tint = (0.0, 0.0, 1.0)
    assert backend.sprites[sprite.sprite_id]["tint"] == (0.0, 0.0, 1.0)


# ------------------------------------------------------------------
# Tint persists through position changes
# ------------------------------------------------------------------

def test_tint_persists_after_position_change(
    game: Game, backend: MockBackend,
) -> None:
    """Changing position does not reset the tint in the backend."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 100),
        anchor=SpriteAnchor.TOP_LEFT,
    )
    sprite.tint = (0.2, 0.4, 0.6)

    # Move the sprite — tint should survive the update_sprite call.
    sprite.position = (300, 400)

    record = backend.sprites[sprite.sprite_id]
    assert record["x"] == 300
    assert record["y"] == 400
    assert record["tint"] == (0.2, 0.4, 0.6)


def test_tint_persists_after_x_change(
    game: Game, backend: MockBackend,
) -> None:
    """Changing sprite.x alone does not reset the tint."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.TOP_LEFT,
    )
    sprite.tint = (0.1, 0.2, 0.3)
    sprite.x = 500

    record = backend.sprites[sprite.sprite_id]
    assert record["x"] == 500
    assert record["tint"] == (0.1, 0.2, 0.3)


def test_tint_persists_after_y_change(
    game: Game, backend: MockBackend,
) -> None:
    """Changing sprite.y alone does not reset the tint."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.TOP_LEFT,
    )
    sprite.tint = (0.9, 0.8, 0.7)
    sprite.y = 600

    record = backend.sprites[sprite.sprite_id]
    assert record["y"] == 600
    assert record["tint"] == (0.9, 0.8, 0.7)


# ------------------------------------------------------------------
# Constructor tint
# ------------------------------------------------------------------

def test_constructor_tint_sets_property(game: Game) -> None:
    """Passing tint= in the constructor sets the tint property."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 100),
        tint=(0.3, 0.6, 0.9),
    )
    assert sprite.tint == (0.3, 0.6, 0.9)


def test_constructor_tint_synced_to_backend(
    game: Game, backend: MockBackend,
) -> None:
    """Tint passed in the constructor is recorded in the backend."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 100),
        tint=(0.1, 0.5, 1.0),
    )
    record = backend.sprites[sprite.sprite_id]
    assert record["tint"] == (0.1, 0.5, 1.0)


# ==================================================================
# Edge case: Sprite tint components are not clamped to 0.0-1.0
# ==================================================================


class TestSpriteTint:
    """Sprite.tint components should be in [0.0, 1.0]; values outside
    this range are clamped."""

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
