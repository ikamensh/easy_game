"""HUD layer — persistent UI that renders above base scenes but below overlays.

The :class:`HUD` is owned lazily by :class:`~saga2d.game.Game`.  It wraps a
:class:`~saga2d.ui.component._UIRoot` and provides ``add`` / ``remove`` /
``clear`` methods for managing persistent UI elements (health bars, mini-maps,
resource counters, etc.).

Visibility logic:

*   The HUD draws when ``hud.visible`` is ``True`` **and** the top scene's
    ``show_hud`` class attribute is ``True``.
*   Overlay scenes (``MessageScreen``, ``ConfirmDialog``, etc.) typically set
    ``show_hud = False`` so the HUD disappears behind modals.

Draw order (handled by :meth:`SceneStack.draw`):

1.  Base scene content + its UI
2.  **HUD** (if visible and ``top.show_hud``)
3.  Transparent overlay scenes + their UIs

Input order (handled by :meth:`Game.tick`):

1.  **HUD** gets events first
2.  Scene UI
3.  ``scene.handle_input()``

Usage::

    # In game setup:
    game.hud.add(Label("Gold: 0", anchor=Anchor.TOP_RIGHT, margin=10))

    # Later, hide HUD during a cutscene overlay:
    game.hud.visible = False
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from saga2d.game import Game
    from saga2d.input import InputEvent
    from saga2d.ui.component import Component, _UIRoot


class HUD:
    """Persistent UI layer that renders above base scenes but below overlays.

    Parameters:
        game: The :class:`~saga2d.game.Game` instance that owns this HUD.
    """

    def __init__(self, game: Game) -> None:
        from saga2d.ui.component import _UIRoot

        self._game = game
        self._root: _UIRoot = _UIRoot(game)
        self.visible: bool = True

    # ------------------------------------------------------------------
    # Component management
    # ------------------------------------------------------------------

    def add(self, component: Component) -> None:
        """Add a UI component to the HUD."""
        self._root.add(component)

    def remove(self, component: Component) -> None:
        """Remove a UI component from the HUD."""
        self._root.remove(component)

    def clear(self) -> None:
        """Remove all components from the HUD."""
        for child in list(self._root._children):
            self._root.remove(child)

    # ------------------------------------------------------------------
    # Internal — called by Game.tick() and SceneStack.draw()
    # ------------------------------------------------------------------

    def _should_draw(self, top_scene_show_hud: bool) -> bool:
        """Return ``True`` if the HUD should be drawn this frame.

        The HUD is drawn when *both* ``self.visible`` and the top scene's
        ``show_hud`` attribute are ``True``.
        """
        return self.visible and top_scene_show_hud

    def _handle_event(self, event: InputEvent) -> bool:
        """Dispatch an input event through the HUD's component tree.

        Returns ``True`` if the event was consumed.
        """
        self._root._ensure_layout()
        return self._root.handle_event(event)

    def _update(self, dt: float) -> None:
        """Update the HUD's component tree (typewriter, tooltips, etc.)."""
        self._root._update_tree(dt)

    def _draw(self) -> None:
        """Lay out and draw the HUD's component tree."""
        self._root._ensure_layout()
        self._root.draw()
