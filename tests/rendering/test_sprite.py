"""Tests for Sprite: creation, position sync, anchor offsets, y-sort, removal, edge cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from easygame import Do, Game, Scene, Sprite
from easygame.actions import Action
from easygame.assets import AssetManager
from easygame.backends.mock_backend import MockBackend
from easygame.rendering.layers import RenderLayer, SpriteAnchor
from easygame.rendering.sprite import _anchor_offset


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
    (sprites / "tree.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def game(asset_dir: Path) -> Game:
    """Return a Game instance with assets pointing at the temp directory."""
    g = Game("Test", backend="mock", resolution=(1920, 1080))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    yield g
    g._teardown()


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
    """BOTTOM_CENTER with 64x64 at (400,300) -> draw at (368, 236)."""
    sprite = Sprite("sprites/knight", position=(400, 300))

    record = backend.sprites[sprite.sprite_id]
    # Default image size is 64x64. dx=32, dy=64 -> (400-32, 300-64) = (368, 236)
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
    """CENTER with 64x64 at (100, 200) -> draw at (68, 168)."""
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
    # dx=24, dy=96 -> (200-24, 300-96) = (176, 204)
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
    # BACKGROUND = 0, y = 200 -> order = 200
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

    # Distance ~= 141.4 px, duration ~= 0.707 s. Single tick with dt >= duration
    # causes both x and y tweens to complete in the same TweenManager.update().
    game.tick(dt=0.8)

    assert len(arrive_calls) == 1


# ==================================================================
# Edge cases: teardown
# ==================================================================


def test_sprite_creation_after_teardown_raises_runtime_error(
    game: Game,
) -> None:
    """Creating a Sprite after _teardown() raises RuntimeError (no active Game)."""
    game._teardown()

    with pytest.raises(RuntimeError, match="No active Game"):
        Sprite("sprites/knight")


# ==================================================================
# Edge cases: property setters on removed sprite
# ==================================================================


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


# ==================================================================
# Edge cases: None, NaN/Inf position, x, y
# ==================================================================


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


# ==================================================================
# Edge cases: NaN/Inf opacity (clamped to [0, 255])
# ==================================================================


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


# ==================================================================
# Edge cases: sprite.do() on removed sprite
# ==================================================================


def test_do_on_removed_sprite_is_noop(game: Game) -> None:
    """sprite.do(action) on removed sprite returns immediately without registering."""
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.do(Action())
    sprite.remove()

    sprite.do(Action())  # should not crash

    assert sprite not in game._action_sprites


# ==================================================================
# Edge cases: Sprite creation in on_reveal and on_exit
# ==================================================================


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


# ==================================================================
# From test_edge_cases.py: Sprite opacity clamping
# ==================================================================


class TestSpriteOpacity:
    """Sprite.opacity should accept any numeric value; the framework
    should clamp it to the valid 0-255 range before syncing to backend."""

    def test_opacity_out_of_range_high(
        self, game: Game, backend: MockBackend
    ) -> None:
        """Setting opacity > 255 clamps to 255."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.opacity = 999
        assert s.opacity == 255

    def test_opacity_negative(self, game: Game) -> None:
        """Setting opacity < 0 clamps to 0."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.opacity = -50
        assert s.opacity == 0

    def test_opacity_float_truncates_to_int(self, game: Game) -> None:
        """Float opacity is truncated to int."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.opacity = 127.9
        assert s.opacity == 127

    def test_opacity_zero_and_255_accepted(self, game: Game) -> None:
        """Boundary values 0 and 255 are accepted as-is."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        s.opacity = 0
        assert s.opacity == 0
        s.opacity = 255
        assert s.opacity == 255


# ==================================================================
# From test_edge_cases.py: Sprite position finite (non-duplicate tests)
# ==================================================================


class TestSpritePositionFinite:
    """Sprite position and assignment must reject non-finite values.

    Note: tests that duplicate edge-case tests above have been removed.
    Kept: init with inf/-inf, y setter with inf, and finite acceptance.
    """

    def test_position_inf_init_raises(self, game: Game) -> None:
        """Creating a Sprite with inf position raises ValueError."""
        game.push(Scene())
        with pytest.raises(ValueError, match="finite"):
            Sprite("sprites/knight", position=(float("inf"), 0))

    def test_position_neg_inf_init_raises(self, game: Game) -> None:
        """Creating a Sprite with -inf position raises ValueError."""
        game.push(Scene())
        with pytest.raises(ValueError, match="finite"):
            Sprite("sprites/knight", position=(0, float("-inf")))

    def test_y_setter_inf_raises(self, game: Game) -> None:
        """Setting y to inf raises ValueError."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(0, 0))
        with pytest.raises(ValueError, match="finite"):
            s.y = float("inf")

    def test_finite_position_accepted(self, game: Game) -> None:
        """Normal finite positions work correctly."""
        game.push(Scene())
        s = Sprite("sprites/knight", position=(100.5, 200.7))
        assert s.position == (100.5, 200.7)
        s.position = (-50.0, 9999.0)
        assert s.position == (-50.0, 9999.0)


# ==================================================================
# From test_edge_cases.py: Sprite remove edge cases (non-duplicate tests)
# ==================================================================


class TestSpriteRemoveEdgeCases:
    """Sprite.remove() edge cases.

    Note: test_remove_twice_is_safe is covered by test_double_remove_is_safe above.
    test_do_on_removed_sprite_is_noop is covered by the standalone function above.
    Only the class shell is kept for structural consistency; if future
    remove edge-case tests are needed, add them here.
    """
