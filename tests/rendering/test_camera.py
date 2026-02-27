"""Tests for Camera: pure math, Scene integration, frustum culling, render sync,
shake behavior, world coordinate conversion, and edge cases.

Merged from:
  - tests/test_camera.py
  - tests/test_camera_shake.py
  - tests/test_world_coords.py
  - tests/test_edge_cases.py (TestCameraNaNInf, TestCameraFollowEdgeCases)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from easygame import Game, Scene, Sprite
from easygame.assets import AssetManager
from easygame.backends.mock_backend import MockBackend
from easygame.input import InputEvent, _with_world_coords
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
        """center_on(500, 400) with 800x600 viewport -> _x=100, _y=100."""
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

        # Would be (100-400, 100-300) = (-300, -200) -> clamped to (0, 0).
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

        # Would be (100-400, 100-300) = (-300, -200) -> clamped to (0, 0).
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
        """screen_to_world -> world_to_screen roundtrips exactly."""
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
        # Sprite at (-30, 300) with 64x64 image -> draw corner (-30, 300).
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
        # Sprite at (-100, 300) with 64x64 -> draw corner (-100, 300).
        # Right edge at -100 + 64 = -36 <= 0, entirely off-screen.
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
        """pan_to accepts a custom ease value."""
        from easygame.util.tween import Ease

        cam = Camera((800, 600))
        cam.center_on(400, 300)

        cam.pan_to(800, 600, duration=1.0, ease=Ease.LINEAR)
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

        # Sprite at (500, 400), TOP_LEFT anchor -> draw corner (500, 400).
        # Camera offset = (100, 100) -> screen pos = (400, 300).
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
        # World pos (500, 400) -> draw corner (500-32, 400-64) = (468, 336).
        # Camera centered on (500, 400) -> top-left (100, 100).
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
                # Camera top-left = (0, 0) -> no offset!

            def draw(self) -> None:
                draw_positions["s1_x"] = backend.sprites[s1.sprite_id]["x"]
                draw_positions["s1_y"] = backend.sprites[s1.sprite_id]["y"]
                draw_positions["s2_x"] = backend.sprites[s2.sprite_id]["x"]
                draw_positions["s2_y"] = backend.sprites[s2.sprite_id]["y"]

        game.push(WorldScene())
        game.tick(dt=0.016)

        # Camera at (0, 0), TOP_LEFT anchors -> screen == world.
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

        # Camera follows hero at (1000, 800) -> top-left (600, 500).
        # Other at (1100, 850) -> screen (1100-600, 850-500) = (500, 350).
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


# ==================================================================
# Bug-fix: handle_input InputEvent type hint
# ==================================================================


class TestHandleInputTypeHint:

    def test_handle_input_accepts_input_event(self, game: Game) -> None:
        """Camera.handle_input works with InputEvent objects."""
        cam = Camera((800, 600))
        cam.enable_key_scroll(speed=300)
        event = InputEvent(type="key_press", key="right", action="right")
        result = cam.handle_input(event)
        assert result is True
        assert "right" in cam._held_dirs


# ==================================================================
# Bug-fix: pan_to ease parameter rename
# ==================================================================


class TestPanToEaseRename:

    def test_pan_to_ease_keyword_works(self, game: Game) -> None:
        """pan_to accepts 'ease' keyword (renamed from 'easing')."""
        from easygame.util.tween import Ease

        cam = Camera((800, 600))
        cam.center_on(400, 300)
        cam.pan_to(800, 600, duration=1.0, ease=Ease.LINEAR)
        game.tick(dt=1.0)
        assert abs(cam.x - 400) < 1e-6

    def test_pan_to_default_ease(self, game: Game) -> None:
        """pan_to with no ease defaults to EASE_IN_OUT."""
        cam = Camera((800, 600))
        cam.center_on(400, 300)
        cam.pan_to(800, 600, duration=1.0)
        game.tick(dt=1.0)
        assert abs(cam.x - 400) < 1e-6


# ==================================================================
# Bug-fix: _cancel_pan uses instance tween manager
# ==================================================================


class TestCancelPanInstanceManager:

    def test_cancel_pan_uses_instance_tween_manager(self, game: Game) -> None:
        """_cancel_pan uses the tween manager captured at pan_to time."""
        cam = Camera((800, 600))
        cam.center_on(400, 300)

        cam.pan_to(800, 600, duration=1.0)
        # Verify the instance reference was captured
        assert cam._tween_manager is not None
        assert cam._tween_manager is game._tween_manager

    def test_cancel_pan_before_any_pan_is_safe(self) -> None:
        """_cancel_pan is safe when no pan has been started."""
        cam = Camera((800, 600))
        assert cam._tween_manager is None
        cam._cancel_pan()  # should not raise
        assert cam._pan_tween_x is None
        assert cam._pan_tween_y is None

    def test_cancel_pan_actually_cancels_tweens(self, game: Game) -> None:
        """_cancel_pan cancels the tween so the camera stops moving."""
        cam = Camera((800, 600))
        cam.center_on(400, 300)

        cam.pan_to(800, 600, duration=2.0)
        game.tick(dt=0.5)
        mid_x = cam.x

        cam._cancel_pan()
        game.tick(dt=1.0)
        # Camera should not have moved further
        assert abs(cam.x - mid_x) < 1e-6


# ==================================================================
# 14. Camera shake — lifecycle
# ==================================================================

class TestCameraShakeLifecycle:

    def test_shake_starts_with_nonzero_offset_in_update(self) -> None:
        """shake(intensity, duration, decay) produces nonzero offset after update()."""
        cam = Camera((800, 600))
        cam.shake(intensity=20.0, duration=1.0, decay=1.0)

        cam.update(0.016)

        assert cam.shake_offset_x != 0.0 or cam.shake_offset_y != 0.0

    def test_shake_decays_to_zero_after_duration(self) -> None:
        """shake(intensity, 1.0, 1.0) ends with zero offsets after duration."""
        cam = Camera((800, 600))
        cam.shake(intensity=20.0, duration=1.0, decay=1.0)

        cam.update(0.5)  # elapsed = 0.5, still shaking
        assert cam._shake_elapsed == 0.5

        cam.update(0.6)  # elapsed = 1.1 >= 1.0, shake ends

        assert cam.shake_offset_x == 0.0
        assert cam.shake_offset_y == 0.0
        assert cam._shake_duration == 0.0

    def test_shake_offset_properties_return_current_offset(self) -> None:
        """shake_offset_x and shake_offset_y return the current offset."""
        cam = Camera((800, 600))
        cam.shake(intensity=10.0, duration=1.0, decay=1.0)
        cam.update(0.016)

        assert cam.shake_offset_x == cam._shake_offset_x
        assert cam.shake_offset_y == cam._shake_offset_y


# ==================================================================
# 15. Camera shake — composition with center_on
# ==================================================================

class TestCameraShakeComposition:

    def test_shake_composes_with_center_on(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Shake offsets are added to _x/_y during sprite sync (draw phase)."""
        sprite = Sprite(
            "sprites/knight", position=(400, 300),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        draw_positions = {}

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.center_on(400, 300)  # _x=0, _y=0
                self.camera.shake(intensity=50.0, duration=1.0, decay=1.0)

            def draw(self) -> None:
                rec = backend.sprites[sprite.sprite_id]
                draw_positions["x"] = rec["x"]
                draw_positions["y"] = rec["y"]
                draw_positions["shake_x"] = self.camera.shake_offset_x
                draw_positions["shake_y"] = self.camera.shake_offset_y

        game.push(WorldScene())
        game.tick(dt=0.016)

        # Without shake: sprite at (400, 300), camera at (0, 0) -> screen (400, 300).
        # With shake: screen = int(world - (camera._x + shake_x, camera._y + shake_y))
        #            = int((400, 300) - (shake_x, shake_y))  -- truncate after subtract
        expected_x = int(400 - draw_positions["shake_x"])
        expected_y = int(300 - draw_positions["shake_y"])
        assert draw_positions["x"] == expected_x
        assert draw_positions["y"] == expected_y


# ==================================================================
# 16. Camera shake — no-op for duration <= 0
# ==================================================================

class TestCameraShakeNoOp:

    def test_shake_duration_zero_resets(self) -> None:
        """shake with duration 0 resets any active shake."""
        cam = Camera((800, 600))
        cam.shake(intensity=20.0, duration=1.0, decay=1.0)
        cam.update(0.016)
        assert cam.shake_offset_x != 0.0 or cam.shake_offset_y != 0.0

        cam.shake(intensity=99.0, duration=0.0, decay=1.0)

        assert cam.shake_offset_x == 0.0
        assert cam.shake_offset_y == 0.0
        assert cam._shake_duration == 0.0
        assert cam._shake_intensity == 0.0

    def test_shake_negative_duration_resets(self) -> None:
        """shake with negative duration resets any active shake."""
        cam = Camera((800, 600))
        cam.shake(intensity=20.0, duration=1.0, decay=1.0)
        cam.update(0.016)

        cam.shake(intensity=99.0, duration=-0.1, decay=1.0)

        assert cam.shake_offset_x == 0.0
        assert cam.shake_offset_y == 0.0
        assert cam._shake_duration == 0.0


# ==================================================================
# 17. Camera shake — multiple calls replace previous
# ==================================================================

class TestCameraShakeReplacement:

    def test_multiple_shake_calls_replace_previous(self) -> None:
        """A new shake() call replaces the previous shake (new params, reset elapsed)."""
        cam = Camera((800, 600))
        cam.shake(intensity=10.0, duration=2.0, decay=1.0)
        cam.update(0.5)  # First shake at 0.5s elapsed

        cam.shake(intensity=5.0, duration=0.5, decay=2.0)  # Replace

        assert cam._shake_intensity == 5.0
        assert cam._shake_duration == 0.5
        assert cam._shake_decay == 2.0
        assert cam._shake_elapsed == 0.0

        # Second shake should end after 0.5s total
        cam.update(0.3)
        cam.update(0.3)  # elapsed = 0.6 >= 0.5
        assert cam.shake_offset_x == 0.0
        assert cam.shake_offset_y == 0.0


# ==================================================================
# 18. Camera shake — randomness
# ==================================================================

class TestCameraShakeRandomness:

    def test_shake_offsets_change_across_updates(self) -> None:
        """Shake offsets are random -- multiple updates produce different values."""
        cam = Camera((800, 600))
        cam.shake(intensity=20.0, duration=1.0, decay=1.0)

        offsets: list[tuple[float, float]] = []
        for _ in range(8):
            cam.update(0.01)
            offsets.append((cam.shake_offset_x, cam.shake_offset_y))

        # At least two distinct offset pairs (allowing for rare collision).
        unique = set(offsets)
        assert len(unique) >= 2, "Shake offsets should vary across updates"


# ==================================================================
# 19. InputEvent world_x / world_y field defaults
# ==================================================================


class TestInputEventWorldFields:
    """world_x and world_y default to None and are part of the frozen dataclass."""

    def test_defaults_are_none(self) -> None:
        e = InputEvent(type="key_press", key="a")
        assert e.world_x is None
        assert e.world_y is None

    def test_mouse_event_defaults_are_none(self) -> None:
        """Before framework dispatch, mouse events have world_x/y = None."""
        e = InputEvent(type="click", x=400, y=300, button="left")
        assert e.world_x is None
        assert e.world_y is None

    def test_can_be_set_explicitly(self) -> None:
        e = InputEvent(type="click", x=400, y=300, button="left",
                       world_x=500.0, world_y=400.0)
        assert e.world_x == 500.0
        assert e.world_y == 400.0

    def test_frozen_world_fields(self) -> None:
        e = InputEvent(type="click", x=100, y=200, world_x=1.0, world_y=2.0)
        with pytest.raises(AttributeError):
            e.world_x = 99.0  # type: ignore[misc]


# ==================================================================
# 20. _with_world_coords helper — unit tests
# ==================================================================


class TestWithWorldCoords:
    """Direct tests of the _with_world_coords helper function."""

    def test_mouse_click_with_camera(self) -> None:
        """Camera-transformed coords for a click event."""
        cam = Camera((800, 600))
        cam.scroll(100, 50)  # camera at (100, 50)

        event = InputEvent(type="click", x=400, y=300, button="left")
        result = _with_world_coords(event, cam)

        # screen_to_world(400, 300) = (400+100, 300+50) = (500, 350)
        assert result.world_x == 500.0
        assert result.world_y == 350.0
        # Original screen coords preserved.
        assert result.x == 400
        assert result.y == 300

    def test_mouse_move_with_camera(self) -> None:
        cam = Camera((800, 600))
        cam.scroll(200, 100)

        event = InputEvent(type="move", x=0, y=0)
        result = _with_world_coords(event, cam)

        assert result.world_x == 200.0
        assert result.world_y == 100.0

    def test_mouse_drag_with_camera(self) -> None:
        cam = Camera((800, 600))
        cam.scroll(50, 25)

        event = InputEvent(type="drag", x=100, y=200, button="left", dx=5, dy=3)
        result = _with_world_coords(event, cam)

        assert result.world_x == 150.0
        assert result.world_y == 225.0
        # Deltas are unchanged.
        assert result.dx == 5
        assert result.dy == 3

    def test_mouse_scroll_with_camera(self) -> None:
        cam = Camera((800, 600))
        cam.scroll(10, 20)

        event = InputEvent(type="scroll", x=300, y=400, dx=0, dy=-3)
        result = _with_world_coords(event, cam)

        assert result.world_x == 310.0
        assert result.world_y == 420.0

    def test_mouse_release_with_camera(self) -> None:
        cam = Camera((800, 600))
        cam.scroll(30, 40)

        event = InputEvent(type="release", x=100, y=200, button="left")
        result = _with_world_coords(event, cam)

        assert result.world_x == 130.0
        assert result.world_y == 240.0

    def test_mouse_click_no_camera(self) -> None:
        """Without a camera, world coords equal screen coords."""
        event = InputEvent(type="click", x=400, y=300, button="left")
        result = _with_world_coords(event, None)

        assert result.world_x == 400.0
        assert result.world_y == 300.0

    def test_mouse_move_no_camera(self) -> None:
        event = InputEvent(type="move", x=123, y=456)
        result = _with_world_coords(event, None)

        assert result.world_x == 123.0
        assert result.world_y == 456.0

    def test_keyboard_event_unchanged(self) -> None:
        """Keyboard events are returned with world_x/y = None."""
        cam = Camera((800, 600))
        cam.scroll(100, 100)

        event = InputEvent(type="key_press", key="a", action="attack")
        result = _with_world_coords(event, cam)

        assert result.world_x is None
        assert result.world_y is None
        # Same object (no copy needed).
        assert result is event

    def test_key_release_unchanged(self) -> None:
        event = InputEvent(type="key_release", key="space")
        result = _with_world_coords(event, None)

        assert result.world_x is None
        assert result.world_y is None
        assert result is event

    def test_camera_after_center_on(self) -> None:
        """World coords reflect camera.center_on positioning."""
        cam = Camera((800, 600))
        cam.center_on(1000, 800)
        # Camera top-left = (1000-400, 800-300) = (600, 500)

        event = InputEvent(type="click", x=400, y=300, button="left")
        result = _with_world_coords(event, cam)

        # screen_to_world(400, 300) = (400+600, 300+500) = (1000, 800)
        assert abs(result.world_x - 1000.0) < 1e-9
        assert abs(result.world_y - 800.0) < 1e-9

    def test_returns_new_frozen_instance(self) -> None:
        """_with_world_coords returns a new InputEvent, not the same one."""
        event = InputEvent(type="click", x=100, y=200, button="left")
        result = _with_world_coords(event, None)

        assert result is not event
        assert result.world_x == 100.0
        assert result.world_y == 200.0


# ==================================================================
# 21. Game integration — scene receives events with world coords
# ==================================================================


class TestGameWorldCoordsIntegration:
    """End-to-end: scenes receive InputEvents with world_x/world_y populated."""

    def test_click_with_camera_scene(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Scene with camera receives click with correct world coords."""
        class WorldScene(Scene):
            def __init__(self) -> None:
                self.events: list[InputEvent] = []

            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.scroll(100, 50)

            def handle_input(self, event: InputEvent) -> bool:
                self.events.append(event)
                return False

        scene = WorldScene()
        game.push(scene)
        backend.inject_click(400, 300)
        game.tick(dt=0.016)

        assert len(scene.events) == 1
        e = scene.events[0]
        assert e.x == 400
        assert e.y == 300
        assert e.world_x == 500.0  # 400 + 100
        assert e.world_y == 350.0  # 300 + 50

    def test_click_without_camera_scene(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Scene without camera receives click with world == screen."""
        class UIScene(Scene):
            def __init__(self) -> None:
                self.events: list[InputEvent] = []

            def handle_input(self, event: InputEvent) -> bool:
                self.events.append(event)
                return False

        scene = UIScene()
        game.push(scene)
        backend.inject_click(400, 300)
        game.tick(dt=0.016)

        e = scene.events[0]
        assert e.world_x == 400.0
        assert e.world_y == 300.0

    def test_key_event_has_no_world_coords(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Keyboard events arrive with world_x/world_y = None."""
        class Tracker(Scene):
            def __init__(self) -> None:
                self.events: list[InputEvent] = []

            def handle_input(self, event: InputEvent) -> bool:
                self.events.append(event)
                return False

        scene = Tracker()
        game.push(scene)
        backend.inject_key("a")
        game.tick(dt=0.016)

        e = scene.events[0]
        assert e.world_x is None
        assert e.world_y is None

    def test_mouse_move_with_camera(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Mouse move events get world coords via camera."""
        class WorldScene(Scene):
            def __init__(self) -> None:
                self.events: list[InputEvent] = []

            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.scroll(200, 100)

            def handle_input(self, event: InputEvent) -> bool:
                self.events.append(event)
                return False

        scene = WorldScene()
        game.push(scene)
        backend.inject_mouse_move(300, 250)
        game.tick(dt=0.016)

        e = scene.events[0]
        assert e.type == "move"
        assert e.world_x == 500.0  # 300 + 200
        assert e.world_y == 350.0  # 250 + 100

    def test_world_coords_update_after_camera_scroll(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """After camera scrolls, subsequent events have new world coords."""
        class WorldScene(Scene):
            def __init__(self) -> None:
                self.events: list[InputEvent] = []

            def on_enter(self) -> None:
                self.camera = Camera((800, 600))

            def handle_input(self, event: InputEvent) -> bool:
                self.events.append(event)
                return False

        scene = WorldScene()
        game.push(scene)

        # First click: camera at (0, 0).
        backend.inject_click(400, 300)
        game.tick(dt=0.016)
        e1 = scene.events[0]
        assert e1.world_x == 400.0
        assert e1.world_y == 300.0

        # Scroll camera.
        scene.camera.scroll(100, 50)

        # Second click: same screen coords, different world coords.
        backend.inject_click(400, 300)
        game.tick(dt=0.016)
        e2 = scene.events[1]
        assert e2.world_x == 500.0
        assert e2.world_y == 350.0

    def test_world_coords_with_centered_camera(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Click at screen center maps to the camera center_on target."""
        class WorldScene(Scene):
            def __init__(self) -> None:
                self.events: list[InputEvent] = []

            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.center_on(2000, 1500)

            def handle_input(self, event: InputEvent) -> bool:
                self.events.append(event)
                return False

        scene = WorldScene()
        game.push(scene)
        # Click at screen center (400, 300).
        backend.inject_click(400, 300)
        game.tick(dt=0.016)

        e = scene.events[0]
        assert abs(e.world_x - 2000.0) < 1e-9
        assert abs(e.world_y - 1500.0) < 1e-9

    def test_drag_event_has_world_coords(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Drag events also get world coordinates."""
        class WorldScene(Scene):
            def __init__(self) -> None:
                self.events: list[InputEvent] = []

            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.scroll(50, 25)

            def handle_input(self, event: InputEvent) -> bool:
                self.events.append(event)
                return False

        scene = WorldScene()
        game.push(scene)
        backend.inject_drag(200, 150, dx=10, dy=5)
        game.tick(dt=0.016)

        e = scene.events[0]
        assert e.type == "drag"
        assert e.world_x == 250.0
        assert e.world_y == 175.0

    def test_multiple_events_in_one_tick(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Mixed key + mouse events: only mouse events get world coords."""
        class WorldScene(Scene):
            def __init__(self) -> None:
                self.events: list[InputEvent] = []

            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.scroll(50, 50)

            def handle_input(self, event: InputEvent) -> bool:
                self.events.append(event)
                return False

        scene = WorldScene()
        game.push(scene)
        backend.inject_key("a")
        backend.inject_click(100, 200)
        backend.inject_key("b")
        game.tick(dt=0.016)

        # Key events: world_x/y = None.
        assert scene.events[0].type == "key_press"
        assert scene.events[0].world_x is None

        # Mouse event: world coords populated.
        assert scene.events[1].type == "click"
        assert scene.events[1].world_x == 150.0
        assert scene.events[1].world_y == 250.0

        # Another key event.
        assert scene.events[2].type == "key_press"
        assert scene.events[2].world_x is None

    def test_screen_coords_preserved(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Adding world coords does not alter the original x/y fields."""
        class WorldScene(Scene):
            def __init__(self) -> None:
                self.events: list[InputEvent] = []

            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.scroll(999, 888)

            def handle_input(self, event: InputEvent) -> bool:
                self.events.append(event)
                return False

        scene = WorldScene()
        game.push(scene)
        backend.inject_click(123, 456)
        game.tick(dt=0.016)

        e = scene.events[0]
        assert e.x == 123
        assert e.y == 456
        assert e.world_x == 1122.0  # 123 + 999
        assert e.world_y == 1344.0  # 456 + 888


# ==================================================================
# 22. Camera NaN/Inf edge cases (from test_edge_cases.py)
# ==================================================================


class TestCameraNaNInf:
    """Camera.center_on() should reject NaN/Inf coordinates."""

    def test_center_on_nan_raises(self) -> None:
        """center_on(NaN, NaN) raises ValueError."""
        cam = Camera((800, 600))
        with pytest.raises(ValueError, match="camera coordinates must be finite"):
            cam.center_on(float("nan"), float("nan"))

    def test_center_on_inf_raises(self) -> None:
        """center_on(inf, -inf) raises ValueError."""
        cam = Camera((800, 600))
        with pytest.raises(ValueError, match="camera coordinates must be finite"):
            cam.center_on(float("inf"), float("-inf"))

    def test_center_on_inf_with_bounds_raises(self) -> None:
        """center_on(inf, inf) with bounds raises ValueError before clamping."""
        cam = Camera((800, 600), world_bounds=(0, 0, 2000, 2000))
        with pytest.raises(ValueError, match="camera coordinates must be finite"):
            cam.center_on(float("inf"), float("inf"))

    def test_center_on_finite_works(self) -> None:
        """center_on() with normal finite coordinates works correctly."""
        cam = Camera((800, 600))
        cam.center_on(500.0, 400.0)
        # viewport top-left = (500 - 400, 400 - 300) = (100, 100)
        assert cam.x == 100.0
        assert cam.y == 100.0

    def test_shake_zero_duration_is_noop(self) -> None:
        """shake(intensity=5, duration=0) resets shake state."""
        cam = Camera((800, 600))
        cam.shake(5.0, 0.0, 1.0)
        assert cam.shake_offset_x == 0.0
        assert cam.shake_offset_y == 0.0

    def test_world_bounds_smaller_than_viewport(self) -> None:
        """World bounds smaller than viewport doesn't crash."""
        cam = Camera((800, 600), world_bounds=(0, 0, 400, 300))
        cam.center_on(200.0, 150.0)
        # Camera should still function (clamp handles this).


# ==================================================================
# 23. Camera follow edge cases (from test_edge_cases.py)
# ==================================================================


class TestCameraFollowEdgeCases:
    """Camera follow edge cases that pass (no findings)."""

    def test_follow_none_stops_following(self) -> None:
        """follow(None) disables following."""
        cam = Camera((800, 600))
        cam.follow(None)
        # Should not crash on update with no follow target.
        cam.update(0.016)

    def test_pan_to_zero_duration(self, game: Game) -> None:
        """pan_to with duration=0 still works (instant pan)."""
        cam = Camera((800, 600))
        # Duration of 0 -- tween system handles it.
        cam.pan_to(500, 400, 0.0)
