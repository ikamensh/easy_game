"""Additional UI widgets.

*   :class:`ImageBox` — displays an image via ``draw_image``.
*   :class:`ProgressBar` — horizontal filled bar via ``draw_rect``.
*   :class:`TextBox` — multi-line text with word wrapping and optional
    typewriter reveal.
*   :class:`List` — scrollable list of selectable text items with
    keyboard navigation.
*   :class:`Grid` — grid of fixed-size cells, each optionally holding a
    child component.  Click to select.
*   :class:`Tooltip` — hover popup that appears after a delay, follows
    the mouse, and renders on top.
*   :class:`TabGroup` — tabbed container that switches between content
    components via clickable tab headers.
*   :class:`DataTable` — rows of data with column headers, alternating
    row colours, and click-to-select.

All inherit from :class:`~saga2d.ui.component.Component` and support
theming via the Theme system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from saga2d.ui.component import Component
from saga2d.ui.components import _estimate_text_width
from saga2d.ui.theme import ResolvedStyle, Style

if TYPE_CHECKING:
    from saga2d.input import InputEvent

# RGBA tuple
Color = tuple[int, int, int, int]


class ImageBox(Component):
    """Display an image in the UI component tree.

    Used for character portraits, item icons, etc. The image is resolved
    via ``game.assets.image(image_name)`` and drawn at the component's
    computed bounds.

    Parameters:
        image_name: Asset name resolved via ``game.assets.image()``.
        width:      Display width in pixels.
        height:     Display height in pixels.
        style:      Explicit :class:`Style` overrides (padding, border).
        **kwargs:   Forwarded to :class:`Component`.
    """

    def __init__(
        self,
        image_name: str,
        *,
        width: int = 64,
        height: int = 64,
        style: Style | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(width=width, height=height, style=style, **kwargs)
        self._image_name = image_name
        self._image_handle: Any = None

    @property
    def image_name(self) -> str:
        """The asset name of the displayed image."""
        return self._image_name

    @image_name.setter
    def image_name(self, value: str) -> None:
        if value != self._image_name:
            self._image_name = value
            self._image_handle = None
            self._mark_layout_dirty()

    def get_preferred_size(self) -> tuple[int, int]:
        return (self._width or 64, self._height or 64)

    def on_draw(self) -> None:
        if self._game is None:
            return
        if self._image_handle is None:
            self._image_handle = self._game.assets.image(self._image_name)
        self._game._backend.draw_image(
            self._image_handle,
            self._computed_x,
            self._computed_y,
            self._computed_w,
            self._computed_h,
        )


class ProgressBar(Component):
    """Horizontal bar showing value/max_value as a filled proportion.

    Draws a background track and a filled bar. Uses ``draw_rect`` only.

    Parameters:
        value:     Current value (0 to max_value).
        max_value: Maximum value (default 100).
        width:     Bar width in pixels.
        height:    Bar height in pixels.
        bar_color: Fill color. ``None`` uses theme default.
        bg_color:  Background/track color. ``None`` uses theme default.
        style:     Explicit :class:`Style` overrides.
        **kwargs:  Forwarded to :class:`Component`.
    """

    def __init__(
        self,
        value: float = 0,
        max_value: float = 100,
        *,
        width: int = 200,
        height: int = 24,
        bar_color: Color | None = None,
        bg_color: Color | None = None,
        style: Style | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(width=width, height=height, style=style, **kwargs)
        self._value = value
        self._max_value = max_value
        self._bar_color = bar_color
        self._bg_color = bg_color

    @property
    def value(self) -> float:
        """Current value (0 to max_value)."""
        return self._value

    @value.setter
    def value(self, v: float) -> None:
        self._value = v

    @property
    def max_value(self) -> float:
        """Maximum value."""
        return self._max_value

    @property
    def fraction(self) -> float:
        """Proportion from 0.0 to 1.0."""
        if self._max_value <= 0:
            return 0.0
        return max(0.0, min(1.0, self._value / self._max_value))

    def get_preferred_size(self) -> tuple[int, int]:
        return (self._width or 200, self._height or 24)

    def on_draw(self) -> None:
        if self._game is None:
            return
        theme = self._game.theme
        bg = (
            self._bg_color if self._bg_color is not None else theme.progressbar_bg_color
        )
        bar = (
            self._bar_color if self._bar_color is not None else theme.progressbar_color
        )

        # Background track (full width)
        self._game._backend.draw_rect(
            self._computed_x,
            self._computed_y,
            self._computed_w,
            self._computed_h,
            bg,
        )

        # Filled bar (width * fraction)
        fill_w = int(self._computed_w * self.fraction)
        if fill_w > 0:
            self._game._backend.draw_rect(
                self._computed_x,
                self._computed_y,
                fill_w,
                self._computed_h,
                bar,
            )


# ---------------------------------------------------------------------------
# Word-wrap helper
# ---------------------------------------------------------------------------


def _word_wrap(text: str, max_width: int, font_size: int) -> list[str]:
    """Split *text* into lines that fit within *max_width* pixels.

    Uses :func:`_estimate_text_width` for per-character width measurement.
    Splits on spaces; a single word wider than *max_width* is placed on
    its own line (never mid-word broken).

    Explicit newlines (``\\n``) are respected.
    """
    if max_width <= 0:
        return [text] if text else []

    result: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        current_line = ""
        for word in words:
            if not current_line:
                # First word on the line — always accept it.
                current_line = word
            else:
                candidate = current_line + " " + word
                if _estimate_text_width(candidate, font_size) <= max_width:
                    current_line = candidate
                else:
                    result.append(current_line)
                    current_line = word
        # Flush the last line of this paragraph.
        result.append(current_line)

    return result


# ---------------------------------------------------------------------------
# TextBox
# ---------------------------------------------------------------------------


class TextBox(Component):
    """Multi-line text display with word wrapping and optional typewriter effect.

    Text is word-wrapped to fit within the component's width using
    :func:`_estimate_text_width`.  When *typewriter_speed* is greater than
    zero, characters are revealed gradually via the :meth:`update` hook
    called each frame by ``_UIRoot._update_tree(dt)``.

    Parameters:
        text:             The full text string.
        typewriter_speed: Characters per second for gradual reveal.
                          ``0`` (default) displays all text instantly.
        width:            Required — word wrapping needs a known width.
        height:           Optional — defaults to content-fit from wrapped
                          line count × line height.
        style:            Explicit :class:`Style` overrides.
        **kwargs:         Forwarded to :class:`Component` (``anchor``,
                          ``margin``, ``visible``, ``enabled``).
    """

    def __init__(
        self,
        text: str,
        *,
        typewriter_speed: float = 0,
        width: int | None = None,
        height: int | None = None,
        style: Style | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(width=width, height=height, style=style, **kwargs)
        self._text = text
        self._typewriter_speed = typewriter_speed
        self._font_handle: Any = None

        # Typewriter state
        self._revealed_count: float = 0.0
        if typewriter_speed <= 0:
            # Instant reveal — all characters visible.
            self._revealed_count = float(len(text))

        # Cached wrapped lines (invalidated on text / size change).
        self._wrapped_lines: list[str] | None = None

    # -- Properties --------------------------------------------------------

    @property
    def text(self) -> str:
        """The full text string."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        if value != self._text:
            self._text = value
            self._font_handle = None
            self._wrapped_lines = None
            self._mark_layout_dirty()
            # Reset typewriter to start of new text.
            if self._typewriter_speed <= 0:
                self._revealed_count = float(len(value))
            else:
                self._revealed_count = 0.0

    @property
    def typewriter_speed(self) -> float:
        """Characters per second for typewriter reveal (0 = instant)."""
        return self._typewriter_speed

    @property
    def revealed_count(self) -> int:
        """Number of characters currently visible."""
        return min(int(self._revealed_count), len(self._text))

    @property
    def is_complete(self) -> bool:
        """``True`` when all characters have been revealed."""
        return self.revealed_count >= len(self._text)

    # -- Typewriter controls -----------------------------------------------

    def skip(self) -> None:
        """Instantly reveal all text (skip the typewriter effect)."""
        self._revealed_count = float(len(self._text))

    def reset(self) -> None:
        """Reset the typewriter to the beginning.

        If *typewriter_speed* is 0 (instant), all text remains visible.
        Otherwise the reveal counter is set back to zero.
        """
        if self._typewriter_speed <= 0:
            self._revealed_count = float(len(self._text))
        else:
            self._revealed_count = 0.0

    # -- Update (typewriter) -----------------------------------------------

    def update(self, dt: float) -> None:
        """Advance the typewriter reveal by *dt* seconds.

        Called by ``_UIRoot._update_tree(dt)`` each game tick.  Does
        nothing when *typewriter_speed* is 0 or all text is already
        revealed.
        """
        if self._typewriter_speed <= 0:
            return
        if self._revealed_count >= len(self._text):
            return
        self._revealed_count += self._typewriter_speed * dt

    # -- Layout ------------------------------------------------------------

    def get_preferred_size(self) -> tuple[int, int]:
        """Width from constructor; height from wrapped line count × line height.

        When no explicit height is given, the TextBox auto-sizes vertically
        to fit all wrapped lines.  This requires a width to be set (for
        word wrapping).
        """
        resolved = self._resolve_style()
        font_size = resolved.font_size
        padding = resolved.padding

        w = self._width or 300
        content_w = w - 2 * padding

        lines = self._wrap(font_size, content_w)
        line_h = int(font_size * 1.4)

        if self._height is not None:
            h = self._height
        else:
            h = len(lines) * line_h + 2 * padding

        return (w, h)

    # -- Drawing -----------------------------------------------------------

    def on_draw(self) -> None:
        """Draw the visible (revealed) portion of wrapped text lines."""
        if self._game is None or not self._text:
            return

        resolved = self._resolve_style()
        font_size = resolved.font_size
        padding = resolved.padding
        content_w = self._computed_w - 2 * padding

        if self._font_handle is None:
            self._font_handle = self._game._backend.load_font(resolved.font)

        lines = self._wrap(font_size, content_w)
        line_h = int(font_size * 1.4)
        max_chars = self.revealed_count

        # Draw each line, respecting the typewriter character budget.
        chars_drawn = 0
        x = self._computed_x + padding
        y = self._computed_y + padding

        for line in lines:
            if chars_drawn >= max_chars:
                break

            # Check if this line's draw position is beyond the component bounds.
            if y + line_h > self._computed_y + self._computed_h:
                break

            remaining = max_chars - chars_drawn
            if remaining >= len(line):
                draw_text = line
            else:
                draw_text = line[:remaining]

            if draw_text:
                self._game._backend.draw_text(
                    draw_text,
                    x,
                    y,
                    font_size,
                    resolved.text_color,
                    font=self._font_handle,
                )

            # Account for the line's characters plus the newline/space that
            # was consumed by the word-wrap split.  Each original line
            # contributes len(line) + 1 to the character budget (the +1 is
            # the separator — space or newline — that was consumed).
            chars_drawn += len(line) + 1

            y += line_h

    # -- Internal ----------------------------------------------------------

    def _resolve_style(self) -> ResolvedStyle:
        """Merge explicit style with label defaults from the theme.

        TextBox uses the same theme resolution as Label — it's a
        text-rendering component.
        """
        if self._game is not None:
            return self._game.theme.resolve_label_style(self.style)
        from saga2d.ui.theme import Theme

        return Theme().resolve_label_style(self.style)

    def _wrap(self, font_size: int, max_width: int) -> list[str]:
        """Return the wrapped lines, caching the result.

        The cache is invalidated when :attr:`text` changes (setter sets
        ``_wrapped_lines = None``).
        """
        if self._wrapped_lines is None:
            self._wrapped_lines = _word_wrap(self._text, max_width, font_size)
        return self._wrapped_lines


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class List(Component):
    """Scrollable list of selectable text items with keyboard navigation.

    Displays a vertical list of string labels.  One item may be selected
    (highlighted).  Keyboard navigation via ``up``/``down`` actions moves
    the selection; ``confirm`` fires the :attr:`on_select` callback.
    Mouse clicks also select items.

    The list auto-scrolls to keep the selected item visible.

    Parameters:
        items:       Initial list of string labels.
        on_select:   ``Callable[[int], Any]`` fired when selection changes
                     (receives the new index).
        item_height: Height of each item row in pixels.
        width:       List width in pixels.
        height:      List height in pixels.  ``None`` sizes to fit all items.
        style:       Explicit :class:`Style` overrides.
        **kwargs:    Forwarded to :class:`Component` (``anchor``,
                     ``margin``, ``visible``, ``enabled``).
    """

    def __init__(
        self,
        items: list[str] | None = None,
        *,
        on_select: Callable[[int], None] | None = None,
        item_height: int = 30,
        width: int = 200,
        height: int | None = None,
        style: Style | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(width=width, height=height, style=style, **kwargs)
        self._items: list[str] = list(items) if items is not None else []
        self.on_select = on_select
        self._item_height = item_height
        self._selected_index: int | None = None
        self._scroll_offset: int = 0
        self._font_handle: Any = None

    # -- Properties --------------------------------------------------------

    @property
    def items(self) -> list[str]:
        """The list of string labels."""
        return list(self._items)

    @items.setter
    def items(self, value: list[str]) -> None:
        self._items = list(value)
        self._font_handle = None
        # Clamp selection and scroll to the new item count.
        if self._selected_index is not None:
            if len(self._items) == 0:
                self._selected_index = None
            elif self._selected_index >= len(self._items):
                self._selected_index = len(self._items) - 1
        self._clamp_scroll()
        self._mark_layout_dirty()

    @property
    def selected_index(self) -> int | None:
        """Index of the selected item, or ``None`` if nothing is selected."""
        return self._selected_index

    @selected_index.setter
    def selected_index(self, value: int | None) -> None:
        if value is not None:
            if len(self._items) == 0:
                value = None
            else:
                value = max(0, min(value, len(self._items) - 1))
        self._selected_index = value
        self._ensure_selected_visible()

    @property
    def scroll_offset(self) -> int:
        """Number of items scrolled past the top."""
        return self._scroll_offset

    @property
    def item_height(self) -> int:
        """Height of each item row in pixels."""
        return self._item_height

    # -- Layout ------------------------------------------------------------

    def get_preferred_size(self) -> tuple[int, int]:
        """Width from constructor; height fits all items if not set."""
        w = self._width or 200
        if self._height is not None:
            h = self._height
        else:
            h = max(len(self._items) * self._item_height, self._item_height)
        return (w, h)

    # -- Input dispatch ----------------------------------------------------

    def on_event(self, event: InputEvent) -> bool:
        """Handle keyboard and mouse input.

        *   ``up``/``down`` actions move the selection.
        *   ``confirm`` action fires :attr:`on_select`.
        *   ``scroll`` events adjust :attr:`_scroll_offset`.
        *   ``click`` events hit-test item rows.
        """
        # Keyboard navigation via actions.
        if event.action == "up":
            self._move_selection(-1)
            return True
        if event.action == "down":
            self._move_selection(1)
            return True
        if event.action == "confirm":
            if self._selected_index is not None and self.on_select is not None:
                self.on_select(self._selected_index)
            return True

        # Mouse click — hit-test to select an item row.
        if event.type == "click" and event.button == "left":
            if self.hit_test(event.x, event.y):
                # Determine which item row was clicked.
                relative_y = event.y - self._computed_y
                row = self._scroll_offset + int(relative_y // self._item_height)
                if 0 <= row < len(self._items):
                    self._selected_index = row
                    if self.on_select is not None:
                        self.on_select(row)
                return True

        # Mouse scroll — adjust scroll offset.
        if event.type == "scroll":
            if self.hit_test(event.x, event.y):
                # dy > 0 → scroll up, dy < 0 → scroll down (standard)
                self._scroll_offset -= event.dy
                self._clamp_scroll()
                return True

        return False

    # -- Drawing -----------------------------------------------------------

    def on_draw(self) -> None:
        """Draw background, visible items, and selection highlight."""
        if self._game is None:
            return

        resolved = self._resolve_style()
        theme = self._game.theme

        # Draw background rect.
        self._game._backend.draw_rect(
            self._computed_x,
            self._computed_y,
            self._computed_w,
            self._computed_h,
            resolved.background_color,
        )

        if not self._items:
            return

        if self._font_handle is None:
            self._font_handle = self._game._backend.load_font(resolved.font)

        visible_count = self._visible_count()
        end = min(self._scroll_offset + visible_count, len(self._items))

        for i in range(self._scroll_offset, end):
            row_y = self._computed_y + (i - self._scroll_offset) * self._item_height

            # Highlight selected row.
            if i == self._selected_index:
                self._game._backend.draw_rect(
                    self._computed_x,
                    row_y,
                    self._computed_w,
                    self._item_height,
                    theme.selected_color,
                )

            # Draw item text, vertically centred in the row.
            text_y = row_y + (self._item_height - resolved.font_size) // 2
            padding = resolved.padding
            self._game._backend.draw_text(
                self._items[i],
                self._computed_x + padding,
                text_y,
                resolved.font_size,
                resolved.text_color,
                font=self._font_handle,
            )

    # -- Internal ----------------------------------------------------------

    def _resolve_style(self) -> ResolvedStyle:
        """Merge explicit style with list defaults from the theme."""
        if self._game is not None:
            return self._game.theme.resolve_list_style(self.style)
        from saga2d.ui.theme import Theme

        return Theme().resolve_list_style(self.style)

    def _visible_count(self) -> int:
        """Number of fully visible item rows given computed height."""
        if self._item_height <= 0:
            return 0
        return max(1, self._computed_h // self._item_height)

    def _clamp_scroll(self) -> None:
        """Clamp :attr:`_scroll_offset` to valid range."""
        vc = self._visible_count()
        max_offset = max(0, len(self._items) - vc)
        self._scroll_offset = max(0, min(self._scroll_offset, max_offset))

    def _ensure_selected_visible(self) -> None:
        """Adjust scroll so the selected item is in the visible window."""
        if self._selected_index is None:
            return
        if self._selected_index < self._scroll_offset:
            self._scroll_offset = self._selected_index
        vc = self._visible_count()
        if self._selected_index >= self._scroll_offset + vc:
            self._scroll_offset = self._selected_index - vc + 1
        self._clamp_scroll()

    def _move_selection(self, delta: int) -> None:
        """Move selection by *delta* (+1 down, −1 up). Wraps to bounds."""
        if not self._items:
            return
        if self._selected_index is None:
            # First selection: pick top or bottom.
            self._selected_index = 0 if delta > 0 else len(self._items) - 1
        else:
            self._selected_index = max(
                0,
                min(self._selected_index + delta, len(self._items) - 1),
            )
        self._ensure_selected_visible()
        if self.on_select is not None:
            self.on_select(self._selected_index)


# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------


class Grid(Component):
    """Grid of fixed-size cells, each optionally holding a child component.

    Used for inventories, equipment slots, spell books, and similar grid
    layouts.  Each cell can hold one :class:`Component` (typically an
    :class:`ImageBox`).  Clicking a cell selects it and fires the
    :attr:`on_select` callback.

    Parameters:
        columns:   Number of columns.
        rows:      Number of rows.
        cell_size: ``(width, height)`` per cell in pixels.
        spacing:   Gap between cells in pixels.
        on_select: ``Callable[[int, int], Any]`` fired on cell selection
                   (receives ``(col, row)``).
        width:     Explicit width override.  ``None`` auto-sizes from
                   columns, cell_size, and spacing.
        height:    Explicit height override.  ``None`` auto-sizes.
        style:     Explicit :class:`Style` overrides.
        **kwargs:  Forwarded to :class:`Component`.
    """

    def __init__(
        self,
        columns: int,
        rows: int,
        *,
        cell_size: tuple[int, int] = (64, 64),
        spacing: int = 4,
        on_select: Callable[[int, int], Any] | None = None,
        width: int | None = None,
        height: int | None = None,
        style: Style | None = None,
        **kwargs: Any,
    ) -> None:
        if spacing < 0:
            raise ValueError(f"spacing cannot be negative, got {spacing}")
        super().__init__(width=width, height=height, style=style, **kwargs)
        self._columns = columns
        self._rows = rows
        self._cell_w, self._cell_h = cell_size
        self._spacing = spacing
        self.on_select = on_select
        self._selected: tuple[int, int] | None = None
        self._cells: dict[tuple[int, int], Component] = {}

    # -- Properties --------------------------------------------------------

    @property
    def columns(self) -> int:
        """Number of columns."""
        return self._columns

    @property
    def rows(self) -> int:
        """Number of rows."""
        return self._rows

    @property
    def cell_size(self) -> tuple[int, int]:
        """``(width, height)`` per cell."""
        return (self._cell_w, self._cell_h)

    @property
    def spacing(self) -> int:
        """Gap between cells in pixels."""
        return self._spacing

    @property
    def selected(self) -> tuple[int, int] | None:
        """``(col, row)`` of the selected cell, or ``None``."""
        return self._selected

    @selected.setter
    def selected(self, value: tuple[int, int] | None) -> None:
        if value is not None:
            if self._columns <= 0 or self._rows <= 0:
                self._selected = None
                return
            col, row = value
            col = max(0, min(col, self._columns - 1))
            row = max(0, min(row, self._rows - 1))
            value = (col, row)
        self._selected = value

    # -- Cell management ---------------------------------------------------

    def set_cell(self, col: int, row: int, component: Component | None) -> None:
        """Place *component* in cell ``(col, row)``.  ``None`` clears it.

        The component is added as a child of this Grid so that it
        participates in the tree (receives ``_game``, draws, etc.).
        """
        key = (col, row)
        # Remove existing component in this cell.
        old = self._cells.pop(key, None)
        if old is not None:
            self.remove(old)

        if component is not None:
            self._cells[key] = component
            self.add(component)
        self._mark_layout_dirty()

    def get_cell(self, col: int, row: int) -> Component | None:
        """Return the component at ``(col, row)``, or ``None``."""
        return self._cells.get((col, row))

    # -- Layout ------------------------------------------------------------

    def get_preferred_size(self) -> tuple[int, int]:
        """Auto-size from columns, rows, cell_size, spacing, and padding.

        ``columns * cell_w + (columns - 1) * spacing + 2 * padding``
        """
        resolved = self._resolve_style()
        padding = resolved.padding

        if self._width is not None:
            w = self._width
        else:
            w = (
                self._columns * self._cell_w
                + max(0, self._columns - 1) * self._spacing
                + 2 * padding
            )

        if self._height is not None:
            h = self._height
        else:
            h = (
                self._rows * self._cell_h
                + max(0, self._rows - 1) * self._spacing
                + 2 * padding
            )

        return (w, h)

    def _layout_children(self) -> None:
        """Position each cell's component within its cell bounds."""
        resolved = self._resolve_style()
        padding = resolved.padding

        for (col, row), child in self._cells.items():
            cx = self._computed_x + padding + col * (self._cell_w + self._spacing)
            cy = self._computed_y + padding + row * (self._cell_h + self._spacing)
            child.compute_layout(cx, cy, self._cell_w, self._cell_h)

    # -- Input dispatch ----------------------------------------------------

    def on_event(self, event: InputEvent) -> bool:
        """Handle mouse click to select a cell.

        Child components receive events via the standard
        :meth:`Component.handle_event` tree walk *before* this method
        is called.  If no child consumes the click, selection is updated
        here.
        """
        if event.type == "click" and event.button == "left":
            if self.hit_test(event.x, event.y):
                cell = self._cell_at(event.x, event.y)
                if cell is not None:
                    self._selected = cell
                    if self.on_select is not None:
                        self.on_select(cell[0], cell[1])
                return True

        return False

    # -- Drawing -----------------------------------------------------------

    def on_draw(self) -> None:
        """Draw grid background, cell backgrounds, selection highlight.

        Child components are drawn by the base :meth:`Component.draw`
        method (which calls ``on_draw`` then draws children), so we only
        need to draw the background and cell overlays here.
        """
        if self._game is None:
            return

        resolved = self._resolve_style()
        theme = self._game.theme
        padding = resolved.padding

        # Overall background.
        self._game._backend.draw_rect(
            self._computed_x,
            self._computed_y,
            self._computed_w,
            self._computed_h,
            resolved.background_color,
        )

        # Draw each cell slot (empty cells get a subtle background).
        cell_bg: Color = (50, 50, 60, 180)
        for row in range(self._rows):
            for col in range(self._columns):
                cx = self._computed_x + padding + col * (self._cell_w + self._spacing)
                cy = self._computed_y + padding + row * (self._cell_h + self._spacing)

                # Cell background.
                self._game._backend.draw_rect(
                    cx,
                    cy,
                    self._cell_w,
                    self._cell_h,
                    cell_bg,
                )

                # Highlight selected cell.
                if self._selected == (col, row):
                    self._game._backend.draw_rect(
                        cx,
                        cy,
                        self._cell_w,
                        self._cell_h,
                        theme.selected_color,
                    )

    # -- Internal ----------------------------------------------------------

    def _resolve_style(self) -> ResolvedStyle:
        """Merge explicit style with grid defaults from the theme."""
        if self._game is not None:
            return self._game.theme.resolve_grid_style(self.style)
        from saga2d.ui.theme import Theme

        return Theme().resolve_grid_style(self.style)

    def _cell_at(self, x: int, y: int) -> tuple[int, int] | None:
        """Return ``(col, row)`` for the cell at pixel ``(x, y)``, or ``None``.

        Returns ``None`` if the click lands in spacing or padding rather
        than inside a cell.
        """
        resolved = self._resolve_style()
        padding = resolved.padding

        # Relative to the grid's content area.
        rx = x - self._computed_x - padding
        ry = y - self._computed_y - padding

        if rx < 0 or ry < 0:
            return None

        cell_stride_x = self._cell_w + self._spacing
        cell_stride_y = self._cell_h + self._spacing

        if cell_stride_x <= 0 or cell_stride_y <= 0:
            return None

        col = int(rx // cell_stride_x)
        row = int(ry // cell_stride_y)

        # Check the click is inside the cell, not in the spacing gap.
        if rx - col * cell_stride_x >= self._cell_w:
            return None
        if ry - row * cell_stride_y >= self._cell_h:
            return None

        if 0 <= col < self._columns and 0 <= row < self._rows:
            return (col, row)
        return None


# ---------------------------------------------------------------------------
# Tooltip
# ---------------------------------------------------------------------------


class Tooltip(Component):
    """Hover popup that appears after a delay and renders on top.

    Call :meth:`show` to start the delay timer at a given position.
    After *delay* seconds the tooltip becomes visible.  Call :meth:`hide`
    to dismiss immediately.  Position can be updated while shown via
    :meth:`show` (the delay only applies the first time).

    The tooltip draws a small styled rectangle with text at the tracked
    position, clamped to the logical screen bounds so it never goes
    off-screen.

    **Rendering order:** When visible the tooltip is drawn during its
    parent's normal draw pass.  For "on top of everything" behaviour,
    add the tooltip directly to the scene's :class:`_UIRoot` — because
    children draw in order, a tooltip appended last will paint over
    earlier siblings.

    Parameters:
        text:    Tooltip text string.
        delay:   Seconds to wait before appearing (default ``0.5``).
        style:   Explicit :class:`Style` overrides.
        **kwargs: Forwarded to :class:`Component`.
    """

    def __init__(
        self,
        text: str,
        *,
        delay: float = 0.5,
        style: Style | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(style=style, **kwargs)
        self._text = text
        self._delay = delay
        self._font_handle: Any = None

        # Timer / visibility state.
        #
        # Component.visible stays True so that _update_tree calls update()
        # even while the tooltip is waiting for the delay to elapse.
        # Drawing is gated by _visible_now, not Component.visible.
        self._timer: float = 0.0
        self._showing: bool = False  # True while delay is ticking or visible
        self._visible_now: bool = False  # True once delay expired

        # Tracked position (set by show(), updated by follow()).
        self._tip_x: int = 0
        self._tip_y: int = 0

    # -- Properties --------------------------------------------------------

    @property
    def text(self) -> str:
        """The tooltip text."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        if value != self._text:
            self._text = value
            self._font_handle = None

    @property
    def delay(self) -> float:
        """Seconds before the tooltip appears."""
        return self._delay

    # -- Show / Hide -------------------------------------------------------

    def show(self, x: int, y: int) -> None:
        """Start showing the tooltip at ``(x, y)``.

        The delay timer begins counting from this call.  If the tooltip
        is already visible (delay already elapsed) the position is
        updated immediately without restarting the timer.
        """
        self._tip_x = x
        self._tip_y = y
        if not self._showing:
            self._showing = True
            self._timer = 0.0
            self._visible_now = False
            # If delay is zero or negative, show immediately.
            if self._delay <= 0:
                self._visible_now = True

    def hide(self) -> None:
        """Hide the tooltip immediately and reset the delay timer."""
        self._showing = False
        self._visible_now = False
        self._timer = 0.0

    # -- Update (delay timer) ----------------------------------------------

    def update(self, dt: float) -> None:
        """Advance the delay timer.

        Called each frame by ``_UIRoot._update_tree(dt)``.  When the
        accumulated time reaches :attr:`delay`, the tooltip becomes
        visible.
        """
        if not self._showing:
            return
        if self._visible_now:
            return  # Already visible — nothing to do.
        self._timer += dt
        if self._timer >= self._delay:
            self._visible_now = True

    # -- Layout ------------------------------------------------------------

    def get_preferred_size(self) -> tuple[int, int]:
        """Size based on text measurement + padding."""
        resolved = self._resolve_style()
        padding = resolved.padding
        text_w = _estimate_text_width(self._text, resolved.font_size)
        text_h = resolved.font_size
        return (text_w + 2 * padding, text_h + 2 * padding)

    # -- Drawing -----------------------------------------------------------

    def on_draw(self) -> None:
        """Draw the tooltip rectangle and text at the tracked position."""
        if self._game is None or not self._visible_now:
            return

        resolved = self._resolve_style()
        padding = resolved.padding
        font_size = resolved.font_size

        if self._font_handle is None:
            self._font_handle = self._game._backend.load_font(resolved.font)

        text_w = _estimate_text_width(self._text, font_size)
        text_h = font_size
        box_w = text_w + 2 * padding
        box_h = text_h + 2 * padding

        # Position: offset slightly from the cursor.
        draw_x = self._tip_x + 12
        draw_y = self._tip_y + 16

        # Clamp to screen bounds so the tooltip never goes off-screen.
        screen_w, screen_h = self._game._resolution
        if draw_x + box_w > screen_w:
            draw_x = screen_w - box_w
        if draw_y + box_h > screen_h:
            draw_y = screen_h - box_h
        if draw_x < 0:
            draw_x = 0
        if draw_y < 0:
            draw_y = 0

        # Background rectangle.
        self._game._backend.draw_rect(
            draw_x,
            draw_y,
            box_w,
            box_h,
            resolved.background_color,
        )

        # Text.
        self._game._backend.draw_text(
            self._text,
            draw_x + padding,
            draw_y + padding,
            font_size,
            resolved.text_color,
            font=self._font_handle,
        )

    # -- Internal ----------------------------------------------------------

    def _resolve_style(self) -> ResolvedStyle:
        """Merge explicit style with tooltip defaults from the theme."""
        if self._game is not None:
            return self._game.theme.resolve_tooltip_style(self.style)
        from saga2d.ui.theme import Theme

        return Theme().resolve_tooltip_style(self.style)


# ---------------------------------------------------------------------------
# TabGroup
# ---------------------------------------------------------------------------


class TabGroup(Component):
    """Tabbed container that switches between content components.

    Displays a horizontal row of clickable tab headers at the top.
    Clicking a header (or calling :meth:`select_tab`) switches which
    content component is visible below the tab bar.

    Parameters:
        tabs:       ``dict[str, Component]`` mapping tab label strings to
                    content components.  Insertion order determines the
                    left-to-right tab order.  ``None`` or ``{}`` starts
                    with no tabs.
        tab_height: Height of the tab header row in pixels.
        style:      Explicit :class:`Style` overrides.
        **kwargs:   Forwarded to :class:`Component`.
    """

    def __init__(
        self,
        tabs: dict[str, Component] | None = None,
        *,
        tab_height: int = 32,
        style: Style | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(style=style, **kwargs)
        self._tab_height = tab_height
        self._font_handle: Any = None

        # Ordered tab data: list of (label, component) preserving insertion order.
        self._tab_labels: list[str] = []
        self._tab_components: dict[str, Component] = {}
        self._active_tab: str | None = None

        # Populate initial tabs.
        if tabs:
            for label, component in tabs.items():
                self._add_tab_internal(label, component)
            # Activate the first tab by default.
            self._active_tab = self._tab_labels[0]
            self._sync_visibility()

    # -- Properties --------------------------------------------------------

    @property
    def active_tab(self) -> str | None:
        """Label of the currently active (visible) tab, or ``None``."""
        return self._active_tab

    @active_tab.setter
    def active_tab(self, label: str) -> None:
        self.select_tab(label)

    @property
    def tab_height(self) -> int:
        """Height of the tab header row in pixels."""
        return self._tab_height

    @property
    def tab_labels(self) -> list[str]:
        """Ordered list of tab label strings (copy)."""
        return list(self._tab_labels)

    # -- Tab management ----------------------------------------------------

    def add_tab(self, label: str, component: Component) -> None:
        """Add a new tab with the given *label* and *component*.

        If this is the first tab it becomes the active tab automatically.
        """
        self._add_tab_internal(label, component)
        if self._active_tab is None:
            self._active_tab = label
        self._sync_visibility()
        self._mark_layout_dirty()

    def select_tab(self, label: str) -> None:
        """Switch to the tab with the given *label*.

        Raises ``KeyError`` if *label* does not exist.
        """
        if label not in self._tab_components:
            available = ", ".join(repr(k) for k in self._tab_labels)
            raise KeyError(f"No tab named {label!r}; available tabs: {available}")
        self._active_tab = label
        self._sync_visibility()
        self._mark_layout_dirty()

    def get_tab_content(self, label: str) -> Component | None:
        """Return the content component for *label*, or ``None``."""
        return self._tab_components.get(label)

    # -- Layout ------------------------------------------------------------

    def get_preferred_size(self) -> tuple[int, int]:
        """Width = max of all content panels; height = tab_height + max content height."""
        max_w = 0
        max_h = 0
        for comp in self._tab_components.values():
            cw, ch = comp.get_preferred_size()
            max_w = max(max_w, cw)
            max_h = max(max_h, ch)

        w = self._width if self._width is not None else max(max_w, 100)
        h = self._height if self._height is not None else (self._tab_height + max_h)
        return (w, h)

    def _layout_children(self) -> None:
        """Position the active content component below the tab bar."""
        content_x = self._computed_x
        content_y = self._computed_y + self._tab_height
        content_w = self._computed_w
        content_h = self._computed_h - self._tab_height

        for label, comp in self._tab_components.items():
            if label == self._active_tab:
                comp.compute_layout(content_x, content_y, content_w, content_h)
            else:
                # Off-screen / zero-size for inactive — they're invisible
                # anyway, but we still need to give them some layout so that
                # compute_layout doesn't leave stale values.
                comp.compute_layout(content_x, content_y, content_w, content_h)

    # -- Input dispatch ----------------------------------------------------

    def on_event(self, event: InputEvent) -> bool:
        """Handle click on tab headers to switch the active tab."""
        if event.type == "click" and event.button == "left":
            if self.hit_test(event.x, event.y):
                # Is the click within the tab header row?
                if event.y < self._computed_y + self._tab_height:
                    label = self._tab_at(event.x)
                    if label is not None:
                        self.select_tab(label)
                    return True

        return False

    # -- Drawing -----------------------------------------------------------

    def on_draw(self) -> None:
        """Draw the tab header bar.

        Content components are drawn automatically by the base
        :meth:`Component.draw` tree walk (only the active tab's
        content has ``visible=True``).
        """
        if self._game is None:
            return

        resolved = self._resolve_style()
        theme = self._game.theme

        if self._font_handle is None:
            self._font_handle = self._game._backend.load_font(resolved.font)

        font_size = resolved.font_size
        padding = resolved.padding
        tab_widths = self._compute_tab_widths(font_size, padding)

        x = self._computed_x
        y = self._computed_y

        for i, label in enumerate(self._tab_labels):
            tw = tab_widths[i]
            is_active = label == self._active_tab

            # Tab header background.
            bg = theme.tab_active_color if is_active else theme.tab_inactive_color
            self._game._backend.draw_rect(
                x,
                y,
                tw,
                self._tab_height,
                bg,
            )

            # Tab label text, vertically centred.
            text_y = y + (self._tab_height - font_size) // 2
            self._game._backend.draw_text(
                label,
                x + padding,
                text_y,
                font_size,
                resolved.text_color,
                font=self._font_handle,
            )

            x += tw

        # Fill any remaining header-row width with the inactive colour
        # so the bar extends across the full component width.
        remaining = self._computed_w - (x - self._computed_x)
        if remaining > 0:
            self._game._backend.draw_rect(
                x,
                y,
                remaining,
                self._tab_height,
                theme.tab_inactive_color,
            )

    # -- Internal ----------------------------------------------------------

    def _add_tab_internal(self, label: str, component: Component) -> None:
        """Add a tab without touching visibility or dirty flags."""
        if label in self._tab_components:
            # Replace existing tab's component.
            old = self._tab_components[label]
            self.remove(old)
        else:
            self._tab_labels.append(label)
        self._tab_components[label] = component
        self.add(component)

    def _sync_visibility(self) -> None:
        """Set ``visible=True`` on the active tab's component, ``False`` on others."""
        for label, comp in self._tab_components.items():
            comp.visible = label == self._active_tab

    def _resolve_style(self) -> ResolvedStyle:
        """Merge explicit style with tab-group defaults from the theme."""
        if self._game is not None:
            return self._game.theme.resolve_tabgroup_style(self.style)
        from saga2d.ui.theme import Theme

        return Theme().resolve_tabgroup_style(self.style)

    def _compute_tab_widths(
        self,
        font_size: int,
        padding: int,
    ) -> list[int]:
        """Compute pixel width for each tab header from text measurement."""
        widths: list[int] = []
        for label in self._tab_labels:
            text_w = _estimate_text_width(label, font_size)
            widths.append(text_w + 2 * padding)
        return widths

    def _tab_at(self, x: int) -> str | None:
        """Return the tab label at pixel *x*, or ``None``."""
        resolved = self._resolve_style()
        font_size = resolved.font_size
        padding = resolved.padding
        tab_widths = self._compute_tab_widths(font_size, padding)

        rx = x - self._computed_x
        cumulative = 0
        for i, tw in enumerate(tab_widths):
            if cumulative <= rx < cumulative + tw:
                return self._tab_labels[i]
            cumulative += tw
        return None


# ---------------------------------------------------------------------------
# DataTable
# ---------------------------------------------------------------------------


class DataTable(Component):
    """Table with column headers and data rows.

    Displays a header row (highlighted) followed by data rows with
    alternating background colours for readability.  Clicking a data row
    selects it (highlighted with the theme's ``selected_color``).

    Scrolling is supported when the number of rows exceeds the visible
    area.

    Parameters:
        columns:       List of column header strings.
        rows:          List of rows, each row is a list of cell strings.
                       ``None`` starts with an empty table.
        col_widths:    Optional list of per-column widths in pixels.
                       ``None`` auto-distributes evenly across the
                       available width.
        row_height:    Height per data row in pixels.
        header_height: Height of the header row in pixels.
        style:         Explicit :class:`Style` overrides.
        **kwargs:      Forwarded to :class:`Component`.
    """

    def __init__(
        self,
        columns: list[str],
        rows: list[list[str]] | None = None,
        *,
        col_widths: list[int] | None = None,
        row_height: int = 28,
        header_height: int = 32,
        style: Style | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(style=style, **kwargs)
        self._columns = list(columns)
        self._rows: list[list[str]] = list(rows) if rows is not None else []
        self._col_widths = list(col_widths) if col_widths is not None else None
        self._row_height = row_height
        self._header_height = header_height
        self._selected_row: int | None = None
        self._scroll_offset: int = 0
        self._font_handle: Any = None

    # -- Properties --------------------------------------------------------

    @property
    def columns(self) -> list[str]:
        """List of column header strings (copy)."""
        return list(self._columns)

    @property
    def rows(self) -> list[list[str]]:
        """List of data rows (copy of outer list)."""
        return list(self._rows)

    @rows.setter
    def rows(self, value: list[list[str]]) -> None:
        self._rows = list(value)
        # Clamp selection and scroll to the new row count.
        if self._selected_row is not None:
            if len(self._rows) == 0:
                self._selected_row = None
            elif self._selected_row >= len(self._rows):
                self._selected_row = len(self._rows) - 1
        self._clamp_scroll()
        self._mark_layout_dirty()

    @property
    def selected_row(self) -> int | None:
        """Index of the selected data row, or ``None``."""
        return self._selected_row

    @selected_row.setter
    def selected_row(self, value: int | None) -> None:
        if value is not None:
            if len(self._rows) == 0:
                value = None
            else:
                value = max(0, min(value, len(self._rows) - 1))
        self._selected_row = value
        self._ensure_selected_visible()

    @property
    def row_height(self) -> int:
        """Height per data row in pixels."""
        return self._row_height

    @property
    def header_height(self) -> int:
        """Height of the header row in pixels."""
        return self._header_height

    # -- Row management ----------------------------------------------------

    def add_row(self, row: list[str]) -> None:
        """Append a data row to the table."""
        self._rows.append(list(row))
        self._mark_layout_dirty()

    def clear_rows(self) -> None:
        """Remove all data rows and reset selection."""
        self._rows.clear()
        self._selected_row = None
        self._scroll_offset = 0
        self._mark_layout_dirty()

    # -- Layout ------------------------------------------------------------

    def get_preferred_size(self) -> tuple[int, int]:
        """Width = sum of col_widths (or auto); height = header + rows."""
        if self._width is not None:
            w = self._width
        elif self._col_widths is not None:
            resolved = self._resolve_style()
            padding = resolved.padding
            w = sum(self._col_widths) + 2 * padding
        else:
            w = 400  # Sensible default when neither width nor col_widths set.

        if self._height is not None:
            h = self._height
        else:
            h = self._header_height + len(self._rows) * self._row_height

        return (w, h)

    # -- Input dispatch ----------------------------------------------------

    def on_event(self, event: InputEvent) -> bool:
        """Handle click to select a data row, scroll to adjust view."""
        # Mouse click — determine which data row was clicked.
        if event.type == "click" and event.button == "left":
            if self.hit_test(event.x, event.y):
                relative_y = event.y - self._computed_y - self._header_height
                if relative_y >= 0:
                    row_idx = self._scroll_offset + int(relative_y // self._row_height)
                    if 0 <= row_idx < len(self._rows):
                        self._selected_row = row_idx
                return True

        # Mouse scroll — adjust scroll offset.
        if event.type == "scroll":
            if self.hit_test(event.x, event.y):
                self._scroll_offset -= event.dy
                self._clamp_scroll()
                return True

        # Keyboard navigation via actions.
        if event.action == "up":
            self._move_selection(-1)
            return True
        if event.action == "down":
            self._move_selection(1)
            return True

        return False

    # -- Drawing -----------------------------------------------------------

    def on_draw(self) -> None:
        """Draw header row, alternating data rows, cell text, and selection."""
        if self._game is None:
            return

        resolved = self._resolve_style()
        theme = self._game.theme
        padding = resolved.padding
        font_size = resolved.font_size

        if self._font_handle is None:
            self._font_handle = self._game._backend.load_font(resolved.font)

        # Compute column widths for this frame.
        col_ws = self._effective_col_widths(padding)

        x0 = self._computed_x
        y0 = self._computed_y

        # -- Header row ----------------------------------------------------
        self._game._backend.draw_rect(
            x0,
            y0,
            self._computed_w,
            self._header_height,
            theme.datatable_header_bg_color,
        )

        # Header text per column.
        hx = x0 + padding
        header_text_y = y0 + (self._header_height - font_size) // 2
        for i, col_name in enumerate(self._columns):
            cw = col_ws[i] if i < len(col_ws) else 0
            self._game._backend.draw_text(
                col_name,
                hx,
                header_text_y,
                font_size,
                theme.datatable_header_text_color,
                font=self._font_handle,
            )
            hx += cw

        # -- Data rows -----------------------------------------------------
        if not self._rows:
            return

        visible_count = self._visible_data_rows()
        end = min(self._scroll_offset + visible_count, len(self._rows))
        row_y = y0 + self._header_height

        for ri in range(self._scroll_offset, end):
            # Alternating row background.
            if ri % 2 == 0:
                row_bg = theme.datatable_row_bg_color
            else:
                row_bg = theme.datatable_alt_row_bg_color

            self._game._backend.draw_rect(
                x0,
                row_y,
                self._computed_w,
                self._row_height,
                row_bg,
            )

            # Selection highlight (drawn on top of the row background).
            if ri == self._selected_row:
                self._game._backend.draw_rect(
                    x0,
                    row_y,
                    self._computed_w,
                    self._row_height,
                    theme.selected_color,
                )

            # Cell text per column.
            cx = x0 + padding
            text_y = row_y + (self._row_height - font_size) // 2
            row_data = self._rows[ri]
            for ci in range(len(self._columns)):
                cw = col_ws[ci] if ci < len(col_ws) else 0
                cell_text = row_data[ci] if ci < len(row_data) else ""
                if cell_text:
                    self._game._backend.draw_text(
                        cell_text,
                        cx,
                        text_y,
                        font_size,
                        resolved.text_color,
                        font=self._font_handle,
                    )
                cx += cw

            row_y += self._row_height

    # -- Internal ----------------------------------------------------------

    def _resolve_style(self) -> ResolvedStyle:
        """Merge explicit style with datatable defaults from the theme."""
        if self._game is not None:
            return self._game.theme.resolve_datatable_style(self.style)
        from saga2d.ui.theme import Theme

        return Theme().resolve_datatable_style(self.style)

    def _effective_col_widths(self, padding: int) -> list[int]:
        """Return the column widths to use for the current frame.

        If explicit ``col_widths`` were provided, returns those.
        Otherwise auto-distributes ``computed_w - 2*padding`` equally
        among columns.
        """
        if self._col_widths is not None:
            return self._col_widths

        n = len(self._columns)
        if n == 0:
            return []
        available = max(0, self._computed_w - 2 * padding)
        base = available // n
        remainder = available % n
        # Distribute remainder one pixel at a time to the first columns.
        widths = [base + (1 if i < remainder else 0) for i in range(n)]
        return widths

    def _visible_data_rows(self) -> int:
        """Number of fully visible data rows (excluding the header)."""
        if self._row_height <= 0:
            return 0
        data_area = max(0, self._computed_h - self._header_height)
        return max(1, data_area // self._row_height)

    def _clamp_scroll(self) -> None:
        """Clamp :attr:`_scroll_offset` to valid range."""
        vc = self._visible_data_rows()
        max_offset = max(0, len(self._rows) - vc)
        self._scroll_offset = max(0, min(self._scroll_offset, max_offset))

    def _ensure_selected_visible(self) -> None:
        """Adjust scroll so the selected row is in the visible window."""
        if self._selected_row is None:
            return
        if self._selected_row < self._scroll_offset:
            self._scroll_offset = self._selected_row
        vc = self._visible_data_rows()
        if self._selected_row >= self._scroll_offset + vc:
            self._scroll_offset = self._selected_row - vc + 1
        self._clamp_scroll()

    def _move_selection(self, delta: int) -> None:
        """Move selection by *delta* (+1 down, −1 up). Clamps to bounds."""
        if not self._rows:
            return
        if self._selected_row is None:
            self._selected_row = 0 if delta > 0 else len(self._rows) - 1
        else:
            self._selected_row = max(
                0,
                min(self._selected_row + delta, len(self._rows) - 1),
            )
        self._ensure_selected_visible()
