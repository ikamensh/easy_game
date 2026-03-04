"""Tests for InputEvent, InputManager, and Game integration."""

import pytest

from saga2d import Game, Scene
from saga2d.backends.base import KeyEvent, MouseEvent
from saga2d.input import InputEvent, InputManager


# ==================================================================
# InputEvent dataclass
# ==================================================================


class TestInputEvent:
    """InputEvent is a frozen dataclass with correct defaults."""

    def test_keyboard_event(self) -> None:
        e = InputEvent(type="key_press", key="a", action="attack")
        assert e.type == "key_press"
        assert e.key == "a"
        assert e.action == "attack"
        assert e.x == 0
        assert e.y == 0

    def test_mouse_event(self) -> None:
        e = InputEvent(type="click", x=400, y=300, button="left")
        assert e.type == "click"
        assert e.x == 400
        assert e.y == 300
        assert e.button == "left"
        assert e.key is None
        assert e.action is None

    def test_frozen(self) -> None:
        e = InputEvent(type="key_press", key="a")
        with pytest.raises(AttributeError):
            e.key = "b"  # type: ignore[misc]

    def test_defaults(self) -> None:
        e = InputEvent(type="key_press")
        assert e.key is None
        assert e.action is None
        assert e.x == 0
        assert e.y == 0
        assert e.button is None
        assert e.dx == 0
        assert e.dy == 0

    def test_importable_from_saga2d(self) -> None:
        from saga2d import InputEvent as IE
        assert IE is InputEvent


# ==================================================================
# InputManager — default bindings
# ==================================================================


class TestInputManagerDefaults:
    """InputManager provides standard default bindings."""

    def test_confirm_bound_to_return(self) -> None:
        mgr = InputManager()
        bindings = mgr.get_bindings()
        assert bindings["confirm"] == "return"

    def test_cancel_bound_to_escape(self) -> None:
        mgr = InputManager()
        assert mgr.get_bindings()["cancel"] == "escape"

    def test_directional_defaults(self) -> None:
        mgr = InputManager()
        b = mgr.get_bindings()
        assert b["up"] == "up"
        assert b["down"] == "down"
        assert b["left"] == "left"
        assert b["right"] == "right"

    def test_six_default_bindings(self) -> None:
        mgr = InputManager()
        assert len(mgr.get_bindings()) == 6


# ==================================================================
# InputManager — translate()
# ==================================================================


class TestInputManagerTranslate:
    """translate() converts raw events to InputEvents with actions."""

    def test_key_press_with_action(self) -> None:
        """Key bound to an action → InputEvent.action is populated."""
        mgr = InputManager()
        raw = [KeyEvent(type="key_press", key="return")]
        result = mgr.translate(raw)

        assert len(result) == 1
        assert result[0].type == "key_press"
        assert result[0].key == "return"
        assert result[0].action == "confirm"

    def test_key_release_with_action(self) -> None:
        """key_release events also get the action mapping."""
        mgr = InputManager()
        raw = [KeyEvent(type="key_release", key="escape")]
        result = mgr.translate(raw)

        assert len(result) == 1
        assert result[0].type == "key_release"
        assert result[0].key == "escape"
        assert result[0].action == "cancel"

    def test_unmapped_key_has_none_action(self) -> None:
        """A key with no binding → action=None, key still available."""
        mgr = InputManager()
        raw = [KeyEvent(type="key_press", key="z")]
        result = mgr.translate(raw)

        assert len(result) == 1
        assert result[0].key == "z"
        assert result[0].action is None

    def test_mouse_click_passes_through(self) -> None:
        """Mouse events are translated with coords, button, action=None."""
        mgr = InputManager()
        raw = [MouseEvent(type="click", x=400, y=300, button="left")]
        result = mgr.translate(raw)

        assert len(result) == 1
        e = result[0]
        assert e.type == "click"
        assert e.x == 400
        assert e.y == 300
        assert e.button == "left"
        assert e.action is None

    def test_mouse_move_passes_through(self) -> None:
        mgr = InputManager()
        raw = [MouseEvent(type="move", x=500, y=600, button=None)]
        result = mgr.translate(raw)

        assert len(result) == 1
        assert result[0].type == "move"
        assert result[0].x == 500
        assert result[0].y == 600

    def test_mouse_scroll_preserves_deltas(self) -> None:
        mgr = InputManager()
        raw = [MouseEvent(type="scroll", x=100, y=200, button=None, dx=0, dy=-3)]
        result = mgr.translate(raw)

        assert len(result) == 1
        assert result[0].dx == 0
        assert result[0].dy == -3

    def test_mouse_drag_preserves_deltas(self) -> None:
        mgr = InputManager()
        raw = [MouseEvent(type="drag", x=300, y=400, button="left", dx=10, dy=-5)]
        result = mgr.translate(raw)

        assert len(result) == 1
        e = result[0]
        assert e.type == "drag"
        assert e.dx == 10
        assert e.dy == -5
        assert e.button == "left"

    def test_multiple_events(self) -> None:
        """translate() handles a list of mixed events."""
        mgr = InputManager()
        raw = [
            KeyEvent(type="key_press", key="return"),
            MouseEvent(type="click", x=100, y=200, button="left"),
            KeyEvent(type="key_release", key="return"),
        ]
        result = mgr.translate(raw)

        assert len(result) == 3
        assert result[0].action == "confirm"
        assert result[1].type == "click"
        assert result[2].action == "confirm"

    def test_empty_list(self) -> None:
        mgr = InputManager()
        assert mgr.translate([]) == []


# ==================================================================
# InputManager — bind / unbind
# ==================================================================


class TestInputManagerBindings:
    """bind() and unbind() modify the action mapping."""

    def test_custom_bind(self) -> None:
        """Binding a new action works."""
        mgr = InputManager()
        mgr.bind("attack", "a")

        raw = [KeyEvent(type="key_press", key="a")]
        result = mgr.translate(raw)
        assert result[0].action == "attack"

    def test_bind_replaces_old_key(self) -> None:
        """Re-binding an action to a new key removes the old binding."""
        mgr = InputManager()
        mgr.bind("confirm", "space")  # was "return"

        # Old key no longer maps.
        raw = [KeyEvent(type="key_press", key="return")]
        result = mgr.translate(raw)
        assert result[0].action is None

        # New key maps correctly.
        raw = [KeyEvent(type="key_press", key="space")]
        result = mgr.translate(raw)
        assert result[0].action == "confirm"

    def test_key_stealing(self) -> None:
        """Binding a new action to an already-bound key unbinds the old action."""
        mgr = InputManager()
        # "return" is bound to "confirm".
        mgr.bind("special_confirm", "return")

        # "confirm" should now be unbound.
        assert "confirm" not in mgr.get_bindings()

        # "return" maps to the new action.
        raw = [KeyEvent(type="key_press", key="return")]
        result = mgr.translate(raw)
        assert result[0].action == "special_confirm"

    def test_unbind_removes_action(self) -> None:
        """unbind() removes the binding; key produces action=None."""
        mgr = InputManager()
        mgr.unbind("confirm")

        raw = [KeyEvent(type="key_press", key="return")]
        result = mgr.translate(raw)
        assert result[0].action is None
        assert "confirm" not in mgr.get_bindings()

    def test_unbind_nonexistent_is_noop(self) -> None:
        """unbind() with unknown action doesn't crash."""
        mgr = InputManager()
        mgr.unbind("nonexistent")  # should not raise

    def test_get_bindings_returns_copy(self) -> None:
        """get_bindings() returns a copy, not the internal dict."""
        mgr = InputManager()
        b = mgr.get_bindings()
        b["hacked"] = "x"
        assert "hacked" not in mgr.get_bindings()


# ==================================================================
# Game integration — scenes receive InputEvent
# ==================================================================


class TestGameInputIntegration:
    """Scenes receive InputEvent objects (not raw KeyEvent/MouseEvent)."""

    def test_scene_receives_input_event(self) -> None:
        """Injected key event arrives as InputEvent with .action field."""
        game = Game("Test", backend="mock", resolution=(800, 600))

        class Tracker(Scene):
            def __init__(self) -> None:
                self.events: list = []

            def handle_input(self, event) -> bool:
                self.events.append(event)
                return False

        scene = Tracker()
        game.push(scene)
        game.backend.inject_key("return")
        game.tick(dt=0.016)

        assert len(scene.events) == 1
        e = scene.events[0]
        assert isinstance(e, InputEvent)
        assert e.type == "key_press"
        assert e.key == "return"
        assert e.action == "confirm"

    def test_scene_receives_unmapped_key(self) -> None:
        """Unmapped key arrives as InputEvent with action=None."""
        game = Game("Test", backend="mock", resolution=(800, 600))

        class Tracker(Scene):
            def __init__(self) -> None:
                self.events: list = []

            def handle_input(self, event) -> bool:
                self.events.append(event)
                return False

        scene = Tracker()
        game.push(scene)
        game.backend.inject_key("z")
        game.tick(dt=0.016)

        e = scene.events[0]
        assert isinstance(e, InputEvent)
        assert e.key == "z"
        assert e.action is None

    def test_scene_receives_mouse_as_input_event(self) -> None:
        """Injected mouse click arrives as InputEvent with coords."""
        game = Game("Test", backend="mock", resolution=(800, 600))

        class Tracker(Scene):
            def __init__(self) -> None:
                self.events: list = []

            def handle_input(self, event) -> bool:
                self.events.append(event)
                return False

        scene = Tracker()
        game.push(scene)
        game.backend.inject_click(400, 300)
        game.tick(dt=0.016)

        e = scene.events[0]
        assert isinstance(e, InputEvent)
        assert e.type == "click"
        assert e.x == 400
        assert e.y == 300
        assert e.button == "left"

    def test_custom_binding_via_game_input(self) -> None:
        """game.input.bind() changes what action scenes receive."""
        game = Game("Test", backend="mock", resolution=(800, 600))
        game.input.bind("attack", "a")

        class Tracker(Scene):
            def __init__(self) -> None:
                self.events: list = []

            def handle_input(self, event) -> bool:
                self.events.append(event)
                return False

        scene = Tracker()
        game.push(scene)
        game.backend.inject_key("a")
        game.tick(dt=0.016)

        assert scene.events[0].action == "attack"

    def test_window_close_still_works(self) -> None:
        """Window close events are handled before translation — game quits."""
        game = Game("Test", backend="mock", resolution=(800, 600))
        game.push(Scene())
        game.backend.inject_window_event("close")
        game.tick(dt=0.016)

        assert game.running is False

    def test_window_close_not_dispatched_to_scene(self) -> None:
        """Window close events are NOT forwarded to scene.handle_input."""
        game = Game("Test", backend="mock", resolution=(800, 600))

        class Tracker(Scene):
            def __init__(self) -> None:
                self.events: list = []

            def handle_input(self, event) -> bool:
                self.events.append(event)
                return False

        scene = Tracker()
        game.push(scene)
        game.backend.inject_window_event("close")
        game.tick(dt=0.016)

        # Scene should NOT receive the window event.
        assert len(scene.events) == 0

    def test_directional_actions_propagate(self) -> None:
        """Default directional bindings work end-to-end."""
        game = Game("Test", backend="mock", resolution=(800, 600))

        class Tracker(Scene):
            def __init__(self) -> None:
                self.actions: list[str | None] = []

            def handle_input(self, event) -> bool:
                self.actions.append(event.action)
                return False

        scene = Tracker()
        game.push(scene)
        for key in ("up", "down", "left", "right"):
            game.backend.inject_key(key)
        game.tick(dt=0.016)

        assert scene.actions == ["up", "down", "left", "right"]


# ==================================================================
# Edge cases — key stealing and binding replacement
# ==================================================================


class TestInputManagerEdgeCases:
    """Edge-case tests for InputManager binding behavior."""

    def test_bind_steals_key_from_other_action(self) -> None:
        """bind("a", "k1") then bind("b", "k1") — "a" is unbound, "b" gets k1."""
        mgr = InputManager()
        mgr.bind("a", "k1")
        mgr.bind("b", "k1")

        assert mgr.get_bindings().get("a") is None
        assert mgr.get_bindings().get("b") == "k1"

    def test_bind_replaces_key_for_old_action(self) -> None:
        """bind("a", "k1") then bind("a", "k2") — k1 is unbound, a gets k2."""
        mgr = InputManager()
        mgr.bind("a", "k1")
        mgr.bind("a", "k2")

        assert mgr.get_bindings().get("a") == "k2"
        # k1 should not be bound to any action
        bindings = mgr.get_bindings()
        assert "k1" not in bindings.values()
