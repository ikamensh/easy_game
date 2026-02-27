"""Comprehensive tests for Stage 11 ColorSwap system.

Tests ColorSwap class, palette registry, AssetManager.image_swapped,
Sprite color_swap/team_palette, and backend load_image_from_pil.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from PIL import Image

from easygame import (
    ColorSwap,
    Game,
    Sprite,
    get_palette,
    register_palette,
)
from easygame.assets import AssetManager, AssetNotFoundError
from easygame.backends.mock_backend import MockBackend


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    """Temp asset dir with a test image (red pixels)."""
    images = tmp_path / "images" / "sprites"
    images.mkdir(parents=True)
    # Create a 4x4 image: red (255,0,0) and dark red (200,0,0)
    img = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    pixels = img.load()
    pixels[0, 0] = (255, 0, 0, 255)
    pixels[1, 0] = (200, 0, 0, 200)
    pixels[2, 0] = (150, 0, 0, 128)
    pixels[0, 1] = (100, 50, 50, 255)  # not in source — unchanged
    pixels[1, 1] = (255, 0, 0, 100)   # red with low alpha
    img.save(images / "knight.png")
    return tmp_path


@pytest.fixture
def game(asset_dir: Path) -> Game:
    g = Game("Test", backend="mock", resolution=(800, 600))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    return g


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


# ------------------------------------------------------------------
# ColorSwap
# ------------------------------------------------------------------


class TestColorSwap:
    def test_swap_replaces_colors(self, asset_dir: Path) -> None:
        swap = ColorSwap(
            source_colors=[(255, 0, 0), (200, 0, 0), (150, 0, 0)],
            target_colors=[(0, 0, 255), (0, 0, 200), (0, 0, 150)],
        )
        path = asset_dir / "images" / "sprites" / "knight.png"
        result = swap.apply(str(path))
        pixels = result.load()
        assert pixels[0, 0] == (0, 0, 255, 255)
        assert pixels[1, 0] == (0, 0, 200, 200)
        assert pixels[2, 0] == (0, 0, 150, 128)

    def test_swap_preserves_alpha(self, asset_dir: Path) -> None:
        swap = ColorSwap(
            source_colors=[(255, 0, 0)],
            target_colors=[(0, 255, 0)],
        )
        path = asset_dir / "images" / "sprites" / "knight.png"
        result = swap.apply(str(path))
        pixels = result.load()
        assert pixels[0, 0] == (0, 255, 0, 255)
        assert pixels[1, 1] == (0, 255, 0, 100)

    def test_swap_unmatched_pixels_unchanged(self, asset_dir: Path) -> None:
        swap = ColorSwap(
            source_colors=[(255, 0, 0)],
            target_colors=[(0, 255, 0)],
        )
        path = asset_dir / "images" / "sprites" / "knight.png"
        result = swap.apply(str(path))
        pixels = result.load()
        assert pixels[0, 1] == (100, 50, 50, 255)

    def test_cache_key_uniqueness(self) -> None:
        a = ColorSwap([(1, 2, 3)], [(4, 5, 6)])
        b = ColorSwap([(1, 2, 3)], [(7, 8, 9)])
        assert a.cache_key() != b.cache_key()

    def test_cache_key_equality(self) -> None:
        a = ColorSwap([(1, 2, 3), (4, 5, 6)], [(7, 8, 9), (10, 11, 12)])
        b = ColorSwap([(1, 2, 3), (4, 5, 6)], [(7, 8, 9), (10, 11, 12)])
        assert a.cache_key() == b.cache_key()

    def test_cache_key_hashable(self) -> None:
        swap = ColorSwap([(255, 0, 0)], [(0, 0, 255)])
        key = swap.cache_key()
        d = {key: "ok"}
        assert d[swap.cache_key()] == "ok"

    def test_source_target_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            ColorSwap([(1, 2, 3)], [(4, 5, 6), (7, 8, 9)])

    def test_empty_swap(self, asset_dir: Path) -> None:
        swap = ColorSwap([], [])
        path = asset_dir / "images" / "sprites" / "knight.png"
        result = swap.apply(str(path))
        pixels = result.load()
        assert pixels[0, 0] == (255, 0, 0, 255)

    def test_apply_nonexistent_path_raises(self) -> None:
        swap = ColorSwap([(255, 0, 0)], [(0, 0, 255)])
        with pytest.raises(FileNotFoundError):
            swap.apply("/nonexistent/image.png")


# ------------------------------------------------------------------
# Palette registry
# ------------------------------------------------------------------


class TestPaletteRegistry:
    def test_register_and_get(self) -> None:
        swap = ColorSwap([(255, 0, 0)], [(0, 0, 255)])
        register_palette("blue", swap)
        assert get_palette("blue") is swap

    def test_get_unregistered_raises(self) -> None:
        with pytest.raises(KeyError, match="not registered"):
            get_palette("nonexistent")

    def test_register_overwrites(self) -> None:
        a = ColorSwap([(1, 0, 0)], [(0, 0, 1)])
        b = ColorSwap([(2, 0, 0)], [(0, 0, 2)])
        register_palette("x", a)
        register_palette("x", b)
        assert get_palette("x") is b


# ------------------------------------------------------------------
# AssetManager.image_swapped
# ------------------------------------------------------------------


class TestColorSwapAssetManager:
    def test_image_swapped_returns_handle(self, game: Game) -> None:
        swap = ColorSwap([(255, 0, 0)], [(0, 0, 255)])
        handle = game.assets.image_swapped("sprites/knight", swap)
        assert handle is not None
        assert game.backend.get_image_size(handle) == (4, 4)

    def test_image_swapped_cached(self, game: Game) -> None:
        swap = ColorSwap([(255, 0, 0)], [(0, 0, 255)])
        h1 = game.assets.image_swapped("sprites/knight", swap)
        h2 = game.assets.image_swapped("sprites/knight", swap)
        assert h1 is h2

    def test_image_swapped_different_swap_different_handle(self, game: Game) -> None:
        swap_blue = ColorSwap([(255, 0, 0)], [(0, 0, 255)])
        swap_green = ColorSwap([(255, 0, 0)], [(0, 255, 0)])
        h1 = game.assets.image_swapped("sprites/knight", swap_blue)
        h2 = game.assets.image_swapped("sprites/knight", swap_green)
        assert h1 != h2

    def test_image_swapped_missing_asset_raises(self, game: Game) -> None:
        swap = ColorSwap([(255, 0, 0)], [(0, 0, 255)])
        with pytest.raises(AssetNotFoundError, match="not found"):
            game.assets.image_swapped("sprites/nonexistent", swap)


# ------------------------------------------------------------------
# Backend load_image_from_pil
# ------------------------------------------------------------------


class TestLoadImageFromPil:
    def test_mock_backend_returns_handle(self, backend: MockBackend) -> None:
        img = Image.new("RGBA", (32, 48), (255, 0, 0, 255))
        handle = backend.load_image_from_pil(img)
        assert handle is not None
        assert backend.get_image_size(handle) == (32, 48)

    def test_mock_backend_unique_handles(self, backend: MockBackend) -> None:
        img = Image.new("RGBA", (8, 8), (0, 0, 0, 255))
        h1 = backend.load_image_from_pil(img)
        h2 = backend.load_image_from_pil(img)
        assert h1 != h2


# ------------------------------------------------------------------
# Sprite with color_swap and team_palette
# ------------------------------------------------------------------


class TestColorSwapSprite:
    def test_sprite_with_color_swap(self, game: Game, backend: MockBackend) -> None:
        swap = ColorSwap([(255, 0, 0)], [(0, 0, 255)])
        sprite = Sprite("sprites/knight", color_swap=swap)
        assert sprite.sprite_id in backend.sprites
        # Handle should be from swapped image (different from plain)
        plain_handle = game.assets.image("sprites/knight")
        swapped_handle = game.assets.image_swapped("sprites/knight", swap)
        record = backend.sprites[sprite.sprite_id]
        assert record["image"] == swapped_handle
        assert record["image"] != plain_handle

    def test_sprite_with_team_palette(
        self, game: Game, backend: MockBackend,
    ) -> None:
        swap = ColorSwap([(255, 0, 0)], [(0, 255, 0)])
        register_palette("green", swap)
        sprite = Sprite("sprites/knight", team_palette="green")
        swapped_handle = game.assets.image_swapped("sprites/knight", swap)
        record = backend.sprites[sprite.sprite_id]
        assert record["image"] == swapped_handle

    def test_color_swap_takes_precedence_over_team_palette(
        self, game: Game, backend: MockBackend,
    ) -> None:
        swap_direct = ColorSwap([(255, 0, 0)], [(0, 0, 255)])
        swap_palette = ColorSwap([(255, 0, 0)], [(0, 255, 0)])
        register_palette("green", swap_palette)
        sprite = Sprite(
            "sprites/knight",
            color_swap=swap_direct,
            team_palette="green",
        )
        expected = game.assets.image_swapped("sprites/knight", swap_direct)
        record = backend.sprites[sprite.sprite_id]
        assert record["image"] == expected

    def test_sprite_team_palette_unregistered_raises(self, game: Game) -> None:
        with pytest.raises(KeyError, match="not registered"):
            Sprite("sprites/knight", team_palette="nonexistent")

    def test_sprite_without_swap_uses_plain_image(
        self, game: Game, backend: MockBackend,
    ) -> None:
        sprite = Sprite("sprites/knight")
        plain_handle = game.assets.image("sprites/knight")
        record = backend.sprites[sprite.sprite_id]
        assert record["image"] == plain_handle


# ------------------------------------------------------------------
# Integration
# ------------------------------------------------------------------


class TestColorSwapIntegration:
    def test_two_sprites_same_swap_same_handle(
        self, game: Game, backend: MockBackend,
    ) -> None:
        swap = ColorSwap([(255, 0, 0)], [(0, 0, 255)])
        s1 = Sprite("sprites/knight", position=(100, 300), color_swap=swap)
        s2 = Sprite("sprites/knight", position=(200, 300), color_swap=swap)
        assert backend.sprites[s1.sprite_id]["image"] == backend.sprites[s2.sprite_id]["image"]

    def test_sprite_dimensions_correct_after_swap(
        self, game: Game,
    ) -> None:
        swap = ColorSwap([(255, 0, 0)], [(0, 0, 255)])
        sprite = Sprite("sprites/knight", color_swap=swap)
        assert sprite._img_w == 4
        assert sprite._img_h == 4
