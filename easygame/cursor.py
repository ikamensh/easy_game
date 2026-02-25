"""CursorManager — manages the mouse cursor appearance.

Loads cursor images from assets and switches between them.
Game code uses ``game.cursor.set("attack")`` to change the cursor.
"""

from __future__ import annotations

from typing import Any


class CursorManager:
    """Manages the mouse cursor appearance.

    Loads cursor images from assets and switches between them.
    The game sets ``game.cursor.set("name")`` to change the cursor.
    """

    def __init__(self, backend: Any, assets: Any) -> None:
        self._backend = backend
        self._assets = assets
        self._current: str = "default"
        self._cursors: dict[str, tuple[Any, tuple[int, int]]] = {}
        # name -> (image_handle, (hotspot_x, hotspot_y))

    def register(
        self,
        name: str,
        image_name: str,
        hotspot: tuple[int, int] = (0, 0),
    ) -> None:
        """Register a custom cursor from an asset image.

        Parameters:
            name:        Cursor name for use with :meth:`set`.
            image_name:  Asset name for the cursor image.
            hotspot:     Pixel offset within the cursor image for the click point.
        """
        handle = self._assets.image(image_name)
        self._cursors[name] = (handle, (hotspot[0], hotspot[1]))

    def set(self, name: str) -> None:
        """Switch to a registered cursor.

        ``"default"`` restores the system cursor (no custom image).
        Raises :exc:`KeyError` if the name is not registered and not ``"default"``.
        """
        if name == "default":
            self._backend.set_cursor(None)
            self._current = "default"
            return
        if name not in self._cursors:
            raise KeyError(
                f"Cursor '{name}' not registered. Use register() first."
            )
        handle, (hx, hy) = self._cursors[name]
        self._backend.set_cursor(handle, hx, hy)
        self._current = name

    def set_visible(self, visible: bool) -> None:
        """Show or hide the mouse cursor."""
        self._backend.set_cursor_visible(visible)

    @property
    def current(self) -> str:
        """Name of the current cursor."""
        return self._current
