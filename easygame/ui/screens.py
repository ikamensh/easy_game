"""Convenience screens — reusable Scene subclasses for common UI flows.

All screens are transparent overlay scenes pushed onto the scene stack.
They build their UI in :meth:`on_enter` using the existing component system.

*   :class:`MessageScreen` — full-screen text with "press any key to continue".
*   :class:`ChoiceScreen` — prompt with a vertical list of button choices.
*   :class:`ConfirmDialog` — Yes / No confirmation dialog.
*   :class:`SaveLoadScreen` — save/load slot selection.
*   :class:`_SequenceRunner` — internal helper for :meth:`Game.show_sequence`.
*   :class:`_SettingsScene` — internal settings screen for
    :meth:`Game.push_settings`.

Usage::

    game.push(MessageScreen("Welcome!", on_dismiss=lambda: print("OK")))

    game.push(ChoiceScreen(
        "Pick a class:",
        ["Warrior", "Mage", "Rogue"],
        on_choice=lambda i: print(f"Chose {i}"),
    ))

    game.push(ConfirmDialog(
        "Overwrite save?",
        on_confirm=lambda: game.save(1),
        on_cancel=lambda: print("cancelled"),
    ))
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from easygame.input import InputEvent
from easygame.scene import Scene
from easygame.ui.components import Button, Label, Panel
from easygame.ui.layout import Anchor, Layout
from easygame.ui.theme import Style
from easygame.ui.widgets import ProgressBar

if TYPE_CHECKING:
    from easygame.save import SaveManager


# ---------------------------------------------------------------------------
# MessageScreen
# ---------------------------------------------------------------------------


class MessageScreen(Scene):
    """Full-screen text overlay that dismisses on any key press or click.

    Parameters:
        text:       The message text to display (centred on screen).
        on_dismiss: Optional callback fired just before popping.
    """

    transparent = True
    show_hud = False

    def __init__(
        self,
        text: str,
        *,
        on_dismiss: Callable[[], Any] | None = None,
    ) -> None:
        self._text = text
        self._on_dismiss = on_dismiss

    def on_enter(self) -> None:
        # Semi-transparent dark background.
        bg = Panel(
            anchor=Anchor.CENTER,
            style=Style(background_color=(0, 0, 0, 160), padding=40),
            layout=Layout.VERTICAL,
            spacing=20,
        )
        # Main text.
        bg.add(
            Label(
                self._text,
                style=Style(text_color=(240, 240, 240, 255), font_size=28),
            )
        )
        # Hint at bottom.
        bg.add(
            Label(
                "Press any key...",
                style=Style(text_color=(180, 180, 180, 200), font_size=18),
            )
        )
        self.ui.add(bg)

    def handle_input(self, event: InputEvent) -> bool:
        """Dismiss on any key press or mouse click.  Consume all events."""
        if event.type in ("key_press", "click"):
            self._dismiss()
        # Consume ALL events — modal.
        return True

    def _dismiss(self) -> None:
        if self._on_dismiss is not None:
            self._on_dismiss()
        self.game.pop()


# ---------------------------------------------------------------------------
# ChoiceScreen
# ---------------------------------------------------------------------------


class ChoiceScreen(Scene):
    """Prompt with a vertical list of button choices.

    Parameters:
        prompt:    The question/prompt text.
        choices:   List of choice label strings.
        on_choice: Callback receiving the chosen index (0-based).
                   Not called if the user presses Escape.
    """

    transparent = True
    show_hud = False

    def __init__(
        self,
        prompt: str,
        choices: list[str],
        *,
        on_choice: Callable[[int], Any] | None = None,
    ) -> None:
        self._prompt = prompt
        self._choices = list(choices)
        self._on_choice = on_choice

    def on_enter(self) -> None:
        container = Panel(
            anchor=Anchor.CENTER,
            style=Style(background_color=(0, 0, 0, 180), padding=30),
            layout=Layout.VERTICAL,
            spacing=12,
        )
        # Prompt label.
        container.add(
            Label(
                self._prompt,
                style=Style(text_color=(240, 240, 240, 255), font_size=26),
            )
        )
        # Choice buttons.
        for i, text in enumerate(self._choices):
            idx = i  # capture for closure

            def make_handler(index: int) -> Callable[[], None]:
                def handler() -> None:
                    self._select(index)

                return handler

            container.add(Button(text, on_click=make_handler(idx)))
        self.ui.add(container)

    def handle_input(self, event: InputEvent) -> bool:
        """Number keys select choices; Escape cancels.  Consume all events."""
        if event.type == "key_press":
            if event.key == "escape" or event.action == "cancel":
                self.game.pop()
                return True
            # Number key shortcuts: "1"–"9" select index 0–8.
            if event.key and len(event.key) == 1 and event.key.isdigit():
                digit = int(event.key)
                if 1 <= digit <= len(self._choices):
                    self._select(digit - 1)
                    return True
        # Consume ALL events — modal.
        return True

    def _select(self, index: int) -> None:
        if self._on_choice is not None:
            self._on_choice(index)
        self.game.pop()


# ---------------------------------------------------------------------------
# ConfirmDialog
# ---------------------------------------------------------------------------


class ConfirmDialog(Scene):
    """Yes/No confirmation dialog.

    Parameters:
        question:   The question text.
        on_confirm: Callback fired when Yes is chosen (or Enter pressed).
        on_cancel:  Callback fired when No is chosen (or Escape pressed).
    """

    transparent = True
    show_hud = False

    def __init__(
        self,
        question: str,
        *,
        on_confirm: Callable[[], Any] | None = None,
        on_cancel: Callable[[], Any] | None = None,
    ) -> None:
        self._question = question
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel

    def on_enter(self) -> None:
        container = Panel(
            anchor=Anchor.CENTER,
            style=Style(background_color=(0, 0, 0, 180), padding=30),
            layout=Layout.VERTICAL,
            spacing=20,
        )
        # Question text.
        container.add(
            Label(
                self._question,
                style=Style(text_color=(240, 240, 240, 255), font_size=26),
            )
        )
        # Button row.
        button_row = Panel(layout=Layout.HORIZONTAL, spacing=20)
        button_row.add(Button("Yes", on_click=self._confirm))
        button_row.add(Button("No", on_click=self._cancel))
        container.add(button_row)
        self.ui.add(container)

    def handle_input(self, event: InputEvent) -> bool:
        """Enter confirms, Escape cancels.  Consume all events."""
        if event.type == "key_press":
            if event.key == "return" or event.action == "confirm":
                self._confirm()
                return True
            if event.key == "escape" or event.action == "cancel":
                self._cancel()
                return True
        # Consume ALL events — modal.
        return True

    def _confirm(self) -> None:
        if self._on_confirm is not None:
            self._on_confirm()
        self.game.pop()

    def _cancel(self) -> None:
        if self._on_cancel is not None:
            self._on_cancel()
        self.game.pop()


# ---------------------------------------------------------------------------
# SaveLoadScreen
# ---------------------------------------------------------------------------


class SaveLoadScreen(Scene):
    """Save/Load slot selection screen.

    Displays a list of save slots with metadata.  In ``"save"`` mode,
    clicking any slot (empty or occupied) saves to it.  In ``"load"``
    mode, clicking an empty slot does nothing.

    Parameters:
        mode:         ``"save"`` or ``"load"``.
        save_manager: The :class:`SaveManager` to read/write slots.
        on_save:      Callback receiving the slot number after a save.
        on_load:      Callback receiving ``(slot, data)`` after a load.
        slot_count:   Number of slots to display (default 10).
    """

    transparent = True
    show_hud = False

    def __init__(
        self,
        mode: str = "load",
        *,
        save_manager: SaveManager | None = None,
        on_save: Callable[[int], Any] | None = None,
        on_load: Callable[[int, dict[str, Any]], Any] | None = None,
        slot_count: int = 10,
    ) -> None:
        if mode not in ("save", "load"):
            raise ValueError(f"mode must be 'save' or 'load', got {mode!r}")
        self._mode = mode
        self._save_manager_override = save_manager
        self._on_save = on_save
        self._on_load = on_load
        self._slot_count = slot_count

    @property
    def _save_manager(self) -> SaveManager:
        """Resolve the save manager: explicit override or game's default."""
        if self._save_manager_override is not None:
            return self._save_manager_override
        return self.game.save_manager

    def on_enter(self) -> None:
        slots = self._save_manager.list_slots(self._slot_count)

        container = Panel(
            anchor=Anchor.CENTER,
            style=Style(background_color=(0, 0, 0, 180), padding=20),
            layout=Layout.VERTICAL,
            spacing=8,
        )

        # Title.
        title_text = "Save Game" if self._mode == "save" else "Load Game"
        container.add(
            Label(
                title_text,
                style=Style(text_color=(240, 240, 240, 255), font_size=28),
            )
        )

        # Slot buttons.
        for i, slot_data in enumerate(slots):
            slot_num = i + 1  # 1-indexed
            if slot_data is not None:
                ts = slot_data.get("timestamp", "")
                # Truncate to date + time (remove microseconds/timezone).
                if "T" in ts:
                    ts = ts.split("T")[0] + " " + ts.split("T")[1][:8]
                label = f"Slot {slot_num} — {ts}"
            else:
                label = f"Slot {slot_num} — Empty"

            def make_handler(
                num: int, data: dict[str, Any] | None
            ) -> Callable[[], None]:
                def handler() -> None:
                    self._on_slot_click(num, data)

                return handler

            container.add(Button(label, on_click=make_handler(slot_num, slot_data)))

        # Back button.
        container.add(Button("Back", on_click=self._back))
        self.ui.add(container)

    def handle_input(self, event: InputEvent) -> bool:
        """Escape pops.  Consume all events — modal."""
        if event.type == "key_press":
            if event.key == "escape" or event.action == "cancel":
                self.game.pop()
                return True
        return True

    def _on_slot_click(self, slot: int, data: dict[str, Any] | None) -> None:
        if self._mode == "save":
            # Save the state of the scene *below* this overlay, not
            # the SaveLoadScreen itself.  Walk down the stack to find
            # the first non-SaveLoadScreen scene.
            stack = self.game._scene_stack._stack
            target_scene = None
            for s in reversed(stack):
                if s is not self:
                    target_scene = s
                    break
            if target_scene is not None:
                state = target_scene.get_save_state()
                class_name = type(target_scene).__name__
                self._save_manager.save(slot, state, class_name)
            if self._on_save is not None:
                self._on_save(slot)
            self.game.pop()
        else:
            # Load mode: only act on non-empty slots.
            if data is not None:
                loaded = self._save_manager.load(slot)
                if loaded is not None and self._on_load is not None:
                    self._on_load(slot, loaded)
                self.game.pop()

    def _back(self) -> None:
        self.game.pop()


# ---------------------------------------------------------------------------
# _SequenceRunner — internal helper for game.show_sequence()
# ---------------------------------------------------------------------------


class _SequenceRunner(Scene):
    """Internal scene that chains a series of :class:`MessageScreen` pushes.

    Sits below the message screens on the stack.  Each time a screen is
    dismissed and popped, ``on_reveal()`` fires on the runner, which then
    pushes the next screen.  When all screens are exhausted, it fires the
    ``on_complete`` callback and pops itself.

    Not exported — accessed only via :meth:`Game.show_sequence`.
    """

    transparent = True
    show_hud = False

    def __init__(
        self,
        screens: list[MessageScreen],
        on_complete: Callable[[], Any] | None = None,
    ) -> None:
        self._screens = list(screens)
        self._on_complete = on_complete
        self._index = 0

    def on_enter(self) -> None:
        # Push the first screen immediately.
        if self._screens:
            self.game.push(self._screens[self._index])
            self._index += 1
        else:
            # No screens at all — fire completion and pop.
            self._finish()

    def on_reveal(self) -> None:
        """Called when the screen above us is popped (dismissed).

        Push the next screen, or finish if all have been shown.
        """
        if self._index < len(self._screens):
            self.game.push(self._screens[self._index])
            self._index += 1
        else:
            self._finish()

    def _finish(self) -> None:
        if self._on_complete is not None:
            self._on_complete()
        self.game.pop()


# ---------------------------------------------------------------------------
# _SettingsScene — internal helper for game.push_settings()
# ---------------------------------------------------------------------------

_VOLUME_STEP: float = 0.1
_VOLUME_CHANNELS: list[tuple[str, str]] = [
    ("master", "Master"),
    ("music", "Music"),
    ("sfx", "SFX"),
    ("ui", "UI"),
]


class _SettingsScene(Scene):
    """Built-in settings screen with audio volume and key rebinding.

    Pushed via :meth:`Game.push_settings`.  Uses the game's current theme.
    Reads/writes ``game.audio`` volume channels and ``game.input`` bindings.

    Not exported — accessed only via :meth:`Game.push_settings`.
    """

    transparent = True
    show_hud = False

    def __init__(self) -> None:
        self._listening_action: str | None = None
        self._listening_button: Button | None = None
        self._volume_bars: dict[str, ProgressBar] = {}
        self._volume_labels: dict[str, Label] = {}

    def on_enter(self) -> None:
        container = Panel(
            anchor=Anchor.CENTER,
            style=Style(background_color=(0, 0, 0, 180), padding=30),
            layout=Layout.VERTICAL,
            spacing=12,
        )

        # Title.
        container.add(
            Label(
                "Settings",
                style=Style(text_color=(240, 240, 240, 255), font_size=28),
            )
        )

        # --- Volume controls ---
        container.add(
            Label(
                "Volume",
                style=Style(text_color=(200, 200, 200, 255), font_size=22),
            )
        )
        for channel, display_name in _VOLUME_CHANNELS:
            row = Panel(layout=Layout.HORIZONTAL, spacing=8)

            # Channel label.
            row.add(
                Label(
                    display_name,
                    style=Style(
                        text_color=(200, 200, 200, 255),
                        font_size=18,
                    ),
                    width=80,
                )
            )

            # Minus button.
            def make_vol_handler(ch: str, delta: float) -> Callable[[], None]:
                def handler() -> None:
                    self._adjust_volume(ch, delta)

                return handler

            row.add(Button("−", on_click=make_vol_handler(channel, -_VOLUME_STEP)))

            # ProgressBar (display only).
            current = self.game.audio.get_volume(channel)
            bar = ProgressBar(
                value=current * 100,
                max_value=100,
                width=150,
                height=20,
            )
            self._volume_bars[channel] = bar
            row.add(bar)

            # Plus button.
            row.add(Button("+", on_click=make_vol_handler(channel, _VOLUME_STEP)))

            # Numeric label.
            vol_label = Label(
                f"{int(current * 100)}%",
                style=Style(text_color=(200, 200, 200, 255), font_size=18),
                width=50,
            )
            self._volume_labels[channel] = vol_label
            row.add(vol_label)

            container.add(row)

        # --- Key bindings ---
        container.add(
            Label(
                "Key Bindings",
                style=Style(text_color=(200, 200, 200, 255), font_size=22),
            )
        )
        bindings = self.game.input.get_bindings()
        for action, keys in sorted(bindings.items()):
            row = Panel(layout=Layout.HORIZONTAL, spacing=8)

            row.add(
                Label(
                    action,
                    style=Style(
                        text_color=(200, 200, 200, 255),
                        font_size=18,
                    ),
                    width=120,
                )
            )

            def make_rebind_handler(
                act: str, btn_ref: list[Button | None]
            ) -> Callable[[], None]:
                def handler() -> None:
                    b = btn_ref[0]
                    if b is not None:
                        self._start_listening(act, b)

                return handler

            # We need the button reference for the closure.
            # Display the primary (first) key; rebinding replaces all keys.
            display_key = keys[0] if keys else "?"
            btn_ref: list[Button | None] = [None]
            btn = Button(
                f"[{display_key.upper()}]",
                on_click=make_rebind_handler(action, btn_ref),
            )
            btn_ref[0] = btn
            row.add(btn)

            container.add(row)

        # --- Back button ---
        container.add(Button("Back", on_click=self._back))
        self.ui.add(container)

    def handle_input(self, event: InputEvent) -> bool:
        """Handle key rebinding in listening mode.  Consume all events."""
        if event.type == "key_press":
            if self._listening_action is not None:
                # Escape cancels rebinding.
                if event.key == "escape":
                    self._cancel_listening()
                    return True
                # Rebind the action to the pressed key.
                # event.key is always set for key_press events.
                assert event.key is not None
                self.game.input.bind(self._listening_action, event.key)
                if self._listening_button is not None:
                    self._listening_button.text = f"[{event.key.upper()}]"
                self._listening_action = None
                self._listening_button = None
                return True
            # Escape pops the settings screen.
            if event.key == "escape" or event.action == "cancel":
                self.game.pop()
                return True
        # Consume ALL events — modal.
        return True

    def _adjust_volume(self, channel: str, delta: float) -> None:
        """Adjust a channel's volume by *delta* and update the UI."""
        current = self.game.audio.get_volume(channel)
        new_level = max(0.0, min(1.0, current + delta))
        self.game.audio.set_volume(channel, new_level)
        # Update the progress bar.
        if channel in self._volume_bars:
            self._volume_bars[channel].value = new_level * 100
        # Update the label.
        if channel in self._volume_labels:
            self._volume_labels[channel].text = f"{int(round(new_level * 100))}%"

    def _start_listening(self, action: str, button: Button) -> None:
        """Enter listening mode for key rebinding."""
        # If already listening for a different action, cancel the old one.
        if self._listening_action is not None:
            self._cancel_listening()
        self._listening_action = action
        self._listening_button = button
        button.text = "[...]"

    def _cancel_listening(self) -> None:
        """Cancel listening mode and restore the button label."""
        if self._listening_button is not None and self._listening_action is not None:
            # Restore the button text to the current binding.
            bindings = self.game.input.get_bindings()
            keys = bindings.get(self._listening_action, [])
            current_key = keys[0] if keys else "?"
            self._listening_button.text = f"[{current_key.upper()}]"
        self._listening_action = None
        self._listening_button = None

    def _back(self) -> None:
        self.game.pop()
