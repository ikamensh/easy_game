"""Screenshot regression tests for Stage 9 UI widgets.

Run from the project root::

    pytest tests/screenshot/test_widget_screenshots.py -v

Requires pyglet (GPU context).  Excluded from the normal ``pytest tests/``
run by ``collect_ignore`` in ``tests/conftest.py``.

Each test creates a Scene subclass that builds a UI tree in ``on_enter()``,
triggers any needed state (selection, tooltip show, etc.), renders one or
more frames, and compares against a golden PNG.  Golden images are
auto-created on first run.
"""

from __future__ import annotations

import pytest

from easygame import Game, Scene
from easygame.ui import (
    Anchor,
    Button,
    DataTable,
    Grid,
    Label,
    Layout,
    List,
    Panel,
    ProgressBar,
    Style,
    TabGroup,
    TextBox,
    Tooltip,
)

from tests.screenshot.harness import assert_screenshot, render_scene

_RESOLUTION = (480, 360)


# ---------------------------------------------------------------------------
# 1. ProgressBar at 75%
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_progress_bar() -> None:
    """A ProgressBar at 75% value centered on screen.

    Shows a background track and a green filled bar occupying three-quarters
    of the total width.  A label above identifies the bar.
    """

    class BarScene(Scene):
        def on_enter(self) -> None:
            panel = Panel(
                anchor=Anchor.CENTER,
                layout=Layout.VERTICAL,
                spacing=8,
            )
            panel.add(Label("Health", style=Style(font_size=20)))
            panel.add(ProgressBar(
                value=75,
                max_value=100,
                width=300,
                height=28,
            ))
            self.ui.add(panel)

    def setup(game: Game) -> None:
        game.push(BarScene())

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "widget_progress_bar")


# ---------------------------------------------------------------------------
# 2. TextBox with wrapped multi-line text (instant reveal)
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_textbox_instant() -> None:
    """TextBox displaying wrapped multi-line text, all revealed instantly.

    The text is long enough to wrap into multiple lines within the given
    width.  A panel provides a visible background behind the text.
    """

    class TextScene(Scene):
        def on_enter(self) -> None:
            panel = Panel(
                anchor=Anchor.CENTER,
                layout=Layout.VERTICAL,
                spacing=6,
                style=Style(padding=12),
            )
            panel.add(Label("Journal Entry", style=Style(font_size=22)))
            panel.add(TextBox(
                "The ancient fortress loomed ahead, its crumbling towers "
                "silhouetted against the crimson sky. Our party pressed "
                "forward through the overgrown courtyard, weapons drawn.",
                width=350,
                style=Style(font_size=16),
            ))
            self.ui.add(panel)

    def setup(game: Game) -> None:
        game.push(TextScene())

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "widget_textbox_instant")


# ---------------------------------------------------------------------------
# 3. List with 5 items and selection at index 2
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_list_with_selection() -> None:
    """List widget with 5 items, the third item (index 2) selected.

    The selected item should be highlighted with the theme's selected_color.
    All items should be visible as text labels within the list bounds.
    """

    class ListScene(Scene):
        def on_enter(self) -> None:
            panel = Panel(
                anchor=Anchor.CENTER,
                layout=Layout.VERTICAL,
                spacing=8,
            )
            panel.add(Label("Save Files", style=Style(font_size=20)))
            lst = List(
                ["Slot 1 - Castle", "Slot 2 - Forest", "Slot 3 - Dungeon",
                 "Slot 4 - Village", "Slot 5 - Empty"],
                width=280,
                item_height=28,
            )
            lst.selected_index = 2
            panel.add(lst)
            self.ui.add(panel)

    def setup(game: Game) -> None:
        game.push(ListScene())

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "widget_list_with_selection")


# ---------------------------------------------------------------------------
# 4. Grid with cells containing Labels and a selection
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_grid_with_cells() -> None:
    """3x3 Grid with Labels in several cells, cell (1,1) selected.

    Some cells are empty, some contain short labels.  The selected cell
    is highlighted with the theme's selected_color overlay.
    """

    class GridScene(Scene):
        def on_enter(self) -> None:
            panel = Panel(
                anchor=Anchor.CENTER,
                layout=Layout.VERTICAL,
                spacing=8,
            )
            panel.add(Label("Inventory", style=Style(font_size=20)))
            grid = Grid(
                3, 3,
                cell_size=(64, 64),
                spacing=4,
                style=Style(padding=6),
            )
            # Place labels in some cells.
            grid.set_cell(0, 0, Label("Sw", style=Style(font_size=14)))
            grid.set_cell(1, 0, Label("Sh", style=Style(font_size=14)))
            grid.set_cell(2, 0, Label("Bw", style=Style(font_size=14)))
            grid.set_cell(0, 1, Label("Hp", style=Style(font_size=14)))
            grid.set_cell(1, 1, Label("Mp", style=Style(font_size=14)))
            # (2,1), (0,2), (1,2), (2,2) are empty
            grid.selected = (1, 1)
            panel.add(grid)
            self.ui.add(panel)

    def setup(game: Game) -> None:
        game.push(GridScene())

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "widget_grid_with_cells")


# ---------------------------------------------------------------------------
# 5. Tooltip visible (past its delay)
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_tooltip_visible() -> None:
    """Tooltip that has passed its delay and is now visible.

    The test calls show() and then advances several frames past the delay
    so the tooltip's internal _visible_now flag is True.  The tooltip
    should appear as a small dark rectangle with light text near the
    specified position.
    """

    class TipScene(Scene):
        def on_enter(self) -> None:
            # Add a label so the scene is not completely empty.
            self.ui.add(Label(
                "Hover over items for details",
                anchor=Anchor.TOP,
                margin=20,
                style=Style(font_size=16),
            ))
            self._tooltip = Tooltip(
                "Sword of Flames (+12 ATK)",
                delay=0.3,
                style=Style(font_size=14),
            )
            self.ui.add(self._tooltip)
            # Start the delay timer at the desired position.
            self._tooltip.show(150, 180)

    def setup(game: Game) -> None:
        game.push(TipScene())
        # Advance enough frames to pass the 0.3 s delay.
        # 30 ticks × (1/60) = 0.5 s > 0.3 s delay.
        for _ in range(30):
            game.tick(dt=1.0 / 60.0)

    # tick_count=1 renders one more frame with the tooltip visible.
    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "widget_tooltip_visible")


# ---------------------------------------------------------------------------
# 6. TabGroup with 3 tabs
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_tabgroup() -> None:
    """TabGroup with 3 tabs, the first tab active by default.

    Tab headers are drawn as a horizontal row.  The active tab has a
    distinct background colour.  Only the first tab's content panel
    is visible.
    """

    class TabScene(Scene):
        def on_enter(self) -> None:
            stats_panel = Panel(
                layout=Layout.VERTICAL,
                spacing=6,
                width=300,
                height=120,
                style=Style(padding=10),
            )
            stats_panel.add(Label("STR: 18", style=Style(font_size=16)))
            stats_panel.add(Label("DEX: 14", style=Style(font_size=16)))
            stats_panel.add(Label("INT: 12", style=Style(font_size=16)))

            skills_panel = Panel(
                layout=Layout.VERTICAL,
                spacing=6,
                width=300,
                height=120,
                style=Style(padding=10),
            )
            skills_panel.add(Label("Fireball Lv.3", style=Style(font_size=16)))
            skills_panel.add(Label("Heal Lv.2", style=Style(font_size=16)))

            items_panel = Panel(
                layout=Layout.VERTICAL,
                spacing=6,
                width=300,
                height=120,
                style=Style(padding=10),
            )
            items_panel.add(Label("Potion x5", style=Style(font_size=16)))
            items_panel.add(Label("Elixir x2", style=Style(font_size=16)))

            tabs = TabGroup(
                {"Stats": stats_panel, "Skills": skills_panel, "Items": items_panel},
                width=320,
                height=160,
                anchor=Anchor.CENTER,
            )
            self.ui.add(tabs)

    def setup(game: Game) -> None:
        game.push(TabScene())

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "widget_tabgroup")


# ---------------------------------------------------------------------------
# 7. DataTable with 3 columns and 5 rows
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_datatable() -> None:
    """DataTable with 3 columns and 5 data rows, row 1 selected.

    The header row should be drawn in the theme's header bg colour.
    Data rows should alternate between two background colours.
    The selected row should have a highlight overlay.
    """

    class TableScene(Scene):
        def on_enter(self) -> None:
            dt = DataTable(
                ["Unit", "Class", "Level"],
                [
                    ["Arthas", "Paladin", "10"],
                    ["Jaina", "Mage", "12"],
                    ["Thrall", "Shaman", "15"],
                    ["Sylvanas", "Ranger", "18"],
                    ["Uther", "Cleric", "9"],
                ],
                width=360,
                anchor=Anchor.CENTER,
            )
            dt.selected_row = 1
            self.ui.add(dt)

    def setup(game: Game) -> None:
        game.push(TableScene())

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "widget_datatable")


# ---------------------------------------------------------------------------
# 8. Combined dialog — RPG-style dialog box
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_combined_dialog() -> None:
    """RPG dialog box: Panel with a portrait ImageBox, TextBox with
    typewriter (skipped to complete), and two action Buttons.

    This simulates a classic RPG dialog scene — a character portrait on
    the left, dialog text on the right, and "Accept" / "Decline" buttons
    below.  The TextBox typewriter is skipped so all text is visible.

    Since ImageBox requires a loaded asset, we create a solid-color image
    via the backend and patch the asset lookup.
    """

    class DialogScene(Scene):
        def on_enter(self) -> None:
            # -- Outer dialog panel (bottom-anchored, full width) ----------
            dialog = Panel(
                anchor=Anchor.BOTTOM,
                margin=10,
                layout=Layout.VERTICAL,
                spacing=8,
                width=460,
                style=Style(
                    background_color=(25, 25, 40, 240),
                    padding=12,
                ),
            )

            # -- Top row: portrait placeholder + text ----------------------
            top_row = Panel(
                layout=Layout.HORIZONTAL,
                spacing=10,
                style=Style(padding=0, background_color=(0, 0, 0, 0)),
            )

            # Use a small coloured label as a portrait placeholder,
            # since we don't have real image assets in the test.
            portrait_panel = Panel(
                width=64,
                height=64,
                style=Style(
                    background_color=(80, 60, 100, 255),
                    padding=4,
                ),
            )
            portrait_panel.add(Label("NPC", style=Style(font_size=14)))
            top_row.add(portrait_panel)

            text = TextBox(
                "Greetings, adventurer! I have a quest for you. "
                "The goblins in the eastern caves have stolen our "
                "sacred relic. Will you retrieve it for us?",
                typewriter_speed=100,
                width=350,
                style=Style(font_size=15),
            )
            # Skip the typewriter so all text is visible for the screenshot.
            text.skip()
            top_row.add(text)

            dialog.add(top_row)

            # -- Bottom row: action buttons --------------------------------
            button_row = Panel(
                layout=Layout.HORIZONTAL,
                spacing=12,
                style=Style(padding=0, background_color=(0, 0, 0, 0)),
            )
            button_row.add(Button(
                "Accept",
                style=Style(font_size=16, padding=8),
            ))
            button_row.add(Button(
                "Decline",
                style=Style(font_size=16, padding=8),
            ))
            dialog.add(button_row)

            self.ui.add(dialog)

    def setup(game: Game) -> None:
        game.push(DialogScene())

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "widget_combined_dialog")
