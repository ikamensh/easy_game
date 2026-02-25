"""Tests for Sprite: creation, position sync, anchor offsets, y-sort, removal."""

from pathlib import Path

import pytest

from easygame import Game, Scene, Sprite
from easygame.assets import AssetManager
from easygame.backends.mock_backend import MockBackend
from easygame.rendering.layers import RenderLayer, SpriteAnchor
from easygame.rendering.sprite import _anchor_offset, _current_game


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
    (sprites / "tree.png").write_bytes(b"png")
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
# Basic creation
# ------------------------------------------------------------------

def test_create_sprite_registers_in_backend(game: Game, backend: MockBackend) -> None:
    """Creating a Sprite calls backend.create_sprite and records it."""
    sprite = Sprite("sprites/knight", position=(400, 300))

    assert sprite.sprite_id in backend.sprites


def test_create_sprite_correct_image_handle(game: Game, backend: MockBackend) -> None:
    """The backend sprite uses the image handle from the asset manager."""
    sprite = Sprite("sprites/knight", position=(100, 200))

    record = backend.sprites[sprite.sprite_id]
    expected_handle = game.assets.image("sprites/knight")
    assert record["image"] == expected_handle


def test_create_sprite_default_layer_is_units(game: Game, backend: MockBackend) -> None:
    """Default layer is RenderLayer.UNITS."""
    sprite = Sprite("sprites/knight")
    assert sprite.layer == RenderLayer.UNITS


def test_create_sprite_default_anchor_is_bottom_center(game: Game) -> None:
    """Default anchor is SpriteAnchor.BOTTOM_CENTER."""
    sprite = Sprite("sprites/knight")
    assert sprite.anchor == SpriteAnchor.BOTTOM_CENTER


# ------------------------------------------------------------------
# Anchor offset math
# ------------------------------------------------------------------

def test_anchor_offset_bottom_center() -> None:
    """BOTTOM_CENTER: dx = width//2, dy = height."""
    dx, dy = _anchor_offset(SpriteAnchor.BOTTOM_CENTER, 64, 64)
    assert (dx, dy) == (32, 64)


def test_anchor_offset_center() -> None:
    """CENTER: dx = width//2, dy = height//2."""
    dx, dy = _anchor_offset(SpriteAnchor.CENTER, 64, 64)
    assert (dx, dy) == (32, 32)


def test_anchor_offset_top_left() -> None:
    """TOP_LEFT: dx = 0, dy = 0 (draw corner matches position)."""
    dx, dy = _anchor_offset(SpriteAnchor.TOP_LEFT, 64, 64)
    assert (dx, dy) == (0, 0)


def test_anchor_offset_top_center() -> None:
    dx, dy = _anchor_offset(SpriteAnchor.TOP_CENTER, 80, 40)
    assert (dx, dy) == (40, 0)


def test_anchor_offset_top_right() -> None:
    dx, dy = _anchor_offset(SpriteAnchor.TOP_RIGHT, 80, 40)
    assert (dx, dy) == (80, 0)


def test_anchor_offset_center_left() -> None:
    dx, dy = _anchor_offset(SpriteAnchor.CENTER_LEFT, 80, 40)
    assert (dx, dy) == (0, 20)


def test_anchor_offset_center_right() -> None:
    dx, dy = _anchor_offset(SpriteAnchor.CENTER_RIGHT, 80, 40)
    assert (dx, dy) == (80, 20)


def test_anchor_offset_bottom_left() -> None:
    dx, dy = _anchor_offset(SpriteAnchor.BOTTOM_LEFT, 80, 40)
    assert (dx, dy) == (0, 40)


def test_anchor_offset_bottom_right() -> None:
    dx, dy = _anchor_offset(SpriteAnchor.BOTTOM_RIGHT, 80, 40)
    assert (dx, dy) == (80, 40)


# ------------------------------------------------------------------
# Draw position with anchors
# ------------------------------------------------------------------

def test_draw_position_bottom_center(game: Game, backend: MockBackend) -> None:
    """BOTTOM_CENTER with 64x64 at (400,300) → draw at (368, 236)."""
    sprite = Sprite("sprites/knight", position=(400, 300))

    record = backend.sprites[sprite.sprite_id]
    # Default image size is 64x64. dx=32, dy=64 → (400-32, 300-64) = (368, 236)
    assert record["x"] == 368
    assert record["y"] == 236


def test_draw_position_top_left(game: Game, backend: MockBackend) -> None:
    """TOP_LEFT: draw position equals the logical position."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.TOP_LEFT,
    )

    record = backend.sprites[sprite.sprite_id]
    assert record["x"] == 100
    assert record["y"] == 200


def test_draw_position_center(game: Game, backend: MockBackend) -> None:
    """CENTER with 64x64 at (100, 200) → draw at (68, 168)."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.CENTER,
    )

    record = backend.sprites[sprite.sprite_id]
    assert record["x"] == 68
    assert record["y"] == 168


def test_draw_position_custom_image_size(game: Game, backend: MockBackend) -> None:
    """Anchor offsets respect the actual image size from get_image_size."""
    # Load the image to get its handle, then set a custom size.
    img_handle = game.assets.image("sprites/knight")
    backend.set_image_size(img_handle, 48, 96)

    sprite = Sprite(
        "sprites/knight",
        position=(200, 300),
        anchor=SpriteAnchor.BOTTOM_CENTER,
    )

    record = backend.sprites[sprite.sprite_id]
    # dx=24, dy=96 → (200-24, 300-96) = (176, 204)
    assert record["x"] == 176
    assert record["y"] == 204


# ------------------------------------------------------------------
# Position updates
# ------------------------------------------------------------------

def test_set_position_updates_backend(game: Game, backend: MockBackend) -> None:
    """Setting sprite.position calls update_sprite with new draw coords."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.TOP_LEFT,
    )
    sprite.position = (300, 400)

    record = backend.sprites[sprite.sprite_id]
    assert record["x"] == 300
    assert record["y"] == 400


def test_set_x_updates_backend(game: Game, backend: MockBackend) -> None:
    """Setting sprite.x updates the x coordinate in the backend."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.TOP_LEFT,
    )
    sprite.x = 500

    record = backend.sprites[sprite.sprite_id]
    assert record["x"] == 500
    assert record["y"] == 200


def test_set_y_updates_backend(game: Game, backend: MockBackend) -> None:
    """Setting sprite.y updates the y coordinate in the backend."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.TOP_LEFT,
    )
    sprite.y = 500

    record = backend.sprites[sprite.sprite_id]
    assert record["x"] == 100
    assert record["y"] == 500


def test_position_getter_returns_logical_coords(game: Game) -> None:
    """sprite.position returns the logical (not draw) coordinates."""
    sprite = Sprite("sprites/knight", position=(400, 300))

    assert sprite.position == (400, 300)


def test_x_y_getters(game: Game) -> None:
    """sprite.x and sprite.y return the logical coordinates."""
    sprite = Sprite("sprites/knight", position=(123.5, 456.7))
    assert sprite.x == 123.5
    assert sprite.y == 456.7


# ------------------------------------------------------------------
# Y-sort ordering
# ------------------------------------------------------------------

def test_y_sort_order_at_creation(game: Game, backend: MockBackend) -> None:
    """Initial draw order is layer * 100_000 + int(y)."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 250),
        layer=RenderLayer.UNITS,
        anchor=SpriteAnchor.TOP_LEFT,
    )

    record = backend.sprites[sprite.sprite_id]
    # UNITS = 2, so order = 2 * 100_000 + 250 = 200_250
    assert record["layer"] == 200_250


def test_y_sort_order_changes_with_position(
    game: Game, backend: MockBackend,
) -> None:
    """Changing position updates the draw order."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 100),
        layer=RenderLayer.UNITS,
        anchor=SpriteAnchor.TOP_LEFT,
    )

    sprite.position = (100, 350)

    record = backend.sprites[sprite.sprite_id]
    assert record["layer"] == 200_350


def test_y_sort_same_layer_higher_y_in_front(
    game: Game, backend: MockBackend,
) -> None:
    """Two sprites in the same layer: higher y = larger order = drawn in front."""
    s1 = Sprite(
        "sprites/knight",
        position=(100, 100),
        layer=RenderLayer.UNITS,
        anchor=SpriteAnchor.TOP_LEFT,
    )
    s2 = Sprite(
        "sprites/knight",
        position=(100, 300),
        layer=RenderLayer.UNITS,
        anchor=SpriteAnchor.TOP_LEFT,
    )

    order_1 = backend.sprites[s1.sprite_id]["layer"]
    order_2 = backend.sprites[s2.sprite_id]["layer"]
    assert order_2 > order_1


# ------------------------------------------------------------------
# Layer ordering
# ------------------------------------------------------------------

def test_different_layers_have_different_orders(
    game: Game, backend: MockBackend,
) -> None:
    """Sprites in different layers have clearly separated draw orders."""
    bg = Sprite(
        "sprites/knight",
        position=(100, 500),
        layer=RenderLayer.BACKGROUND,
        anchor=SpriteAnchor.TOP_LEFT,
    )
    unit = Sprite(
        "sprites/knight",
        position=(100, 100),
        layer=RenderLayer.UNITS,
        anchor=SpriteAnchor.TOP_LEFT,
    )

    bg_order = backend.sprites[bg.sprite_id]["layer"]
    unit_order = backend.sprites[unit.sprite_id]["layer"]
    # BG at y=500: 0 * 100_000 + 500 = 500
    # UNITS at y=100: 2 * 100_000 + 100 = 200_100
    assert unit_order > bg_order


def test_effects_layer_above_units(game: Game, backend: MockBackend) -> None:
    """EFFECTS layer always draws above UNITS regardless of y."""
    unit = Sprite(
        "sprites/knight",
        position=(100, 900),
        layer=RenderLayer.UNITS,
        anchor=SpriteAnchor.TOP_LEFT,
    )
    effect = Sprite(
        "sprites/knight",
        position=(100, 0),
        layer=RenderLayer.EFFECTS,
        anchor=SpriteAnchor.TOP_LEFT,
    )

    unit_order = backend.sprites[unit.sprite_id]["layer"]
    effect_order = backend.sprites[effect.sprite_id]["layer"]
    # UNITS at y=900: 2 * 100_000 + 900 = 200_900
    # EFFECTS at y=0: 3 * 100_000 + 0 = 300_000
    assert effect_order > unit_order


# ------------------------------------------------------------------
# Opacity and visibility
# ------------------------------------------------------------------

def test_opacity_default_255(game: Game, backend: MockBackend) -> None:
    """Default opacity is 255."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    record = backend.sprites[sprite.sprite_id]
    assert record["opacity"] == 255


def test_set_opacity_updates_backend(game: Game, backend: MockBackend) -> None:
    """Setting sprite.opacity syncs to the backend."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.opacity = 128

    record = backend.sprites[sprite.sprite_id]
    assert record["opacity"] == 128


def test_opacity_setter_coerces_float(game: Game, backend: MockBackend) -> None:
    """Opacity setter coerces float to int (e.g. from tween)."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.opacity = 127.5

    record = backend.sprites[sprite.sprite_id]
    assert record["opacity"] == 127
    assert sprite.opacity == 127


def test_opacity_getter(game: Game) -> None:
    """sprite.opacity returns the current value."""
    sprite = Sprite("sprites/knight", position=(100, 100), opacity=200)
    assert sprite.opacity == 200


def test_visible_default_true(game: Game, backend: MockBackend) -> None:
    """Default visible is True."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    record = backend.sprites[sprite.sprite_id]
    assert record["visible"] is True


def test_set_visible_false(game: Game, backend: MockBackend) -> None:
    """Setting sprite.visible = False syncs to the backend."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.visible = False

    record = backend.sprites[sprite.sprite_id]
    assert record["visible"] is False


def test_visible_getter(game: Game) -> None:
    """sprite.visible returns the current value."""
    sprite = Sprite("sprites/knight", visible=False)
    assert sprite.visible is False


# ------------------------------------------------------------------
# Removal
# ------------------------------------------------------------------

def test_remove_deletes_from_backend(game: Game, backend: MockBackend) -> None:
    """remove() removes the sprite from the backend."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sid = sprite.sprite_id

    assert sid in backend.sprites
    sprite.remove()
    assert sid not in backend.sprites


def test_remove_sets_is_removed(game: Game) -> None:
    """remove() marks the sprite as removed."""
    sprite = Sprite("sprites/knight")
    assert sprite.is_removed is False
    sprite.remove()
    assert sprite.is_removed is True


def test_double_remove_is_safe(game: Game, backend: MockBackend) -> None:
    """Calling remove() twice does not raise."""
    sprite = Sprite("sprites/knight")
    sprite.remove()
    sprite.remove()  # should not raise


def test_update_after_remove_is_noop(game: Game, backend: MockBackend) -> None:
    """Setting position after removal does not crash (sync is a no-op)."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.remove()
    # This should not raise even though the sprite_id is gone from backend.
    sprite.position = (200, 200)


# ------------------------------------------------------------------
# Construction with initial opacity and visible
# ------------------------------------------------------------------

def test_set_image_property(game: Game, backend: MockBackend) -> None:
    """Setting sprite.image swaps the displayed image and updates dimensions."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    tree_handle = game.assets.image("sprites/tree")
    backend.set_image_size(tree_handle, 32, 48)

    sprite.image = "sprites/tree"

    record = backend.sprites[sprite.sprite_id]
    assert record["image"] == tree_handle
    assert sprite.image == "sprites/tree"


def test_initial_opacity_synced(game: Game, backend: MockBackend) -> None:
    """Custom initial opacity is synced to backend at creation."""
    sprite = Sprite("sprites/knight", position=(100, 100), opacity=100)
    record = backend.sprites[sprite.sprite_id]
    assert record["opacity"] == 100


def test_initial_visible_false_synced(game: Game, backend: MockBackend) -> None:
    """visible=False at creation is synced to backend."""
    sprite = Sprite("sprites/knight", position=(100, 100), visible=False)
    record = backend.sprites[sprite.sprite_id]
    assert record["visible"] is False


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------

def test_no_game_raises_runtime_error(asset_dir: Path) -> None:
    """Creating a Sprite when no Game exists raises RuntimeError."""
    import easygame.rendering.sprite as sprite_mod

    old = sprite_mod._current_game
    try:
        sprite_mod._current_game = None
        with pytest.raises(RuntimeError, match="No active Game"):
            Sprite("sprites/knight")
    finally:
        sprite_mod._current_game = old


# ------------------------------------------------------------------
# Multiple sprites
# ------------------------------------------------------------------

def test_two_sprites_get_different_ids(game: Game, backend: MockBackend) -> None:
    """Each sprite gets a unique backend id."""
    s1 = Sprite("sprites/knight", position=(100, 100))
    s2 = Sprite("sprites/tree", position=(200, 200))

    assert s1.sprite_id != s2.sprite_id
    assert s1.sprite_id in backend.sprites
    assert s2.sprite_id in backend.sprites


def test_custom_layer(game: Game, backend: MockBackend) -> None:
    """Sprite with custom layer uses that layer for ordering."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        layer=RenderLayer.BACKGROUND,
        anchor=SpriteAnchor.TOP_LEFT,
    )

    record = backend.sprites[sprite.sprite_id]
    # BACKGROUND = 0, y = 200 → order = 200
    assert record["layer"] == 200


# ------------------------------------------------------------------
# move_to and on_arrive
# ------------------------------------------------------------------


def test_move_to_on_arrive_called_once_when_both_axes_finish_same_frame(
    game: Game,
) -> None:
    """on_arrive is called exactly once even when x and y tweens complete in the same tick."""
    game.push(Scene())
    sprite = Sprite("sprites/knight", position=(100, 300))
    arrive_calls: list[None] = []

    sprite.move_to((200, 400), speed=200, on_arrive=lambda: arrive_calls.append(None))

    # Distance ≈ 141.4 px, duration ≈ 0.707 s. Single tick with dt >= duration
    # causes both x and y tweens to complete in the same TweenManager.update().
    game.tick(dt=0.8)

    assert len(arrive_calls) == 1


# ------------------------------------------------------------------
# Bug-fix: NaN position guard
# ------------------------------------------------------------------


def test_nan_position_does_not_crash(game: Game, backend: MockBackend) -> None:
    """Setting position to NaN skips the backend sync instead of ValueError."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.TOP_LEFT,
    )
    sid = sprite.sprite_id
    old_x = backend.sprites[sid]["x"]
    old_y = backend.sprites[sid]["y"]

    # Setting NaN position should not raise.
    sprite.position = (float("nan"), 200)
    # Backend should NOT have been updated (NaN guard skips sync).
    assert backend.sprites[sid]["x"] == old_x
    assert backend.sprites[sid]["y"] == old_y


def test_nan_y_position_does_not_crash(game: Game, backend: MockBackend) -> None:
    """NaN on y coordinate also skips sync safely."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.TOP_LEFT,
    )
    sid = sprite.sprite_id
    old_x = backend.sprites[sid]["x"]
    old_y = backend.sprites[sid]["y"]

    sprite.position = (100, float("nan"))
    assert backend.sprites[sid]["x"] == old_x
    assert backend.sprites[sid]["y"] == old_y


def test_normal_position_still_syncs_after_nan(game: Game, backend: MockBackend) -> None:
    """After NaN, a valid position update still syncs correctly."""
    sprite = Sprite(
        "sprites/knight",
        position=(100, 200),
        anchor=SpriteAnchor.TOP_LEFT,
    )
    sid = sprite.sprite_id

    # First set NaN (skipped)
    sprite.position = (float("nan"), float("nan"))
    # Then set valid position
    sprite.position = (300, 400)

    assert backend.sprites[sid]["x"] == 300
    assert backend.sprites[sid]["y"] == 400
