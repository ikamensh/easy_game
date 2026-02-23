"""Tests for Scene drawing helpers: draw_rect and draw_world_rect."""

from __future__ import annotations

import pytest

from easygame import Game, Scene
from easygame.backends.mock_backend import MockBackend
from easygame.rendering.camera import Camera


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def game() -> Game:
    return Game("Test", backend="mock", resolution=(800, 600))


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


# ------------------------------------------------------------------
# draw_rect — screen-space
# ------------------------------------------------------------------


def test_draw_rect_delegates_to_backend(game: Game, backend: MockBackend) -> None:
    """draw_rect() records the rect in the backend."""
    color = (255, 0, 0, 255)

    class DrawScene(Scene):
        def draw(self) -> None:
            self.draw_rect(10, 20, 100, 50, color)

    game.push(DrawScene())
    game.tick(dt=0.016)

    assert len(backend.rects) == 1
    rect = backend.rects[0]
    assert rect["x"] == 10
    assert rect["y"] == 20
    assert rect["width"] == 100
    assert rect["height"] == 50
    assert rect["color"] == color
    assert rect["opacity"] == 1.0


def test_draw_rect_with_opacity(game: Game, backend: MockBackend) -> None:
    """draw_rect() passes opacity to the backend."""
    color = (0, 255, 0, 128)

    class DrawScene(Scene):
        def draw(self) -> None:
            self.draw_rect(0, 0, 50, 50, color, opacity=0.5)

    game.push(DrawScene())
    game.tick(dt=0.016)

    assert len(backend.rects) == 1
    assert backend.rects[0]["opacity"] == 0.5


def test_draw_rect_converts_floats_to_int(game: Game, backend: MockBackend) -> None:
    """draw_rect() truncates float coords to int."""
    color = (255, 255, 255, 255)

    class DrawScene(Scene):
        def draw(self) -> None:
            self.draw_rect(10.7, 20.3, 100.9, 50.1, color)

    game.push(DrawScene())
    game.tick(dt=0.016)

    rect = backend.rects[0]
    assert rect["x"] == 10
    assert rect["y"] == 20
    assert rect["width"] == 100
    assert rect["height"] == 50


def test_draw_rect_multiple_calls(game: Game, backend: MockBackend) -> None:
    """Multiple draw_rect() calls produce multiple backend entries."""
    color1 = (255, 0, 0, 255)
    color2 = (0, 0, 255, 255)

    class DrawScene(Scene):
        def draw(self) -> None:
            self.draw_rect(0, 0, 10, 10, color1)
            self.draw_rect(50, 50, 20, 20, color2)

    game.push(DrawScene())
    game.tick(dt=0.016)

    assert len(backend.rects) == 2
    assert backend.rects[0]["color"] == color1
    assert backend.rects[1]["color"] == color2


# ------------------------------------------------------------------
# draw_world_rect — world-space with camera transform
# ------------------------------------------------------------------


def test_draw_world_rect_applies_camera_offset(
    game: Game, backend: MockBackend,
) -> None:
    """draw_world_rect() transforms world coords to screen via camera."""
    color = (255, 0, 0, 255)

    class WorldScene(Scene):
        def on_enter(self) -> None:
            self.camera = Camera((800, 600))
            # Scroll camera so top-left is at (100, 50) in world space.
            self.camera.scroll(100, 50)

        def draw(self) -> None:
            # World position (200, 150) should map to screen (100, 100).
            self.draw_world_rect(200, 150, 30, 10, color)

    game.push(WorldScene())
    game.tick(dt=0.016)

    assert len(backend.rects) == 1
    rect = backend.rects[0]
    assert rect["x"] == 100  # 200 - 100
    assert rect["y"] == 100  # 150 - 50
    assert rect["width"] == 30
    assert rect["height"] == 10
    assert rect["color"] == color


def test_draw_world_rect_no_scroll(game: Game, backend: MockBackend) -> None:
    """draw_world_rect() with camera at origin passes world coords through."""
    color = (0, 128, 255, 200)

    class WorldScene(Scene):
        def on_enter(self) -> None:
            self.camera = Camera((800, 600))

        def draw(self) -> None:
            self.draw_world_rect(50, 75, 40, 20, color)

    game.push(WorldScene())
    game.tick(dt=0.016)

    rect = backend.rects[0]
    assert rect["x"] == 50
    assert rect["y"] == 75


def test_draw_world_rect_with_opacity(
    game: Game, backend: MockBackend,
) -> None:
    """draw_world_rect() passes opacity to the backend."""
    color = (0, 255, 0, 128)

    class WorldScene(Scene):
        def on_enter(self) -> None:
            self.camera = Camera((800, 600))

        def draw(self) -> None:
            self.draw_world_rect(10, 10, 20, 20, color, opacity=0.75)

    game.push(WorldScene())
    game.tick(dt=0.016)

    assert backend.rects[0]["opacity"] == 0.75


def test_draw_world_rect_without_camera_raises(game: Game) -> None:
    """draw_world_rect() raises RuntimeError when no camera is set."""
    color = (255, 0, 0, 255)

    class NoCamera(Scene):
        def draw(self) -> None:
            self.draw_world_rect(10, 20, 30, 40, color)

    game.push(NoCamera())

    with pytest.raises(RuntimeError, match="requires a camera"):
        game.tick(dt=0.016)


def test_draw_world_rect_negative_camera_offset(
    game: Game, backend: MockBackend,
) -> None:
    """draw_world_rect() works correctly with negative camera offsets."""
    color = (255, 255, 0, 255)

    class WorldScene(Scene):
        def on_enter(self) -> None:
            self.camera = Camera((800, 600))
            # Camera center_on moves top-left to negative world coords
            # when centering at (0,0) — top-left becomes (-400, -300).
            self.camera.center_on(0, 0)

        def draw(self) -> None:
            # World (0, 0) → screen (400, 300) because camera TL is (-400,-300)
            self.draw_world_rect(0, 0, 10, 10, color)

    game.push(WorldScene())
    game.tick(dt=0.016)

    rect = backend.rects[0]
    assert rect["x"] == 400
    assert rect["y"] == 300


def test_draw_world_rect_converts_floats_to_int(
    game: Game, backend: MockBackend,
) -> None:
    """draw_world_rect() truncates float results to int."""
    color = (255, 255, 255, 255)

    class WorldScene(Scene):
        def on_enter(self) -> None:
            self.camera = Camera((800, 600))
            # Scroll by fractional amount.
            self.camera.scroll(0.5, 0.3)

        def draw(self) -> None:
            self.draw_world_rect(10.7, 20.9, 30.5, 15.2, color)

    game.push(WorldScene())
    game.tick(dt=0.016)

    rect = backend.rects[0]
    # x: int(10.7 - 0.5) = int(10.2) = 10
    assert rect["x"] == 10
    # y: int(20.9 - 0.3) = int(20.6) = 20
    assert rect["y"] == 20
    assert rect["width"] == 30
    assert rect["height"] == 15


def test_draw_world_rect_multiple_rects(
    game: Game, backend: MockBackend,
) -> None:
    """Multiple draw_world_rect() calls produce correct screen positions."""
    color_bg = (50, 50, 50, 255)
    color_fill = (0, 200, 0, 255)

    class WorldScene(Scene):
        def on_enter(self) -> None:
            self.camera = Camera((800, 600))
            self.camera.scroll(200, 100)

        def draw(self) -> None:
            # Health bar background at world (300, 200) → screen (100, 100)
            self.draw_world_rect(300, 200, 40, 6, color_bg)
            # Health bar fill at world (300, 200) → screen (100, 100)
            self.draw_world_rect(300, 200, 30, 6, color_fill)

    game.push(WorldScene())
    game.tick(dt=0.016)

    assert len(backend.rects) == 2
    assert backend.rects[0]["x"] == 100
    assert backend.rects[0]["width"] == 40
    assert backend.rects[0]["color"] == color_bg
    assert backend.rects[1]["x"] == 100
    assert backend.rects[1]["width"] == 30
    assert backend.rects[1]["color"] == color_fill


# ------------------------------------------------------------------
# Per-frame clearing: rects don't leak across frames
# ------------------------------------------------------------------


def test_rects_cleared_each_frame(game: Game, backend: MockBackend) -> None:
    """draw_rect calls are cleared each frame (backend.begin_frame)."""
    call_count = 0

    class DrawScene(Scene):
        def draw(self) -> None:
            nonlocal call_count
            call_count += 1
            self.draw_rect(0, 0, 10, 10, (255, 0, 0, 255))

    game.push(DrawScene())
    game.tick(dt=0.016)
    assert len(backend.rects) == 1

    game.tick(dt=0.016)
    # Each frame produces exactly 1 rect (the previous frame's rect was cleared).
    assert len(backend.rects) == 1
    assert call_count == 2
