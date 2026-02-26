"""Tests for Stage 12 — Drag-and-Drop system.

Tests cover:
- DragManager lifecycle (start, move, drop, cancel)
- Component drag-drop attributes
- Ghost position tracking
- Drop target hit-testing and acceptance
- Reject drops on invalid targets
- Cancel drag with Escape
- Visual feedback (ghost rendering, highlight colors)
- Integration with _UIRoot and Game.tick()
- Edge cases (non-draggable, disabled, invisible, etc.)
"""

from __future__ import annotations

import pytest

from easygame import Game, Scene
from easygame.backends.base import MouseEvent
from easygame.input import InputEvent
from easygame.ui.component import Component
from easygame.ui.drag_drop import DragManager, _DragSession
from easygame.ui.theme import Theme


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_game() -> Game:
    """Return a Game instance with backend='mock' for headless testing."""
    return Game("Test", backend="mock", resolution=(800, 600))


@pytest.fixture
def mock_backend(mock_game: Game) -> object:
    return mock_game.backend


@pytest.fixture
def scene_with_ui(mock_game: Game) -> Scene:
    """Push a scene and return it (with game reference set)."""
    scene = Scene()
    mock_game.push(scene)
    return scene


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FixedBox(Component):
    """Component that pins its computed position regardless of layout.

    Overrides ``compute_layout`` to always use the position set at
    construction, ignoring the parent's layout pass.  This makes tests
    deterministic without depending on anchor/flow layout.
    """

    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        w: int = 64,
        h: int = 64,
        draggable: bool = False,
        drag_data=None,
        drop_accept=None,
        on_drop=None,
    ) -> None:
        super().__init__(
            width=w,
            height=h,
            draggable=draggable,
            drag_data=drag_data,
            drop_accept=drop_accept,
            on_drop=on_drop,
        )
        self._fixed_x = x
        self._fixed_y = y

    def compute_layout(self, x: int, y: int, w: int, h: int) -> None:
        self._computed_x = self._fixed_x
        self._computed_y = self._fixed_y
        self._computed_w = self._width or 64
        self._computed_h = self._height or 64
        self._layout_children()
        self._layout_dirty = False


def _make_box(
    *,
    x: int = 0,
    y: int = 0,
    w: int = 64,
    h: int = 64,
    draggable: bool = False,
    drag_data=None,
    drop_accept=None,
    on_drop=None,
) -> _FixedBox:
    """Create a Component with fixed layout position for testing."""
    return _FixedBox(
        x=x, y=y, w=w, h=h,
        draggable=draggable,
        drag_data=drag_data,
        drop_accept=drop_accept,
        on_drop=on_drop,
    )


# ===========================================================================
# TestDragManagerConstruction
# ===========================================================================

class TestDragManagerConstruction:
    """DragManager basic lifecycle."""

    def test_initial_state(self, scene_with_ui) -> None:
        dm = scene_with_ui.ui.drag_manager
        assert isinstance(dm, DragManager)
        assert dm.is_dragging is False
        assert dm.drag_data is None

    def test_lazy_creation(self, scene_with_ui) -> None:
        """DragManager is not created until first access."""
        # Access .ui to create _UIRoot, but _drag_manager should still be None.
        root = scene_with_ui.ui
        assert root._drag_manager is None
        _ = root.drag_manager
        assert root._drag_manager is not None

    def test_same_instance(self, scene_with_ui) -> None:
        """Repeated access returns the same DragManager."""
        dm1 = scene_with_ui.ui.drag_manager
        dm2 = scene_with_ui.ui.drag_manager
        assert dm1 is dm2


# ===========================================================================
# TestComponentDragAttributes
# ===========================================================================

class TestComponentDragAttributes:
    """Component drag-drop attribute defaults and settings."""

    def test_defaults(self) -> None:
        c = Component(width=10, height=10)
        assert c.draggable is False
        assert c.drag_data is None
        assert c.drop_accept is None
        assert c.on_drop is None

    def test_draggable_set(self) -> None:
        c = Component(width=10, height=10, draggable=True, drag_data="sword")
        assert c.draggable is True
        assert c.drag_data == "sword"

    def test_drop_target_set(self) -> None:
        accept_fn = lambda data: isinstance(data, str)
        drop_fn = lambda comp, data: None
        c = Component(
            width=10, height=10,
            drop_accept=accept_fn,
            on_drop=drop_fn,
        )
        assert c.drop_accept is accept_fn
        assert c.on_drop is drop_fn

    def test_attributes_mutable(self) -> None:
        c = Component(width=10, height=10)
        c.draggable = True
        c.drag_data = {"item": "potion"}
        assert c.draggable is True
        assert c.drag_data == {"item": "potion"}


# ===========================================================================
# TestDragStart
# ===========================================================================

class TestDragStart:
    """Starting a drag session via click on draggable component."""

    def test_click_on_draggable_starts_drag(self, scene_with_ui) -> None:
        root = scene_with_ui.ui
        box = _make_box(x=100, y=100, draggable=True, drag_data="item_A")
        root.add(box)
        root._ensure_layout()

        event = InputEvent(type="click", x=120, y=120, button="left")
        consumed = root.handle_event(event)

        assert consumed is True
        assert root.drag_manager.is_dragging is True
        assert root.drag_manager.drag_data == "item_A"

    def test_click_on_non_draggable_no_drag(self, scene_with_ui) -> None:
        root = scene_with_ui.ui
        box = _make_box(x=100, y=100, draggable=False)
        root.add(box)
        root._ensure_layout()

        event = InputEvent(type="click", x=120, y=120, button="left")
        root.handle_event(event)

        assert root.drag_manager.is_dragging is False

    def test_right_click_does_not_start_drag(self, scene_with_ui) -> None:
        root = scene_with_ui.ui
        box = _make_box(x=100, y=100, draggable=True, drag_data="x")
        root.add(box)
        root._ensure_layout()

        event = InputEvent(type="click", x=120, y=120, button="right")
        root.handle_event(event)

        assert root.drag_manager.is_dragging is False

    def test_click_outside_does_not_start_drag(self, scene_with_ui) -> None:
        root = scene_with_ui.ui
        box = _make_box(x=100, y=100, w=50, h=50, draggable=True, drag_data="x")
        root.add(box)
        root._ensure_layout()

        event = InputEvent(type="click", x=200, y=200, button="left")
        root.handle_event(event)

        assert root.drag_manager.is_dragging is False

    def test_disabled_component_no_drag(self, scene_with_ui) -> None:
        root = scene_with_ui.ui
        box = _make_box(x=100, y=100, draggable=True, drag_data="x")
        box.enabled = False
        root.add(box)
        root._ensure_layout()

        event = InputEvent(type="click", x=120, y=120, button="left")
        root.handle_event(event)

        assert root.drag_manager.is_dragging is False

    def test_invisible_component_no_drag(self, scene_with_ui) -> None:
        root = scene_with_ui.ui
        box = _make_box(x=100, y=100, draggable=True, drag_data="x")
        box.visible = False
        root.add(box)
        root._ensure_layout()

        event = InputEvent(type="click", x=120, y=120, button="left")
        root.handle_event(event)

        assert root.drag_manager.is_dragging is False


# ===========================================================================
# TestGhostTracking
# ===========================================================================

class TestGhostTracking:
    """Ghost position tracking during drag."""

    def test_ghost_starts_at_source_position(self, scene_with_ui) -> None:
        root = scene_with_ui.ui
        box = _make_box(x=100, y=100, draggable=True, drag_data="x")
        root.add(box)
        root._ensure_layout()

        # Click at (120, 130) — inside box at (100, 100)
        root.handle_event(InputEvent(type="click", x=120, y=130, button="left"))

        dm = root.drag_manager
        session = dm._active
        assert session is not None
        assert session.ghost_x == 100  # source._computed_x
        assert session.ghost_y == 100  # source._computed_y

    def test_ghost_follows_move(self, scene_with_ui) -> None:
        root = scene_with_ui.ui
        box = _make_box(x=100, y=100, draggable=True, drag_data="x")
        root.add(box)
        root._ensure_layout()

        # Click at (120, 130)
        root.handle_event(InputEvent(type="click", x=120, y=130, button="left"))
        dm = root.drag_manager

        # Move to (200, 250) — ghost should track with offset
        root.handle_event(InputEvent(type="move", x=200, y=250))

        session = dm._active
        # ghost_offset_x = 100 - 120 = -20, ghost_offset_y = 100 - 130 = -30
        # ghost_x = 200 + (-20) = 180, ghost_y = 250 + (-30) = 220
        assert session.ghost_x == 180
        assert session.ghost_y == 220

    def test_ghost_follows_drag_event(self, scene_with_ui) -> None:
        root = scene_with_ui.ui
        box = _make_box(x=100, y=100, draggable=True, drag_data="x")
        root.add(box)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=100, y=100, button="left"))
        dm = root.drag_manager

        # "drag" events also track ghost
        root.handle_event(InputEvent(type="drag", x=150, y=160, dx=50, dy=60))

        session = dm._active
        # ghost_offset = (100 - 100, 100 - 100) = (0, 0)
        assert session.ghost_x == 150
        assert session.ghost_y == 160


# ===========================================================================
# TestDropOnValidTarget
# ===========================================================================

class TestDropOnValidTarget:
    """Dropping on a component that accepts the data."""

    def test_drop_fires_on_drop(self, scene_with_ui) -> None:
        dropped = []
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="potion")
        target = _make_box(
            x=200, y=200,
            drop_accept=lambda data: data == "potion",
            on_drop=lambda comp, data: dropped.append((comp, data)),
        )
        root.add(source)
        root.add(target)
        root._ensure_layout()

        # Start drag
        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        assert root.drag_manager.is_dragging

        # Move over target
        root.handle_event(InputEvent(type="move", x=220, y=220))

        # Release on target
        root.handle_event(InputEvent(type="release", x=220, y=220, button="left"))

        assert root.drag_manager.is_dragging is False
        assert len(dropped) == 1
        assert dropped[0][0] is target
        assert dropped[0][1] == "potion"

    def test_drop_on_target_that_rejects(self, scene_with_ui) -> None:
        dropped = []
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="sword")
        target = _make_box(
            x=200, y=200,
            drop_accept=lambda data: data == "potion",  # rejects "sword"
            on_drop=lambda comp, data: dropped.append(data),
        )
        root.add(source)
        root.add(target)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        root.handle_event(InputEvent(type="move", x=220, y=220))
        root.handle_event(InputEvent(type="release", x=220, y=220, button="left"))

        assert root.drag_manager.is_dragging is False
        assert len(dropped) == 0  # on_drop NOT called

    def test_drop_on_non_target(self, scene_with_ui) -> None:
        dropped: list[str] = []
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="item")
        non_target = _make_box(x=200, y=200)  # no drop_accept
        root.add(source)
        root.add(non_target)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        root.handle_event(InputEvent(type="move", x=220, y=220))
        root.handle_event(InputEvent(type="release", x=220, y=220, button="left"))

        assert root.drag_manager.is_dragging is False
        assert len(dropped) == 0

    def test_drop_on_empty_space(self, scene_with_ui) -> None:
        """Releasing over empty space cancels drag without error."""
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="item")
        root.add(source)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        root.handle_event(InputEvent(type="move", x=700, y=500))
        root.handle_event(InputEvent(type="release", x=700, y=500, button="left"))

        assert root.drag_manager.is_dragging is False


# ===========================================================================
# TestCancelDrag
# ===========================================================================

class TestCancelDrag:
    """Cancelling a drag with Escape key."""

    def test_escape_cancels_drag(self, scene_with_ui) -> None:
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="item")
        root.add(source)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        assert root.drag_manager.is_dragging

        consumed = root.handle_event(
            InputEvent(type="key_press", key="escape", action="cancel"),
        )
        assert consumed is True
        assert root.drag_manager.is_dragging is False

    def test_non_cancel_key_during_drag_consumed(self, scene_with_ui) -> None:
        """Other key events are consumed during drag (not passed through)."""
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="item")
        root.add(source)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        assert root.drag_manager.is_dragging

        consumed = root.handle_event(
            InputEvent(type="key_press", key="a"),
        )
        assert consumed is True
        assert root.drag_manager.is_dragging is True  # still dragging


# ===========================================================================
# TestDropTargetFeedback
# ===========================================================================

class TestDropTargetFeedback:
    """Drop target highlight state tracking during drag."""

    def test_hover_over_accepting_target(self, scene_with_ui) -> None:
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="item")
        target = _make_box(
            x=200, y=200,
            drop_accept=lambda data: True,
            on_drop=lambda c, d: None,
        )
        root.add(source)
        root.add(target)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        root.handle_event(InputEvent(type="move", x=220, y=220))

        session = root.drag_manager._active
        assert session.current_target is target
        assert session.target_accepts is True

    def test_hover_over_rejecting_target(self, scene_with_ui) -> None:
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="item")
        target = _make_box(
            x=200, y=200,
            drop_accept=lambda data: False,
        )
        root.add(source)
        root.add(target)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        root.handle_event(InputEvent(type="move", x=220, y=220))

        session = root.drag_manager._active
        assert session.current_target is target
        assert session.target_accepts is False

    def test_hover_over_non_target(self, scene_with_ui) -> None:
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="item")
        non_target = _make_box(x=200, y=200)  # no drop_accept
        root.add(source)
        root.add(non_target)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        root.handle_event(InputEvent(type="move", x=220, y=220))

        session = root.drag_manager._active
        assert session.current_target is None
        assert session.target_accepts is False

    def test_target_changes_on_move(self, scene_with_ui) -> None:
        """Moving from one target to another updates the current target."""
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="item")
        target_a = _make_box(
            x=100, y=100,
            drop_accept=lambda data: True,
            on_drop=lambda c, d: None,
        )
        target_b = _make_box(
            x=300, y=300,
            drop_accept=lambda data: False,
        )
        root.add(source)
        root.add(target_a)
        root.add(target_b)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))

        # Move over target_a
        root.handle_event(InputEvent(type="move", x=120, y=120))
        assert root.drag_manager._active.current_target is target_a
        assert root.drag_manager._active.target_accepts is True

        # Move over target_b
        root.handle_event(InputEvent(type="move", x=320, y=320))
        assert root.drag_manager._active.current_target is target_b
        assert root.drag_manager._active.target_accepts is False

    def test_source_is_not_drop_target(self, scene_with_ui) -> None:
        """Cannot drop onto the source component itself."""
        root = scene_with_ui.ui
        dropped = []
        source = _make_box(
            x=100, y=100,
            draggable=True,
            drag_data="item",
            drop_accept=lambda data: True,
            on_drop=lambda c, d: dropped.append(d),
        )
        root.add(source)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=120, y=120, button="left"))
        root.handle_event(InputEvent(type="move", x=130, y=130))

        session = root.drag_manager._active
        assert session.current_target is None  # source itself is excluded

        root.handle_event(InputEvent(type="release", x=130, y=130, button="left"))
        assert len(dropped) == 0


# ===========================================================================
# TestGhostRendering
# ===========================================================================

class TestGhostRendering:
    """Ghost and overlay rendering during draw phase."""

    def test_ghost_rect_drawn_for_component(self, scene_with_ui, mock_backend) -> None:
        """When source has no _image_handle, a fallback rect ghost is drawn."""
        root = scene_with_ui.ui
        source = _make_box(x=100, y=100, w=50, h=50, draggable=True, drag_data="x")
        root.add(source)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=120, y=120, button="left"))

        # Clear any prior draw calls, then draw the tree
        mock_backend.begin_frame()
        root.draw()

        # Should find a rect for the ghost
        ghost_rects = [
            r for r in mock_backend.rects
            if r["x"] == 100 and r["y"] == 100
            and r["width"] == 50 and r["height"] == 50
            and r["color"] == (180, 180, 180, 128)
        ]
        assert len(ghost_rects) == 1

    def test_accept_highlight_drawn(self, scene_with_ui, mock_backend) -> None:
        """Green highlight is drawn on a valid drop target."""
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="item")
        target = _make_box(
            x=200, y=200, w=80, h=80,
            drop_accept=lambda data: True,
        )
        root.add(source)
        root.add(target)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        root.handle_event(InputEvent(type="move", x=220, y=220))

        mock_backend.begin_frame()
        root.draw()

        theme = scene_with_ui.game.theme
        highlight_rects = [
            r for r in mock_backend.rects
            if r["x"] == 200 and r["y"] == 200
            and r["width"] == 80 and r["height"] == 80
            and r["color"] == theme.drop_accept_color
        ]
        assert len(highlight_rects) == 1

    def test_reject_highlight_drawn(self, scene_with_ui, mock_backend) -> None:
        """Red highlight is drawn on an invalid drop target."""
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="item")
        target = _make_box(
            x=200, y=200, w=80, h=80,
            drop_accept=lambda data: False,
        )
        root.add(source)
        root.add(target)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        root.handle_event(InputEvent(type="move", x=220, y=220))

        mock_backend.begin_frame()
        root.draw()

        theme = scene_with_ui.game.theme
        highlight_rects = [
            r for r in mock_backend.rects
            if r["x"] == 200 and r["y"] == 200
            and r["width"] == 80 and r["height"] == 80
            and r["color"] == theme.drop_reject_color
        ]
        assert len(highlight_rects) == 1

    def test_no_ghost_when_not_dragging(self, scene_with_ui, mock_backend) -> None:
        """No ghost or highlights when not dragging."""
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="x")
        root.add(source)
        root._ensure_layout()

        mock_backend.begin_frame()
        root.draw()

        assert len(mock_backend.rects) == 0
        assert len(mock_backend.images) == 0


# ===========================================================================
# TestThemeDragProperties
# ===========================================================================

class TestThemeDragProperties:
    """Theme default values for drag-and-drop colors."""

    def test_default_drop_accept_color(self) -> None:
        theme = Theme()
        assert theme.drop_accept_color == (0, 180, 0, 80)

    def test_default_drop_reject_color(self) -> None:
        theme = Theme()
        assert theme.drop_reject_color == (180, 0, 0, 80)

    def test_default_ghost_opacity(self) -> None:
        theme = Theme()
        assert theme.ghost_opacity == 0.5

    def test_custom_theme_colors(self) -> None:
        theme = Theme(
            drop_accept_color=(0, 255, 0, 100),
            drop_reject_color=(255, 0, 0, 100),
            ghost_opacity=0.75,
        )
        assert theme.drop_accept_color == (0, 255, 0, 100)
        assert theme.drop_reject_color == (255, 0, 0, 100)
        assert theme.ghost_opacity == 0.75


# ===========================================================================
# TestGameTickIntegration
# ===========================================================================

class TestGameTickIntegration:
    """Full integration with Game.tick() and event injection."""

    def test_drag_via_game_tick(self, mock_game, mock_backend) -> None:
        """Full drag lifecycle via game.tick() with mock backend events."""
        scene = Scene()
        mock_game.push(scene)

        dropped = []
        source = _make_box(x=10, y=10, draggable=True, drag_data="spell")
        target = _make_box(
            x=200, y=200, w=80, h=80,
            drop_accept=lambda data: data == "spell",
            on_drop=lambda comp, data: dropped.append(data),
        )
        scene.ui.add(source)
        scene.ui.add(target)
        scene.ui._ensure_layout()

        # Start drag via click
        mock_backend.inject_click(30, 30)
        mock_game.tick(dt=0.016)
        assert scene.ui.drag_manager.is_dragging

        # Move over target
        mock_backend.inject_mouse_move(220, 220)
        mock_game.tick(dt=0.016)

        # Drop via release
        mock_backend.inject_event(
            MouseEvent(type="release", x=220, y=220, button="left"),
        )
        mock_game.tick(dt=0.016)

        assert not scene.ui.drag_manager.is_dragging
        assert dropped == ["spell"]

    def test_cancel_via_escape_in_game_tick(self, mock_game, mock_backend) -> None:
        """Escape during drag cancels via game.tick()."""
        scene = Scene()
        mock_game.push(scene)

        source = _make_box(x=10, y=10, draggable=True, drag_data="x")
        scene.ui.add(source)
        scene.ui._ensure_layout()

        mock_backend.inject_click(30, 30)
        mock_game.tick(dt=0.016)
        assert scene.ui.drag_manager.is_dragging

        mock_backend.inject_key("escape")
        mock_game.tick(dt=0.016)
        assert not scene.ui.drag_manager.is_dragging

    def test_ghost_drawn_during_frame(self, mock_game, mock_backend) -> None:
        """Ghost rect appears in the backend during a frame with active drag."""
        scene = Scene()
        mock_game.push(scene)

        source = _make_box(x=50, y=50, w=40, h=40, draggable=True, drag_data="x")
        scene.ui.add(source)
        scene.ui._ensure_layout()

        # Start drag
        mock_backend.inject_click(60, 60)
        mock_game.tick(dt=0.016)
        assert scene.ui.drag_manager.is_dragging

        # The tick renders a frame — check for ghost rect.
        # The ghost should be at source position since we haven't moved.
        ghost_rects = [
            r for r in mock_backend.rects
            if r["width"] == 40 and r["height"] == 40
            and r["color"] == (180, 180, 180, 128)
        ]
        assert len(ghost_rects) >= 1


# ===========================================================================
# TestNestedComponents
# ===========================================================================

class TestNestedComponents:
    """Drag-drop with nested component trees."""

    def test_drag_child_in_parent(self, scene_with_ui) -> None:
        """A draggable child inside a non-draggable parent."""
        root = scene_with_ui.ui
        parent = _make_box(x=0, y=0, w=300, h=300)
        child = _make_box(x=50, y=50, w=40, h=40, draggable=True, drag_data="nested")
        parent.add(child)
        root.add(parent)
        root._ensure_layout()

        # Click on the child
        root.handle_event(InputEvent(type="click", x=60, y=60, button="left"))
        assert root.drag_manager.is_dragging
        assert root.drag_manager.drag_data == "nested"

    def test_deepest_drop_target_wins(self, scene_with_ui) -> None:
        """The deepest matching drop target in the tree wins."""
        dropped_inner = []
        dropped_outer = []

        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="x")

        outer_target = _make_box(
            x=200, y=200, w=200, h=200,
            drop_accept=lambda data: True,
            on_drop=lambda c, d: dropped_outer.append(d),
        )
        inner_target = _make_box(
            x=210, y=210, w=50, h=50,
            drop_accept=lambda data: True,
            on_drop=lambda c, d: dropped_inner.append(d),
        )
        outer_target.add(inner_target)

        root.add(source)
        root.add(outer_target)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        root.handle_event(InputEvent(type="move", x=220, y=220))

        # During move, the deepest target should be found
        session = root.drag_manager._active
        assert session.current_target is inner_target

        # Drop on inner target
        root.handle_event(InputEvent(type="release", x=220, y=220, button="left"))
        assert len(dropped_inner) == 1
        assert len(dropped_outer) == 0


# ===========================================================================
# TestDragDataTypes
# ===========================================================================

class TestDragDataTypes:
    """Various data types as drag_data."""

    def test_none_data(self, scene_with_ui) -> None:
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data=None)
        root.add(source)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        assert root.drag_manager.drag_data is None

    def test_dict_data(self, scene_with_ui) -> None:
        data = {"type": "weapon", "name": "Excalibur", "damage": 50}
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data=data)
        root.add(source)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        assert root.drag_manager.drag_data is data

    def test_object_data(self, scene_with_ui) -> None:
        class Item:
            def __init__(self, name):
                self.name = name

        item = Item("Health Potion")
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data=item)
        target = _make_box(
            x=200, y=200,
            drop_accept=lambda d: isinstance(d, Item),
            on_drop=lambda c, d: None,
        )
        root.add(source)
        root.add(target)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        root.handle_event(InputEvent(type="move", x=220, y=220))

        session = root.drag_manager._active
        assert session.target_accepts is True


# ===========================================================================
# TestDragSessionDataclass
# ===========================================================================

class TestDragSessionDataclass:
    """Direct testing of _DragSession dataclass."""

    def test_fields(self) -> None:
        source = Component(width=10, height=10)
        session = _DragSession(
            source=source,
            data="test",
            start_x=100,
            start_y=200,
            ghost_x=100,
            ghost_y=200,
            ghost_offset_x=-5,
            ghost_offset_y=-10,
            current_target=None,
            target_accepts=False,
        )
        assert session.source is source
        assert session.data == "test"
        assert session.start_x == 100
        assert session.start_y == 200
        assert session.ghost_offset_x == -5


# ===========================================================================
# TestEdgeCases
# ===========================================================================

class TestEdgeCases:
    """Edge cases for drag-and-drop."""

    def test_drop_on_target_with_accept_but_no_on_drop(self, scene_with_ui) -> None:
        """Target has drop_accept but no on_drop — silently cancels."""
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="x")
        target = _make_box(
            x=200, y=200,
            drop_accept=lambda data: True,
            on_drop=None,  # no callback
        )
        root.add(source)
        root.add(target)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        root.handle_event(InputEvent(type="move", x=220, y=220))
        root.handle_event(InputEvent(type="release", x=220, y=220, button="left"))

        # Should not raise — gracefully cancelled
        assert root.drag_manager.is_dragging is False

    def test_multiple_drags_in_sequence(self, scene_with_ui) -> None:
        """Starting a new drag after the first one ends."""
        dropped = []
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="a")
        target = _make_box(
            x=200, y=200,
            drop_accept=lambda data: True,
            on_drop=lambda c, d: dropped.append(d),
        )
        root.add(source)
        root.add(target)
        root._ensure_layout()

        # First drag and drop
        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        root.handle_event(InputEvent(type="move", x=220, y=220))
        root.handle_event(InputEvent(type="release", x=220, y=220, button="left"))
        assert len(dropped) == 1

        # Second drag and drop
        source.drag_data = "b"
        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        root.handle_event(InputEvent(type="move", x=220, y=220))
        root.handle_event(InputEvent(type="release", x=220, y=220, button="left"))
        assert len(dropped) == 2
        assert dropped == ["a", "b"]

    def test_drag_cancel_then_new_drag(self, scene_with_ui) -> None:
        """Cancel a drag, then start a new one."""
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="x")
        root.add(source)
        root._ensure_layout()

        # Start and cancel
        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        assert root.drag_manager.is_dragging
        root.handle_event(InputEvent(type="key_press", key="escape", action="cancel"))
        assert not root.drag_manager.is_dragging

        # Start again
        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        assert root.drag_manager.is_dragging

    def test_all_events_consumed_during_drag(self, scene_with_ui) -> None:
        """All event types are consumed while dragging."""
        root = scene_with_ui.ui
        source = _make_box(x=10, y=10, draggable=True, drag_data="x")
        root.add(source)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=30, y=30, button="left"))
        assert root.drag_manager.is_dragging

        # Various event types should all be consumed
        assert root.handle_event(InputEvent(type="move", x=50, y=50)) is True
        assert root.handle_event(InputEvent(type="drag", x=60, y=60, dx=10, dy=10)) is True
        assert root.handle_event(InputEvent(type="key_press", key="a")) is True
        assert root.handle_event(InputEvent(type="scroll", x=30, y=30, dx=0, dy=5)) is True

    def test_drag_manager_handle_event_when_not_dragging(self, scene_with_ui) -> None:
        """DragManager.handle_event returns False when not dragging."""
        dm = scene_with_ui.ui.drag_manager
        event = InputEvent(type="move", x=100, y=100)
        assert dm.handle_event(event) is False
