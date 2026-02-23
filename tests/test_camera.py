"""Tests for Camera: pure math, Scene integration, frustum culling, render sync."""

from __future__ import annotations

from pathlib import Path

import pytest

from easygame import Game, Scene, Sprite
from easygame.assets import AssetManager
from easygame.backends.mock_backend import MockBackend
from easygame.input import InputEvent
from easygame.rendering.camera import Camera
from easygame.rendering.layers import SpriteAnchor


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
    """Return a Game instance with assets pointing at the temp directory."""
    g = Game("Test", backend="mock", resolution=(800, 600))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    return g


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


# ==================================================================
# 1. center_on
# ==================================================================

class TestCenterOn:

    def test_center_on_sets_top_left(self) -> None:
        """center_on(500, 400) with 800x600 viewport → _x=100, _y=100."""
        cam = Camera((800, 600))
        cam.center_on(500, 400)

        assert cam.x == 500 - 400  # 100
        assert cam.y == 400 - 300  # 100

    def test_center_on_with_different_viewport(self) -> None:
        """Viewport size affects centering offset."""
        cam = Camera((1920, 1080))
        cam.center_on(960, 540)

        assert cam.x == 0.0
        assert cam.y == 0.0

    def test_center_on_clamps_to_world_bounds_low(self) -> None:
        """center_on near top-left corner clamps to (0, 0)."""
        cam = Camera((800, 600), world_bounds=(0, 0, 4096, 4096))
        cam.center_on(100, 100)

        # Would be (100-400, 100-300) = (-300, -200) → clamped to (0, 0).
        assert cam.x == 0.0
        assert cam.y == 0.0

    def test_center_on_clamps_to_world_bounds_high(self) -> None:
        """center_on near bottom-right corner clamps to max."""
        cam = Camera((800, 600), world_bounds=(0, 0, 4096, 4096))
        cam.center_on(4096, 4096)

        # max_x = 4096 - 800 = 3296, max_y = 4096 - 600 = 3496
        assert cam.x == 3296.0
        assert cam.y == 3496.0

    def test_center_on_no_clamping_without_bounds(self) -> None:
        """Without world_bounds, center_on allows negative positions."""
        cam = Camera((800, 600))
        cam.center_on(0, 0)

        assert cam.x == -400.0
        assert cam.y == -300.0

    def test_center_on_cancels_follow(self, game: Game) -> None:
        """center_on disables follow mode."""
        cam = Camera((800, 600))
        sprite = Sprite("sprites/knight", position=(500, 400))
        cam.follow(sprite)
        assert cam._follow_target is sprite

        cam.center_on(100, 100)
        assert cam._follow_target is None


# ==================================================================
# 2. follow
# ==================================================================

class TestFollow:

    def test_follow_tracks_sprite_position(self, game: Game) -> None:
        """update() centers camera on followed sprite."""
        cam = Camera((800, 600))
        sprite = Sprite(
            "sprites/knight", position=(500, 400),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        cam.follow(sprite)
        cam.update(0.016)

        assert cam.x == 500 - 400  # 100
        assert cam.y == 400 - 300  # 100

    def test_follow_updates_when_sprite_moves(self, game: Game) -> None:
        """Camera re-centers each update() as sprite moves."""
        cam = Camera((800, 600))
        sprite = Sprite(
            "sprites/knight", position=(500, 400),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        cam.follow(sprite)
        cam.update(0.016)

        sprite.position = (1000, 800)
        cam.update(0.016)

        assert cam.x == 1000 - 400
        assert cam.y == 800 - 300

    def test_follow_none_stops_following(self, game: Game) -> None:
        """follow(None) stops tracking."""
        cam = Camera((800, 600))
        sprite = Sprite(
            "sprites/knight", position=(500, 400),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        cam.follow(sprite)
        cam.update(0.016)

        cam.follow(None)
        sprite.position = (9999, 9999)
        cam.update(0.016)

        # Camera should not have moved to the new sprite position.
        assert cam.x == 500 - 400
        assert cam.y == 400 - 300

    def test_follow_removed_sprite_clears_follow(self, game: Game) -> None:
        """Following a removed sprite gracefully clears follow mode."""
        cam = Camera((800, 600))
        sprite = Sprite(
            "sprites/knight", position=(500, 400),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        cam.follow(sprite)
        cam.update(0.016)

        old_x, old_y = cam.x, cam.y
        sprite.remove()
        cam.update(0.016)

        # Camera stays at last position, doesn't crash.
        assert cam.x == old_x
        assert cam.y == old_y
        assert cam._follow_target is None

    def test_follow_clamps_to_world_bounds(self, game: Game) -> None:
        """Follow respects world_bounds clamping."""
        cam = Camera((800, 600), world_bounds=(0, 0, 2000, 2000))
        sprite = Sprite(
            "sprites/knight", position=(100, 100),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        cam.follow(sprite)
        cam.update(0.016)

        # Would be (100-400, 100-300) = (-300, -200) → clamped to (0, 0).
        assert cam.x == 0.0
        assert cam.y == 0.0


# ==================================================================
# 3. scroll
# ==================================================================

class TestScroll:

    def test_scroll_moves_camera(self) -> None:
        """scroll(dx, dy) offsets camera position."""
        cam = Camera((800, 600))
        cam.scroll(50, 30)

        assert cam.x == 50.0
        assert cam.y == 30.0

    def test_scroll_accumulates(self) -> None:
        """Multiple scrolls accumulate."""
        cam = Camera((800, 600))
        cam.scroll(10, 20)
        cam.scroll(30, 40)

        assert cam.x == 40.0
        assert cam.y == 60.0

    def test_scroll_clamps_to_world_bounds(self) -> None:
        """Scrolling past world_bounds is clamped."""
        cam = Camera((800, 600), world_bounds=(0, 0, 1000, 1000))
        cam.scroll(500, 500)

        # max_x = 1000 - 800 = 200, max_y = 1000 - 600 = 400
        assert cam.x == 200.0
        assert cam.y == 400.0

    def test_scroll_clamps_negative(self) -> None:
        """Scrolling negative past bounds clamps to min."""
        cam = Camera((800, 600), world_bounds=(0, 0, 2000, 2000))
        cam.scroll(-100, -200)

        assert cam.x == 0.0
        assert cam.y == 0.0

    def test_scroll_cancels_follow(self, game: Game) -> None:
        """scroll() disables follow mode."""
        cam = Camera((800, 600))
        sprite = Sprite("sprites/knight", position=(500, 400))
        cam.follow(sprite)

        cam.scroll(10, 10)
        assert cam._follow_target is None

    def test_scroll_cancels_pan(self, game: Game) -> None:
        """scroll() cancels an active pan_to tween."""
        cam = Camera((800, 600))
        cam.pan_to(500, 500, duration=1.0)
        assert cam._pan_tween_x is not None

        cam.scroll(10, 10)
        assert cam._pan_tween_x is None
        assert cam._pan_tween_y is None


# ==================================================================
# 4. screen_to_world / world_to_screen
# ==================================================================

class TestCoordinateConversion:

    def test_roundtrip(self) -> None:
        """screen_to_world → world_to_screen roundtrips exactly."""
        cam = Camera((800, 600))
        cam.center_on(1000, 800)

        wx, wy = cam.screen_to_world(200, 150)
        sx, sy = cam.world_to_screen(wx, wy)

        assert abs(sx - 200) < 1e-9
        assert abs(sy - 150) < 1e-9

    def test_screen_origin_maps_to_camera_top_left(self) -> None:
        """Screen (0, 0) maps to the camera's top-left world position."""
        cam = Camera((800, 600))
        cam.center_on(1000, 800)

        wx, wy = cam.screen_to_world(0, 0)

        assert wx == cam.x
        assert wy == cam.y

    def test_screen_center_maps_to_camera_center(self) -> None:
        """Screen center maps to the camera's center world position."""
        cam = Camera((800, 600))
        cam.center_on(1000, 800)

        wx, wy = cam.screen_to_world(400, 300)

        assert abs(wx - 1000) < 1e-9
        assert abs(wy - 800) < 1e-9

    def test_world_to_screen_basic(self) -> None:
        """World position at camera top-left maps to screen (0, 0)."""
        cam = Camera((800, 600))
        cam.center_on(500, 400)

        sx, sy = cam.world_to_screen(cam.x, cam.y)

        assert sx == 0.0
        assert sy == 0.0

    def test_conversion_after_scroll(self) -> None:
        """Coordinate conversion reflects scroll offset."""
        cam = Camera((800, 600))
        cam.scroll(100, 50)

        wx, wy = cam.screen_to_world(0, 0)
        assert wx == 100.0
        assert wy == 50.0

        sx, sy = cam.world_to_screen(100, 50)
        assert sx == 0.0
        assert sy == 0.0

    def test_conversion_with_no_offset(self) -> None:
        """With camera at (0, 0), screen coords == world coords."""
        cam = Camera((800, 600))

        wx, wy = cam.screen_to_world(200, 300)
        assert wx == 200.0
        assert wy == 300.0

        sx, sy = cam.world_to_screen(200, 300)
        assert sx == 200.0
        assert sy == 300.0


# ==================================================================
# 5. Frustum culling
# ==================================================================

class TestFrustumCulling:

    def test_offscreen_sprite_hidden_during_draw(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Sprite far outside viewport is hidden during draw."""
        sprite = Sprite(
            "sprites/knight", position=(5000, 5000),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        visible_during_draw = {}

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.center_on(400, 300)  # viewport at (0, 0)

            def draw(self) -> None:
                rec = backend.sprites[sprite.sprite_id]
                visible_during_draw["v"] = rec["visible"]

        game.push(WorldScene())
        game.tick(dt=0.016)

        assert visible_during_draw["v"] is False

    def test_onscreen_sprite_visible_during_draw(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Sprite within viewport is visible during draw."""
        sprite = Sprite(
            "sprites/knight", position=(400, 300),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        visible_during_draw = {}

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.center_on(400, 300)

            def draw(self) -> None:
                rec = backend.sprites[sprite.sprite_id]
                visible_during_draw["v"] = rec["visible"]

        game.push(WorldScene())
        game.tick(dt=0.016)

        assert visible_during_draw["v"] is True

    def test_visibility_restored_after_draw(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Off-screen sprite has visibility restored after the draw phase."""
        sprite = Sprite(
            "sprites/knight", position=(5000, 5000),
            anchor=SpriteAnchor.TOP_LEFT,
        )

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.center_on(400, 300)

        game.push(WorldScene())
        game.tick(dt=0.016)

        # After tick, backend should have restored the original visible=True.
        rec = backend.sprites[sprite.sprite_id]
        assert rec["visible"] is True

    def test_user_hidden_sprite_stays_hidden(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Sprite with visible=False stays hidden even if in viewport."""
        sprite = Sprite(
            "sprites/knight", position=(400, 300),
            anchor=SpriteAnchor.TOP_LEFT, visible=False,
        )
        visible_during_draw = {}

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.center_on(400, 300)

            def draw(self) -> None:
                rec = backend.sprites[sprite.sprite_id]
                visible_during_draw["v"] = rec["visible"]

        game.push(WorldScene())
        game.tick(dt=0.016)

        assert visible_during_draw["v"] is False

    def test_sprite_partially_onscreen_is_visible(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Sprite whose bounding box overlaps the viewport edge is visible."""
        # Camera at (0, 0), viewport 800x600.
        # Sprite at (-30, 300) with 64x64 image → draw corner (-30, 300).
        # Right edge at -30 + 64 = 34 > 0, so it overlaps.
        sprite = Sprite(
            "sprites/knight", position=(-30, 300),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        visible_during_draw = {}

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                # Camera at (0, 0).

            def draw(self) -> None:
                rec = backend.sprites[sprite.sprite_id]
                visible_during_draw["v"] = rec["visible"]

        game.push(WorldScene())
        game.tick(dt=0.016)

        assert visible_during_draw["v"] is True

    def test_sprite_just_off_left_edge_is_hidden(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Sprite entirely off the left edge is hidden."""
        # Camera at (0, 0), viewport 800x600.
        # Sprite at (-100, 300) with 64x64 → draw corner (-100, 300).
        # Right edge at -100 + 64 = -36 ≤ 0, entirely off-screen.
        sprite = Sprite(
            "sprites/knight", position=(-100, 300),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        visible_during_draw = {}

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))

            def draw(self) -> None:
                rec = backend.sprites[sprite.sprite_id]
                visible_during_draw["v"] = rec["visible"]

        game.push(WorldScene())
        game.tick(dt=0.016)

        assert visible_during_draw["v"] is False


# ==================================================================
# 6. Edge scroll
# ==================================================================

class TestEdgeScroll:

    def test_edge_scroll_left(self) -> None:
        """Mouse near left edge scrolls camera left."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_edge_scroll(margin=20, speed=100)
        old_x = cam.x

        cam.update(1.0, mouse_x=5, mouse_y=300)

        assert cam.x < old_x
        assert cam.x == old_x - 100

    def test_edge_scroll_right(self) -> None:
        """Mouse near right edge scrolls camera right."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_edge_scroll(margin=20, speed=100)
        old_x = cam.x

        cam.update(1.0, mouse_x=795, mouse_y=300)

        assert cam.x > old_x
        assert cam.x == old_x + 100

    def test_edge_scroll_up(self) -> None:
        """Mouse near top edge scrolls camera up."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_edge_scroll(margin=20, speed=100)
        old_y = cam.y

        cam.update(1.0, mouse_x=400, mouse_y=5)

        assert cam.y < old_y
        assert cam.y == old_y - 100

    def test_edge_scroll_down(self) -> None:
        """Mouse near bottom edge scrolls camera down."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_edge_scroll(margin=20, speed=100)
        old_y = cam.y

        cam.update(1.0, mouse_x=400, mouse_y=595)

        assert cam.y > old_y
        assert cam.y == old_y + 100

    def test_edge_scroll_diagonal(self) -> None:
        """Mouse near both left and top scrolls diagonally."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_edge_scroll(margin=20, speed=100)
        old_x, old_y = cam.x, cam.y

        cam.update(1.0, mouse_x=5, mouse_y=5)

        assert cam.x == old_x - 100
        assert cam.y == old_y - 100

    def test_edge_scroll_center_no_movement(self) -> None:
        """Mouse in center of viewport causes no scrolling."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_edge_scroll(margin=20, speed=100)
        old_x, old_y = cam.x, cam.y

        cam.update(1.0, mouse_x=400, mouse_y=300)

        assert cam.x == old_x
        assert cam.y == old_y

    def test_edge_scroll_disabled(self) -> None:
        """disable_edge_scroll() stops edge scrolling."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_edge_scroll(margin=20, speed=100)
        cam.disable_edge_scroll()
        old_x = cam.x

        cam.update(1.0, mouse_x=5, mouse_y=300)

        assert cam.x == old_x

    def test_edge_scroll_none_mouse_no_scroll(self) -> None:
        """Edge scroll with None mouse coords does not scroll."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_edge_scroll(margin=20, speed=100)
        old_x = cam.x

        cam.update(1.0, mouse_x=None, mouse_y=None)

        assert cam.x == old_x

    def test_edge_scroll_respects_world_bounds(self) -> None:
        """Edge scrolling clamps to world bounds."""
        cam = Camera((800, 600), world_bounds=(0, 0, 2000, 2000))
        cam.center_on(400, 300)  # camera at (0, 0)
        cam.enable_edge_scroll(margin=20, speed=500)

        cam.update(1.0, mouse_x=5, mouse_y=5)

        assert cam.x == 0.0
        assert cam.y == 0.0

    def test_edge_scroll_via_game_tick(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Edge scroll works through the full Game.tick() pipeline."""

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.center_on(500, 500)
                self.camera.enable_edge_scroll(margin=20, speed=100)

        game.push(WorldScene())
        scene = game._scene_stack.top()
        old_x = scene.camera.x

        backend.inject_mouse_move(5, 300)
        game.tick(dt=1.0)

        assert scene.camera.x < old_x


# ==================================================================
# 6b. Key scroll
# ==================================================================

class TestKeyScroll:

    def test_key_scroll_left(self) -> None:
        """Holding left arrow scrolls camera left."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_key_scroll(speed=100)
        old_x = cam.x

        cam.handle_input(InputEvent(type="key_press", key="left", action="left"))
        cam.update(1.0)

        assert cam.x < old_x
        assert cam.x == old_x - 100

    def test_key_scroll_right(self) -> None:
        """Holding right arrow scrolls camera right."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_key_scroll(speed=100)
        old_x = cam.x

        cam.handle_input(InputEvent(type="key_press", key="right", action="right"))
        cam.update(1.0)

        assert cam.x > old_x
        assert cam.x == old_x + 100

    def test_key_scroll_up(self) -> None:
        """Holding up arrow scrolls camera up."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_key_scroll(speed=100)
        old_y = cam.y

        cam.handle_input(InputEvent(type="key_press", key="up", action="up"))
        cam.update(1.0)

        assert cam.y < old_y
        assert cam.y == old_y - 100

    def test_key_scroll_down(self) -> None:
        """Holding down arrow scrolls camera down."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_key_scroll(speed=100)
        old_y = cam.y

        cam.handle_input(InputEvent(type="key_press", key="down", action="down"))
        cam.update(1.0)

        assert cam.y > old_y
        assert cam.y == old_y + 100

    def test_key_scroll_release_stops(self) -> None:
        """Releasing key stops scrolling."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_key_scroll(speed=100)
        old_x = cam.x

        cam.handle_input(InputEvent(type="key_press", key="left", action="left"))
        cam.update(1.0)
        assert cam.x < old_x

        cam.handle_input(InputEvent(type="key_release", key="left", action="left"))
        cam.update(1.0)
        after_release = cam.x

        cam.update(1.0)
        assert cam.x == after_release

    def test_key_scroll_diagonal(self) -> None:
        """Holding left+up scrolls diagonally."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_key_scroll(speed=100)
        old_x, old_y = cam.x, cam.y

        cam.handle_input(InputEvent(type="key_press", key="left", action="left"))
        cam.handle_input(InputEvent(type="key_press", key="up", action="up"))
        cam.update(1.0)

        assert cam.x == old_x - 100
        assert cam.y == old_y - 100

    def test_key_scroll_opposite_keys_cancel(self) -> None:
        """Holding left+right results in no horizontal movement."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_key_scroll(speed=100)
        old_x = cam.x

        cam.handle_input(InputEvent(type="key_press", key="left", action="left"))
        cam.handle_input(InputEvent(type="key_press", key="right", action="right"))
        cam.update(1.0)

        assert cam.x == old_x

    def test_key_scroll_disabled(self) -> None:
        """disable_key_scroll stops scrolling."""
        cam = Camera((800, 600))
        cam.center_on(500, 500)
        cam.enable_key_scroll(speed=100)
        cam.disable_key_scroll()
        old_x = cam.x

        cam.handle_input(InputEvent(type="key_press", key="left", action="left"))
        cam.update(1.0)

        assert cam.x == old_x

    def test_key_scroll_respects_world_bounds(self) -> None:
        """Key scrolling clamps to world bounds."""
        cam = Camera((800, 600), world_bounds=(0, 0, 2000, 2000))
        cam.center_on(400, 300)  # camera at (0, 0)
        cam.enable_key_scroll(speed=500)

        cam.handle_input(InputEvent(type="key_press", key="left", action="left"))
        cam.handle_input(InputEvent(type="key_press", key="up", action="up"))
        cam.update(1.0)

        assert cam.x == 0.0
        assert cam.y == 0.0

    def test_key_scroll_via_game_tick(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Key scroll works through the full Game.tick() pipeline."""

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.center_on(500, 500)
                self.camera.enable_key_scroll(speed=100)

        game.push(WorldScene())
        scene = game._scene_stack.top()
        old_x = scene.camera.x

        backend.inject_key("left", type="key_press")
        game.tick(dt=1.0)

        assert scene.camera.x < old_x
        assert scene.camera.x == old_x - 100


# ==================================================================
# 7. pan_to
# ==================================================================

class TestPanTo:

    def test_pan_to_animates_toward_target(self, game: Game) -> None:
        """pan_to creates tweens that move camera over time."""
        cam = Camera((800, 600))
        cam.center_on(400, 300)
        old_x, old_y = cam.x, cam.y

        cam.pan_to(1000, 800, duration=1.0)

        # After half the duration, camera should have moved partway.
        game.tick(dt=0.5)
        assert cam.x != old_x
        assert cam.y != old_y

    def test_pan_to_reaches_target_after_duration(self, game: Game) -> None:
        """pan_to reaches the target center position after full duration."""
        cam = Camera((800, 600))
        cam.center_on(400, 300)

        cam.pan_to(1000, 800, duration=1.0)
        game.tick(dt=1.0)

        # Target top-left = (1000-400, 800-300) = (600, 500).
        assert abs(cam.x - 600) < 1e-6
        assert abs(cam.y - 500) < 1e-6

    def test_pan_to_cancels_follow(self, game: Game) -> None:
        """pan_to disables follow mode."""
        cam = Camera((800, 600))
        sprite = Sprite("sprites/knight", position=(500, 400))
        cam.follow(sprite)

        cam.pan_to(1000, 800, duration=1.0)
        assert cam._follow_target is None

    def test_pan_to_replaces_previous_pan(self, game: Game) -> None:
        """Starting a new pan_to cancels the previous pan."""
        cam = Camera((800, 600))
        cam.center_on(400, 300)

        cam.pan_to(1000, 800, duration=2.0)
        old_tween_x = cam._pan_tween_x

        cam.pan_to(200, 100, duration=1.0)
        assert cam._pan_tween_x != old_tween_x

        game.tick(dt=1.0)

        # Should reach the second target, not the first.
        # Target top-left = (200-400, 100-300) = (-200, -200).
        assert abs(cam.x - (-200)) < 1e-6
        assert abs(cam.y - (-200)) < 1e-6

    def test_pan_to_clamps_target_to_world_bounds(self, game: Game) -> None:
        """pan_to clamps the target position to world_bounds."""
        cam = Camera((800, 600), world_bounds=(0, 0, 1000, 1000))
        cam.center_on(400, 300)

        cam.pan_to(5000, 5000, duration=1.0)
        game.tick(dt=1.0)

        # max_x = 1000 - 800 = 200, max_y = 1000 - 600 = 400
        assert abs(cam.x - 200) < 1e-6
        assert abs(cam.y - 400) < 1e-6

    def test_pan_to_clears_tween_ids_on_complete(self, game: Game) -> None:
        """After pan completes, tween ids are cleared."""
        cam = Camera((800, 600))
        cam.center_on(400, 300)

        cam.pan_to(1000, 800, duration=0.5)
        assert cam._pan_tween_x is not None
        assert cam._pan_tween_y is not None

        game.tick(dt=0.5)

        assert cam._pan_tween_x is None
        assert cam._pan_tween_y is None

    def test_pan_to_with_custom_easing(self, game: Game) -> None:
        """pan_to accepts a custom easing function."""
        from easygame.util.tween import Ease

        cam = Camera((800, 600))
        cam.center_on(400, 300)

        cam.pan_to(800, 600, duration=1.0, easing=Ease.LINEAR)
        game.tick(dt=0.5)

        # With LINEAR easing, at 50% time we should be ~50% of the way.
        target_x = 800 - 400  # 400
        start_x = 0.0
        mid_x = (start_x + target_x) / 2  # 200
        assert abs(cam.x - mid_x) < 5.0  # allow small tolerance


# ==================================================================
# 8. Integration with rendering (camera offset in backend)
# ==================================================================

class TestRenderIntegration:

    def test_camera_offset_applied_during_draw(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """During draw, sprite backend position = world pos - camera offset."""
        sprite = Sprite(
            "sprites/knight", position=(500, 400),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        draw_positions = {}

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.center_on(500, 400)
                # Camera top-left = (100, 100).

            def draw(self) -> None:
                rec = backend.sprites[sprite.sprite_id]
                draw_positions["x"] = rec["x"]
                draw_positions["y"] = rec["y"]

        game.push(WorldScene())
        game.tick(dt=0.016)

        # Sprite at (500, 400), TOP_LEFT anchor → draw corner (500, 400).
        # Camera offset = (100, 100) → screen pos = (400, 300).
        assert draw_positions["x"] == 400
        assert draw_positions["y"] == 300

    def test_positions_restored_after_draw(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """After tick completes, sprite backend positions are restored."""
        sprite = Sprite(
            "sprites/knight", position=(500, 400),
            anchor=SpriteAnchor.TOP_LEFT,
        )

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.center_on(500, 400)

        game.push(WorldScene())
        game.tick(dt=0.016)

        rec = backend.sprites[sprite.sprite_id]
        assert rec["x"] == 500
        assert rec["y"] == 400

    def test_world_position_unchanged_by_camera(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Camera never modifies the sprite's world position."""
        sprite = Sprite(
            "sprites/knight", position=(500, 400),
            anchor=SpriteAnchor.TOP_LEFT,
        )

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.center_on(1000, 800)

        game.push(WorldScene())
        game.tick(dt=0.016)

        assert sprite.position == (500.0, 400.0)

    def test_camera_with_bottom_center_anchor(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Camera offset works correctly with BOTTOM_CENTER anchor."""
        # Default image size is 64x64.
        # BOTTOM_CENTER: dx=32, dy=64.
        # World pos (500, 400) → draw corner (500-32, 400-64) = (468, 336).
        # Camera centered on (500, 400) → top-left (100, 100).
        # Screen pos = (468-100, 336-100) = (368, 236).
        sprite = Sprite("sprites/knight", position=(500, 400))
        draw_positions = {}

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.center_on(500, 400)

            def draw(self) -> None:
                rec = backend.sprites[sprite.sprite_id]
                draw_positions["x"] = rec["x"]
                draw_positions["y"] = rec["y"]

        game.push(WorldScene())
        game.tick(dt=0.016)

        assert draw_positions["x"] == 368
        assert draw_positions["y"] == 236

    def test_multiple_sprites_offset_correctly(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """All sprites in _all_sprites are offset by the camera."""
        s1 = Sprite(
            "sprites/knight", position=(200, 100),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        s2 = Sprite(
            "sprites/knight", position=(600, 500),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        draw_positions = {}

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.center_on(400, 300)
                # Camera top-left = (0, 0) → no offset!

            def draw(self) -> None:
                draw_positions["s1_x"] = backend.sprites[s1.sprite_id]["x"]
                draw_positions["s1_y"] = backend.sprites[s1.sprite_id]["y"]
                draw_positions["s2_x"] = backend.sprites[s2.sprite_id]["x"]
                draw_positions["s2_y"] = backend.sprites[s2.sprite_id]["y"]

        game.push(WorldScene())
        game.tick(dt=0.016)

        # Camera at (0, 0), TOP_LEFT anchors → screen == world.
        assert draw_positions["s1_x"] == 200
        assert draw_positions["s1_y"] == 100
        assert draw_positions["s2_x"] == 600
        assert draw_positions["s2_y"] == 500

    def test_no_camera_scene_draws_at_world_positions(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Without a camera, sprites draw at their world positions (no offset)."""
        sprite = Sprite(
            "sprites/knight", position=(300, 200),
            anchor=SpriteAnchor.TOP_LEFT,
        )

        class UIScene(Scene):
            pass

        game.push(UIScene())
        game.tick(dt=0.016)

        rec = backend.sprites[sprite.sprite_id]
        assert rec["x"] == 300
        assert rec["y"] == 200

    def test_camera_follow_offset_during_draw(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Follow-mode camera applies correct offset during draw."""
        hero = Sprite(
            "sprites/knight", position=(1000, 800),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        other = Sprite(
            "sprites/knight", position=(1100, 850),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        draw_positions = {}

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.follow(hero)

            def draw(self) -> None:
                draw_positions["other_x"] = backend.sprites[other.sprite_id]["x"]
                draw_positions["other_y"] = backend.sprites[other.sprite_id]["y"]

        game.push(WorldScene())
        game.tick(dt=0.016)

        # Camera follows hero at (1000, 800) → top-left (600, 500).
        # Other at (1100, 850) → screen (1100-600, 850-500) = (500, 350).
        assert draw_positions["other_x"] == 500
        assert draw_positions["other_y"] == 350


# ==================================================================
# 9. Mouse coordinate conversion (via camera.screen_to_world)
# ==================================================================

class TestMouseCoordinateConversion:

    def test_screen_to_world_after_center_on(self) -> None:
        """Click at screen center maps to the world center point."""
        cam = Camera((800, 600))
        cam.center_on(2000, 1500)

        wx, wy = cam.screen_to_world(400, 300)

        assert abs(wx - 2000) < 1e-9
        assert abs(wy - 1500) < 1e-9

    def test_screen_to_world_after_scroll(self) -> None:
        """screen_to_world reflects manual scroll offset."""
        cam = Camera((800, 600))
        cam.scroll(200, 150)

        wx, wy = cam.screen_to_world(0, 0)
        assert wx == 200.0
        assert wy == 150.0

    def test_screen_to_world_top_left_click(self) -> None:
        """Clicking screen (0, 0) with camera at (100, 50)."""
        cam = Camera((800, 600))
        cam.scroll(100, 50)

        wx, wy = cam.screen_to_world(0, 0)
        assert wx == 100.0
        assert wy == 50.0

    def test_screen_to_world_bottom_right_click(self) -> None:
        """Clicking bottom-right corner maps to camera far-corner."""
        cam = Camera((800, 600))
        cam.scroll(100, 50)

        wx, wy = cam.screen_to_world(800, 600)
        assert wx == 900.0
        assert wy == 650.0


# ==================================================================
# 10. Sprite registry (_all_sprites)
# ==================================================================

class TestSpriteRegistry:

    def test_sprite_registered_on_creation(self, game: Game) -> None:
        """New sprites are added to game._all_sprites."""
        sprite = Sprite("sprites/knight", position=(100, 100))
        assert sprite in game._all_sprites

    def test_sprite_deregistered_on_removal(self, game: Game) -> None:
        """Removed sprites are removed from game._all_sprites."""
        sprite = Sprite("sprites/knight", position=(100, 100))
        sprite.remove()
        assert sprite not in game._all_sprites

    def test_multiple_sprites_registered(self, game: Game) -> None:
        """Multiple sprites are all registered."""
        s1 = Sprite("sprites/knight", position=(100, 100))
        s2 = Sprite("sprites/knight", position=(200, 200))
        s3 = Sprite("sprites/knight", position=(300, 300))

        assert len(game._all_sprites) >= 3
        assert {s1, s2, s3}.issubset(game._all_sprites)

    def test_double_remove_does_not_crash_registry(self, game: Game) -> None:
        """Double remove is safe for the sprite registry."""
        sprite = Sprite("sprites/knight", position=(100, 100))
        sprite.remove()
        sprite.remove()  # should not raise
        assert sprite not in game._all_sprites


# ==================================================================
# 11. Mouse tracking in Game
# ==================================================================

class TestMouseTracking:

    def test_mouse_move_updates_game_position(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Mouse move events update game._mouse_x/y."""
        game.push(Scene())
        backend.inject_mouse_move(400, 300)
        game.tick(dt=0.016)

        assert game._mouse_x == 400.0
        assert game._mouse_y == 300.0

    def test_mouse_drag_updates_game_position(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Mouse drag events also update game._mouse_x/y."""
        game.push(Scene())
        backend.inject_drag(500, 250, dx=10, dy=0)
        game.tick(dt=0.016)

        assert game._mouse_x == 500.0
        assert game._mouse_y == 250.0

    def test_click_does_not_update_mouse_position(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Click events do NOT update the tracked mouse position."""
        game.push(Scene())
        game._mouse_x = None
        game._mouse_y = None

        backend.inject_click(100, 200)
        game.tick(dt=0.016)

        assert game._mouse_x is None
        assert game._mouse_y is None

    def test_latest_mouse_position_wins(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Multiple mouse moves in one tick: last one wins."""
        game.push(Scene())
        backend.inject_mouse_move(100, 200)
        backend.inject_mouse_move(300, 400)
        backend.inject_mouse_move(500, 600)
        game.tick(dt=0.016)

        assert game._mouse_x == 500.0
        assert game._mouse_y == 600.0


# ==================================================================
# 12. Scene.camera attribute
# ==================================================================

class TestSceneCameraAttribute:

    def test_scene_camera_defaults_to_none(self) -> None:
        """Scene.camera is None by default."""
        scene = Scene()
        assert scene.camera is None

    def test_scene_camera_can_be_set(self) -> None:
        """Scene.camera can be set to a Camera instance."""
        scene = Scene()
        cam = Camera((800, 600))
        scene.camera = cam
        assert scene.camera is cam

    def test_scene_camera_set_in_on_enter(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Camera set in on_enter() is used during tick."""
        draw_called = []

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.center_on(400, 300)

            def draw(self) -> None:
                draw_called.append(True)

        game.push(WorldScene())
        game.tick(dt=0.016)

        assert len(draw_called) == 1


# ==================================================================
# 13. world_bounds property
# ==================================================================

class TestWorldBounds:

    def test_world_bounds_setter_clamps_immediately(self) -> None:
        """Setting world_bounds clamps the current position."""
        cam = Camera((100, 100))
        cam.scroll(500, 500)
        assert cam.x == 500.0

        cam.world_bounds = (0, 0, 200, 200)

        # max_x = 200-100=100, max_y = 200-100=100
        assert cam.x == 100.0
        assert cam.y == 100.0

    def test_world_bounds_none_removes_clamping(self) -> None:
        """Setting world_bounds to None allows unconstrained scrolling."""
        cam = Camera((800, 600), world_bounds=(0, 0, 1000, 1000))
        cam.scroll(500, 500)
        assert cam.x == 200.0  # clamped

        cam.world_bounds = None
        cam.scroll(500, 500)
        assert cam.x == 700.0  # not clamped

    def test_world_bounds_getter(self) -> None:
        """world_bounds getter returns the current bounds."""
        bounds = (10, 20, 1000, 2000)
        cam = Camera((800, 600), world_bounds=bounds)
        assert cam.world_bounds == bounds
