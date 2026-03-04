#!/usr/bin/env python3
"""UI Widget Gallery — render every widget type to PNG images.

Generates a gallery of screenshots showing all UI widgets with the current
theme, including forced states (hover, pressed, disabled) for interactive
components.

Run from the project root::

    python -m tests.screenshot.gallery

Images are saved to ``/tmp/gallery/``.  Open the directory to visually
inspect every widget type.

Requires pyglet with a display (GPU context).  On headless machines the
script exits cleanly with a message.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _display_available() -> bool:
    """Return True if pyglet can obtain a screen for rendering."""
    try:
        import pyglet  # noqa: F401

        display = pyglet.display.get_display()
        display.get_default_screen()
        return True
    except (ImportError, IndexError):
        return False


from saga2d import Game, Scene
from saga2d.ui import (
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

from tests.screenshot.harness import render_scene

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

GALLERY_DIR = Path("/tmp/gallery")


def _ensure_gallery_dir() -> Path:
    """Create and return the gallery output directory."""
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    return GALLERY_DIR


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_RES = (640, 480)  # Wider resolution for gallery panels
_RES_WIDE = (800, 480)  # Extra-wide for DataTable


# ---------------------------------------------------------------------------
# 1. Panel with Label + Buttons (normal, hover, pressed, disabled)
# ---------------------------------------------------------------------------

def gallery_panel_buttons() -> None:
    """Panel with a title Label and four Buttons in different states."""

    class ButtonStatesScene(Scene):
        def on_enter(self) -> None:
            panel = Panel(
                anchor=Anchor.CENTER,
                layout=Layout.VERTICAL,
                spacing=10,
                style=Style(padding=20),
            )
            panel.add(Label(
                "Button States",
                style=Style(font_size=28, text_color=(255, 220, 100, 255)),
            ))
            panel.add(Label(
                "All four button visual states:",
                style=Style(font_size=16),
            ))

            # Row of buttons in different states
            row = Panel(
                layout=Layout.HORIZONTAL,
                spacing=12,
                style=Style(padding=0, background_color=(0, 0, 0, 0)),
            )

            btn_normal = Button("Normal", style=Style(font_size=18, padding=10))
            # Normal state is the default — nothing to force.

            btn_hover = Button("Hovered", style=Style(font_size=18, padding=10))
            btn_hover._state = "hovered"

            btn_pressed = Button("Pressed", style=Style(font_size=18, padding=10))
            btn_pressed._state = "pressed"

            btn_disabled = Button("Disabled", style=Style(font_size=18, padding=10))
            btn_disabled.enabled = False

            row.add(btn_normal)
            row.add(btn_hover)
            row.add(btn_pressed)
            row.add(btn_disabled)

            panel.add(row)
            self.ui.add(panel)

    def setup(game: Game) -> None:
        game.push(ButtonStatesScene())

    image = render_scene(setup, tick_count=1, resolution=_RES)
    image.save(_ensure_gallery_dir() / "01_panel_buttons.png")
    print("  ✓ 01_panel_buttons.png")


# ---------------------------------------------------------------------------
# 2. ProgressBar (0%, 50%, 100%)
# ---------------------------------------------------------------------------

def gallery_progress_bars() -> None:
    """Three ProgressBars at 0%, 50%, and 100%.

    Demonstrates:
    - Blue fill color (not green)
    - Dark blue background track
    - Progressive fill from 0% to 100%
    """

    class BarScene(Scene):
        def on_enter(self) -> None:
            panel = Panel(
                anchor=Anchor.CENTER,
                layout=Layout.VERTICAL,
                spacing=12,
                style=Style(padding=20),
            )
            panel.add(Label(
                "Progress Bars",
                style=Style(font_size=28, text_color=(255, 220, 100, 255)),
            ))
            panel.add(Label(
                "Blue fill on dark blue track:",
                style=Style(font_size=16),
            ))

            for pct in (0, 50, 100):
                row = Panel(
                    layout=Layout.HORIZONTAL,
                    spacing=10,
                    style=Style(padding=0, background_color=(0, 0, 0, 0)),
                )
                row.add(Label(f"{pct:>3d}%", style=Style(font_size=18)))
                row.add(ProgressBar(
                    value=pct,
                    max_value=100,
                    width=350,
                    height=28,
                ))
                panel.add(row)

            self.ui.add(panel)

    def setup(game: Game) -> None:
        game.push(BarScene())

    image = render_scene(setup, tick_count=1, resolution=_RES)
    image.save(_ensure_gallery_dir() / "02_progress_bars.png")
    print("  ✓ 02_progress_bars.png")


# ---------------------------------------------------------------------------
# 3. List with items and selection highlight
# ---------------------------------------------------------------------------

def gallery_list() -> None:
    """List widget with several items and one selected.

    Demonstrates:
    - Alternating row backgrounds (odd rows have subtle tint)
    - Selection highlight (row 3 selected)
    - Visual contrast between states
    """

    class ListScene(Scene):
        def on_enter(self) -> None:
            panel = Panel(
                anchor=Anchor.CENTER,
                layout=Layout.VERTICAL,
                spacing=10,
                style=Style(padding=20),
            )
            panel.add(Label(
                "List Widget",
                style=Style(font_size=28, text_color=(255, 220, 100, 255)),
            ))
            panel.add(Label(
                "Alternating rows + selection (row 3):",
                style=Style(font_size=16),
            ))

            lst = List(
                [
                    "Slot 1 — Elven Forest",
                    "Slot 2 — Dwarven Mines",
                    "Slot 3 — Dragon Keep",
                    "Slot 4 — Haunted Marsh",
                    "Slot 5 — Crystal Caves",
                    "Slot 6 — Shadow Tower",
                ],
                width=320,
                item_height=30,
            )
            lst.selected_index = 2  # "Dragon Keep"
            panel.add(lst)
            self.ui.add(panel)

    def setup(game: Game) -> None:
        game.push(ListScene())

    image = render_scene(setup, tick_count=1, resolution=_RES)
    image.save(_ensure_gallery_dir() / "03_list.png")
    print("  ✓ 03_list.png")


# ---------------------------------------------------------------------------
# 4. Grid with cells and selection
# ---------------------------------------------------------------------------

def gallery_grid() -> None:
    """4x3 Grid with Labels in some cells and cell (2,1) selected."""

    class GridScene(Scene):
        def on_enter(self) -> None:
            panel = Panel(
                anchor=Anchor.CENTER,
                layout=Layout.VERTICAL,
                spacing=10,
                style=Style(padding=20),
            )
            panel.add(Label(
                "Grid Widget",
                style=Style(font_size=28, text_color=(255, 220, 100, 255)),
            ))
            panel.add(Label(
                "Inventory grid — cell (2,1) selected:",
                style=Style(font_size=16),
            ))

            grid = Grid(
                4, 3,
                cell_size=(72, 72),
                spacing=4,
                style=Style(padding=8),
            )
            # Populate some cells with item abbreviations
            items = {
                (0, 0): "Sword",
                (1, 0): "Shield",
                (2, 0): "Bow",
                (3, 0): "Staff",
                (0, 1): "HpPot",
                (1, 1): "MpPot",
                (2, 1): "Elixir",
                (0, 2): "Ring",
                (2, 2): "Scroll",
            }
            for (c, r), name in items.items():
                grid.set_cell(c, r, Label(name, style=Style(font_size=12)))

            grid.selected = (2, 1)  # "Elixir"
            panel.add(grid)
            self.ui.add(panel)

    def setup(game: Game) -> None:
        game.push(GridScene())

    image = render_scene(setup, tick_count=1, resolution=_RES)
    image.save(_ensure_gallery_dir() / "04_grid.png")
    print("  ✓ 04_grid.png")


# ---------------------------------------------------------------------------
# 5. TextBox with wrapped text
# ---------------------------------------------------------------------------

def gallery_textbox() -> None:
    """TextBox with a long paragraph, word-wrapped, fully revealed."""

    class TextScene(Scene):
        def on_enter(self) -> None:
            panel = Panel(
                anchor=Anchor.CENTER,
                layout=Layout.VERTICAL,
                spacing=10,
                style=Style(padding=20),
            )
            panel.add(Label(
                "TextBox Widget",
                style=Style(font_size=28, text_color=(255, 220, 100, 255)),
            ))

            text = TextBox(
                "The ancient fortress loomed ahead, its crumbling towers "
                "silhouetted against the crimson sky. Our party pressed "
                "forward through the overgrown courtyard, weapons drawn. "
                "The air was thick with the scent of decay and forgotten "
                "magic. Somewhere in the depths below, the artifact awaited.",
                width=450,
                style=Style(font_size=16),
            )
            panel.add(text)
            self.ui.add(panel)

    def setup(game: Game) -> None:
        game.push(TextScene())

    image = render_scene(setup, tick_count=1, resolution=_RES)
    image.save(_ensure_gallery_dir() / "05_textbox.png")
    print("  ✓ 05_textbox.png")


# ---------------------------------------------------------------------------
# 6. TabGroup with multiple tabs
# ---------------------------------------------------------------------------

def gallery_tabgroup() -> None:
    """TabGroup with 3 tabs — Stats (active), Skills, and Items.

    Demonstrates:
    - Active tab background (Stats - lighter blue)
    - Inactive tab backgrounds (Skills, Items - darker blue)
    - Clear visual distinction between states
    """

    class TabScene(Scene):
        def on_enter(self) -> None:
            # Stats tab content
            stats_panel = Panel(
                layout=Layout.VERTICAL,
                spacing=6,
                width=400,
                height=140,
                style=Style(padding=12),
            )
            stats_panel.add(Label("STR: 18  (+4)", style=Style(font_size=16)))
            stats_panel.add(Label("DEX: 14  (+2)", style=Style(font_size=16)))
            stats_panel.add(Label("CON: 16  (+3)", style=Style(font_size=16)))
            stats_panel.add(Label("INT: 12  (+1)", style=Style(font_size=16)))
            stats_panel.add(Label("WIS: 10  (+0)", style=Style(font_size=16)))

            # Skills tab content
            skills_panel = Panel(
                layout=Layout.VERTICAL,
                spacing=6,
                width=400,
                height=140,
                style=Style(padding=12),
            )
            skills_panel.add(Label("Fireball Lv.3", style=Style(font_size=16)))
            skills_panel.add(Label("Heal Lv.2", style=Style(font_size=16)))
            skills_panel.add(Label("Lightning Bolt Lv.1", style=Style(font_size=16)))
            skills_panel.add(Label("Shield Wall Lv.4", style=Style(font_size=16)))

            # Items tab content
            items_panel = Panel(
                layout=Layout.VERTICAL,
                spacing=6,
                width=400,
                height=140,
                style=Style(padding=12),
            )
            items_panel.add(Label("Health Potion x5", style=Style(font_size=16)))
            items_panel.add(Label("Mana Elixir x2", style=Style(font_size=16)))
            items_panel.add(Label("Scroll of Recall x1", style=Style(font_size=16)))

            tabs = TabGroup(
                {"Stats": stats_panel, "Skills": skills_panel, "Items": items_panel},
                width=420,
                height=180,
                anchor=Anchor.CENTER,
            )
            self.ui.add(tabs)

    def setup(game: Game) -> None:
        game.push(TabScene())

    image = render_scene(setup, tick_count=1, resolution=_RES)
    image.save(_ensure_gallery_dir() / "06_tabgroup.png")
    print("  ✓ 06_tabgroup.png")


# ---------------------------------------------------------------------------
# 7. DataTable with header and rows
# ---------------------------------------------------------------------------

def gallery_datatable() -> None:
    """DataTable with 4 columns, 6 rows, and row 2 selected.

    Demonstrates:
    - Header row with distinct background color
    - Alternating row backgrounds (even/odd)
    - Selection highlight (row 2 = Thrall)
    - Column alignment
    """

    class TableScene(Scene):
        def on_enter(self) -> None:
            panel = Panel(
                anchor=Anchor.CENTER,
                layout=Layout.VERTICAL,
                spacing=10,
                style=Style(padding=20),
            )
            panel.add(Label(
                "DataTable Widget",
                style=Style(font_size=28, text_color=(255, 220, 100, 255)),
            ))
            panel.add(Label(
                "Header + alternating rows + selection:",
                style=Style(font_size=16),
            ))

            dt = DataTable(
                ["Name", "Class", "Level", "HP"],
                [
                    ["Arthas", "Paladin", "10", "320"],
                    ["Jaina", "Mage", "12", "180"],
                    ["Thrall", "Shaman", "15", "290"],
                    ["Sylvanas", "Ranger", "18", "240"],
                    ["Uther", "Cleric", "9", "260"],
                    ["Illidan", "Demon Hunter", "20", "350"],
                ],
                width=500,
            )
            dt.selected_row = 2  # Thrall
            panel.add(dt)
            self.ui.add(panel)

    def setup(game: Game) -> None:
        game.push(TableScene())

    image = render_scene(setup, tick_count=1, resolution=_RES_WIDE)
    image.save(_ensure_gallery_dir() / "07_datatable.png")
    print("  ✓ 07_datatable.png")


# ---------------------------------------------------------------------------
# 8. Tooltip visible
# ---------------------------------------------------------------------------

def gallery_tooltip() -> None:
    """Tooltip that has passed its delay and is fully visible."""

    class TipScene(Scene):
        def on_enter(self) -> None:
            # Background context — a button grid and some labels
            panel = Panel(
                anchor=Anchor.CENTER,
                layout=Layout.VERTICAL,
                spacing=10,
                style=Style(padding=20),
            )
            panel.add(Label(
                "Tooltip Widget",
                style=Style(font_size=28, text_color=(255, 220, 100, 255)),
            ))
            panel.add(Label(
                "Hover over items for details",
                style=Style(font_size=16),
            ))

            row = Panel(
                layout=Layout.HORIZONTAL,
                spacing=12,
                style=Style(padding=0, background_color=(0, 0, 0, 0)),
            )
            row.add(Button("Inventory", style=Style(font_size=16, padding=10)))
            row.add(Button("Character", style=Style(font_size=16, padding=10)))
            row.add(Button("Map", style=Style(font_size=16, padding=10)))
            panel.add(row)
            self.ui.add(panel)

            # Tooltip — added last so it draws on top
            self._tooltip = Tooltip(
                "Sword of Flames (+12 ATK, +5 Fire DMG)",
                delay=0.3,
                style=Style(font_size=16),
            )
            self.ui.add(self._tooltip)
            self._tooltip.show(180, 200)

    def setup(game: Game) -> None:
        game.push(TipScene())
        # Advance 30 frames (0.5s) to pass the 0.3s tooltip delay.
        for _ in range(30):
            game.tick(dt=1.0 / 60.0)

    image = render_scene(setup, tick_count=1, resolution=_RES)
    image.save(_ensure_gallery_dir() / "08_tooltip.png")
    print("  ✓ 08_tooltip.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

_GALLERY_FUNCS = [
    ("Panel + Button States", gallery_panel_buttons),
    ("Progress Bars", gallery_progress_bars),
    ("List", gallery_list),
    ("Grid", gallery_grid),
    ("TextBox", gallery_textbox),
    ("TabGroup", gallery_tabgroup),
    ("DataTable", gallery_datatable),
    ("Tooltip", gallery_tooltip),
]


def main() -> None:
    """Generate all gallery images."""
    if not _display_available():
        print(
            "No display available — pyglet needs a GPU context to render.\n"
            "Run this script on a machine with a display (not headless CI)."
        )
        sys.exit(0)

    out = _ensure_gallery_dir()
    print(f"Generating UI widget gallery → {out}/\n")

    failed: list[str] = []
    for name, func in _GALLERY_FUNCS:
        try:
            func()
        except Exception as exc:
            import traceback

            print(f"  ✗ {name}: {exc}")
            traceback.print_exc()
            failed.append(name)

    print()
    total = len(_GALLERY_FUNCS)
    ok = total - len(failed)
    print(f"Done: {ok}/{total} images generated in {out}/")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
