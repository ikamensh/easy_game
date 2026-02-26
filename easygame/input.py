"""Input translation layer: raw backend events → action-mapped InputEvents.

:class:`InputEvent` is a frozen dataclass that unifies keyboard and mouse
events with an optional ``action`` field.  The ``action`` is populated by
:class:`InputManager`, which maintains a configurable key→action mapping.

Game code checks ``event.action`` for intent-based input::

    def handle_input(self, event: InputEvent) -> bool:
        if event.action == "confirm":
            self.select_current()
            return True

The ``InputManager`` is owned by :class:`~easygame.game.Game` and exposed
as ``game.input``.  It provides default bindings for common actions (confirm,
cancel, directional) and supports rebinding at runtime.

Multiple keys can be bound to the same action::

    game.input.bind("move_left", "left", "a")   # arrow key OR 'a'

Each key still maps to at most one action.  Binding a key that is already
bound to a *different* action steals it from the old action.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from easygame.backends.base import Event, KeyEvent, MouseEvent

if TYPE_CHECKING:
    from easygame.rendering.camera import Camera


# ---------------------------------------------------------------------------
# InputEvent — frozen dataclass, public
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InputEvent:
    """Translated input event with optional action mapping.

    For keyboard events::

        type: "key_press" | "key_release"
        key: raw key string (e.g. "a", "space", "return")
        action: mapped action (e.g. "confirm", "attack") or None

    For mouse events::

        type: "click" | "release" | "move" | "drag" | "scroll"
        x, y: logical coordinates (already converted by backend)
        button: "left" | "right" | "middle" | None
        dx, dy: drag/scroll deltas
        action: None (mouse events don't map to actions)
        world_x, world_y: camera-transformed coordinates (auto-populated)

    Attributes:
        type:     Event type string.
        key:      Raw key name for keyboard events, ``None`` for mouse.
        action:   Mapped action name, or ``None`` if no binding exists.
        x:        Logical x coordinate (mouse events).
        y:        Logical y coordinate (mouse events).
        button:   Mouse button name, or ``None``.
        dx:       Horizontal delta (drag/scroll).
        dy:       Vertical delta (drag/scroll).
        world_x:  Camera-transformed x coordinate, or ``None`` for non-mouse
                  events.  Populated automatically by the framework before
                  the event reaches :meth:`Scene.handle_input`.  When the
                  scene has a camera, equals ``camera.screen_to_world(x, y)[0]``.
                  When there is no camera, equals ``x``.
        world_y:  Camera-transformed y coordinate (see *world_x*).
    """

    type: str
    key: str | None = None
    action: str | None = None
    x: int = 0
    y: int = 0
    button: str | None = None
    dx: int = 0
    dy: int = 0
    world_x: float | None = None
    world_y: float | None = None


# Mouse event types that carry meaningful coordinates.
_MOUSE_EVENT_TYPES = frozenset({"click", "release", "move", "drag", "scroll"})


def _with_world_coords(
    event: InputEvent,
    camera: Camera | None,
) -> InputEvent:
    """Return *event* with ``world_x``/``world_y`` populated.

    * **Mouse events** — if *camera* is not ``None``, world coordinates are
      computed via ``camera.screen_to_world(event.x, event.y)``.  If *camera*
      is ``None`` (UI-only scene), world coordinates equal screen coordinates.
    * **Non-mouse events** — returned unchanged (``world_x``/``world_y`` stay
      ``None``).

    This is called by :meth:`Game.tick` before dispatching to scenes so that
    game code never needs to call ``camera.screen_to_world`` manually.
    """
    if event.type not in _MOUSE_EVENT_TYPES:
        return event
    if camera is not None:
        wx, wy = camera.screen_to_world(event.x, event.y)
    else:
        wx = float(event.x)
        wy = float(event.y)
    return replace(event, world_x=wx, world_y=wy)


# ---------------------------------------------------------------------------
# InputManager — internal, accessed via game.input
# ---------------------------------------------------------------------------


class InputManager:
    """Translates raw backend events into :class:`InputEvent` objects.

    Maintains a many-to-one key→action mapping: multiple keys can trigger
    the same action, but each key maps to at most one action.

    Default bindings::

        confirm → return
        cancel  → escape
        up      → up
        down    → down
        left    → left
        right   → right
    """

    def __init__(self) -> None:
        self._key_to_action: dict[str, str] = {}
        self._action_to_keys: dict[str, list[str]] = {}
        self._setup_defaults()

    # ------------------------------------------------------------------
    # Binding API
    # ------------------------------------------------------------------

    def bind(self, action: str, *keys: str) -> None:
        """Bind *action* to one or more *keys*.

        Replaces any previous binding for *action*.  If a key is already
        bound to a *different* action, it is stolen (the old action loses
        that key).

        Examples::

            game.input.bind("confirm", "return")          # single key
            game.input.bind("move_left", "left", "a")     # two keys
        """
        if not keys:
            raise ValueError("bind() requires at least one key")

        # Remove all old keys for this action.
        old_keys = self._action_to_keys.pop(action, [])
        for old_key in old_keys:
            self._key_to_action.pop(old_key, None)

        # Steal keys from any other actions that had them.
        new_keys: list[str] = []
        for key in keys:
            old_action = self._key_to_action.pop(key, None)
            if old_action is not None and old_action != action:
                # Remove this key from the old action's key list.
                old_action_keys = self._action_to_keys.get(old_action, [])
                if key in old_action_keys:
                    old_action_keys.remove(key)
                # If the old action has no keys left, remove it entirely.
                if not old_action_keys:
                    self._action_to_keys.pop(old_action, None)

            self._key_to_action[key] = action
            new_keys.append(key)

        self._action_to_keys[action] = new_keys

    def unbind(self, action: str) -> None:
        """Remove all bindings for *action*.  No-op if not bound."""
        keys = self._action_to_keys.pop(action, [])
        for key in keys:
            self._key_to_action.pop(key, None)

    def get_bindings(self) -> dict[str, list[str]]:
        """Return a copy of the current action→keys mapping.

        Each value is a list of key strings (may have one or more entries).
        """
        return {action: list(keys) for action, keys in self._action_to_keys.items()}

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    def translate(self, raw_events: list[Event]) -> list[InputEvent]:
        """Translate a list of raw backend events into :class:`InputEvent` s.

        :class:`WindowEvent` objects are **not** translated — they are
        handled by the framework before this method is called and should
        not appear in *raw_events*.
        """
        result: list[InputEvent] = []
        for event in raw_events:
            if isinstance(event, KeyEvent):
                action = self._key_to_action.get(event.key)
                result.append(
                    InputEvent(
                        type=event.type,
                        key=event.key,
                        action=action,
                    )
                )
            elif isinstance(event, MouseEvent):
                result.append(
                    InputEvent(
                        type=event.type,
                        x=event.x,
                        y=event.y,
                        button=event.button,
                        dx=event.dx,
                        dy=event.dy,
                    )
                )
            # WindowEvent is intentionally skipped — handled by Game.tick().
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _setup_defaults(self) -> None:
        """Install the default action bindings."""
        self.bind("confirm", "return")
        self.bind("cancel", "escape")
        self.bind("up", "up")
        self.bind("down", "down")
        self.bind("left", "left")
        self.bind("right", "right")
