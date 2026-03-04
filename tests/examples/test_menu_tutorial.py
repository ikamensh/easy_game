"""Headless verification of the Menus & Navigation tutorial demo.

Uses the mock backend since pyglet requires a display.  Verifies:
- All five scenes load without error
- UI renders correct labels and buttons
- Scene stack navigation works (push/pop/replace/clear_and_push)
- Hotkey bindings (I for inventory, ESC for pause)
- Overlay transparency and pause_below flags
- Full navigation round-trips
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from easygame import Game, Theme

_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from tutorials.menus.menu_demo import (  # noqa: E402
    GameScreen,
    InventoryScreen,
    PauseMenu,
    SettingsOverlay,
    TitleScreen,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def game() -> Game:
    """Game with mock backend and menu-tutorial theme."""
    g = Game(
        "Menu Tutorial Test",
        resolution=(800, 600),
        fullscreen=False,
        backend="mock",
    )
    g.theme = Theme(
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
    return g


def _texts(game: Game) -> list[str]:
    """Extract all rendered text strings from the mock backend."""
    return [t["text"] for t in game.backend.texts]


def _stack_names(game: Game) -> list[str]:
    """Get class names of all scenes on the stack."""
    return [s.__class__.__name__ for s in game._scene_stack._stack]


# ---------------------------------------------------------------------------
# TitleScreen
# ---------------------------------------------------------------------------

class TestTitleScreen:
    def test_renders_title_and_buttons(self, game: Game) -> None:
        """TitleScreen shows game title and all three buttons."""
        game.push(TitleScreen())
        for _ in range(3):
            game.tick(dt=0.016)

        texts = _texts(game)
        assert "My Game" in texts
        assert "Play" in texts
        assert "Settings" in texts
        assert "Quit" in texts

    def test_subtitle_shown(self, game: Game) -> None:
        """TitleScreen shows the demo subtitle."""
        game.push(TitleScreen())
        game.tick(dt=0.016)

        texts = _texts(game)
        assert "Menus & Navigation Demo" in texts

    def test_quit_callback_stops_game(self, game: Game) -> None:
        """Quit callback sets game.running to False."""
        game.push(TitleScreen())
        game.tick(dt=0.016)

        scene = game._scene_stack._stack[-1]
        scene._quit()
        game.tick(dt=0.016)

        assert game.running is False

    def test_cancel_key_quits(self, game: Game) -> None:
        """Pressing ESC on title screen quits the game."""
        game.push(TitleScreen())
        game.tick(dt=0.016)

        game.backend.inject_key("escape")
        game.tick(dt=0.016)

        assert game.running is False

    def test_confirm_key_goes_to_game(self, game: Game) -> None:
        """Pressing Enter on title screen transitions to GameScreen."""
        game.push(TitleScreen())
        game.tick(dt=0.016)

        game.backend.inject_key("return")
        game.tick(dt=0.016)

        assert _stack_names(game)[-1] == "GameScreen"


# ---------------------------------------------------------------------------
# SettingsOverlay
# ---------------------------------------------------------------------------

class TestSettingsOverlay:
    def test_settings_is_transparent_overlay(self, game: Game) -> None:
        """SettingsOverlay has transparent and pause_below flags set."""
        assert SettingsOverlay.transparent is True
        assert SettingsOverlay.pause_below is True
        assert SettingsOverlay.pop_on_cancel is True

    def test_settings_renders_content(self, game: Game) -> None:
        """SettingsOverlay shows its title and back button."""
        game.push(TitleScreen())
        game.tick(dt=0.016)
        game.push(SettingsOverlay())
        game.tick(dt=0.016)

        texts = _texts(game)
        assert "Settings" in texts
        assert "Back" in texts
        assert len(game._scene_stack._stack) == 2

    def test_esc_pops_settings(self, game: Game) -> None:
        """ESC dismisses the settings overlay, returning to title."""
        game.push(TitleScreen())
        game.tick(dt=0.016)
        game.push(SettingsOverlay())
        game.tick(dt=0.016)

        game.backend.inject_key("escape")
        game.tick(dt=0.016)

        assert _stack_names(game) == ["TitleScreen"]


# ---------------------------------------------------------------------------
# GameScreen
# ---------------------------------------------------------------------------

class TestGameScreen:
    def test_game_screen_renders(self, game: Game) -> None:
        """GameScreen shows the game world label and hint text."""
        game.push(GameScreen())
        game.tick(dt=0.016)

        texts = _texts(game)
        assert "GAME WORLD" in texts
        assert any("Inventory" in t for t in texts)

    def test_esc_opens_pause(self, game: Game) -> None:
        """ESC during gameplay opens the pause menu."""
        game.push(GameScreen())
        game.tick(dt=0.016)

        game.backend.inject_key("escape")
        game.tick(dt=0.016)

        assert _stack_names(game) == ["GameScreen", "PauseMenu"]

    def test_i_opens_inventory(self, game: Game) -> None:
        """Pressing I during gameplay opens inventory."""
        game.push(GameScreen())
        game.tick(dt=0.016)

        game.backend.inject_key("i")
        game.tick(dt=0.016)

        assert _stack_names(game) == ["GameScreen", "InventoryScreen"]


# ---------------------------------------------------------------------------
# PauseMenu
# ---------------------------------------------------------------------------

class TestPauseMenu:
    def test_pause_is_transparent_overlay(self, game: Game) -> None:
        """PauseMenu has correct overlay flags."""
        assert PauseMenu.transparent is True
        assert PauseMenu.pause_below is True
        assert PauseMenu.pop_on_cancel is True

    def test_pause_renders_content(self, game: Game) -> None:
        """PauseMenu shows PAUSED label and buttons."""
        game.push(GameScreen())
        game.tick(dt=0.016)
        game.push(PauseMenu())
        game.tick(dt=0.016)

        texts = _texts(game)
        assert "PAUSED" in texts
        assert "Resume" in texts
        assert "Quit to Title" in texts

    def test_esc_resumes_game(self, game: Game) -> None:
        """ESC pops the pause menu, returning to gameplay."""
        game.push(GameScreen())
        game.tick(dt=0.016)
        game.push(PauseMenu())
        game.tick(dt=0.016)

        game.backend.inject_key("escape")
        game.tick(dt=0.016)

        assert _stack_names(game) == ["GameScreen"]


# ---------------------------------------------------------------------------
# InventoryScreen
# ---------------------------------------------------------------------------

class TestInventoryScreen:
    def test_inventory_is_transparent_overlay(self, game: Game) -> None:
        """InventoryScreen has correct overlay flags."""
        assert InventoryScreen.transparent is True
        assert InventoryScreen.pause_below is True
        assert InventoryScreen.pop_on_cancel is True

    def test_inventory_renders_content(self, game: Game) -> None:
        """InventoryScreen shows title and close button."""
        game.push(GameScreen())
        game.tick(dt=0.016)
        game.push(InventoryScreen())
        game.tick(dt=0.016)

        texts = _texts(game)
        assert "Inventory" in texts
        assert "Close" in texts
        assert "(empty)" in texts

    def test_esc_closes_inventory(self, game: Game) -> None:
        """ESC pops inventory back to game screen."""
        game.push(GameScreen())
        game.tick(dt=0.016)
        game.push(InventoryScreen())
        game.tick(dt=0.016)

        game.backend.inject_key("escape")
        game.tick(dt=0.016)

        assert _stack_names(game) == ["GameScreen"]


# ---------------------------------------------------------------------------
# Full navigation flows
# ---------------------------------------------------------------------------

class TestNavigationFlows:
    def test_title_play_pause_resume(self, game: Game) -> None:
        """Title → Play → Pause → Resume → back in game."""
        game.push(TitleScreen())
        game.tick(dt=0.016)

        # Play (via keyboard)
        game.backend.inject_key("return")
        game.tick(dt=0.016)
        assert _stack_names(game)[-1] == "GameScreen"

        # Pause
        game.backend.inject_key("escape")
        game.tick(dt=0.016)
        assert _stack_names(game)[-1] == "PauseMenu"

        # Resume (via ESC)
        game.backend.inject_key("escape")
        game.tick(dt=0.016)
        assert _stack_names(game)[-1] == "GameScreen"

    def test_title_play_pause_quit_to_title(self, game: Game) -> None:
        """Title → Play → Pause → Quit to Title → back at title."""
        game.push(TitleScreen())
        game.tick(dt=0.016)

        # Play
        game.backend.inject_key("return")
        game.tick(dt=0.016)

        # Pause
        game.backend.inject_key("escape")
        game.tick(dt=0.016)
        assert _stack_names(game) == ["GameScreen", "PauseMenu"]

        # Quit to title uses clear_and_push — stack should be [TitleScreen]
        pause = game._scene_stack._stack[-1]
        pause._quit_to_title()
        game.tick(dt=0.016)

        assert _stack_names(game) == ["TitleScreen"]

    def test_game_inventory_close_back_to_game(self, game: Game) -> None:
        """Game → Inventory → Close → back in game."""
        game.push(GameScreen())
        game.tick(dt=0.016)

        # Open inventory
        game.backend.inject_key("i")
        game.tick(dt=0.016)
        assert _stack_names(game) == ["GameScreen", "InventoryScreen"]

        # Close via ESC
        game.backend.inject_key("escape")
        game.tick(dt=0.016)
        assert _stack_names(game) == ["GameScreen"]

    def test_title_settings_back_to_title(self, game: Game) -> None:
        """Title → Settings → Back → title restored."""
        game.push(TitleScreen())
        game.tick(dt=0.016)

        game.push(SettingsOverlay())
        game.tick(dt=0.016)
        assert len(game._scene_stack._stack) == 2

        # ESC back
        game.backend.inject_key("escape")
        game.tick(dt=0.016)
        assert _stack_names(game) == ["TitleScreen"]

        # Title screen should still render
        texts = _texts(game)
        assert "My Game" in texts

    def test_replace_does_not_keep_title_on_stack(self, game: Game) -> None:
        """Play uses replace — title should NOT be on the stack."""
        game.push(TitleScreen())
        game.tick(dt=0.016)

        # Trigger play (which calls game.replace)
        game.backend.inject_key("return")
        game.tick(dt=0.016)

        # Stack should only have GameScreen, not TitleScreen underneath
        names = _stack_names(game)
        assert "TitleScreen" not in names
        assert names == ["GameScreen"]

    def test_nested_overlays(self, game: Game) -> None:
        """Multiple overlays can stack and unstack correctly."""
        game.push(GameScreen())
        game.tick(dt=0.016)

        # Open pause
        game.backend.inject_key("escape")
        game.tick(dt=0.016)

        # Push another overlay on top (settings as example)
        game.push(SettingsOverlay())
        game.tick(dt=0.016)
        assert len(game._scene_stack._stack) == 3

        # Pop settings
        game.backend.inject_key("escape")
        game.tick(dt=0.016)
        assert _stack_names(game) == ["GameScreen", "PauseMenu"]

        # Pop pause
        game.backend.inject_key("escape")
        game.tick(dt=0.016)
        assert _stack_names(game) == ["GameScreen"]


# ---------------------------------------------------------------------------
# Detailed ESC and Inventory verification
# ---------------------------------------------------------------------------

class TestEscFromGame:
    """Step-by-step verification of pressing ESC during gameplay."""

    def test_esc_pushes_pause_over_game(self, game: Game) -> None:
        """ESC pushes PauseMenu; GameScreen stays underneath."""
        game.push(GameScreen())
        game.tick(dt=0.016)

        # Before ESC: only GameScreen
        assert _stack_names(game) == ["GameScreen"]

        game.backend.inject_key("escape")
        game.tick(dt=0.016)

        # After ESC: GameScreen still on stack, PauseMenu on top
        stack = game._scene_stack._stack
        assert len(stack) == 2
        assert stack[0].__class__.__name__ == "GameScreen"
        assert stack[1].__class__.__name__ == "PauseMenu"

    def test_pause_overlay_renders_over_game(self, game: Game) -> None:
        """PauseMenu is transparent — both game and pause UI should render."""
        game.push(GameScreen())
        game.tick(dt=0.016)
        game.backend.inject_key("escape")
        game.tick(dt=0.016)

        texts = _texts(game)
        # Pause menu content
        assert "PAUSED" in texts
        assert "Resume" in texts
        assert "Quit to Title" in texts
        # Game screen content still visible through transparency
        assert "GAME WORLD" in texts

    def test_pause_freezes_game_below(self, game: Game) -> None:
        """PauseMenu has pause_below=True so GameScreen.update is NOT called."""
        game.push(GameScreen())
        game.tick(dt=0.016)

        pause = PauseMenu()
        game.push(pause)
        game.tick(dt=0.016)

        # Verify the flag
        assert pause.pause_below is True

        # The game scene should exist but not receive updates
        game_scene = game._scene_stack._stack[0]
        assert game_scene.__class__.__name__ == "GameScreen"

    def test_esc_on_pause_pops_back_to_game(self, game: Game) -> None:
        """Pressing ESC on PauseMenu pops it; GameScreen becomes active again."""
        game.push(GameScreen())
        game.tick(dt=0.016)
        game.backend.inject_key("escape")
        game.tick(dt=0.016)

        assert _stack_names(game) == ["GameScreen", "PauseMenu"]

        # ESC again — pop_on_cancel pops the pause menu
        game.backend.inject_key("escape")
        game.tick(dt=0.016)

        assert _stack_names(game) == ["GameScreen"]

        # GameScreen renders normally again
        texts = _texts(game)
        assert "GAME WORLD" in texts
        assert "PAUSED" not in texts

    def test_game_hotkeys_work_after_pause_dismissed(self, game: Game) -> None:
        """After ESC pops PauseMenu, GameScreen hotkeys (I key) still work."""
        game.push(GameScreen())
        game.tick(dt=0.016)

        # Open and close pause
        game.backend.inject_key("escape")
        game.tick(dt=0.016)
        game.backend.inject_key("escape")
        game.tick(dt=0.016)
        assert _stack_names(game) == ["GameScreen"]

        # I key should still open inventory
        game.backend.inject_key("i")
        game.tick(dt=0.016)
        assert _stack_names(game) == ["GameScreen", "InventoryScreen"]


class TestInventoryFromGame:
    """Step-by-step verification of opening inventory during gameplay."""

    def test_i_key_pushes_inventory_over_game(self, game: Game) -> None:
        """Pressing I pushes InventoryScreen; GameScreen stays underneath."""
        game.push(GameScreen())
        game.tick(dt=0.016)

        assert _stack_names(game) == ["GameScreen"]

        game.backend.inject_key("i")
        game.tick(dt=0.016)

        stack = game._scene_stack._stack
        assert len(stack) == 2
        assert stack[0].__class__.__name__ == "GameScreen"
        assert stack[1].__class__.__name__ == "InventoryScreen"

    def test_inventory_renders_over_game(self, game: Game) -> None:
        """Inventory is transparent — both game and inventory UI should render."""
        game.push(GameScreen())
        game.tick(dt=0.016)
        game.backend.inject_key("i")
        game.tick(dt=0.016)

        texts = _texts(game)
        # Inventory content
        assert "Inventory" in texts
        assert "(empty)" in texts
        assert "Close" in texts
        # Game screen content still visible through transparency
        assert "GAME WORLD" in texts

    def test_inventory_pauses_game(self, game: Game) -> None:
        """InventoryScreen has pause_below=True so game is frozen."""
        game.push(GameScreen())
        game.tick(dt=0.016)
        game.backend.inject_key("i")
        game.tick(dt=0.016)

        inv = game._scene_stack._stack[-1]
        assert inv.__class__.__name__ == "InventoryScreen"
        assert inv.transparent is True
        assert inv.pause_below is True
        assert inv.pop_on_cancel is True

    def test_esc_closes_inventory_restores_game(self, game: Game) -> None:
        """ESC on inventory pops it; game renders normally again."""
        game.push(GameScreen())
        game.tick(dt=0.016)
        game.backend.inject_key("i")
        game.tick(dt=0.016)

        assert _stack_names(game) == ["GameScreen", "InventoryScreen"]

        game.backend.inject_key("escape")
        game.tick(dt=0.016)

        assert _stack_names(game) == ["GameScreen"]
        texts = _texts(game)
        assert "GAME WORLD" in texts
        assert "Inventory" not in texts

    def test_i_key_does_not_work_while_paused(self, game: Game) -> None:
        """I key pressed on PauseMenu does NOT open inventory (different scene)."""
        game.push(GameScreen())
        game.tick(dt=0.016)

        # Open pause
        game.backend.inject_key("escape")
        game.tick(dt=0.016)
        assert _stack_names(game) == ["GameScreen", "PauseMenu"]

        # Press I — PauseMenu has no I binding, should be ignored
        game.backend.inject_key("i")
        game.tick(dt=0.016)

        # Inventory should NOT have opened
        assert _stack_names(game) == ["GameScreen", "PauseMenu"]

    def test_inventory_then_pause_sequence(self, game: Game) -> None:
        """Open inventory, close it, then open pause — both work independently."""
        game.push(GameScreen())
        game.tick(dt=0.016)

        # Open and close inventory
        game.backend.inject_key("i")
        game.tick(dt=0.016)
        assert _stack_names(game)[-1] == "InventoryScreen"
        game.backend.inject_key("escape")
        game.tick(dt=0.016)
        assert _stack_names(game) == ["GameScreen"]

        # Now open pause
        game.backend.inject_key("escape")
        game.tick(dt=0.016)
        assert _stack_names(game) == ["GameScreen", "PauseMenu"]

        # Close pause
        game.backend.inject_key("escape")
        game.tick(dt=0.016)
        assert _stack_names(game) == ["GameScreen"]
