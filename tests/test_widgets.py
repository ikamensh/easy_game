"""Tests for Stage 9 UI Widgets: ImageBox, ProgressBar, TextBox, List,
Grid, Tooltip, TabGroup, DataTable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from easygame import Game
from easygame.assets import AssetManager
from easygame.backends.mock_backend import MockBackend
from easygame.input import InputEvent
from easygame.ui import (
    Anchor,
    Component,
    DataTable,
    Grid,
    ImageBox,
    Label,
    List,
    Panel,
    ProgressBar,
    Style,
    TabGroup,
    TextBox,
    Theme,
    Tooltip,
)
from easygame.ui.component import _UIRoot
from easygame.ui.components import _estimate_text_width
from easygame.ui.widgets import _word_wrap


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def game() -> Game:
    """Game with mock backend at 800×600."""
    return Game("Widget Test", backend="mock", resolution=(800, 600))


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
    (sprites / "icon.png").write_bytes(b"png")
    return tmp_path


# ==================================================================
# 1. ImageBox (~8 tests)
# ==================================================================


class TestImageBox:
    """ImageBox creation, image_name setter, preferred size, and drawing."""

    def test_creation_defaults(self) -> None:
        """ImageBox has image_name and default 64×64 size."""
        box = ImageBox("sprites/icon")
        assert box.image_name == "sprites/icon"
        assert box.get_preferred_size() == (64, 64)

    def test_creation_custom_size(self) -> None:
        """ImageBox with explicit width/height."""
        box = ImageBox("portrait", width=128, height=96)
        assert box.get_preferred_size() == (128, 96)

    def test_image_name_setter_invalidates_handle(self) -> None:
        """Changing image_name clears cached handle and marks dirty."""
        box = ImageBox("old_image", width=32, height=32)
        box._image_handle = "cached"
        box._layout_dirty = False
        box.image_name = "new_image"
        assert box.image_name == "new_image"
        assert box._image_handle is None
        assert box._layout_dirty is True

    def test_image_name_setter_same_no_change(self) -> None:
        """Setting same image_name does not invalidate."""
        box = ImageBox("same", width=32, height=32)
        box._image_handle = "cached"
        box._layout_dirty = False
        box.image_name = "same"
        assert box._image_handle == "cached"
        assert box._layout_dirty is False

    def test_draw_calls_draw_image(
        self, root: _UIRoot, backend: MockBackend, game: Game, asset_dir: Path,
    ) -> None:
        """ImageBox draws via backend.draw_image with correct bounds."""
        game.assets = AssetManager(game.backend, base_path=asset_dir)
        box = ImageBox("sprites/icon", width=96, height=96, anchor=Anchor.TOP_LEFT)
        root.add(box)
        root._ensure_layout()
        root.draw()

        assert len(backend.images) == 1
        img = backend.images[0]
        assert img["x"] == 0
        assert img["y"] == 0
        assert img["width"] == 96
        assert img["height"] == 96

    def test_draw_no_game_noop(self) -> None:
        """ImageBox without _game does not crash on draw."""
        box = ImageBox("icon")
        box.on_draw()  # should be a no-op

    def test_anchor_positioning(
        self, root: _UIRoot,
    ) -> None:
        """ImageBox respects anchor positioning."""
        box = ImageBox("icon", width=64, height=64, anchor=Anchor.CENTER)
        root.add(box)
        root._ensure_layout()
        assert box._computed_x == (800 - 64) // 2
        assert box._computed_y == (600 - 64) // 2

    def test_visible_false_no_draw(
        self, root: _UIRoot, backend: MockBackend, game: Game, asset_dir: Path,
    ) -> None:
        """Invisible ImageBox produces no draw calls."""
        game.assets = AssetManager(game.backend, base_path=asset_dir)
        box = ImageBox("sprites/icon", width=64, height=64, anchor=Anchor.TOP_LEFT, visible=False)
        root.add(box)
        root._ensure_layout()
        root.draw()
        assert len(backend.images) == 0


# ==================================================================
# 2. ProgressBar (~10 tests)
# ==================================================================


class TestProgressBar:
    """ProgressBar creation, value clamping, fraction, and drawing."""

    def test_creation_defaults(self) -> None:
        """ProgressBar defaults: 0/100, 200×24 size."""
        bar = ProgressBar()
        assert bar.value == 0
        assert bar.max_value == 100
        assert bar.fraction == 0.0
        assert bar.get_preferred_size() == (200, 24)

    def test_fraction_at_50_percent(self) -> None:
        """fraction = 0.5 when value = 50, max = 100."""
        bar = ProgressBar(value=50, max_value=100)
        assert bar.fraction == pytest.approx(0.5)

    def test_fraction_above_max_clamped(self) -> None:
        """fraction clamped to 1.0 when value > max."""
        bar = ProgressBar(value=200, max_value=100)
        assert bar.fraction == 1.0

    def test_fraction_below_zero_clamped(self) -> None:
        """fraction clamped to 0.0 when value < 0."""
        bar = ProgressBar(value=-50, max_value=100)
        assert bar.fraction == 0.0

    def test_fraction_zero_max(self) -> None:
        """fraction = 0.0 when max_value <= 0."""
        bar = ProgressBar(value=50, max_value=0)
        assert bar.fraction == 0.0

    def test_value_setter(self) -> None:
        """value property can be updated."""
        bar = ProgressBar(value=10, max_value=100)
        bar.value = 75
        assert bar.value == 75
        assert bar.fraction == pytest.approx(0.75)

    def test_draw_bg_and_fill(
        self, root: _UIRoot, backend: MockBackend, game: Game,
    ) -> None:
        """50% ProgressBar draws background + half-width fill rect."""
        bar = ProgressBar(value=50, max_value=100, width=200, height=24, anchor=Anchor.TOP_LEFT)
        root.add(bar)
        root._ensure_layout()
        root.draw()

        assert len(backend.rects) == 2
        # Background
        assert backend.rects[0]["width"] == 200
        assert backend.rects[0]["color"] == game.theme.progressbar_bg_color
        # Fill
        assert backend.rects[1]["width"] == 100  # 50% of 200
        assert backend.rects[1]["color"] == game.theme.progressbar_color

    def test_draw_empty_bar(
        self, root: _UIRoot, backend: MockBackend,
    ) -> None:
        """0% ProgressBar draws only background, no fill."""
        bar = ProgressBar(value=0, max_value=100, width=200, height=24, anchor=Anchor.TOP_LEFT)
        root.add(bar)
        root._ensure_layout()
        root.draw()

        assert len(backend.rects) == 1  # background only

    def test_draw_full_bar(
        self, root: _UIRoot, backend: MockBackend,
    ) -> None:
        """100% ProgressBar has fill == full width."""
        bar = ProgressBar(value=100, max_value=100, width=200, height=24, anchor=Anchor.TOP_LEFT)
        root.add(bar)
        root._ensure_layout()
        root.draw()

        assert len(backend.rects) == 2
        assert backend.rects[1]["width"] == 200

    def test_explicit_colors(
        self, root: _UIRoot, backend: MockBackend,
    ) -> None:
        """Explicit bar_color/bg_color override theme defaults."""
        bar = ProgressBar(
            value=50, max_value=100, width=100, height=20,
            bar_color=(255, 0, 0, 255), bg_color=(0, 0, 0, 255),
            anchor=Anchor.TOP_LEFT,
        )
        root.add(bar)
        root._ensure_layout()
        root.draw()

        assert backend.rects[0]["color"] == (0, 0, 0, 255)
        assert backend.rects[1]["color"] == (255, 0, 0, 255)


# ==================================================================
# 3. TextBox (~14 tests)
# ==================================================================


class TestWordWrap:
    """Unit tests for the _word_wrap helper."""

    def test_single_word_fits(self) -> None:
        """Single short word → one line."""
        lines = _word_wrap("Hello", 200, 24)
        assert lines == ["Hello"]

    def test_wraps_at_word_boundary(self) -> None:
        """Long text wraps at word boundaries."""
        # Each char at font_size=24 is roughly 0.65*24≈15.6px for lowercase
        # "aaaa bbbb" with max_width=70 should split
        lines = _word_wrap("aaaa bbbb", 70, 24)
        assert len(lines) == 2
        assert lines[0] == "aaaa"
        assert lines[1] == "bbbb"

    def test_explicit_newlines(self) -> None:
        """Explicit \\n is respected."""
        lines = _word_wrap("line1\nline2", 500, 24)
        assert lines == ["line1", "line2"]

    def test_empty_text(self) -> None:
        """Empty text returns single empty line (from paragraph split)."""
        lines = _word_wrap("", 200, 24)
        assert lines == [""]

    def test_zero_width_returns_text(self) -> None:
        """Zero max_width returns the full text as a single line."""
        lines = _word_wrap("hello world", 0, 24)
        assert lines == ["hello world"]


class TestTextBox:
    """TextBox word-wrap, typewriter, skip, reset, is_complete."""

    def test_creation_instant(self) -> None:
        """Default TextBox (speed=0) reveals all text immediately."""
        tb = TextBox("Hello World", width=300)
        assert tb.text == "Hello World"
        assert tb.typewriter_speed == 0
        assert tb.is_complete is True
        assert tb.revealed_count == len("Hello World")

    def test_creation_typewriter(self) -> None:
        """Typewriter TextBox starts with 0 revealed characters."""
        tb = TextBox("Hello", typewriter_speed=10, width=300)
        assert tb.revealed_count == 0
        assert tb.is_complete is False

    def test_typewriter_advance(self) -> None:
        """update(dt) advances revealed_count correctly."""
        tb = TextBox("Hello World", typewriter_speed=10, width=300)
        # 10 chars/sec × 0.5 sec = 5 chars
        tb.update(0.5)
        assert tb.revealed_count == 5

    def test_typewriter_multiple_updates(self) -> None:
        """Multiple small updates accumulate."""
        tb = TextBox("ABCDE", typewriter_speed=10, width=300)
        tb.update(0.1)  # 1 char
        tb.update(0.1)  # 2 chars
        tb.update(0.1)  # 3 chars
        assert tb.revealed_count == 3

    def test_typewriter_completes(self) -> None:
        """is_complete becomes True when all characters revealed."""
        tb = TextBox("Hi", typewriter_speed=10, width=300)
        tb.update(1.0)  # 10 chars, but "Hi" is only 2
        assert tb.is_complete is True
        assert tb.revealed_count == 2  # clamped to text length

    def test_skip_instantly_completes(self) -> None:
        """skip() reveals all text immediately."""
        tb = TextBox("Long text here", typewriter_speed=5, width=300)
        assert tb.is_complete is False
        tb.skip()
        assert tb.is_complete is True
        assert tb.revealed_count == len("Long text here")

    def test_reset_restarts_typewriter(self) -> None:
        """reset() sets revealed_count back to 0 for typewriter."""
        tb = TextBox("Hello", typewriter_speed=10, width=300)
        tb.update(1.0)
        assert tb.is_complete is True
        tb.reset()
        assert tb.revealed_count == 0
        assert tb.is_complete is False

    def test_reset_instant_stays_complete(self) -> None:
        """reset() with speed=0 keeps all text visible."""
        tb = TextBox("Hello", width=300)
        tb.reset()
        assert tb.is_complete is True

    def test_text_setter_resets_typewriter(self) -> None:
        """Changing text resets the typewriter for the new text."""
        tb = TextBox("Old", typewriter_speed=10, width=300)
        tb.update(1.0)  # reveal all of "Old"
        assert tb.is_complete is True
        tb.text = "New Longer Text"
        assert tb.revealed_count == 0
        assert tb.is_complete is False

    def test_text_setter_instant(self) -> None:
        """Changing text with speed=0 instantly reveals new text."""
        tb = TextBox("Old", width=300)
        tb.text = "New"
        assert tb.is_complete is True
        assert tb.revealed_count == 3

    def test_preferred_size_auto_height(self) -> None:
        """TextBox auto-sizes height from wrapped lines."""
        tb = TextBox("A", width=300)
        w, h = tb.get_preferred_size()
        assert w == 300
        # With label style: font_size=24, padding=0 (label default)
        # 1 line × int(24*1.4) = 33 + 2*0 padding = 33
        assert h > 0

    def test_draw_produces_text_calls(
        self, root: _UIRoot, backend: MockBackend,
    ) -> None:
        """TextBox with text draws at least one draw_text call."""
        tb = TextBox("Hello", width=300, anchor=Anchor.TOP_LEFT)
        root.add(tb)
        root._ensure_layout()
        root.draw()
        assert len(backend.texts) >= 1
        assert backend.texts[0]["text"] == "Hello"

    def test_draw_empty_text_no_calls(
        self, root: _UIRoot, backend: MockBackend,
    ) -> None:
        """Empty text TextBox produces no draw calls."""
        tb = TextBox("", width=300, anchor=Anchor.TOP_LEFT)
        root.add(tb)
        root._ensure_layout()
        root.draw()
        assert len(backend.texts) == 0

    def test_update_noop_when_speed_zero(self) -> None:
        """update() does nothing when typewriter_speed is 0."""
        tb = TextBox("Hello", width=300)
        count_before = tb.revealed_count
        tb.update(1.0)
        assert tb.revealed_count == count_before


# ==================================================================
# 4. List (~14 tests)
# ==================================================================


class TestList:
    """List creation, selection, keyboard nav, mouse click, scroll."""

    def test_creation_empty(self) -> None:
        """List with no items starts empty."""
        lst = List()
        assert lst.items == []
        assert lst.selected_index is None
        assert lst.item_height == 30

    def test_creation_with_items(self) -> None:
        """List with initial items stores them."""
        lst = List(["A", "B", "C"])
        assert lst.items == ["A", "B", "C"]
        assert lst.selected_index is None

    def test_selected_index_starts_none(self) -> None:
        """selected_index is None until explicitly set."""
        lst = List(["X", "Y"])
        assert lst.selected_index is None

    def test_selected_index_clamped(self) -> None:
        """Setting selected_index beyond bounds clamps it."""
        lst = List(["A", "B", "C"])
        lst.selected_index = 99
        assert lst.selected_index == 2  # last valid
        lst.selected_index = -5
        assert lst.selected_index == 0

    def test_selected_index_none_on_empty(self) -> None:
        """selected_index becomes None for empty list."""
        lst = List()
        lst.selected_index = 5
        assert lst.selected_index is None

    def test_keyboard_down_selects_first(self) -> None:
        """Down action selects index 0 when nothing selected."""
        lst = List(["A", "B", "C"])
        lst.compute_layout(0, 0, 200, 90)
        event = InputEvent(type="key", action="down")
        consumed = lst.on_event(event)
        assert consumed is True
        assert lst.selected_index == 0

    def test_keyboard_down_moves(self) -> None:
        """Down action moves selection down by one."""
        lst = List(["A", "B", "C"])
        lst.compute_layout(0, 0, 200, 90)
        lst._selected_index = 0
        event = InputEvent(type="key", action="down")
        lst.on_event(event)
        assert lst.selected_index == 1

    def test_keyboard_up_selects_last(self) -> None:
        """Up action selects last item when nothing selected."""
        lst = List(["A", "B", "C"])
        lst.compute_layout(0, 0, 200, 90)
        event = InputEvent(type="key", action="up")
        lst.on_event(event)
        assert lst.selected_index == 2

    def test_keyboard_up_moves(self) -> None:
        """Up action moves selection up by one."""
        lst = List(["A", "B", "C"])
        lst.compute_layout(0, 0, 200, 90)
        lst._selected_index = 2
        event = InputEvent(type="key", action="up")
        lst.on_event(event)
        assert lst.selected_index == 1

    def test_keyboard_down_clamps_at_bottom(self) -> None:
        """Down action stops at last item."""
        lst = List(["A", "B"])
        lst.compute_layout(0, 0, 200, 60)
        lst._selected_index = 1
        event = InputEvent(type="key", action="down")
        lst.on_event(event)
        assert lst.selected_index == 1

    def test_confirm_fires_on_select(self) -> None:
        """Confirm action calls on_select with current index."""
        received = []
        lst = List(["A", "B"], on_select=lambda i: received.append(i))
        lst.compute_layout(0, 0, 200, 60)
        lst._selected_index = 1
        event = InputEvent(type="key", action="confirm")
        consumed = lst.on_event(event)
        assert consumed is True
        assert received == [1]

    def test_confirm_no_callback_no_crash(self) -> None:
        """Confirm with no on_select and no selection is safe."""
        lst = List(["A"])
        lst.compute_layout(0, 0, 200, 30)
        event = InputEvent(type="key", action="confirm")
        consumed = lst.on_event(event)
        assert consumed is True  # event still consumed

    def test_mouse_click_selects_item(self) -> None:
        """Clicking on an item row selects it."""
        received = []
        lst = List(["A", "B", "C"], on_select=lambda i: received.append(i))
        lst.compute_layout(0, 0, 200, 90)
        # Click in second item (row_height=30, so y=35 is in row 1)
        event = InputEvent(type="click", button="left", x=100, y=35)
        consumed = lst.on_event(event)
        assert consumed is True
        assert lst.selected_index == 1
        assert received == [1]

    def test_mouse_click_outside_not_consumed(self) -> None:
        """Click outside list bounds is not consumed."""
        lst = List(["A"], width=100, height=30)
        lst.compute_layout(0, 0, 100, 30)
        event = InputEvent(type="click", button="left", x=500, y=500)
        consumed = lst.on_event(event)
        assert consumed is False

    def test_scroll_offset_changes(self) -> None:
        """Scroll event adjusts scroll_offset."""
        # 10 items at 30px each = 300px, but only 90px visible → 3 visible
        lst = List([f"item{i}" for i in range(10)], height=90)
        lst.compute_layout(0, 0, 200, 90)
        assert lst.scroll_offset == 0
        # Scroll down (dy < 0)
        event = InputEvent(type="scroll", x=100, y=45, dy=-1)
        consumed = lst.on_event(event)
        assert consumed is True
        assert lst.scroll_offset == 1

    def test_items_setter_clamps_selection(self) -> None:
        """Setting items clamps selection if out of new range."""
        lst = List(["A", "B", "C"])
        lst._selected_index = 2
        lst.items = ["X"]  # only 1 item
        assert lst.selected_index == 0

    def test_items_setter_clears_on_empty(self) -> None:
        """Setting empty items clears selection."""
        lst = List(["A", "B"])
        lst._selected_index = 1
        lst.items = []
        assert lst.selected_index is None

    def test_preferred_size_auto_height(self) -> None:
        """Height auto-sizes from item count × item_height."""
        lst = List(["A", "B", "C"], item_height=30)
        w, h = lst.get_preferred_size()
        assert w == 200  # default
        assert h == 90  # 3 × 30

    def test_preferred_size_explicit_height(self) -> None:
        """Explicit height overrides auto-size."""
        lst = List(["A", "B", "C"], height=50)
        _, h = lst.get_preferred_size()
        assert h == 50

    def test_draw_background_and_items(
        self, root: _UIRoot, backend: MockBackend,
    ) -> None:
        """List draws background rect and text for each visible item."""
        lst = List(["Alpha", "Beta"], width=200, height=60, anchor=Anchor.TOP_LEFT)
        root.add(lst)
        root._ensure_layout()
        root.draw()

        # 1 background rect + 0 selection rects
        assert len(backend.rects) == 1
        # 2 text items
        assert len(backend.texts) == 2
        texts = [t["text"] for t in backend.texts]
        assert "Alpha" in texts
        assert "Beta" in texts

    def test_draw_with_selection_highlight(
        self, root: _UIRoot, backend: MockBackend, game: Game,
    ) -> None:
        """Selected item draws a highlight rect."""
        lst = List(["Alpha", "Beta"], width=200, height=60, anchor=Anchor.TOP_LEFT)
        lst._selected_index = 0
        root.add(lst)
        root._ensure_layout()
        root.draw()

        # 1 background + 1 highlight
        assert len(backend.rects) == 2
        assert backend.rects[1]["color"] == game.theme.selected_color

    def test_on_select_callback_on_keyboard(self) -> None:
        """Keyboard nav fires on_select callback."""
        received = []
        lst = List(["A", "B", "C"], on_select=lambda i: received.append(i))
        lst.compute_layout(0, 0, 200, 90)
        lst.on_event(InputEvent(type="key", action="down"))
        assert received == [0]


# ==================================================================
# 5. Grid (~12 tests)
# ==================================================================


class TestGrid:
    """Grid creation, cell management, click-select, drawing."""

    def test_creation_defaults(self) -> None:
        """Grid stores columns, rows, cell_size, spacing."""
        grid = Grid(3, 2)
        assert grid.columns == 3
        assert grid.rows == 2
        assert grid.cell_size == (64, 64)
        assert grid.spacing == 4
        assert grid.selected is None

    def test_set_cell_get_cell(self) -> None:
        """set_cell stores component, get_cell retrieves it."""
        grid = Grid(2, 2)
        comp = Label("X")
        grid.set_cell(0, 1, comp)
        assert grid.get_cell(0, 1) is comp
        assert grid.get_cell(1, 0) is None

    def test_set_cell_none_clears(self) -> None:
        """set_cell with None removes the component."""
        grid = Grid(2, 2)
        comp = Label("X")
        grid.set_cell(0, 0, comp)
        grid.set_cell(0, 0, None)
        assert grid.get_cell(0, 0) is None

    def test_set_cell_replaces_existing(self) -> None:
        """set_cell replaces an existing component in the same cell."""
        grid = Grid(2, 2)
        old = Label("Old")
        new = Label("New")
        grid.set_cell(0, 0, old)
        grid.set_cell(0, 0, new)
        assert grid.get_cell(0, 0) is new
        assert old.parent is None  # removed from tree

    def test_set_cell_adds_child(self) -> None:
        """set_cell adds the component as a child of the grid."""
        grid = Grid(2, 2)
        comp = Label("X")
        grid.set_cell(1, 1, comp)
        assert comp.parent is grid

    def test_selected_property_clamped(self) -> None:
        """selected setter clamps to grid bounds."""
        grid = Grid(3, 2)
        grid.selected = (10, 10)
        assert grid.selected == (2, 1)

    def test_selected_none(self) -> None:
        """selected can be set to None."""
        grid = Grid(3, 2)
        grid.selected = (1, 1)
        grid.selected = None
        assert grid.selected is None

    def test_click_selects_cell(self) -> None:
        """Clicking within a cell selects it."""
        grid = Grid(3, 2, cell_size=(64, 64), spacing=4, style=Style(padding=4))
        grid.compute_layout(0, 0, 300, 200)
        # Cell (0,0) starts at x=4 (padding), y=4 (padding)
        event = InputEvent(type="click", button="left", x=10, y=10)
        consumed = grid.on_event(event)
        assert consumed is True
        assert grid.selected == (0, 0)

    def test_click_in_spacing_no_select(self) -> None:
        """Clicking in the spacing gap between cells does not select."""
        grid = Grid(2, 2, cell_size=(64, 64), spacing=10, style=Style(padding=4))
        grid.compute_layout(0, 0, 300, 200)
        # Cell (0,0) is at x=4..68. Spacing gap is x=68..78. Cell (1,0) starts at x=78.
        event = InputEvent(type="click", button="left", x=72, y=10)
        consumed = grid.on_event(event)
        assert consumed is True
        # Click was inside the grid bounds, but in spacing — no cell selected
        assert grid.selected is None

    def test_on_select_callback(self) -> None:
        """on_select fires with (col, row) on click."""
        received = []
        grid = Grid(3, 2, on_select=lambda c, r: received.append((c, r)),
                     style=Style(padding=4))
        grid.compute_layout(0, 0, 300, 200)
        event = InputEvent(type="click", button="left", x=10, y=10)
        grid.on_event(event)
        assert received == [(0, 0)]

    def test_preferred_size_auto(self) -> None:
        """Auto-size from columns × cell_w + spacing + padding."""
        grid = Grid(3, 2, cell_size=(64, 64), spacing=4, style=Style(padding=4))
        w, h = grid.get_preferred_size()
        expected_w = 3 * 64 + 2 * 4 + 2 * 4  # 200
        expected_h = 2 * 64 + 1 * 4 + 2 * 4  # 140
        assert w == expected_w
        assert h == expected_h

    def test_preferred_size_explicit(self) -> None:
        """Explicit width/height overrides auto-size."""
        grid = Grid(3, 2, width=500, height=400)
        assert grid.get_preferred_size() == (500, 400)

    def test_draw_produces_rects(
        self, root: _UIRoot, backend: MockBackend,
    ) -> None:
        """Grid draws background + cell backgrounds."""
        grid = Grid(2, 2, cell_size=(64, 64), spacing=4,
                     width=200, height=200, anchor=Anchor.TOP_LEFT)
        root.add(grid)
        root._ensure_layout()
        root.draw()

        # 1 overall bg + 4 cell bgs = 5
        assert len(backend.rects) == 5

    def test_draw_with_selection(
        self, root: _UIRoot, backend: MockBackend, game: Game,
    ) -> None:
        """Selected cell draws an additional highlight rect."""
        grid = Grid(2, 2, cell_size=(64, 64), spacing=4,
                     width=200, height=200, anchor=Anchor.TOP_LEFT)
        grid._selected = (0, 0)
        root.add(grid)
        root._ensure_layout()
        root.draw()

        # 1 bg + 4 cells + 1 highlight = 6
        assert len(backend.rects) == 6
        # Last rect should be the selection color
        sel_rects = [r for r in backend.rects if r["color"] == game.theme.selected_color]
        assert len(sel_rects) == 1

    # -- Bug-fix tests -------------------------------------------------

    def test_cell_at_zero_cell_size_no_crash(self) -> None:
        """_cell_at returns None (no ZeroDivisionError) when cell_size=(0,0) and spacing=0."""
        grid = Grid(2, 2, cell_size=(0, 0), spacing=0, style=Style(padding=0))
        grid.compute_layout(0, 0, 100, 100)
        result = grid._cell_at(5, 5)
        assert result is None

    def test_cell_at_zero_width_cell(self) -> None:
        """_cell_at returns None when cell width is 0 (stride_x == spacing only)."""
        grid = Grid(2, 2, cell_size=(0, 64), spacing=4, style=Style(padding=0))
        grid.compute_layout(0, 0, 100, 200)
        result = grid._cell_at(2, 10)
        assert result is None

    def test_cell_at_zero_height_cell(self) -> None:
        """_cell_at returns None when cell height is 0 (stride_y == spacing only)."""
        grid = Grid(2, 2, cell_size=(64, 0), spacing=4, style=Style(padding=0))
        grid.compute_layout(0, 0, 200, 100)
        result = grid._cell_at(10, 2)
        assert result is None

    def test_selected_setter_empty_grid_zero_columns(self) -> None:
        """Setting selected on a grid with 0 columns sets None."""
        grid = Grid(0, 2)
        grid.selected = (0, 0)
        assert grid.selected is None

    def test_selected_setter_empty_grid_zero_rows(self) -> None:
        """Setting selected on a grid with 0 rows sets None."""
        grid = Grid(3, 0)
        grid.selected = (1, 0)
        assert grid.selected is None

    def test_selected_setter_empty_grid_both_zero(self) -> None:
        """Setting selected on a 0×0 grid sets None."""
        grid = Grid(0, 0)
        grid.selected = (0, 0)
        assert grid.selected is None

    def test_selected_setter_none_on_empty_grid(self) -> None:
        """Setting selected to None on an empty grid works fine."""
        grid = Grid(0, 0)
        grid.selected = None
        assert grid.selected is None


# ==================================================================
# 6. Tooltip (~12 tests)
# ==================================================================


class TestTooltip:
    """Tooltip creation, delay, show/hide, update, drawing."""

    def test_creation_defaults(self) -> None:
        """Tooltip defaults: 0.5s delay, not visible."""
        tip = Tooltip("Help text")
        assert tip.text == "Help text"
        assert tip.delay == 0.5
        assert tip._showing is False
        assert tip._visible_now is False

    def test_show_starts_timer(self) -> None:
        """show() sets _showing=True, resets timer."""
        tip = Tooltip("Help")
        tip.show(100, 200)
        assert tip._showing is True
        assert tip._visible_now is False
        assert tip._tip_x == 100
        assert tip._tip_y == 200

    def test_update_before_delay_not_visible(self) -> None:
        """update() before delay elapses keeps _visible_now False."""
        tip = Tooltip("Help", delay=0.5)
        tip.show(0, 0)
        tip.update(0.3)
        assert tip._visible_now is False

    def test_update_past_delay_becomes_visible(self) -> None:
        """update() past delay makes tooltip visible."""
        tip = Tooltip("Help", delay=0.5)
        tip.show(0, 0)
        tip.update(0.5)
        assert tip._visible_now is True

    def test_update_incremental(self) -> None:
        """Multiple small updates accumulate to pass the delay."""
        tip = Tooltip("Help", delay=1.0)
        tip.show(0, 0)
        tip.update(0.3)
        assert tip._visible_now is False
        tip.update(0.3)
        assert tip._visible_now is False
        tip.update(0.5)  # total = 1.1
        assert tip._visible_now is True

    def test_hide_resets(self) -> None:
        """hide() resets everything."""
        tip = Tooltip("Help", delay=0.5)
        tip.show(0, 0)
        tip.update(1.0)
        assert tip._visible_now is True
        tip.hide()
        assert tip._showing is False
        assert tip._visible_now is False
        assert tip._timer == 0.0

    def test_show_again_after_hide(self) -> None:
        """show() after hide() restarts the delay timer."""
        tip = Tooltip("Help", delay=0.5)
        tip.show(0, 0)
        tip.update(1.0)
        tip.hide()
        tip.show(50, 50)
        assert tip._showing is True
        assert tip._visible_now is False
        tip.update(0.5)
        assert tip._visible_now is True

    def test_show_updates_position_while_visible(self) -> None:
        """show() while already visible updates position without restarting timer."""
        tip = Tooltip("Help", delay=0.5)
        tip.show(10, 20)
        tip.update(1.0)
        assert tip._visible_now is True
        # Call show again — should update position, stay visible
        tip.show(100, 200)
        assert tip._visible_now is True
        assert tip._tip_x == 100
        assert tip._tip_y == 200

    def test_zero_delay_immediate(self) -> None:
        """Tooltip with delay=0 shows immediately on show()."""
        tip = Tooltip("Instant", delay=0)
        tip.show(50, 50)
        assert tip._visible_now is True

    def test_text_setter(self) -> None:
        """text property can be changed."""
        tip = Tooltip("Old")
        tip.text = "New"
        assert tip.text == "New"

    def test_update_without_show_noop(self) -> None:
        """update() without show() does nothing."""
        tip = Tooltip("Help")
        tip.update(10.0)
        assert tip._visible_now is False

    def test_draw_not_visible_no_calls(
        self, root: _UIRoot, backend: MockBackend,
    ) -> None:
        """Tooltip that's not visible produces no draw calls."""
        tip = Tooltip("Help", anchor=Anchor.TOP_LEFT)
        root.add(tip)
        root._ensure_layout()
        root.draw()
        assert len(backend.rects) == 0
        assert len(backend.texts) == 0

    def test_draw_visible_produces_calls(
        self, root: _UIRoot, backend: MockBackend,
    ) -> None:
        """Visible tooltip draws rect + text."""
        tip = Tooltip("Help", delay=0)
        root.add(tip)
        root._ensure_layout()
        tip.show(100, 100)
        root.draw()

        assert len(backend.rects) == 1
        assert len(backend.texts) == 1
        assert backend.texts[0]["text"] == "Help"

    def test_component_visible_stays_true(self) -> None:
        """Component.visible stays True even when tooltip is hidden."""
        tip = Tooltip("Help")
        assert tip.visible is True
        tip.show(0, 0)
        assert tip.visible is True
        tip.hide()
        assert tip.visible is True

    def test_game_tick_update_advances_timer(
        self, root: _UIRoot,
    ) -> None:
        """_UIRoot._update_tree advances tooltip timer correctly."""
        tip = Tooltip("Help", delay=0.5)
        root.add(tip)
        root._ensure_layout()
        tip.show(0, 0)

        root._update_tree(0.6)
        assert tip._visible_now is True


# ==================================================================
# 7. TabGroup (~14 tests)
# ==================================================================


class TestTabGroup:
    """TabGroup creation, tab switching, visibility, and drawing."""

    def test_creation_with_tabs(self) -> None:
        """TabGroup with initial tabs activates the first."""
        c1 = Panel(width=200, height=100)
        c2 = Panel(width=200, height=100)
        tg = TabGroup({"Tab1": c1, "Tab2": c2})
        assert tg.active_tab == "Tab1"
        assert tg.tab_labels == ["Tab1", "Tab2"]

    def test_creation_empty(self) -> None:
        """Empty TabGroup has no active tab."""
        tg = TabGroup()
        assert tg.active_tab is None
        assert tg.tab_labels == []

    def test_first_tab_content_visible(self) -> None:
        """Active tab's content is visible, others are hidden."""
        c1 = Panel(width=200, height=100)
        c2 = Panel(width=200, height=100)
        tg = TabGroup({"A": c1, "B": c2})
        assert c1.visible is True
        assert c2.visible is False

    def test_select_tab_switches_visibility(self) -> None:
        """select_tab changes visibility of content panels."""
        c1 = Panel(width=200, height=100)
        c2 = Panel(width=200, height=100)
        tg = TabGroup({"A": c1, "B": c2})
        tg.select_tab("B")
        assert tg.active_tab == "B"
        assert c1.visible is False
        assert c2.visible is True

    def test_select_tab_unknown_raises(self) -> None:
        """select_tab with unknown label raises KeyError listing available tabs."""
        tg = TabGroup({"A": Panel()})
        with pytest.raises(KeyError, match="No tab named 'Z'.*available tabs.*'A'"):
            tg.select_tab("Z")

    def test_select_tab_error_lists_multiple_tabs(self) -> None:
        """select_tab error message lists all available tab names."""
        tg = TabGroup({"Alpha": Panel(), "Beta": Panel(), "Gamma": Panel()})
        with pytest.raises(KeyError, match="available tabs.*'Alpha'.*'Beta'.*'Gamma'"):
            tg.select_tab("Delta")

    def test_active_tab_setter(self) -> None:
        """active_tab setter delegates to select_tab."""
        c1 = Panel()
        c2 = Panel()
        tg = TabGroup({"A": c1, "B": c2})
        tg.active_tab = "B"
        assert tg.active_tab == "B"

    def test_add_tab(self) -> None:
        """add_tab appends a new tab."""
        tg = TabGroup()
        comp = Panel()
        tg.add_tab("New", comp)
        assert tg.tab_labels == ["New"]
        assert tg.active_tab == "New"  # first tab auto-activates
        assert comp.visible is True

    def test_add_tab_second_not_active(self) -> None:
        """Adding a second tab does not change the active tab."""
        tg = TabGroup()
        c1 = Panel()
        c2 = Panel()
        tg.add_tab("First", c1)
        tg.add_tab("Second", c2)
        assert tg.active_tab == "First"
        assert c2.visible is False

    def test_get_tab_content(self) -> None:
        """get_tab_content returns the component or None."""
        c1 = Panel()
        tg = TabGroup({"A": c1})
        assert tg.get_tab_content("A") is c1
        assert tg.get_tab_content("B") is None

    def test_tab_height(self) -> None:
        """tab_height property returns the configured value."""
        tg = TabGroup(tab_height=48)
        assert tg.tab_height == 48

    def test_preferred_size(self) -> None:
        """Preferred size accounts for tab_height + content."""
        c1 = Panel(width=200, height=100)
        c2 = Panel(width=300, height=150)
        tg = TabGroup({"A": c1, "B": c2})
        w, h = tg.get_preferred_size()
        # width = max(200, 300) = 300 (at least 100)
        assert w == 300
        # height = tab_height (32) + max(100, 150) = 182
        assert h == 32 + 150

    def test_click_tab_header_switches(
        self, root: _UIRoot,
    ) -> None:
        """Clicking a tab header switches the active tab."""
        c1 = Panel(width=200, height=100)
        c2 = Panel(width=200, height=100)
        tg = TabGroup({"TabA": c1, "TabB": c2},
                       width=400, height=200, anchor=Anchor.TOP_LEFT)
        root.add(tg)
        root._ensure_layout()
        assert tg.active_tab == "TabA"

        # Compute where "TabB" header is. "TabA" width = text_width + 2*padding
        resolved = tg._resolve_style()
        font_size = resolved.font_size
        padding = resolved.padding
        tab_a_width = _estimate_text_width("TabA", font_size) + 2 * padding
        # Click in the middle of TabB header
        click_x = tab_a_width + 5
        click_y = tg._tab_height // 2

        event = InputEvent(type="click", button="left", x=click_x, y=click_y)
        consumed = root.handle_event(event)
        assert consumed is True
        assert tg.active_tab == "TabB"

    def test_draw_produces_rects_and_texts(
        self, root: _UIRoot, backend: MockBackend,
    ) -> None:
        """TabGroup draws tab header rects and text labels."""
        c1 = Panel(width=200, height=100)
        c2 = Panel(width=200, height=100)
        tg = TabGroup({"A": c1, "B": c2},
                       width=400, height=200, anchor=Anchor.TOP_LEFT)
        root.add(tg)
        root._ensure_layout()
        root.draw()

        # Tab headers: 2 tab rects + 1 remaining fill + 1 active content panel bg
        # = at least 3 rects from TabGroup + 1 from visible Panel
        assert len(backend.rects) >= 3
        # Tab header texts: "A" and "B"
        tab_texts = [t["text"] for t in backend.texts]
        assert "A" in tab_texts
        assert "B" in tab_texts

    def test_children_are_tab_components(self) -> None:
        """Tab content components are children of the TabGroup."""
        c1 = Panel()
        c2 = Panel()
        tg = TabGroup({"A": c1, "B": c2})
        assert c1.parent is tg
        assert c2.parent is tg


# ==================================================================
# 8. DataTable (~18 tests)
# ==================================================================


class TestDataTable:
    """DataTable creation, row management, selection, auto-widths, drawing."""

    def test_creation_defaults(self) -> None:
        """DataTable stores columns and defaults."""
        dt = DataTable(["Name", "Level"])
        assert dt.columns == ["Name", "Level"]
        assert dt.rows == []
        assert dt.selected_row is None
        assert dt.row_height == 28
        assert dt.header_height == 32

    def test_creation_with_rows(self) -> None:
        """DataTable stores initial rows."""
        dt = DataTable(["A", "B"], [["x", "y"], ["1", "2"]])
        assert len(dt.rows) == 2
        assert dt.rows[0] == ["x", "y"]

    def test_add_row(self) -> None:
        """add_row appends to the rows list."""
        dt = DataTable(["A"])
        dt.add_row(["value"])
        assert len(dt.rows) == 1
        assert dt.rows[0] == ["value"]

    def test_add_row_copies_data(self) -> None:
        """add_row makes a copy of the input list."""
        dt = DataTable(["A"])
        data = ["mutable"]
        dt.add_row(data)
        data[0] = "changed"
        assert dt.rows[0] == ["mutable"]

    def test_clear_rows(self) -> None:
        """clear_rows removes all rows and resets selection."""
        dt = DataTable(["A"], [["1"], ["2"]])
        dt._selected_row = 1
        dt.clear_rows()
        assert dt.rows == []
        assert dt.selected_row is None

    def test_rows_setter(self) -> None:
        """rows property setter replaces data."""
        dt = DataTable(["A"])
        dt.rows = [["x"], ["y"], ["z"]]
        assert len(dt.rows) == 3

    def test_rows_setter_clamps_selection(self) -> None:
        """rows setter clamps selected_row to new length."""
        dt = DataTable(["A"], [["1"], ["2"], ["3"]])
        dt._selected_row = 2
        dt.rows = [["x"]]  # only 1 row now
        assert dt.selected_row == 0

    def test_rows_setter_clears_on_empty(self) -> None:
        """rows setter with empty list clears selection."""
        dt = DataTable(["A"], [["1"]])
        dt._selected_row = 0
        dt.rows = []
        assert dt.selected_row is None

    def test_selected_row_clamped(self) -> None:
        """selected_row setter clamps to valid range."""
        dt = DataTable(["A"], [["1"], ["2"], ["3"]])
        dt.selected_row = 99
        assert dt.selected_row == 2
        dt.selected_row = -5
        assert dt.selected_row == 0

    def test_selected_row_none_on_empty(self) -> None:
        """selected_row becomes None on empty table."""
        dt = DataTable(["A"])
        dt.selected_row = 5
        assert dt.selected_row is None

    def test_preferred_size_auto_width(self) -> None:
        """Default width is 400 when no col_widths or width given."""
        dt = DataTable(["A", "B"])
        w, h = dt.get_preferred_size()
        assert w == 400
        assert h == 32  # header only, no rows

    def test_preferred_size_with_rows(self) -> None:
        """Height = header + rows × row_height."""
        dt = DataTable(["A"], [["1"], ["2"], ["3"]])
        _, h = dt.get_preferred_size()
        assert h == 32 + 3 * 28  # 116

    def test_preferred_size_explicit_col_widths(self) -> None:
        """Width = sum(col_widths) + 2*padding when col_widths given."""
        dt = DataTable(["A", "B"], col_widths=[100, 200])
        w, _ = dt.get_preferred_size()
        # padding = 6 (theme default)
        assert w == 100 + 200 + 2 * 6  # 312

    def test_preferred_size_explicit_width(self) -> None:
        """Explicit width overrides auto-distribution."""
        dt = DataTable(["A", "B"], width=500)
        w, _ = dt.get_preferred_size()
        assert w == 500

    def test_col_auto_distribution_even(self) -> None:
        """Auto col widths distribute evenly."""
        dt = DataTable(["A", "B", "C"])
        dt._computed_w = 306  # 306 - 2*6(padding) = 294 / 3 = 98 each
        widths = dt._effective_col_widths(6)
        assert len(widths) == 3
        assert sum(widths) == 294
        assert widths == [98, 98, 98]

    def test_col_auto_distribution_remainder(self) -> None:
        """Remainder pixels go to first columns."""
        dt = DataTable(["A", "B", "C"])
        dt._computed_w = 308  # 308 - 12 = 296 / 3 = 98 rem 2
        widths = dt._effective_col_widths(6)
        assert sum(widths) == 296
        assert widths == [99, 99, 98]

    def test_col_explicit_widths(self) -> None:
        """Explicit col_widths are returned as-is."""
        dt = DataTable(["A", "B"], col_widths=[100, 150])
        dt._computed_w = 500
        widths = dt._effective_col_widths(6)
        assert widths == [100, 150]

    def test_click_selects_row(self) -> None:
        """Clicking in the data area selects a row."""
        dt = DataTable(["A"], [["1"], ["2"], ["3"]], width=200, height=200)
        dt.compute_layout(0, 0, 200, 200)
        # Header is 32px. First data row starts at y=32.
        # Click in second data row: y = 32 + 28 + 5 = 65
        event = InputEvent(type="click", button="left", x=50, y=65)
        consumed = dt.on_event(event)
        assert consumed is True
        assert dt.selected_row == 1

    def test_click_header_no_select(self) -> None:
        """Clicking in the header area does not select a row."""
        dt = DataTable(["A"], [["1"], ["2"]], width=200, height=200)
        dt.compute_layout(0, 0, 200, 200)
        event = InputEvent(type="click", button="left", x=50, y=10)
        consumed = dt.on_event(event)
        assert consumed is True
        assert dt.selected_row is None

    def test_click_outside_not_consumed(self) -> None:
        """Click outside table bounds is not consumed."""
        dt = DataTable(["A"], [["1"]], width=100, height=100)
        dt.compute_layout(0, 0, 100, 100)
        event = InputEvent(type="click", button="left", x=500, y=500)
        consumed = dt.on_event(event)
        assert consumed is False

    def test_keyboard_down(self) -> None:
        """Down action selects first row from nothing selected."""
        dt = DataTable(["A"], [["1"], ["2"]])
        dt.compute_layout(0, 0, 200, 200)
        event = InputEvent(type="key", action="down")
        consumed = dt.on_event(event)
        assert consumed is True
        assert dt.selected_row == 0

    def test_keyboard_down_moves(self) -> None:
        """Down action moves selection down."""
        dt = DataTable(["A"], [["1"], ["2"], ["3"]])
        dt.compute_layout(0, 0, 200, 200)
        dt._selected_row = 0
        dt.on_event(InputEvent(type="key", action="down"))
        assert dt.selected_row == 1

    def test_keyboard_up(self) -> None:
        """Up action selects last row from nothing selected."""
        dt = DataTable(["A"], [["1"], ["2"], ["3"]])
        dt.compute_layout(0, 0, 200, 200)
        event = InputEvent(type="key", action="up")
        dt.on_event(event)
        assert dt.selected_row == 2

    def test_keyboard_up_moves(self) -> None:
        """Up action moves selection up."""
        dt = DataTable(["A"], [["1"], ["2"], ["3"]])
        dt.compute_layout(0, 0, 200, 200)
        dt._selected_row = 2
        dt.on_event(InputEvent(type="key", action="up"))
        assert dt.selected_row == 1

    def test_keyboard_down_clamps(self) -> None:
        """Down stops at last row."""
        dt = DataTable(["A"], [["1"], ["2"]])
        dt.compute_layout(0, 0, 200, 200)
        dt._selected_row = 1
        dt.on_event(InputEvent(type="key", action="down"))
        assert dt.selected_row == 1

    def test_keyboard_up_clamps(self) -> None:
        """Up stops at first row."""
        dt = DataTable(["A"], [["1"], ["2"]])
        dt.compute_layout(0, 0, 200, 200)
        dt._selected_row = 0
        dt.on_event(InputEvent(type="key", action="up"))
        assert dt.selected_row == 0

    def test_draw_header(
        self, root: _UIRoot, backend: MockBackend, game: Game,
    ) -> None:
        """DataTable draws header rect with correct color."""
        dt = DataTable(["Name", "Level"], width=400, height=200, anchor=Anchor.TOP_LEFT)
        root.add(dt)
        root._ensure_layout()
        root.draw()

        # At minimum: 1 header rect
        assert len(backend.rects) >= 1
        assert backend.rects[0]["color"] == game.theme.datatable_header_bg_color
        assert backend.rects[0]["height"] == 32

    def test_draw_header_text(
        self, root: _UIRoot, backend: MockBackend, game: Game,
    ) -> None:
        """DataTable draws header column text."""
        dt = DataTable(["Name", "Level"], width=400, height=200, anchor=Anchor.TOP_LEFT)
        root.add(dt)
        root._ensure_layout()
        root.draw()

        texts = [t["text"] for t in backend.texts]
        assert "Name" in texts
        assert "Level" in texts
        # Header text uses header text color
        for t in backend.texts:
            if t["text"] in ("Name", "Level"):
                assert t["color"] == game.theme.datatable_header_text_color

    def test_draw_alternating_rows(
        self, root: _UIRoot, backend: MockBackend, game: Game,
    ) -> None:
        """DataTable draws alternating row background colors."""
        dt = DataTable(["A"], [["r0"], ["r1"], ["r2"]],
                        width=400, height=200, anchor=Anchor.TOP_LEFT)
        root.add(dt)
        root._ensure_layout()
        root.draw()

        # Header rect (index 0) + 3 row rects (indices 1,2,3)
        assert len(backend.rects) >= 4
        assert backend.rects[1]["color"] == game.theme.datatable_row_bg_color  # even
        assert backend.rects[2]["color"] == game.theme.datatable_alt_row_bg_color  # odd
        assert backend.rects[3]["color"] == game.theme.datatable_row_bg_color  # even

    def test_draw_selection_highlight(
        self, root: _UIRoot, backend: MockBackend, game: Game,
    ) -> None:
        """Selected row gets a highlight rect."""
        dt = DataTable(["A"], [["r0"], ["r1"]],
                        width=400, height=200, anchor=Anchor.TOP_LEFT)
        dt._selected_row = 0
        root.add(dt)
        root._ensure_layout()
        root.draw()

        # Header + 2 row bg + 1 highlight = 4
        assert len(backend.rects) == 4
        sel_rects = [r for r in backend.rects if r["color"] == game.theme.selected_color]
        assert len(sel_rects) == 1

    def test_draw_cell_text(
        self, root: _UIRoot, backend: MockBackend,
    ) -> None:
        """DataTable draws cell text for each visible row."""
        dt = DataTable(["A", "B"], [["x", "y"], ["1", "2"]],
                        width=400, height=200, anchor=Anchor.TOP_LEFT)
        root.add(dt)
        root._ensure_layout()
        root.draw()

        # 2 header texts + 4 cell texts = 6
        texts = [t["text"] for t in backend.texts]
        assert texts.count("A") == 1  # header
        assert texts.count("B") == 1  # header
        assert "x" in texts
        assert "y" in texts
        assert "1" in texts
        assert "2" in texts

    def test_draw_empty_table(
        self, root: _UIRoot, backend: MockBackend,
    ) -> None:
        """DataTable with no rows draws only header."""
        dt = DataTable(["A", "B"], width=400, height=200, anchor=Anchor.TOP_LEFT)
        root.add(dt)
        root._ensure_layout()
        root.draw()

        # Only header rect + header texts
        assert len(backend.rects) == 1
        assert len(backend.texts) == 2

    def test_scroll_event(self) -> None:
        """Scroll adjusts _scroll_offset."""
        # 10 rows, only space for ~3 visible
        dt = DataTable(["A"], [[f"r{i}"] for i in range(10)], width=200, height=32 + 3 * 28)
        dt.compute_layout(0, 0, 200, 32 + 3 * 28)
        event = InputEvent(type="scroll", x=100, y=50, dy=-1)
        consumed = dt.on_event(event)
        assert consumed is True
        assert dt._scroll_offset == 1

    def test_theme_integration(self) -> None:
        """Theme has all datatable properties."""
        theme = Theme()
        assert theme.datatable_header_bg_color == (55, 55, 75, 255)
        assert theme.datatable_header_text_color == (240, 240, 240, 255)
        assert theme.datatable_row_bg_color == (35, 35, 45, 200)
        assert theme.datatable_alt_row_bg_color == (42, 42, 55, 200)

    def test_resolve_datatable_style(self) -> None:
        """resolve_datatable_style returns correct defaults."""
        theme = Theme()
        resolved = theme.resolve_datatable_style(None)
        assert resolved.padding == 6
        assert resolved.font == "serif"
        assert resolved.font_size == 24
