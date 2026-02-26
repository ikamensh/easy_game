"""Tests for automatic world_x/world_y population on InputEvent.

Friction point #7: mouse events dispatched to scenes should carry
camera-transformed world coordinates so game code never needs to call
camera.screen_to_world() manually.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from easygame import Game, Scene
from easygame.assets import AssetManager
from easygame.backends.mock_backend import MockBackend
from easygame.input import InputEvent, _with_world_coords
from easygame.rendering.camera import Camera


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    images = tmp_path / "images" / "sprites"
    images.mkdir(parents=True)
    (images / "knight.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def game(asset_dir: Path) -> Game:
    g = Game("Test", backend="mock", resolution=(800, 600))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    return g


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


# ==================================================================
# 1. InputEvent dataclass — world_x / world_y field defaults
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
# 2. _with_world_coords helper — unit tests
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
# 3. Game integration — scene receives events with world coords
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
