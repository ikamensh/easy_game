"""Tests for _SettingsScene (Stage 13 Part 4).

Covers:
- _SettingsScene: creation, attributes, UI structure
- Volume controls: minus/plus buttons adjust volume, ProgressBar updates
- Key rebinding: listening mode, rebind on key press, cancel with Escape
- Back button and Escape to pop
- game.push_settings() convenience method
"""

from __future__ import annotations

import pytest

from easygame import Game, Scene
from easygame.backends.mock_backend import MockBackend
from easygame.ui.screens import _SettingsScene


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


def _find_buttons(component, result: list) -> None:
    """Recursively find all Button instances in a component tree."""
    from easygame.ui.components import Button
    if isinstance(component, Button):
        result.append(component)
    for child in component._children:
        _find_buttons(child, result)


def _find_progressbars(component, result: list) -> None:
    """Recursively find all ProgressBar instances in a component tree."""
    from easygame.ui.widgets import ProgressBar
    if isinstance(component, ProgressBar):
        result.append(component)
    for child in component._children:
        _find_progressbars(child, result)


def _find_labels(component, result: list) -> None:
    """Recursively find all Label instances in a component tree."""
    from easygame.ui.components import Label
    if isinstance(component, Label):
        result.append(component)
    for child in component._children:
        _find_labels(child, result)


# ---------------------------------------------------------------------------
# _SettingsScene attributes
# ---------------------------------------------------------------------------

class TestSettingsSceneAttributes:
    """Test _SettingsScene class attributes."""

    def test_is_scene_subclass(self) -> None:
        assert issubclass(_SettingsScene, Scene)

    def test_is_transparent(self) -> None:
        assert _SettingsScene.transparent is True

    def test_show_hud_false(self) -> None:
        assert _SettingsScene.show_hud is False


# ---------------------------------------------------------------------------
# UI Structure
# ---------------------------------------------------------------------------

class TestSettingsUIStructure:
    """Test the UI layout built in on_enter."""

    def test_builds_ui_on_enter(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """_SettingsScene builds a UI tree."""
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)

        assert settings._ui is not None
        assert len(settings._ui._children) > 0

    def test_has_title_label(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """The UI contains a 'Settings' title label."""
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)

        labels = []
        _find_labels(settings._ui, labels)
        title_texts = [lb._text for lb in labels]
        assert "Settings" in title_texts

    def test_has_volume_label(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """The UI contains a 'Volume' section label."""
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)

        labels = []
        _find_labels(settings._ui, labels)
        texts = [lb._text for lb in labels]
        assert "Volume" in texts

    def test_has_key_bindings_label(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """The UI contains a 'Key Bindings' section label."""
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)

        labels = []
        _find_labels(settings._ui, labels)
        texts = [lb._text for lb in labels]
        assert "Key Bindings" in texts

    def test_has_four_progress_bars(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """The UI has 4 ProgressBars (one per volume channel)."""
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)

        bars = []
        _find_progressbars(settings._ui, bars)
        assert len(bars) == 4

    def test_has_back_button(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """The UI has a Back button."""
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)

        buttons = []
        _find_buttons(settings._ui, buttons)
        texts = [b._text for b in buttons]
        assert "Back" in texts

    def test_has_volume_buttons(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """The UI has minus and plus buttons for volume."""
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)

        buttons = []
        _find_buttons(settings._ui, buttons)
        texts = [b._text for b in buttons]
        # 4 channels × 2 buttons (− and +) = 8 volume buttons.
        assert texts.count("−") == 4
        assert texts.count("+") == 4

    def test_has_binding_buttons(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """The UI has a button for each bound action."""
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)

        bindings = game.input.get_bindings()
        buttons = []
        _find_buttons(settings._ui, buttons)
        # Find buttons that look like "[KEY]".
        binding_buttons = [b for b in buttons if b._text.startswith("[") and b._text.endswith("]")]
        assert len(binding_buttons) == len(bindings)

    def test_draws_without_error(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """_SettingsScene can render a frame without error."""
        game.push(Scene())
        game.push(_SettingsScene())
        game.tick(dt=0.016)  # Should not raise.


# ---------------------------------------------------------------------------
# Volume controls
# ---------------------------------------------------------------------------

class TestVolumeControls:
    """Test volume adjustment through the settings screen."""

    def test_plus_increases_volume(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Clicking + increases the channel volume by 0.1."""
        game.audio.set_volume("master", 0.5)
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        # Find the plus button for master (first + button).
        buttons = []
        _find_buttons(settings._ui, buttons)
        plus_buttons = [b for b in buttons if b._text == "+"]
        assert len(plus_buttons) >= 1

        # First + is for master.
        plus_buttons[0]._on_click()

        assert abs(game.audio.get_volume("master") - 0.6) < 0.01

    def test_minus_decreases_volume(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Clicking − decreases the channel volume by 0.1."""
        game.audio.set_volume("master", 0.5)
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        buttons = []
        _find_buttons(settings._ui, buttons)
        minus_buttons = [b for b in buttons if b._text == "−"]
        assert len(minus_buttons) >= 1

        # First − is for master.
        minus_buttons[0]._on_click()

        assert abs(game.audio.get_volume("master") - 0.4) < 0.01

    def test_volume_clamps_at_max(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Volume does not exceed 1.0."""
        game.audio.set_volume("master", 0.95)
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        buttons = []
        _find_buttons(settings._ui, buttons)
        plus_buttons = [b for b in buttons if b._text == "+"]
        plus_buttons[0]._on_click()

        assert game.audio.get_volume("master") <= 1.0

    def test_volume_clamps_at_min(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Volume does not go below 0.0."""
        game.audio.set_volume("master", 0.05)
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        buttons = []
        _find_buttons(settings._ui, buttons)
        minus_buttons = [b for b in buttons if b._text == "−"]
        minus_buttons[0]._on_click()

        assert game.audio.get_volume("master") >= 0.0

    def test_progress_bar_updates(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """ProgressBar value updates when volume changes."""
        game.audio.set_volume("master", 0.5)
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        # Verify initial bar value.
        bar = settings._volume_bars["master"]
        assert abs(bar.value - 50.0) < 0.1

        # Click plus.
        buttons = []
        _find_buttons(settings._ui, buttons)
        plus_buttons = [b for b in buttons if b._text == "+"]
        plus_buttons[0]._on_click()

        assert abs(bar.value - 60.0) < 0.1

    def test_volume_label_updates(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Volume percentage label updates when volume changes."""
        game.audio.set_volume("master", 0.5)
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        label = settings._volume_labels["master"]
        assert label._text == "50%"

        buttons = []
        _find_buttons(settings._ui, buttons)
        plus_buttons = [b for b in buttons if b._text == "+"]
        plus_buttons[0]._on_click()

        assert label._text == "60%"

    def test_different_channels_independent(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Adjusting one channel doesn't affect another."""
        game.audio.set_volume("master", 0.5)
        game.audio.set_volume("music", 0.7)
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        # Click + on master (first + button).
        buttons = []
        _find_buttons(settings._ui, buttons)
        plus_buttons = [b for b in buttons if b._text == "+"]
        plus_buttons[0]._on_click()  # master

        assert abs(game.audio.get_volume("master") - 0.6) < 0.01
        assert abs(game.audio.get_volume("music") - 0.7) < 0.01

    def test_music_channel_adjustable(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Music channel can be adjusted via its + button."""
        game.audio.set_volume("music", 0.5)
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        buttons = []
        _find_buttons(settings._ui, buttons)
        plus_buttons = [b for b in buttons if b._text == "+"]
        # Order: master, music, sfx, ui → second + is music.
        plus_buttons[1]._on_click()

        assert abs(game.audio.get_volume("music") - 0.6) < 0.01


# ---------------------------------------------------------------------------
# Key rebinding
# ---------------------------------------------------------------------------

class TestKeyRebinding:
    """Test the key rebinding UI."""

    def test_clicking_binding_enters_listening(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Clicking a binding button enters listening mode."""
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        # Find a binding button (e.g. for "confirm").
        buttons = []
        _find_buttons(settings._ui, buttons)
        binding_buttons = [b for b in buttons if b._text.startswith("[") and b._text.endswith("]")]
        assert len(binding_buttons) > 0

        binding_buttons[0]._on_click()

        assert settings._listening_action is not None
        assert settings._listening_button is not None
        assert binding_buttons[0]._text == "[...]"

    def test_key_press_rebinds_action(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Pressing a key while listening rebinds the action."""
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        # Find the binding button for "confirm" action.
        buttons = []
        _find_buttons(settings._ui, buttons)
        binding_buttons = [b for b in buttons if b._text.startswith("[") and b._text.endswith("]")]

        # Find confirm button by checking current binding.
        confirm_btn = None
        for b in binding_buttons:
            if b._text == "[RETURN]":
                confirm_btn = b
                break
        assert confirm_btn is not None

        confirm_btn._on_click()  # Enter listening mode.
        assert settings._listening_action is not None

        # Now press "space" to rebind.
        backend.inject_key("space")
        game.tick(dt=0.016)

        # Confirm should now be bound to space.
        bindings = game.input.get_bindings()
        assert bindings.get("confirm") == "space"
        assert confirm_btn._text == "[SPACE]"
        assert settings._listening_action is None

    def test_escape_cancels_rebinding(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Pressing Escape during listening cancels the rebind."""
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        buttons = []
        _find_buttons(settings._ui, buttons)
        binding_buttons = [b for b in buttons if b._text.startswith("[") and b._text.endswith("]")]

        # Find confirm button.
        confirm_btn = None
        for b in binding_buttons:
            if b._text == "[RETURN]":
                confirm_btn = b
                break
        assert confirm_btn is not None

        confirm_btn._on_click()  # Enter listening mode.
        assert settings._listening_action is not None

        # Press Escape to cancel.
        backend.inject_key("escape")
        game.tick(dt=0.016)

        # Binding should be unchanged.
        bindings = game.input.get_bindings()
        assert bindings.get("confirm") == "return"
        assert confirm_btn._text == "[RETURN]"
        assert settings._listening_action is None
        # Settings should NOT have popped (escape was consumed by listening cancel).
        assert len(game._scene_stack._stack) == 2

    def test_cancel_restores_button_text(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Cancelling listening restores the original key display."""
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        buttons = []
        _find_buttons(settings._ui, buttons)
        binding_buttons = [b for b in buttons if b._text.startswith("[") and b._text.endswith("]")]

        btn = binding_buttons[0]
        original_text = btn._text
        btn._on_click()
        assert btn._text == "[...]"

        settings._cancel_listening()
        assert btn._text == original_text

    def test_listening_switch_cancels_previous(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Clicking a second binding button cancels the first listening."""
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        buttons = []
        _find_buttons(settings._ui, buttons)
        binding_buttons = [b for b in buttons if b._text.startswith("[") and b._text.endswith("]")]
        assert len(binding_buttons) >= 2

        first_text = binding_buttons[0]._text
        binding_buttons[0]._on_click()
        assert binding_buttons[0]._text == "[...]"

        # Click second binding button.
        binding_buttons[1]._on_click()

        # First should be restored, second should be listening.
        assert binding_buttons[0]._text == first_text
        assert binding_buttons[1]._text == "[...]"


# ---------------------------------------------------------------------------
# Back / Escape
# ---------------------------------------------------------------------------

class TestSettingsNavigation:
    """Test dismissing the settings screen."""

    def test_back_button_pops(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Clicking Back pops the settings screen."""
        game.push(Scene())
        game.push(_SettingsScene())
        assert len(game._scene_stack._stack) == 2

        game.tick(dt=0.016)

        buttons = []
        _find_buttons(game._scene_stack._stack[-1]._ui, buttons)
        back_btn = [b for b in buttons if b._text == "Back"][0]
        back_btn._on_click()

        assert len(game._scene_stack._stack) == 1

    def test_escape_pops(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Pressing Escape pops the settings screen."""
        game.push(Scene())
        game.push(_SettingsScene())
        assert len(game._scene_stack._stack) == 2

        backend.inject_key("escape")
        game.tick(dt=0.016)

        assert len(game._scene_stack._stack) == 1

    def test_consumes_all_events(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """_SettingsScene consumes all events (modal)."""
        scene_events = []

        class TrackScene(Scene):
            def handle_input(self, event) -> bool:
                scene_events.append(event)
                return True

        game.push(TrackScene())
        game.push(_SettingsScene())

        backend.inject_mouse_move(100, 100)
        game.tick(dt=0.016)

        assert len(scene_events) == 0


# ---------------------------------------------------------------------------
# game.push_settings()
# ---------------------------------------------------------------------------

class TestPushSettings:
    """Test the game.push_settings() convenience method."""

    def test_push_settings_pushes_scene(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """push_settings() pushes a _SettingsScene onto the stack."""
        game.push(Scene())
        game.push_settings()

        assert len(game._scene_stack._stack) == 2
        assert isinstance(game._scene_stack._stack[-1], _SettingsScene)

    def test_push_settings_scene_is_functional(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Settings screen pushed via push_settings() can render."""
        game.push(Scene())
        game.push_settings()
        game.tick(dt=0.016)  # Should not raise.

    def test_push_settings_escape_pops(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Settings screen pushed via push_settings() can be dismissed."""
        game.push(Scene())
        game.push_settings()
        assert len(game._scene_stack._stack) == 2

        backend.inject_key("escape")
        game.tick(dt=0.016)

        assert len(game._scene_stack._stack) == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestSettingsEdgeCases:
    """Test edge cases for the settings screen."""

    def test_volume_at_zero(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Volume at 0 with minus stays at 0."""
        game.audio.set_volume("master", 0.0)
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        buttons = []
        _find_buttons(settings._ui, buttons)
        minus_buttons = [b for b in buttons if b._text == "−"]
        minus_buttons[0]._on_click()

        assert game.audio.get_volume("master") == 0.0

    def test_volume_at_one(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Volume at 1.0 with plus stays at 1.0."""
        game.audio.set_volume("master", 1.0)
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        buttons = []
        _find_buttons(settings._ui, buttons)
        plus_buttons = [b for b in buttons if b._text == "+"]
        plus_buttons[0]._on_click()

        assert game.audio.get_volume("master") == 1.0

    def test_multiple_adjustments(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Multiple clicks accumulate volume changes."""
        game.audio.set_volume("master", 0.5)
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)

        buttons = []
        _find_buttons(settings._ui, buttons)
        plus_buttons = [b for b in buttons if b._text == "+"]
        plus_buttons[0]._on_click()
        plus_buttons[0]._on_click()
        plus_buttons[0]._on_click()

        assert abs(game.audio.get_volume("master") - 0.8) < 0.01

    def test_no_bindings_still_works(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Settings screen works even with no bindings."""
        # Unbind all.
        for action in list(game.input.get_bindings()):
            game.input.unbind(action)

        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)
        game.tick(dt=0.016)  # Should not raise.

        # No binding buttons (just volume buttons and Back).
        buttons = []
        _find_buttons(settings._ui, buttons)
        binding_buttons = [b for b in buttons if b._text.startswith("[") and b._text.endswith("]")]
        assert len(binding_buttons) == 0

    def test_initial_volume_display(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Volume bars reflect current audio volume at construction."""
        game.audio.set_volume("music", 0.3)
        game.push(Scene())
        settings = _SettingsScene()
        game.push(settings)

        bar = settings._volume_bars["music"]
        assert abs(bar.value - 30.0) < 0.1

        label = settings._volume_labels["music"]
        assert label._text == "30%"
