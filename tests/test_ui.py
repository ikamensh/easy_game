"""Tests for Stage 8 UI Foundation: layout math, Label, Button, Panel,
Theme/Style, and Scene integration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from easygame import (
    Game,
    Scene,
    compute_anchor_position,
    compute_content_size,
    compute_flow_layout,
)
from easygame.assets import AssetManager
from easygame.backends.mock_backend import MockBackend
from easygame.input import InputEvent
from easygame.ui import (
    Anchor,
    Button,
    ImageBox,
    Label,
    Layout,
    Panel,
    ProgressBar,
    Style,
    Theme,
)
from easygame.ui.component import _UIRoot
from easygame.ui.components import _estimate_text_width


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def game() -> Game:
    """Game with mock backend at 800×600."""
    return Game("UI Test", backend="mock", resolution=(800, 600))


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


@pytest.fixture
def root(game: Game) -> _UIRoot:
    """A _UIRoot attached to the game (simulates Scene.ui)."""
    return _UIRoot(game)


@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    """Create a temporary asset directory with a test image."""
    images = tmp_path / "images"
    images.mkdir()
    sprites = images / "sprites"
    sprites.mkdir()
    (sprites / "portrait.png").write_bytes(b"png")
    return tmp_path


# ==================================================================
# 0. Package API
# ==================================================================


def test_version_attribute() -> None:
    """__version__ is exposed and non-empty."""
    import easygame
    assert hasattr(easygame, "__version__")
    assert isinstance(easygame.__version__, str)
    assert len(easygame.__version__) > 0


# ==================================================================
# 1. Layout math (~10 tests)
# ==================================================================


class TestLayoutMath:
    """Pure-math anchor positioning, flow layout, and content sizing."""

    def test_anchor_center(self) -> None:
        """CENTER places child at the middle of the parent."""
        x, y = compute_anchor_position(
            Anchor.CENTER, 0, 0, 800, 600, 200, 100,
        )
        assert x == 300
        assert y == 250

    def test_anchor_top_left(self) -> None:
        """TOP_LEFT places child at parent origin (plus margin)."""
        x, y = compute_anchor_position(
            Anchor.TOP_LEFT, 0, 0, 800, 600, 200, 100,
        )
        assert (x, y) == (0, 0)

    def test_anchor_top_right(self) -> None:
        """TOP_RIGHT places child flush-right at top."""
        x, y = compute_anchor_position(
            Anchor.TOP_RIGHT, 0, 0, 800, 600, 200, 100,
        )
        assert (x, y) == (600, 0)

    def test_anchor_bottom_left(self) -> None:
        x, y = compute_anchor_position(
            Anchor.BOTTOM_LEFT, 0, 0, 800, 600, 200, 100,
        )
        assert (x, y) == (0, 500)

    def test_anchor_bottom_right(self) -> None:
        x, y = compute_anchor_position(
            Anchor.BOTTOM_RIGHT, 0, 0, 800, 600, 200, 100,
        )
        assert (x, y) == (600, 500)

    def test_anchor_top(self) -> None:
        """TOP centers horizontally and pins to top edge."""
        x, y = compute_anchor_position(
            Anchor.TOP, 0, 0, 800, 600, 200, 100,
        )
        assert (x, y) == (300, 0)

    def test_anchor_bottom(self) -> None:
        x, y = compute_anchor_position(
            Anchor.BOTTOM, 0, 0, 800, 600, 200, 100,
        )
        assert (x, y) == (300, 500)

    def test_anchor_left(self) -> None:
        x, y = compute_anchor_position(
            Anchor.LEFT, 0, 0, 800, 600, 200, 100,
        )
        assert (x, y) == (0, 250)

    def test_anchor_right(self) -> None:
        x, y = compute_anchor_position(
            Anchor.RIGHT, 0, 0, 800, 600, 200, 100,
        )
        assert (x, y) == (600, 250)

    def test_anchor_with_margin(self) -> None:
        """Margin pushes inward from the anchor edge."""
        x, y = compute_anchor_position(
            Anchor.TOP_LEFT, 0, 0, 800, 600, 200, 100, margin=10,
        )
        assert (x, y) == (10, 10)

    def test_anchor_with_parent_offset(self) -> None:
        """Parent offset shifts the result."""
        x, y = compute_anchor_position(
            Anchor.TOP_LEFT, 50, 100, 800, 600, 200, 100,
        )
        assert (x, y) == (50, 100)

    def test_vertical_flow_layout(self) -> None:
        """VERTICAL stacks children top-to-bottom, centered horizontally."""
        positions = compute_flow_layout(
            Layout.VERTICAL, 0, 0, 200, 400,
            [(100, 30), (100, 30)], spacing=10, padding=5,
        )
        # First child: centered x = (200 - 100) // 2 = 50, y = 0 + 5
        assert positions[0] == (50, 5)
        # Second child: y = 5 + 30 + 10 = 45
        assert positions[1] == (50, 45)

    def test_horizontal_flow_layout(self) -> None:
        """HORIZONTAL stacks children left-to-right, centered vertically."""
        positions = compute_flow_layout(
            Layout.HORIZONTAL, 0, 0, 400, 100,
            [(60, 40), (60, 40)], spacing=10, padding=5,
        )
        # First child: x = 0 + 5, y = (100 - 40) // 2 = 30
        assert positions[0] == (5, 30)
        # Second child: x = 5 + 60 + 10 = 75
        assert positions[1] == (75, 30)

    def test_content_size_vertical(self) -> None:
        """Vertical content size: max width, sum of heights + spacing + padding."""
        w, h = compute_content_size(
            Layout.VERTICAL,
            [(100, 30), (120, 40)],
            spacing=10,
            padding=8,
        )
        assert w == 120 + 2 * 8  # 136  (max child width + 2*padding)
        assert h == 30 + 40 + 10 + 2 * 8  # 96  (sum heights + 1 spacing + 2*padding)

    def test_content_size_horizontal(self) -> None:
        """Horizontal content size: sum of widths + spacing, max height."""
        w, h = compute_content_size(
            Layout.HORIZONTAL,
            [(100, 30), (120, 40)],
            spacing=10,
            padding=8,
        )
        assert w == 100 + 120 + 10 + 2 * 8  # 246
        assert h == 40 + 2 * 8  # 56

    def test_content_size_empty(self) -> None:
        """No children yields just padding."""
        w, h = compute_content_size(Layout.VERTICAL, [], spacing=10, padding=5)
        assert (w, h) == (10, 10)

    def test_flow_layout_none_returns_empty(self) -> None:
        """Layout.NONE returns empty positions list."""
        positions = compute_flow_layout(
            Layout.NONE, 0, 0, 400, 400,
            [(100, 50)], spacing=10,
        )
        assert positions == []


# ==================================================================
# 2. Label (~8 tests)
# ==================================================================


class TestLabel:
    """Label creation, sizing, text property, and drawing."""

    def test_creation(self) -> None:
        """Label stores text and defaults."""
        label = Label("Hello")
        assert label.text == "Hello"
        assert label.visible is True
        assert label.enabled is True

    def test_preferred_size_heuristic(self) -> None:
        """Default size uses per-character heuristic, font_size × 1.4 height."""
        label = Label("Hello")
        w, h = label.get_preferred_size()
        # Default font_size = 24
        assert w == _estimate_text_width("Hello", 24)
        assert h == int(24 * 1.4)  # 33

    def test_preferred_size_explicit_override(self) -> None:
        """Explicit width/height override the heuristic."""
        label = Label("Hello", width=300, height=50)
        assert label.get_preferred_size() == (300, 50)

    def test_text_setter_marks_dirty(self) -> None:
        """Changing text invalidates layout."""
        label = Label("Old")
        label._layout_dirty = False
        label.text = "New"
        assert label._layout_dirty is True

    def test_text_setter_no_change_no_dirty(self) -> None:
        """Setting text to same value does not invalidate layout."""
        label = Label("Same")
        label._layout_dirty = False
        label.text = "Same"
        assert label._layout_dirty is False

    def test_draw_calls_backend(self, root: _UIRoot, backend: MockBackend) -> None:
        """Drawing a label calls backend.draw_text with correct args."""
        label = Label("Test")
        root.add(label)
        root._ensure_layout()
        root.draw()

        assert len(backend.texts) == 1
        t = backend.texts[0]
        assert t["text"] == "Test"
        assert t["font_size"] == 24  # default
        assert t["color"] == (220, 220, 220, 255)  # default label color

    def test_draw_empty_text_no_call(self, root: _UIRoot, backend: MockBackend) -> None:
        """Empty text string produces no draw_text call."""
        label = Label("")
        root.add(label)
        root._ensure_layout()
        root.draw()

        assert len(backend.texts) == 0

    def test_style_override_font_size(self, root: _UIRoot, backend: MockBackend) -> None:
        """Explicit style font_size is used instead of theme default."""
        label = Label("Big", style=Style(font_size=48))
        root.add(label)
        root._ensure_layout()
        root.draw()

        assert backend.texts[0]["font_size"] == 48

    def test_preferred_size_with_custom_font_size(self) -> None:
        """Custom font_size from style affects preferred size."""
        label = Label("Hi", style=Style(font_size=48))
        w, h = label.get_preferred_size()
        assert w == _estimate_text_width("Hi", 48)
        assert h == int(48 * 1.4)  # 67

    def test_convenience_kwargs_font_size_text_color(self, root: _UIRoot, backend: MockBackend) -> None:
        """font_size and text_color as direct kwargs work without Style wrapper."""
        label = Label("Hello", font_size=24, text_color=(255, 255, 255, 255))
        root.add(label)
        root._ensure_layout()
        root.draw()

        assert backend.texts[0]["font_size"] == 24
        assert backend.texts[0]["color"] == (255, 255, 255, 255)

    def test_convenience_kwargs_preferred_size(self) -> None:
        """font_size as direct kwarg affects preferred size."""
        label = Label("Hi", font_size=36)
        w, h = label.get_preferred_size()
        assert w == _estimate_text_width("Hi", 36)
        assert h == int(36 * 1.4)

    def test_style_overrides_convenience_kwargs_when_both(self, root: _UIRoot, backend: MockBackend) -> None:
        """Explicit style wins over convenience kwargs for overlapping fields."""
        label = Label("Hi", font_size=24, style=Style(font_size=48, text_color=(255, 0, 0, 255)))
        root.add(label)
        root._ensure_layout()
        root.draw()

        assert backend.texts[0]["font_size"] == 48  # style wins
        assert backend.texts[0]["color"] == (255, 0, 0, 255)  # style wins

    def test_convenience_kwargs_merge_with_style(self, root: _UIRoot, backend: MockBackend) -> None:
        """Convenience kwargs fill in fields not set by explicit style."""
        label = Label("Hi", font_size=32, style=Style(text_color=(0, 255, 0, 255)))
        root.add(label)
        root._ensure_layout()
        root.draw()

        assert backend.texts[0]["font_size"] == 32  # from kwarg
        assert backend.texts[0]["color"] == (0, 255, 0, 255)  # from style


# ==================================================================
# 3. Button (~12 tests)
# ==================================================================


class TestButton:
    """Button creation, state machine, on_click, event consumption, and drawing."""

    def test_creation_defaults(self) -> None:
        """Button starts in normal state with no callback."""
        btn = Button("Play")
        assert btn.text == "Play"
        assert btn.state == "normal"
        assert btn.on_click is None

    def test_preferred_size_includes_padding(self) -> None:
        """Button size includes padding on all sides and respects min_width."""
        btn = Button("OK")
        w, h = btn.get_preferred_size()
        # padding default = 12, text_w = int(2 * 24 * 0.6) = 28
        # text_h = int(24 * 1.4) = 33
        # w = max(28 + 24, 200) = 200 (min_width kicks in)
        assert w == 200
        assert h == 33 + 24  # text_h + 2*padding

    def test_preferred_size_long_text_exceeds_min_width(self) -> None:
        """Long text button is wider than min_width."""
        btn = Button("A Very Long Button Label Text")
        w, h = btn.get_preferred_size()
        text_w = _estimate_text_width("A Very Long Button Label Text", 24)
        assert w == text_w + 24  # text_w + 2*padding > 200

    def test_hover_on_mouse_enter(self, root: _UIRoot) -> None:
        """Mouse move into bounds → hovered.  Not consumed (siblings need moves)."""
        btn = Button("Click", width=100, height=40, anchor=Anchor.TOP_LEFT)
        root.add(btn)
        root._ensure_layout()

        # btn is at (0, 0, 100, 40)
        event = InputEvent(type="move", x=50, y=20)
        consumed = root.handle_event(event)

        assert btn.state == "hovered"
        assert consumed is False  # moves never consumed — siblings need them

    def test_hover_on_mouse_leave(self, root: _UIRoot) -> None:
        """Mouse move out of bounds → normal."""
        btn = Button("Click", width=100, height=40, anchor=Anchor.TOP_LEFT)
        root.add(btn)
        root._ensure_layout()

        # Enter first
        root.handle_event(InputEvent(type="move", x=50, y=20))
        assert btn.state == "hovered"

        # Leave
        consumed = root.handle_event(InputEvent(type="move", x=500, y=500))
        assert btn.state == "normal"
        assert consumed is False  # leaving does not consume

    def test_click_fires_callback(self, root: _UIRoot) -> None:
        """Clicking a button fires on_click."""
        fired = []
        btn = Button("Go", on_click=lambda: fired.append(True),
                     width=100, height=40, anchor=Anchor.TOP_LEFT)
        root.add(btn)
        root._ensure_layout()

        consumed = root.handle_event(InputEvent(type="click", x=50, y=20))

        assert consumed is True
        assert len(fired) == 1
        assert btn.state == "pressed"

    def test_click_outside_does_not_fire(self, root: _UIRoot) -> None:
        """Click outside bounds does not fire callback or change state."""
        fired = []
        btn = Button("Go", on_click=lambda: fired.append(True),
                     width=100, height=40, anchor=Anchor.TOP_LEFT)
        root.add(btn)
        root._ensure_layout()

        consumed = root.handle_event(InputEvent(type="click", x=500, y=500))

        assert consumed is False
        assert len(fired) == 0
        assert btn.state == "normal"

    def test_release_returns_to_hovered(self, root: _UIRoot) -> None:
        """Release while over button → hovered."""
        btn = Button("Go", width=100, height=40, anchor=Anchor.TOP_LEFT)
        root.add(btn)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=50, y=20))
        assert btn.state == "pressed"

        consumed = root.handle_event(InputEvent(type="release", x=50, y=20))
        assert btn.state == "hovered"
        assert consumed is True

    def test_release_outside_returns_to_normal(self, root: _UIRoot) -> None:
        """Release while NOT over button → normal."""
        btn = Button("Go", width=100, height=40, anchor=Anchor.TOP_LEFT)
        root.add(btn)
        root._ensure_layout()

        root.handle_event(InputEvent(type="click", x=50, y=20))
        assert btn.state == "pressed"

        consumed = root.handle_event(InputEvent(type="release", x=500, y=500))
        assert btn.state == "normal"
        assert consumed is True

    def test_disabled_button_ignores_events(self, root: _UIRoot) -> None:
        """Disabled button does not respond to any events."""
        fired = []
        btn = Button("Go", on_click=lambda: fired.append(True),
                     width=100, height=40, anchor=Anchor.TOP_LEFT, enabled=False)
        root.add(btn)
        root._ensure_layout()

        consumed = root.handle_event(InputEvent(type="click", x=50, y=20))
        assert consumed is False
        assert len(fired) == 0
        assert btn.state == "normal"

    def test_on_click_settable(self) -> None:
        """on_click can be set after construction."""
        btn = Button("Go")
        assert btn.on_click is None
        btn.on_click = lambda: None
        assert btn.on_click is not None

    def test_draw_calls_rect_and_text(
        self, root: _UIRoot, backend: MockBackend,
    ) -> None:
        """Drawing a button produces one rect and one text draw call."""
        btn = Button("Play", width=200, height=50, anchor=Anchor.TOP_LEFT)
        root.add(btn)
        root._ensure_layout()
        root.draw()

        assert len(backend.rects) == 1
        r = backend.rects[0]
        assert r["x"] == 0
        assert r["y"] == 0
        assert r["width"] == 200
        assert r["height"] == 50

        assert len(backend.texts) == 1
        t = backend.texts[0]
        assert t["text"] == "Play"
        assert t["anchor_x"] == "center"
        assert t["anchor_y"] == "center"

    def test_hovered_uses_hover_color(
        self, root: _UIRoot, backend: MockBackend, game: Game,
    ) -> None:
        """Button in hovered state draws with hover_color."""
        btn = Button("Go", width=100, height=40, anchor=Anchor.TOP_LEFT)
        root.add(btn)
        root._ensure_layout()

        # Transition to hovered
        root.handle_event(InputEvent(type="move", x=50, y=20))
        assert btn.state == "hovered"

        root.draw()

        expected_bg = game.theme.resolve_button_style(None, "hovered").background_color
        assert backend.rects[0]["color"] == expected_bg

    def test_disabled_button_uses_disabled_style(
        self, root: _UIRoot, backend: MockBackend, game: Game,
    ) -> None:
        """Disabled button draws with distinct muted/grayed-out colors."""
        btn = Button("Buy", width=100, height=40, anchor=Anchor.TOP_LEFT, enabled=False)
        root.add(btn)
        root._ensure_layout()
        root.draw()

        disabled_style = game.theme.resolve_button_style(None, "disabled")
        normal_style = game.theme.resolve_button_style(None, "normal")

        assert backend.rects[0]["color"] == disabled_style.background_color
        assert backend.rects[0]["color"] != normal_style.background_color

        assert backend.texts[0]["color"] == disabled_style.text_color
        assert backend.texts[0]["color"] != normal_style.text_color


# ==================================================================
# 4. Panel (~10 tests)
# ==================================================================


class TestPanel:
    """Panel creation, children, layout, sizing, and drawing."""

    def test_creation_defaults(self) -> None:
        """Panel defaults: NONE layout, 0 spacing, no children."""
        panel = Panel()
        assert panel.layout == Layout.NONE
        assert panel.spacing == 0
        assert panel.children == []

    def test_creation_with_children(self) -> None:
        """Panel constructor accepts children list."""
        l1 = Label("A")
        l2 = Label("B")
        panel = Panel(children=[l1, l2])
        assert len(panel.children) == 2
        assert l1.parent is panel
        assert l2.parent is panel

    def test_add_remove_children(self) -> None:
        """add/remove works as expected."""
        panel = Panel()
        label = Label("Hi")
        panel.add(label)
        assert len(panel.children) == 1
        panel.remove(label)
        assert len(panel.children) == 0
        assert label.parent is None

    def test_vertical_layout_positions(self, root: _UIRoot) -> None:
        """VERTICAL layout stacks children top-to-bottom."""
        l1 = Label("A", width=80, height=30)
        l2 = Label("B", width=80, height=30)
        panel = Panel(
            layout=Layout.VERTICAL, spacing=10,
            children=[l1, l2],
            width=200, height=200,
            anchor=Anchor.TOP_LEFT,
        )
        root.add(panel)
        root._ensure_layout()

        # Panel is at (0, 0), padding default = 16
        # First child: y = 0 + 16 = 16, x = 0 + (200-80)//2 = 60
        assert l1._computed_y == 16
        assert l1._computed_x == 60
        # Second child: y = 16 + 30 + 10 = 56
        assert l2._computed_y == 56
        assert l2._computed_x == 60

    def test_horizontal_layout_positions(self, root: _UIRoot) -> None:
        """HORIZONTAL layout stacks children left-to-right."""
        l1 = Label("A", width=60, height=30)
        l2 = Label("B", width=60, height=30)
        panel = Panel(
            layout=Layout.HORIZONTAL, spacing=10,
            children=[l1, l2],
            width=300, height=100,
            anchor=Anchor.TOP_LEFT,
        )
        root.add(panel)
        root._ensure_layout()

        # First child: x = 0 + 16 = 16, y = 0 + (100-30)//2 = 35
        assert l1._computed_x == 16
        assert l1._computed_y == 35
        # Second child: x = 16 + 60 + 10 = 86
        assert l2._computed_x == 86
        assert l2._computed_y == 35

    def test_content_fit_vertical(self) -> None:
        """Panel without explicit size auto-sizes to fit children (vertical)."""
        l1 = Label("Hello", width=100, height=30)
        l2 = Label("World", width=120, height=40)
        panel = Panel(layout=Layout.VERTICAL, spacing=10, children=[l1, l2])

        w, h = panel.get_preferred_size()
        # padding = 16 (default)
        assert w == 120 + 2 * 16  # max child width + 2*padding = 152
        assert h == 30 + 40 + 10 + 2 * 16  # sum heights + spacing + 2*padding = 112

    def test_explicit_size_overrides_content(self) -> None:
        """Panel with explicit width/height ignores content sizing."""
        panel = Panel(width=500, height=400, layout=Layout.VERTICAL)
        panel.add(Label("Tiny", width=20, height=10))
        assert panel.get_preferred_size() == (500, 400)

    def test_none_layout_fallback(self) -> None:
        """Panel with Layout.NONE and no dimensions falls back to (100, 100)."""
        panel = Panel(layout=Layout.NONE)
        assert panel.get_preferred_size() == (100, 100)

    def test_nested_panels(self, root: _UIRoot) -> None:
        """Panels can be nested and layout propagates correctly."""
        inner = Panel(
            layout=Layout.VERTICAL,
            children=[Label("A", width=80, height=30)],
        )
        outer = Panel(
            layout=Layout.VERTICAL, spacing=5,
            children=[inner],
            anchor=Anchor.TOP_LEFT,
        )
        root.add(outer)
        root._ensure_layout()

        # inner should be positioned inside outer
        assert inner._computed_y >= outer._computed_y

    def test_background_draw(
        self, root: _UIRoot, backend: MockBackend, game: Game,
    ) -> None:
        """Panel draws its background rect."""
        panel = Panel(width=200, height=100, anchor=Anchor.TOP_LEFT)
        root.add(panel)
        root._ensure_layout()
        root.draw()

        assert len(backend.rects) == 1
        r = backend.rects[0]
        assert r["width"] == 200
        assert r["height"] == 100
        assert r["color"] == game.theme.resolve_panel_style(None).background_color

    def test_spacing_between_children(self, root: _UIRoot) -> None:
        """Spacing inserts gap between children in flow layout."""
        l1 = Label("X", width=50, height=20)
        l2 = Label("Y", width=50, height=20)
        panel = Panel(
            layout=Layout.VERTICAL, spacing=30,
            children=[l1, l2],
            width=200, height=300,
            anchor=Anchor.TOP_LEFT,
            style=Style(padding=0),  # zero padding for clarity
        )
        root.add(panel)
        root._ensure_layout()

        # With 0 padding: l1 at y=0, l2 at y=0+20+30=50
        assert l2._computed_y == l1._computed_y + 20 + 30

    def test_panel_anchor_center(self, root: _UIRoot) -> None:
        """Panel with CENTER anchor is centered in parent."""
        panel = Panel(width=200, height=100, anchor=Anchor.CENTER)
        root.add(panel)
        root._ensure_layout()

        # Root is 800×600
        assert panel._computed_x == (800 - 200) // 2  # 300
        assert panel._computed_y == (600 - 100) // 2  # 250


# ==================================================================
# 5. Theme/Style (~6 tests)
# ==================================================================


class TestThemeStyle:
    """Theme defaults, Style override merging, and propagation."""

    def test_default_theme_values(self) -> None:
        """Default Theme has expected font, font_size, colors."""
        theme = Theme()
        assert theme.button_min_width == 200

        resolved = theme.resolve_label_style(None)
        assert resolved.font == "serif"
        assert resolved.font_size == 24
        assert resolved.text_color == (220, 220, 220, 255)

    def test_style_override_merging(self) -> None:
        """Explicit Style fields take precedence; None inherits from theme."""
        theme = Theme()
        style = Style(font_size=48, text_color=(255, 0, 0, 255))
        resolved = theme.resolve_label_style(style)

        assert resolved.font_size == 48  # overridden
        assert resolved.text_color == (255, 0, 0, 255)  # overridden
        assert resolved.font == "serif"  # inherited from theme

    def test_button_state_normal(self) -> None:
        """Normal state uses background_color default."""
        theme = Theme()
        resolved = theme.resolve_button_style(None, "normal")
        assert resolved.background_color == (70, 70, 90, 255)

    def test_button_state_hovered(self) -> None:
        """Hovered state uses hover_color."""
        theme = Theme()
        resolved = theme.resolve_button_style(None, "hovered")
        assert resolved.background_color == (100, 100, 130, 255)

    def test_button_state_pressed(self) -> None:
        """Pressed state uses press_color."""
        theme = Theme()
        resolved = theme.resolve_button_style(None, "pressed")
        assert resolved.background_color == (50, 50, 70, 255)

    def test_panel_style_defaults(self) -> None:
        """Panel defaults include background color and padding."""
        theme = Theme()
        resolved = theme.resolve_panel_style(None)
        assert resolved.background_color == (40, 40, 50, 200)
        assert resolved.padding == 16

    def test_progressbar_theme_defaults(self) -> None:
        """Theme has progressbar_color and progressbar_bg_color."""
        theme = Theme()
        assert theme.progressbar_color == (60, 180, 60, 255)
        assert theme.progressbar_bg_color == (40, 40, 40, 200)

    def test_custom_theme_propagates(self, game: Game) -> None:
        """Custom theme set on Game is used by components."""
        custom_theme = Theme(font_size=36, button_min_width=300)
        game.theme = custom_theme

        root = _UIRoot(game)
        label = Label("Test")
        root.add(label)

        w, h = label.get_preferred_size()
        # font_size=36
        assert w == _estimate_text_width("Test", 36)
        assert h == int(36 * 1.4)  # 50

    def test_game_theme_lazy_creation(self, game: Game) -> None:
        """Game.theme creates a default Theme on first access."""
        # Access theme — should be auto-created
        theme = game.theme
        assert isinstance(theme, Theme)
        # Same instance on second access
        assert game.theme is theme


# ==================================================================
# 5b. ImageBox and ProgressBar (~8 tests)
# ==================================================================


class TestImageBox:
    """ImageBox creation, sizing, and drawing."""

    def test_creation_defaults(self) -> None:
        """ImageBox has image_name and default size."""
        box = ImageBox("sprites/portrait", width=96, height=96)
        assert box.image_name == "sprites/portrait"
        assert box.get_preferred_size() == (96, 96)

    def test_preferred_size_fallback(self) -> None:
        """ImageBox without explicit size uses 64×64."""
        box = ImageBox("icon")
        assert box.get_preferred_size() == (64, 64)

    def test_image_name_setter(self) -> None:
        """Changing image_name invalidates cached handle."""
        box = ImageBox("old", width=32, height=32)
        box._image_handle = "cached"
        box.image_name = "new"
        assert box.image_name == "new"
        assert box._image_handle is None

    def test_draw_calls_backend(
        self,
        root: _UIRoot,
        backend: MockBackend,
        game: Game,
        asset_dir: Path,
    ) -> None:
        """ImageBox draws via backend.draw_image."""
        game.assets = AssetManager(game.backend, base_path=asset_dir)
        box = ImageBox("sprites/portrait", width=96, height=96, anchor=Anchor.TOP_LEFT)
        root.add(box)
        root._ensure_layout()
        root.draw()

        assert len(backend.images) == 1
        img = backend.images[0]
        assert img["width"] == 96
        assert img["height"] == 96
        assert img["x"] == 0
        assert img["y"] == 0


class TestProgressBar:
    """ProgressBar creation, value, fraction, and drawing."""

    def test_creation_defaults(self) -> None:
        """ProgressBar starts at 0/100 with default size."""
        bar = ProgressBar()
        assert bar.value == 0
        assert bar.max_value == 100
        assert bar.fraction == 0.0
        assert bar.get_preferred_size() == (200, 24)

    def test_fraction_clamped(self) -> None:
        """fraction is clamped to 0.0–1.0."""
        bar = ProgressBar(value=50, max_value=100)
        assert bar.fraction == 0.5

        bar.value = 150
        assert bar.fraction == 1.0

        bar.value = -10
        assert bar.fraction == 0.0

    def test_value_setter(self) -> None:
        """value can be updated."""
        bar = ProgressBar(value=25, max_value=100)
        bar.value = 75
        assert bar.value == 75
        assert bar.fraction == 0.75

    def test_draw_calls_backend(
        self,
        root: _UIRoot,
        backend: MockBackend,
        game: Game,
    ) -> None:
        """ProgressBar draws background and fill rects."""
        bar = ProgressBar(
            value=50,
            max_value=100,
            width=200,
            height=24,
            anchor=Anchor.TOP_LEFT,
        )
        root.add(bar)
        root._ensure_layout()
        root.draw()

        assert len(backend.rects) == 2  # bg + fill
        bar_color = game.theme.progressbar_color
        bg_color = game.theme.progressbar_bg_color
        assert backend.rects[0]["width"] == 200
        assert backend.rects[0]["height"] == 24
        assert backend.rects[0]["color"] == bg_color
        assert backend.rects[1]["width"] == 100  # 50% of 200
        assert backend.rects[1]["height"] == 24
        assert backend.rects[1]["color"] == bar_color

    def test_explicit_colors_override_theme(
        self,
        root: _UIRoot,
        backend: MockBackend,
    ) -> None:
        """Explicit bar_color and bg_color override theme."""
        bar = ProgressBar(
            value=50,
            max_value=100,
            width=100,
            height=20,
            bar_color=(255, 0, 0, 255),
            bg_color=(0, 0, 0, 255),
            anchor=Anchor.TOP_LEFT,
        )
        root.add(bar)
        root._ensure_layout()
        root.draw()

        assert backend.rects[0]["color"] == (0, 0, 0, 255)
        assert backend.rects[1]["color"] == (255, 0, 0, 255)
        assert backend.rects[1]["width"] == 50

    def test_empty_bar_no_fill(
        self,
        root: _UIRoot,
        backend: MockBackend,
    ) -> None:
        """ProgressBar at 0% draws only background."""
        bar = ProgressBar(value=0, max_value=100, width=100, height=20, anchor=Anchor.TOP_LEFT)
        root.add(bar)
        root._ensure_layout()
        root.draw()

        assert len(backend.rects) == 1
        assert backend.rects[0]["width"] == 100  # bg only


# ==================================================================
# 6. Scene UI integration (~8 tests)
# ==================================================================


class TestSceneIntegration:
    """Scene.ui lazy property, draw integration, and input dispatch."""

    def test_scene_ui_creates_root(self, game: Game) -> None:
        """Scene.ui creates a _UIRoot on first access."""
        scene = Scene()
        game.push(scene)

        assert scene._ui is None  # not yet accessed
        ui = scene.ui
        assert isinstance(ui, _UIRoot)
        assert scene._ui is ui  # cached

    def test_scene_ui_covers_full_screen(self, game: Game) -> None:
        """_UIRoot covers the full logical resolution."""
        scene = Scene()
        game.push(scene)

        root = scene.ui
        assert root._computed_w == 800
        assert root._computed_h == 600

    def test_ui_draw_after_scene_draw(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """UI draw calls appear in mock backend after a tick."""
        class MyScene(Scene):
            def on_enter(self) -> None:
                self.ui.add(Label("HUD"))

        scene = MyScene()
        game.push(scene)
        game.tick(dt=0.016)

        assert len(backend.texts) == 1
        assert backend.texts[0]["text"] == "HUD"

    def test_ui_button_click_consumes_event(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Click consumed by UI button does NOT reach scene.handle_input."""
        scene_received = []

        class MyScene(Scene):
            def on_enter(self) -> None:
                self.ui.add(
                    Button("Go", on_click=lambda: None,
                           width=200, height=50, anchor=Anchor.TOP_LEFT),
                )

            def handle_input(self, event: InputEvent) -> bool:
                scene_received.append(event)
                return False

        scene = MyScene()
        game.push(scene)
        game.tick(dt=0.016)  # initial layout

        # Click inside button (0,0 → 200,50)
        backend.inject_click(100, 25)
        game.tick(dt=0.016)

        assert len(scene_received) == 0  # scene never saw the click

    def test_non_consumed_event_reaches_scene(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Events not consumed by UI still reach scene.handle_input."""
        scene_received = []

        class MyScene(Scene):
            def on_enter(self) -> None:
                self.ui.add(
                    Button("Go", width=100, height=50, anchor=Anchor.TOP_LEFT),
                )

            def handle_input(self, event: InputEvent) -> bool:
                scene_received.append(event)
                return False

        scene = MyScene()
        game.push(scene)
        game.tick(dt=0.016)

        # Click far from button
        backend.inject_click(700, 500)
        game.tick(dt=0.016)

        assert any(e.type == "click" for e in scene_received)

    def test_scene_without_ui_works(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """A scene that never touches self.ui works normally."""
        class PlainScene(Scene):
            pass

        scene = PlainScene()
        game.push(scene)
        game.tick(dt=0.016)  # should not crash

        assert scene._ui is None  # never created

    def test_full_menu_integration(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Full panel + label + button menu renders correctly."""
        clicked = []

        class MenuScene(Scene):
            def on_enter(self) -> None:
                panel = Panel(
                    anchor=Anchor.CENTER,
                    layout=Layout.VERTICAL,
                    spacing=10,
                )
                panel.add(Label("Menu"))
                panel.add(Button("Start", on_click=lambda: clicked.append("start")))
                panel.add(Button("Quit", on_click=lambda: clicked.append("quit")))
                self.ui.add(panel)

        scene = MenuScene()
        game.push(scene)
        game.tick(dt=0.016)

        # Should have 3 rects (panel bg + 2 button bgs) and 3 texts
        assert len(backend.rects) == 3
        assert len(backend.texts) == 3
        text_strs = [t["text"] for t in backend.texts]
        assert "Menu" in text_strs
        assert "Start" in text_strs
        assert "Quit" in text_strs

        # Click the Start button — find its position
        start_btn = scene.ui.children[0].children[1]
        cx = start_btn._computed_x + start_btn._computed_w // 2
        cy = start_btn._computed_y + start_btn._computed_h // 2
        backend.inject_click(cx, cy)
        game.tick(dt=0.016)

        assert clicked == ["start"]

    def test_ui_for_transparent_scene_stack(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Both scenes' UIs draw when top scene is transparent."""
        class BottomScene(Scene):
            def on_enter(self) -> None:
                self.ui.add(Label("Bottom"))

        class TopScene(Scene):
            transparent = True

            def on_enter(self) -> None:
                self.ui.add(Label("Top"))

        game.push(BottomScene())
        game.push(TopScene())
        game.tick(dt=0.016)

        text_strs = [t["text"] for t in backend.texts]
        assert "Bottom" in text_strs
        assert "Top" in text_strs


# ==================================================================
# Bug-fix: error messages include valid enum values
# ==================================================================


class TestLayoutErrorMessages:

    def test_anchor_error_includes_valid_values(self) -> None:
        """compute_anchor_position error includes valid Anchor names."""
        with pytest.raises(ValueError, match="valid values.*CENTER.*TOP_LEFT"):
            compute_anchor_position("bogus", 0, 0, 100, 100, 50, 50)

    def test_flow_layout_error_includes_valid_values(self) -> None:
        """compute_flow_layout error includes valid Layout names."""
        with pytest.raises(ValueError, match="valid values.*NONE.*VERTICAL.*HORIZONTAL"):
            compute_flow_layout("bogus", 0, 0, 100, 100, [(50, 50)])

    def test_content_size_error_includes_valid_values(self) -> None:
        """compute_content_size error includes valid Layout names."""
        with pytest.raises(ValueError, match="valid values.*NONE.*VERTICAL.*HORIZONTAL"):
            compute_content_size("bogus", [(50, 50)])
