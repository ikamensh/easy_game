"""Tests for convenience screens (Stage 13 Part 1).

Covers:
- MessageScreen: creation, dismiss on key/click, callback, event consumption
- ChoiceScreen: button display, callback on selection, cancel, number keys
- ConfirmDialog: confirm/cancel callbacks, keyboard shortcuts
- SaveLoadScreen: slot listing, save/load mechanics, back button
- show_sequence: chaining behavior, completion callback
"""

from __future__ import annotations

from pathlib import Path

import pytest

from easygame import Game, Scene
from easygame.backends.mock_backend import MockBackend
from easygame.save import SaveManager
from easygame.ui.screens import (
    ChoiceScreen,
    ConfirmDialog,
    MessageScreen,
    SaveLoadScreen,
    _SequenceRunner,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def game() -> Game:
    """Return a mock game instance."""
    return Game("Test", backend="mock", resolution=(800, 600))


@pytest.fixture
def backend(game: Game) -> MockBackend:
    """Return the mock backend from the game."""
    return game._backend


@pytest.fixture
def save_mgr(tmp_path: Path) -> SaveManager:
    """Return a SaveManager with a temp directory."""
    return SaveManager(tmp_path / "saves")


# ---------------------------------------------------------------------------
# MessageScreen
# ---------------------------------------------------------------------------

class TestMessageScreen:
    """Test MessageScreen creation and behaviour."""

    def test_is_transparent(self) -> None:
        """MessageScreen is a transparent overlay."""
        assert MessageScreen.transparent is True

    def test_show_hud_false(self) -> None:
        """MessageScreen hides the HUD."""
        assert MessageScreen.show_hud is False

    def test_dismiss_on_key_press(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Pressing any key dismisses the MessageScreen."""
        game.push(Scene())
        game.push(MessageScreen("Hello"))
        assert len(game._scene_stack._stack) == 2

        backend.inject_key("space")
        game.tick(dt=0.016)

        # MessageScreen should have popped.
        assert len(game._scene_stack._stack) == 1

    def test_dismiss_on_click(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Clicking dismisses the MessageScreen."""
        game.push(Scene())
        game.push(MessageScreen("Hello"))

        backend.inject_click(400, 300)
        game.tick(dt=0.016)

        assert len(game._scene_stack._stack) == 1

    def test_on_dismiss_callback(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """on_dismiss callback fires before pop."""
        called = []
        game.push(Scene())
        game.push(MessageScreen("Hi", on_dismiss=lambda: called.append(True)))

        backend.inject_key("return")
        game.tick(dt=0.016)

        assert called == [True]

    def test_no_callback_if_none(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Works fine without on_dismiss callback."""
        game.push(Scene())
        game.push(MessageScreen("Hi"))

        backend.inject_key("return")
        game.tick(dt=0.016)

        assert len(game._scene_stack._stack) == 1

    def test_consumes_all_events(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """MessageScreen consumes all events (modal)."""
        scene_events = []

        class TrackScene(Scene):
            def handle_input(self, event) -> bool:
                scene_events.append(event)
                return True

        game.push(TrackScene())
        game.push(MessageScreen("Modal"))

        # Inject a move event (not key_press or click, won't dismiss).
        backend.inject_mouse_move(100, 100)
        game.tick(dt=0.016)

        # The scene below should NOT have seen the event.
        assert len(scene_events) == 0
        # MessageScreen should still be on stack (moves don't dismiss).
        assert len(game._scene_stack._stack) == 2

    def test_builds_ui_on_enter(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """MessageScreen builds UI components in on_enter."""
        game.push(Scene())
        msg = MessageScreen("Test Message")
        game.push(msg)

        # Should have created a UI tree.
        assert msg._ui is not None
        assert len(msg._ui._children) > 0

    def test_draws_without_error(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """MessageScreen can render a frame without error."""
        game.push(Scene())
        game.push(MessageScreen("Render test"))
        game.tick(dt=0.016)  # Should not raise.


# ---------------------------------------------------------------------------
# ChoiceScreen
# ---------------------------------------------------------------------------

class TestChoiceScreen:
    """Test ChoiceScreen creation and behaviour."""

    def test_is_transparent(self) -> None:
        assert ChoiceScreen.transparent is True

    def test_show_hud_false(self) -> None:
        assert ChoiceScreen.show_hud is False

    def test_escape_cancels_without_callback(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Pressing Escape pops without calling on_choice."""
        called = []
        game.push(Scene())
        game.push(ChoiceScreen(
            "Pick:", ["A", "B"],
            on_choice=lambda i: called.append(i),
        ))

        backend.inject_key("escape")
        game.tick(dt=0.016)

        assert called == []
        assert len(game._scene_stack._stack) == 1

    def test_button_click_calls_on_choice(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Clicking a choice button fires on_choice(index)."""
        called = []
        game.push(Scene())
        screen = ChoiceScreen(
            "Pick:", ["Warrior", "Mage", "Rogue"],
            on_choice=lambda i: called.append(i),
        )
        game.push(screen)

        # Force a layout pass so buttons have computed positions.
        game.tick(dt=0.016)

        # Find the buttons in the UI tree.
        buttons = []
        _find_buttons(screen._ui, buttons)

        assert len(buttons) == 3  # One per choice.

        # Click the second button (index 1) by simulating on_click.
        buttons[1]._on_click()

        # The callback should have been called and the screen popped.
        assert called == [1]

    def test_number_key_selects_choice(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Pressing a number key (1-based) selects the choice."""
        called = []
        game.push(Scene())
        game.push(ChoiceScreen(
            "Pick:", ["A", "B", "C"],
            on_choice=lambda i: called.append(i),
        ))

        backend.inject_key("2")
        game.tick(dt=0.016)

        assert called == [1]  # 0-based index
        assert len(game._scene_stack._stack) == 1

    def test_invalid_number_key_ignored(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Number keys out of range don't trigger selection."""
        called = []
        game.push(Scene())
        game.push(ChoiceScreen(
            "Pick:", ["A", "B"],
            on_choice=lambda i: called.append(i),
        ))

        backend.inject_key("5")  # Only 2 choices.
        game.tick(dt=0.016)

        assert called == []
        assert len(game._scene_stack._stack) == 2  # Still on stack.

    def test_consumes_all_events(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """ChoiceScreen consumes all events (modal)."""
        scene_events = []

        class TrackScene(Scene):
            def handle_input(self, event) -> bool:
                scene_events.append(event)
                return True

        game.push(TrackScene())
        game.push(ChoiceScreen("Pick:", ["A"]))

        backend.inject_mouse_move(100, 100)
        game.tick(dt=0.016)

        assert len(scene_events) == 0

    def test_no_callback_works(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """ChoiceScreen works without on_choice callback."""
        game.push(Scene())
        game.push(ChoiceScreen("Pick:", ["A", "B"]))

        backend.inject_key("1")
        game.tick(dt=0.016)

        assert len(game._scene_stack._stack) == 1

    def test_builds_ui_with_prompt_and_buttons(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """ChoiceScreen creates prompt label and choice buttons."""
        game.push(Scene())
        screen = ChoiceScreen("Question?", ["Yes", "No", "Maybe"])
        game.push(screen)

        buttons = []
        _find_buttons(screen._ui, buttons)
        assert len(buttons) == 3


# ---------------------------------------------------------------------------
# ConfirmDialog
# ---------------------------------------------------------------------------

class TestConfirmDialog:
    """Test ConfirmDialog creation and behaviour."""

    def test_is_transparent(self) -> None:
        assert ConfirmDialog.transparent is True

    def test_show_hud_false(self) -> None:
        assert ConfirmDialog.show_hud is False

    def test_yes_button_calls_on_confirm(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Clicking Yes fires on_confirm and pops."""
        called = []
        game.push(Scene())
        dialog = ConfirmDialog(
            "Sure?",
            on_confirm=lambda: called.append("yes"),
            on_cancel=lambda: called.append("no"),
        )
        game.push(dialog)
        game.tick(dt=0.016)  # Layout pass.

        buttons = []
        _find_buttons(dialog._ui, buttons)

        # First button should be "Yes".
        assert buttons[0]._text == "Yes"
        buttons[0]._on_click()

        assert called == ["yes"]

    def test_no_button_calls_on_cancel(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Clicking No fires on_cancel and pops."""
        called = []
        game.push(Scene())
        dialog = ConfirmDialog(
            "Sure?",
            on_confirm=lambda: called.append("yes"),
            on_cancel=lambda: called.append("no"),
        )
        game.push(dialog)
        game.tick(dt=0.016)

        buttons = []
        _find_buttons(dialog._ui, buttons)

        assert buttons[1]._text == "No"
        buttons[1]._on_click()

        assert called == ["no"]

    def test_enter_key_confirms(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Pressing Enter/Return fires on_confirm."""
        called = []
        game.push(Scene())
        game.push(ConfirmDialog(
            "Sure?",
            on_confirm=lambda: called.append("yes"),
        ))

        backend.inject_key("return")
        game.tick(dt=0.016)

        assert called == ["yes"]
        assert len(game._scene_stack._stack) == 1

    def test_escape_key_cancels(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Pressing Escape fires on_cancel."""
        called = []
        game.push(Scene())
        game.push(ConfirmDialog(
            "Sure?",
            on_cancel=lambda: called.append("no"),
        ))

        backend.inject_key("escape")
        game.tick(dt=0.016)

        assert called == ["no"]
        assert len(game._scene_stack._stack) == 1

    def test_consumes_all_events(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """ConfirmDialog consumes all events (modal)."""
        scene_events = []

        class TrackScene(Scene):
            def handle_input(self, event) -> bool:
                scene_events.append(event)
                return True

        game.push(TrackScene())
        game.push(ConfirmDialog("Sure?"))

        backend.inject_mouse_move(100, 100)
        game.tick(dt=0.016)

        assert len(scene_events) == 0

    def test_no_callbacks_works(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """ConfirmDialog works with no callbacks."""
        game.push(Scene())
        game.push(ConfirmDialog("Sure?"))

        backend.inject_key("return")
        game.tick(dt=0.016)

        assert len(game._scene_stack._stack) == 1

    def test_builds_ui_with_buttons(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """ConfirmDialog creates Yes and No buttons."""
        game.push(Scene())
        dialog = ConfirmDialog("Question?")
        game.push(dialog)

        buttons = []
        _find_buttons(dialog._ui, buttons)
        texts = [b._text for b in buttons]
        assert "Yes" in texts
        assert "No" in texts


# ---------------------------------------------------------------------------
# SaveLoadScreen
# ---------------------------------------------------------------------------

class TestSaveLoadScreen:
    """Test SaveLoadScreen creation and behaviour."""

    def test_is_transparent(self) -> None:
        mgr = SaveManager(Path("/tmp/fake"))
        assert SaveLoadScreen(save_manager=mgr).transparent is True

    def test_show_hud_false(self) -> None:
        mgr = SaveManager(Path("/tmp/fake"))
        assert SaveLoadScreen(save_manager=mgr).show_hud is False

    def test_invalid_mode_raises(self, save_mgr: SaveManager) -> None:
        """Invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="mode must be"):
            SaveLoadScreen("invalid", save_manager=save_mgr)

    def test_load_screen_shows_slots(
        self, game: Game, backend: MockBackend, save_mgr: SaveManager,
    ) -> None:
        """SaveLoadScreen in load mode shows slot buttons."""
        save_mgr.save(1, {"gold": 100}, "MapScene")
        game.push(Scene())
        screen = SaveLoadScreen(
            "load", save_manager=save_mgr, slot_count=3,
        )
        game.push(screen)

        buttons = []
        _find_buttons(screen._ui, buttons)
        # 3 slot buttons + 1 Back button = 4.
        assert len(buttons) == 4
        # First button should mention "Slot 1" (has data).
        assert "Slot 1" in buttons[0]._text
        assert "Empty" not in buttons[0]._text
        # Second button should be empty.
        assert "Slot 2" in buttons[1]._text
        assert "Empty" in buttons[1]._text

    def test_save_mode_saves_on_slot_click(
        self, game: Game, backend: MockBackend, save_mgr: SaveManager,
    ) -> None:
        """In save mode, clicking a slot calls game.save() and on_save."""
        saved_slots = []

        class GameScene(Scene):
            def get_save_state(self) -> dict:
                return {"gold": 999}

        game.push(GameScene())
        # Need to wire up save manager.
        game._save_manager = save_mgr

        screen = SaveLoadScreen(
            "save",
            save_manager=save_mgr,
            on_save=lambda slot: saved_slots.append(slot),
            slot_count=3,
        )
        game.push(screen)
        game.tick(dt=0.016)  # Layout.

        buttons = []
        _find_buttons(screen._ui, buttons)

        # Click slot 1 button.
        buttons[0]._on_click()

        assert 1 in saved_slots
        # Data should have been written.
        data = save_mgr.load(1)
        assert data is not None
        assert data["state"]["gold"] == 999

    def test_load_mode_loads_on_filled_slot(
        self, game: Game, backend: MockBackend, save_mgr: SaveManager,
    ) -> None:
        """In load mode, clicking a filled slot fires on_load."""
        loaded_data = []
        save_mgr.save(2, {"level": 5}, "BattleScene")

        game.push(Scene())
        screen = SaveLoadScreen(
            "load",
            save_manager=save_mgr,
            on_load=lambda slot, data: loaded_data.append((slot, data)),
            slot_count=3,
        )
        game.push(screen)
        game.tick(dt=0.016)

        buttons = []
        _find_buttons(screen._ui, buttons)

        # Click slot 2 (index 1).
        buttons[1]._on_click()

        assert len(loaded_data) == 1
        assert loaded_data[0][0] == 2
        assert loaded_data[0][1]["state"]["level"] == 5

    def test_load_mode_ignores_empty_slot(
        self, game: Game, backend: MockBackend, save_mgr: SaveManager,
    ) -> None:
        """In load mode, clicking an empty slot does nothing."""
        loaded_data = []

        game.push(Scene())
        screen = SaveLoadScreen(
            "load",
            save_manager=save_mgr,
            on_load=lambda slot, data: loaded_data.append((slot, data)),
            slot_count=3,
        )
        game.push(screen)
        game.tick(dt=0.016)

        buttons = []
        _find_buttons(screen._ui, buttons)

        # Click slot 1 (empty).
        buttons[0]._on_click()

        assert loaded_data == []
        # Screen should still be on stack (didn't pop).
        assert len(game._scene_stack._stack) == 2

    def test_back_button_pops(
        self, game: Game, backend: MockBackend, save_mgr: SaveManager,
    ) -> None:
        """Clicking Back pops the SaveLoadScreen."""
        game.push(Scene())
        screen = SaveLoadScreen(
            "load", save_manager=save_mgr, slot_count=2,
        )
        game.push(screen)
        game.tick(dt=0.016)

        buttons = []
        _find_buttons(screen._ui, buttons)

        # Last button should be "Back".
        back = buttons[-1]
        assert back._text == "Back"
        back._on_click()

        assert len(game._scene_stack._stack) == 1

    def test_escape_pops(
        self, game: Game, backend: MockBackend, save_mgr: SaveManager,
    ) -> None:
        """Pressing Escape pops the SaveLoadScreen."""
        game.push(Scene())
        game.push(SaveLoadScreen(
            "load", save_manager=save_mgr, slot_count=2,
        ))

        backend.inject_key("escape")
        game.tick(dt=0.016)

        assert len(game._scene_stack._stack) == 1


# ---------------------------------------------------------------------------
# show_sequence
# ---------------------------------------------------------------------------

class TestShowSequence:
    """Test game.show_sequence() chaining behaviour."""

    def test_sequence_pushes_first_screen(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """show_sequence pushes _SequenceRunner + first MessageScreen."""
        game.push(Scene())
        msgs = [
            MessageScreen("Page 1"),
            MessageScreen("Page 2"),
        ]
        game.show_sequence(msgs)

        # Stack: [Scene, _SequenceRunner, MessageScreen("Page 1")]
        assert len(game._scene_stack._stack) == 3
        assert isinstance(game._scene_stack._stack[1], _SequenceRunner)
        assert isinstance(game._scene_stack._stack[2], MessageScreen)

    def test_sequence_chains_on_dismiss(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Dismissing one screen pushes the next."""
        game.push(Scene())
        msgs = [
            MessageScreen("Page 1"),
            MessageScreen("Page 2"),
            MessageScreen("Page 3"),
        ]
        game.show_sequence(msgs)

        # Stack: [Scene, Runner, Page1]
        assert len(game._scene_stack._stack) == 3

        # Dismiss Page 1.
        backend.inject_key("space")
        game.tick(dt=0.016)

        # Stack: [Scene, Runner, Page2]
        assert len(game._scene_stack._stack) == 3
        assert game._scene_stack._stack[2] is msgs[1]

        # Dismiss Page 2.
        backend.inject_key("space")
        game.tick(dt=0.016)

        # Stack: [Scene, Runner, Page3]
        assert len(game._scene_stack._stack) == 3
        assert game._scene_stack._stack[2] is msgs[2]

        # Dismiss Page 3 — runner fires completion and pops.
        backend.inject_key("space")
        game.tick(dt=0.016)

        # Stack: [Scene]
        assert len(game._scene_stack._stack) == 1

    def test_sequence_fires_on_complete(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """on_complete callback fires after last screen is dismissed."""
        completed = []
        game.push(Scene())
        game.show_sequence(
            [MessageScreen("Only one")],
            on_complete=lambda: completed.append(True),
        )

        # Dismiss.
        backend.inject_key("space")
        game.tick(dt=0.016)

        assert completed == [True]

    def test_empty_sequence_fires_on_complete_immediately(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Empty screen list fires on_complete immediately."""
        completed = []
        game.push(Scene())
        game.show_sequence(
            [],
            on_complete=lambda: completed.append(True),
        )

        # _SequenceRunner should have popped itself already.
        assert completed == [True]
        assert len(game._scene_stack._stack) == 1

    def test_sequence_no_callback_works(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """show_sequence works without on_complete callback."""
        game.push(Scene())
        game.show_sequence([MessageScreen("Hi")])

        backend.inject_key("space")
        game.tick(dt=0.016)

        assert len(game._scene_stack._stack) == 1

    def test_sequence_runner_is_transparent(self) -> None:
        """_SequenceRunner is a transparent scene."""
        assert _SequenceRunner.transparent is True


# ---------------------------------------------------------------------------
# Screen attribute checks
# ---------------------------------------------------------------------------

class TestScreenAttributes:
    """Verify that all screens have correct Scene attributes."""

    def test_message_screen_is_scene(self) -> None:
        assert issubclass(MessageScreen, Scene)

    def test_choice_screen_is_scene(self) -> None:
        assert issubclass(ChoiceScreen, Scene)

    def test_confirm_dialog_is_scene(self) -> None:
        assert issubclass(ConfirmDialog, Scene)

    def test_save_load_screen_is_scene(self) -> None:
        assert issubclass(SaveLoadScreen, Scene)

    def test_sequence_runner_is_scene(self) -> None:
        assert issubclass(_SequenceRunner, Scene)


# ---------------------------------------------------------------------------
# Export checks
# ---------------------------------------------------------------------------

class TestExports:
    """Verify screens are exported from the package."""

    def test_import_from_easygame(self) -> None:
        pass

    def test_import_from_easygame_ui(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Bug-fix: handle_input uses InputEvent type hint
# ---------------------------------------------------------------------------


class TestScreenInputEventTypeHint:
    """Screens accept InputEvent (not Any) in handle_input."""

    def test_message_screen_handle_input_signature(self) -> None:
        """MessageScreen.handle_input type hint is InputEvent."""
        import inspect
        sig = inspect.signature(MessageScreen.handle_input)
        param = sig.parameters["event"]
        # The annotation should reference InputEvent (not Any)
        ann = param.annotation
        # With 'from __future__ import annotations' the annotation is a string
        assert "InputEvent" in str(ann)

    def test_choice_screen_handle_input_signature(self) -> None:
        """ChoiceScreen.handle_input type hint is InputEvent."""
        import inspect
        sig = inspect.signature(ChoiceScreen.handle_input)
        ann = sig.parameters["event"].annotation
        assert "InputEvent" in str(ann)

    def test_confirm_dialog_handle_input_signature(self) -> None:
        """ConfirmDialog.handle_input type hint is InputEvent."""
        import inspect
        sig = inspect.signature(ConfirmDialog.handle_input)
        ann = sig.parameters["event"].annotation
        assert "InputEvent" in str(ann)

    def test_message_screen_still_works_with_events(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """MessageScreen still dismisses correctly with InputEvent dispatch."""
        game.push(Scene())
        game.push(MessageScreen("Hello"))
        assert len(game._scene_stack._stack) == 2

        backend.inject_key("space")
        game.tick(dt=0.016)
        assert len(game._scene_stack._stack) == 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_buttons(component, result: list) -> None:
    """Recursively find all Button instances in a component tree."""
    from easygame.ui.components import Button
    if isinstance(component, Button):
        result.append(component)
    for child in component._children:
        _find_buttons(child, result)
