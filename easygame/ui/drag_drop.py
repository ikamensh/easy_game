"""Drag-and-drop system — DragManager coordinates drag sessions within a scene's UI tree.

A :class:`DragManager` is owned by :class:`~easygame.ui.component._UIRoot`
(created lazily) and intercepts input events during an active drag.  It
provides:

* **Ghost rendering** — a semi-transparent copy of the dragged component
  follows the cursor.
* **Drop target feedback** — green/red overlays on components that accept or
  reject the dragged data.

Drag-and-drop uses four attributes on :class:`~easygame.ui.component.Component`:

* ``draggable`` (bool) — can this component be dragged?
* ``drag_data`` (Any) — opaque payload from source to target.
* ``drop_accept`` (callable) — if not None, component can receive drops.
* ``on_drop`` (callable) — fires when a valid drop lands on this component.

Usage::

    slot = ImageBox(icon, draggable=True, drag_data=item)
    grid = Grid(
        columns=4, rows=3,
        drop_accept=lambda data: isinstance(data, Item),
        on_drop=lambda comp, data: equip_item(comp, data),
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from easygame.input import InputEvent
    from easygame.ui.component import Component, _UIRoot


# ---------------------------------------------------------------------------
# Internal drag session state
# ---------------------------------------------------------------------------


@dataclass
class _DragSession:
    """Bookkeeping for one active drag operation."""

    source: Component  # the component being dragged
    data: Any  # the drag_data payload
    start_x: int  # mouse-down position
    start_y: int
    ghost_x: int  # current ghost top-left position
    ghost_y: int
    ghost_offset_x: int  # offset from cursor to ghost top-left
    ghost_offset_y: int
    current_target: Component | None  # component under cursor with drop_accept
    target_accepts: bool  # result of drop_accept(data) on current_target


# ---------------------------------------------------------------------------
# DragManager
# ---------------------------------------------------------------------------


class DragManager:
    """Coordinates drag-and-drop sessions within a scene's UI tree.

    Owned by :class:`_UIRoot`.  During an active drag, all input events
    are intercepted by :meth:`handle_event` — the normal component dispatch
    is bypassed.
    """

    def __init__(self, ui_root: _UIRoot) -> None:
        self._root: _UIRoot = ui_root
        self._active: _DragSession | None = None

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def is_dragging(self) -> bool:
        """``True`` while a drag session is in progress."""
        return self._active is not None

    @property
    def drag_data(self) -> Any | None:
        """The dragged data payload, or ``None`` if not dragging."""
        return self._active.data if self._active is not None else None

    # ------------------------------------------------------------------
    # Event handling during drag
    # ------------------------------------------------------------------

    def handle_event(self, event: InputEvent) -> bool:
        """Process *event* during an active drag.

        Returns ``True`` if consumed (always ``True`` during drag — all
        events are captured).

        Handles:

        * ``"move"`` / ``"drag"`` — update ghost position, find drop target.
        * ``"release"`` — drop on target (if valid) or cancel.
        * ``"key_press"`` with ``action="cancel"`` — cancel drag.
        """
        if self._active is None:
            return False

        session = self._active

        if event.type in ("move", "drag"):
            # Update ghost position to follow cursor.
            session.ghost_x = event.x + session.ghost_offset_x
            session.ghost_y = event.y + session.ghost_offset_y
            # Find the drop target under the cursor.
            target = self._find_drop_target(event.x, event.y)
            session.current_target = target
            if target is not None and target.drop_accept is not None:
                session.target_accepts = target.drop_accept(session.data)
            else:
                session.target_accepts = False
            return True

        if event.type == "release":
            self._end_drag(event.x, event.y)
            return True

        if event.type == "key_press" and event.action == "cancel":
            self._cancel_drag()
            return True

        # All other events are swallowed during drag (no pass-through).
        return True

    # ------------------------------------------------------------------
    # Drag lifecycle (internal — called by Component and self)
    # ------------------------------------------------------------------

    def _start_drag(
        self,
        source: Component,
        data: Any,
        x: int,
        y: int,
    ) -> None:
        """Begin a drag session from *source* at click position ``(x, y)``."""
        # Ghost offset: cursor was at (x, y), ghost top-left is at
        # the source's computed position.  This keeps the ghost aligned
        # with where the user clicked relative to the component.
        ghost_offset_x = source._computed_x - x
        ghost_offset_y = source._computed_y - y

        self._active = _DragSession(
            source=source,
            data=data,
            start_x=x,
            start_y=y,
            ghost_x=source._computed_x,
            ghost_y=source._computed_y,
            ghost_offset_x=ghost_offset_x,
            ghost_offset_y=ghost_offset_y,
            current_target=None,
            target_accepts=False,
        )

    def _end_drag(self, x: int, y: int) -> None:
        """Complete or cancel the drag at release position ``(x, y)``."""
        if self._active is None:
            return

        session = self._active

        # Re-evaluate the target at the release point.
        target = self._find_drop_target(x, y)
        if (
            target is not None
            and target.drop_accept is not None
            and target.drop_accept(session.data)
            and target.on_drop is not None
        ):
            target.on_drop(target, session.data)

        self._active = None

    def cancel_active(self) -> None:
        """Cancel any active drag session.

        Called externally (e.g. when the UI root is being torn down) to
        ensure no stale drag state lingers.
        """
        self._active = None

    def _cancel_drag(self) -> None:
        """Abort the drag without dropping."""
        self._active = None

    # ------------------------------------------------------------------
    # Drop target hit-testing
    # ------------------------------------------------------------------

    def _find_drop_target(self, x: int, y: int) -> Component | None:
        """Walk the UI tree to find the deepest component at ``(x, y)``
        that has ``drop_accept`` set.  Skip the drag source itself.
        """
        if self._active is None:
            return None
        return self._walk_for_target(self._root, x, y)

    def _walk_for_target(
        self,
        comp: Component,
        x: int,
        y: int,
    ) -> Component | None:
        """Recursive depth-first search for the deepest drop target."""
        if not comp.visible or not comp.enabled:
            return None
        if not comp.hit_test(x, y):
            return None

        # Check children deepest-first (reverse for front-most priority).
        for child in reversed(comp._children):
            found = self._walk_for_target(child, x, y)
            if found is not None:
                return found

        # This component itself?
        if (
            self._active is not None
            and comp.drop_accept is not None
            and comp is not self._active.source
        ):
            return comp

        return None

    # ------------------------------------------------------------------
    # Ghost and overlay rendering
    # ------------------------------------------------------------------

    def _draw_ghost(self) -> None:
        """Draw the drag ghost and drop target highlight overlay.

        Called by :meth:`_UIRoot.draw` after all children have been drawn.
        """
        if self._active is None:
            return

        session = self._active
        game = self._root._game
        if game is None:
            return

        backend = game._backend
        theme = game.theme
        ghost_opacity = theme.ghost_opacity

        src = session.source

        # Draw the ghost image (semi-transparent copy of the source).
        if hasattr(src, "_image_handle") and src._image_handle is not None:
            backend.draw_image(
                src._image_handle,
                session.ghost_x,
                session.ghost_y,
                src._computed_w,
                src._computed_h,
                opacity=ghost_opacity,
            )
        else:
            # Fallback: semi-transparent rect matching source bounds.
            backend.draw_rect(
                session.ghost_x,
                session.ghost_y,
                src._computed_w,
                src._computed_h,
                (180, 180, 180, 128),
                opacity=ghost_opacity,
            )

        # Draw drop target highlight.
        if session.current_target is not None:
            target = session.current_target
            if session.target_accepts:
                color = theme.drop_accept_color
            else:
                color = theme.drop_reject_color
            backend.draw_rect(
                target._computed_x,
                target._computed_y,
                target._computed_w,
                target._computed_h,
                color,
            )
