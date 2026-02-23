"""Tests for AssetManager: loading, caching, @2x variants, errors."""

from pathlib import Path

import pytest

from easygame.assets import AssetManager, AssetNotFoundError
from easygame.backends.mock_backend import MockBackend


@pytest.fixture
def backend() -> MockBackend:
    return MockBackend()


@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    """Create a temporary asset directory with a few test images."""
    images = tmp_path / "images"
    images.mkdir()
    sprites = images / "sprites"
    sprites.mkdir()
    bgs = images / "backgrounds"
    bgs.mkdir()

    # Create minimal files (content doesn't matter — MockBackend doesn't read them).
    (sprites / "knight.png").write_bytes(b"png")
    (sprites / "knight@2x.png").write_bytes(b"png2x")
    (sprites / "tree.png").write_bytes(b"png")
    # tree has no @2x variant
    (bgs / "forest.jpg").write_bytes(b"jpg")
    # Animation frames for frames() tests
    for i in (1, 2, 3):
        (sprites / f"knight_walk_{i:02d}.png").write_bytes(b"png")
    return tmp_path


# ------------------------------------------------------------------
# Basic loading
# ------------------------------------------------------------------

def test_image_loads_png_by_name(backend: MockBackend, asset_dir: Path) -> None:
    """image('sprites/knight') loads <base>/images/sprites/knight.png."""
    mgr = AssetManager(backend, base_path=asset_dir)
    handle = mgr.image("sprites/knight")

    assert handle is not None
    # MockBackend.load_image was called with the full path.
    expected_path = str(asset_dir / "images" / "sprites" / "knight.png")
    assert expected_path in backend._loaded_images


def test_image_loads_with_explicit_extension(
    backend: MockBackend, asset_dir: Path,
) -> None:
    """image('backgrounds/forest.jpg') loads the .jpg directly."""
    mgr = AssetManager(backend, base_path=asset_dir)
    handle = mgr.image("backgrounds/forest.jpg")

    assert handle is not None
    expected_path = str(asset_dir / "images" / "backgrounds" / "forest.jpg")
    assert expected_path in backend._loaded_images


# ------------------------------------------------------------------
# Caching
# ------------------------------------------------------------------

def test_image_caches_by_name(backend: MockBackend, asset_dir: Path) -> None:
    """Calling image() twice with the same name returns the same handle."""
    mgr = AssetManager(backend, base_path=asset_dir)

    h1 = mgr.image("sprites/knight")
    h2 = mgr.image("sprites/knight")

    assert h1 is h2


def test_image_cache_keyed_by_name_not_path(
    backend: MockBackend, asset_dir: Path,
) -> None:
    """Different names produce different handles even if they could resolve similarly."""
    mgr = AssetManager(backend, base_path=asset_dir)

    h1 = mgr.image("sprites/knight")
    h2 = mgr.image("sprites/tree")

    assert h1 is not h2


# ------------------------------------------------------------------
# @2x variant loading
# ------------------------------------------------------------------

def test_prefers_2x_variant_when_scale_high(
    backend: MockBackend, asset_dir: Path,
) -> None:
    """With scale_factor >= 1.5, loads knight@2x.png instead of knight.png."""
    mgr = AssetManager(backend, base_path=asset_dir, scale_factor=2.0)
    handle = mgr.image("sprites/knight")

    expected_2x = str(asset_dir / "images" / "sprites" / "knight@2x.png")
    assert expected_2x in backend._loaded_images


def test_falls_back_to_1x_when_no_2x(
    backend: MockBackend, asset_dir: Path,
) -> None:
    """With high scale_factor but no @2x file, falls back to base image."""
    mgr = AssetManager(backend, base_path=asset_dir, scale_factor=2.0)
    handle = mgr.image("sprites/tree")

    expected_1x = str(asset_dir / "images" / "sprites" / "tree.png")
    assert expected_1x in backend._loaded_images
    # Confirm @2x was NOT loaded.
    expected_2x = str(asset_dir / "images" / "sprites" / "tree@2x.png")
    assert expected_2x not in backend._loaded_images


def test_loads_1x_when_scale_low(
    backend: MockBackend, asset_dir: Path,
) -> None:
    """With scale_factor < 1.5, always loads base file even if @2x exists."""
    mgr = AssetManager(backend, base_path=asset_dir, scale_factor=1.0)
    handle = mgr.image("sprites/knight")

    expected_1x = str(asset_dir / "images" / "sprites" / "knight.png")
    assert expected_1x in backend._loaded_images
    # Confirm @2x was NOT loaded.
    expected_2x = str(asset_dir / "images" / "sprites" / "knight@2x.png")
    assert expected_2x not in backend._loaded_images


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------

def test_missing_asset_raises_with_clear_message(
    backend: MockBackend, asset_dir: Path,
) -> None:
    """Loading a nonexistent asset raises AssetNotFoundError."""
    mgr = AssetManager(backend, base_path=asset_dir)

    with pytest.raises(AssetNotFoundError, match="nonexistent"):
        mgr.image("sprites/nonexistent")


def test_asset_not_found_error_is_file_not_found() -> None:
    """AssetNotFoundError is a subclass of FileNotFoundError."""
    assert issubclass(AssetNotFoundError, FileNotFoundError)


def test_missing_asset_message_includes_tried_paths(
    backend: MockBackend, asset_dir: Path,
) -> None:
    """Error message lists all paths that were tried."""
    mgr = AssetManager(backend, base_path=asset_dir, scale_factor=2.0)

    with pytest.raises(AssetNotFoundError) as exc_info:
        mgr.image("sprites/ghost")

    msg = str(exc_info.value)
    assert "ghost.png" in msg
    assert "ghost@2x.png" in msg


# ------------------------------------------------------------------
# frames() — animation frame discovery
# ------------------------------------------------------------------

def test_frames_discovers_numbered_files(
    backend: MockBackend, asset_dir: Path,
) -> None:
    """frames('sprites/knight_walk') returns sorted list of asset names."""
    mgr = AssetManager(backend, base_path=asset_dir)
    names = mgr.frames("sprites/knight_walk")

    assert names == [
        "sprites/knight_walk_01",
        "sprites/knight_walk_02",
        "sprites/knight_walk_03",
    ]


def test_frames_caches_result(backend: MockBackend, asset_dir: Path) -> None:
    """Calling frames() twice returns the same list (cached)."""
    mgr = AssetManager(backend, base_path=asset_dir)

    r1 = mgr.frames("sprites/knight_walk")
    r2 = mgr.frames("sprites/knight_walk")

    assert r1 is r2


def test_frames_missing_prefix_raises(
    backend: MockBackend, asset_dir: Path,
) -> None:
    """frames() with no matching files raises AssetNotFoundError."""
    mgr = AssetManager(backend, base_path=asset_dir)

    with pytest.raises(AssetNotFoundError, match="No animation frames"):
        mgr.frames("sprites/nonexistent_anim")


# ------------------------------------------------------------------
# Game.assets integration
# ------------------------------------------------------------------

def test_game_asset_path_parameter_uses_custom_path(
    asset_dir: Path,
) -> None:
    """Game(asset_path=...) creates AssetManager with that base path."""
    from easygame import Game

    game = Game(
        "Test",
        backend="mock",
        resolution=(800, 600),
        asset_path=asset_dir,
    )
    handle = game.assets.image("sprites/knight")

    assert handle is not None
    expected_path = str(asset_dir / "images" / "sprites" / "knight.png")
    assert expected_path in game.backend._loaded_images


def test_game_assets_property_creates_manager() -> None:
    """Game.assets lazily creates an AssetManager."""
    from easygame import Game

    game = Game("Test", backend="mock", resolution=(800, 600))
    mgr = game.assets

    assert isinstance(mgr, AssetManager)


def test_game_assets_is_same_instance() -> None:
    """Accessing game.assets twice returns the same instance."""
    from easygame import Game

    game = Game("Test", backend="mock", resolution=(800, 600))

    assert game.assets is game.assets


def test_game_assets_can_be_overridden() -> None:
    """game.assets can be set to a custom AssetManager (overrides asset_path)."""
    from easygame import Game

    game = Game(
        "Test",
        backend="mock",
        resolution=(800, 600),
        asset_path="ignored_path",
    )
    custom = AssetManager(game.backend, base_path=Path("/custom"))
    game.assets = custom

    assert game.assets is custom
