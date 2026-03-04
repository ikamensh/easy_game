"""Menus & Navigation Demo
=========================

Runnable version of the menu tutorial.  Five screens demonstrating
the full scene-stack navigation model:

*   **TitleScreen** — title + Play / Settings / Quit buttons
*   **SettingsOverlay** — transparent overlay with Back button (ESC dismisses)
*   **GameScreen** — the "game" with hotkeys (I = Inventory, ESC = Pause)
*   **PauseMenu** — transparent pause overlay with Resume / Quit-to-Title
*   **InventoryScreen** — transparent overlay showing inventory stub

Run from the project root::

    python tutorials/menus/menu_demo.py

"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — ensures ``import saga2d`` works regardless of cwd.
# ---------------------------------------------------------------------------
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from saga2d import (  # noqa: E402
    Anchor,
    Button,
    Game,
    InputEvent,
    Label,
    Layout,
    Panel,
    Scene,
    Style,
    Theme,
)


# ======================================================================
# Colour palette
# ======================================================================

BG_TITLE = (20, 24, 35, 255)       # dark blue-grey (title screen)
BG_GAME = (10, 60, 10, 255)        # dark green (game world)
TITLE_COLOR = (255, 220, 80, 255)  # gold
HINT_COLOR = (180, 180, 190, 255)  # muted grey


# ======================================================================
# TitleScreen
# ======================================================================

class TitleScreen(Scene):
    """Title screen — entry point of the game."""

    background_color = BG_TITLE

    def on_enter(self) -> None:
        panel = Panel(
            layout=Layout.VERTICAL,
            spacing=20,
            anchor=Anchor.CENTER,
            style=Style(background_color=(30, 35, 50, 220), padding=40),
            children=[
                Label("My Game", font_size=52, text_color=TITLE_COLOR),
                Label("Menus & Navigation Demo", font_size=18, text_color=HINT_COLOR),
                Button("Play", on_click=self._play),
                Button("Settings", on_click=self._settings),
                Button("Quit", on_click=self._quit),
            ],
        )
        self.ui.add(panel)

    def _play(self) -> None:
        self.game.replace(GameScreen())

    def _settings(self) -> None:
        self.game.push(SettingsOverlay())

    def _quit(self) -> None:
        self.game.quit()

    def handle_input(self, event: InputEvent) -> bool:
        if event.action == "confirm":
            self._play()
            return True
        if event.action == "cancel":
            self._quit()
            return True
        return False


# ======================================================================
# SettingsOverlay
# ======================================================================

class SettingsOverlay(Scene):
    """Settings panel — transparent overlay on top of the title screen."""

    transparent = True
    pause_below = True
    pop_on_cancel = True

    def on_enter(self) -> None:
        panel = Panel(
            anchor=Anchor.CENTER,
            layout=Layout.VERTICAL,
            spacing=16,
            style=Style(background_color=(0, 0, 0, 180), padding=40),
            children=[
                Label("Settings", font_size=40),
                Label("(nothing here yet)", font_size=18, text_color=HINT_COLOR),
                Button("Back", on_click=lambda: self.game.pop()),
            ],
        )
        self.ui.add(panel)


# ======================================================================
# GameScreen
# ======================================================================

class GameScreen(Scene):
    """The main game screen with hotkey bindings."""

    background_color = BG_GAME

    def on_enter(self) -> None:
        self.bind_key("cancel", lambda: self.game.push(PauseMenu()))
        self.bind_key("i", lambda: self.game.push(InventoryScreen()))

        panel = Panel(
            layout=Layout.VERTICAL,
            spacing=12,
            anchor=Anchor.CENTER,
            children=[
                Label("GAME WORLD", font_size=36, text_color=TITLE_COLOR),
                Label("You are playing the game.", font_size=20),
            ],
        )
        self.ui.add(panel)

        self.ui.add(Label(
            "I = Inventory   ESC = Pause",
            font_size=16,
            anchor=Anchor.BOTTOM_LEFT,
            margin=12,
            text_color=HINT_COLOR,
        ))


# ======================================================================
# PauseMenu
# ======================================================================

class PauseMenu(Scene):
    """Pause overlay — transparent, pauses the game below."""

    transparent = True
    pause_below = True
    pop_on_cancel = True

    def on_enter(self) -> None:
        menu = Panel(
            anchor=Anchor.CENTER,
            layout=Layout.VERTICAL,
            spacing=16,
            style=Style(background_color=(0, 0, 0, 160), padding=40),
            children=[
                Label("PAUSED", font_size=48),
                Button("Resume", on_click=lambda: self.game.pop()),
                Button("Quit to Title", on_click=self._quit_to_title),
            ],
        )
        self.ui.add(menu)

    def _quit_to_title(self) -> None:
        self.game.clear_and_push(TitleScreen())


# ======================================================================
# InventoryScreen
# ======================================================================

class InventoryScreen(Scene):
    """Inventory overlay — transparent, pauses below."""

    transparent = True
    pause_below = True
    pop_on_cancel = True

    def on_enter(self) -> None:
        panel = Panel(
            anchor=Anchor.CENTER,
            layout=Layout.VERTICAL,
            spacing=16,
            style=Style(background_color=(10, 10, 30, 200), padding=40),
            children=[
                Label("Inventory", font_size=40),
                Label("(empty)", font_size=18, text_color=HINT_COLOR),
                Button("Close", on_click=lambda: self.game.pop()),
            ],
        )
        self.ui.add(panel)


# ======================================================================
# Main
# ======================================================================

def main() -> None:
    """Create the game and run the title screen."""
    game = Game(
        "Menus & Navigation Demo",
        resolution=(800, 600),
        fullscreen=False,
        backend="pyglet",
    )
    game.theme = Theme(
        font="serif",
        font_size=24,
        text_color=(220, 220, 230, 255),
        panel_background_color=(30, 35, 50, 220),
        panel_padding=16,
        button_background_color=(50, 55, 80, 255),
        button_hover_color=(70, 80, 120, 255),
        button_press_color=(35, 40, 60, 255),
        button_text_color=(220, 220, 230, 255),
        button_padding=14,
        button_font_size=26,
        button_min_width=200,
    )
    game.run(TitleScreen())


if __name__ == "__main__":
    main()
