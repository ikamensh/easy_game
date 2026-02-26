"""ColorSwap — per-pixel color replacement for team palettes and variants.

Creates cached recolored images at load time (one-time cost, not per-frame).
Used for team colors, faction variants, and armor tints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image


# ---------------------------------------------------------------------------
# Palette registry (global, for team_palette convenience)
# ---------------------------------------------------------------------------

_TEAM_PALETTES: dict[str, "ColorSwap"] = {}


def register_palette(name: str, swap: "ColorSwap") -> None:
    """Register a named palette for use with ``Sprite(..., team_palette=name)``."""
    _TEAM_PALETTES[name] = swap


def _clear_palettes() -> None:
    """Clear the palette registry. Called by Game._teardown()."""
    _TEAM_PALETTES.clear()


def get_palette(name: str) -> "ColorSwap":
    """Return the registered palette by name.

    Raises:
        KeyError: If the name is not registered.
    """
    if name not in _TEAM_PALETTES:
        raise KeyError(
            f"Palette '{name}' not registered. Use register_palette() first."
        )
    return _TEAM_PALETTES[name]


# ---------------------------------------------------------------------------
# ColorSwap
# ---------------------------------------------------------------------------


class ColorSwap:
    """Pixel-level color replacement applied at image load time.

    Creates a cached recolored image — one-time cost, not per-frame.
    """

    def __init__(
        self,
        source_colors: list[tuple[int, int, int]],
        target_colors: list[tuple[int, int, int]],
    ) -> None:
        """Build a color mapping from source RGB tuples to target RGB tuples.

        Parameters:
            source_colors: RGB tuples to find in the image (e.g. red team base).
            target_colors: RGB tuples to replace with (e.g. blue team colors).
        """
        if len(source_colors) != len(target_colors):
            raise ValueError(
                "source_colors and target_colors must have the same length"
                f" (got {len(source_colors)} source and"
                f" {len(target_colors)} target)"
            )
        self.source_colors = list(source_colors)
        self.target_colors = list(target_colors)

    def apply(self, image_path: str) -> "Image.Image":
        """Load image at path, replace colors, return PIL Image.

        Preserves alpha. Unmatched pixels are unchanged.

        Only PNG images are accepted.  The ``formats`` restriction is a
        defence-in-depth measure against CVE-2026-25990 (Pillow PSD
        out-of-bounds write) and any future format-specific vulnerabilities.
        """
        from PIL import Image

        with Image.open(image_path, formats=["PNG"]) as raw:
            img: Image.Image = raw.convert("RGBA")
        pixels = img.load()
        if pixels is None:
            raise RuntimeError(
                f"Failed to load pixel data from image: {image_path}."
                " Ensure the file exists, is a valid PNG image, and that"
                " Pillow (PIL) is installed."
            )
        color_map = dict(zip(self.source_colors, self.target_colors))

        for y in range(img.height):
            for x in range(img.width):
                r, g, b, a = pixels[x, y]  # type: ignore[misc]  # PIL RGBA pixel is a tuple at runtime
                rgb = (r, g, b)
                if rgb in color_map:
                    tr, tg, tb = color_map[rgb]
                    pixels[x, y] = (tr, tg, tb, a)

        return img

    def cache_key(
        self,
    ) -> tuple[tuple[tuple[int, int, int], tuple[int, int, int]], ...]:
        """Hashable key for caching: tuple of (src, tgt) pairs."""
        return tuple(zip(self.source_colors, self.target_colors))
