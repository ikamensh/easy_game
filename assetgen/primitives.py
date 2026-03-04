"""
Reusable Pillow-based drawing helpers for procedural asset generation.

Two API layers:

**Low-level** — operate on an existing ``PIL.Image.Image`` (RGBA mode):
    ``filled_polygon``, ``outlined_polygon``, ``vertical_gradient``,
    ``horizontal_gradient``, ``crosshatch``, ``filled_ellipse``,
    ``outlined_ellipse``.

**High-level** — *return* a new ``PIL.Image.Image`` (RGBA, transparent bg):
    ``solid_rect``, ``labeled_rect``, ``triangle``, ``circle``, ``ring``.

Coordinates use top-left origin, matching Pillow and Saga2D conventions.
"""

from __future__ import annotations

from typing import Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Color = Tuple[int, int, int, int]  # RGBA
Point = Tuple[float, float]        # (x, y)


# ---------------------------------------------------------------------------
# Polygons
# ---------------------------------------------------------------------------

def filled_polygon(
    img: Image.Image,
    points: Sequence[Point],
    fill: Color = (255, 255, 255, 255),
) -> None:
    """Draw a filled polygon onto *img*.

    Args:
        img:    Target RGBA image.
        points: Sequence of (x, y) vertices.
        fill:   RGBA fill colour.
    """
    draw = ImageDraw.Draw(img, "RGBA")
    draw.polygon([tuple(p) for p in points], fill=fill)


def outlined_polygon(
    img: Image.Image,
    points: Sequence[Point],
    outline: Color = (255, 255, 255, 255),
    width: int = 1,
) -> None:
    """Draw a polygon outline (no fill) onto *img*.

    Args:
        img:     Target RGBA image.
        points:  Sequence of (x, y) vertices.
        outline: RGBA stroke colour.
        width:   Line width in pixels.
    """
    draw = ImageDraw.Draw(img, "RGBA")
    # ImageDraw.polygon outline width was only added in Pillow 10.
    # For broad compatibility, draw the edges individually.
    pts = [tuple(p) for p in points]
    for i in range(len(pts)):
        draw.line([pts[i], pts[(i + 1) % len(pts)]], fill=outline, width=width)


# ---------------------------------------------------------------------------
# Gradient fills
# ---------------------------------------------------------------------------

def vertical_gradient(
    img: Image.Image,
    top_color: Color,
    bottom_color: Color,
    bbox: Tuple[int, int, int, int] | None = None,
) -> None:
    """Fill a region with a vertical (top-to-bottom) linear gradient.

    Args:
        img:          Target RGBA image.
        top_color:    RGBA colour at the top edge.
        bottom_color: RGBA colour at the bottom edge.
        bbox:         Optional (x0, y0, x1, y1) sub-region; defaults to full image.
    """
    x0, y0, x1, y1 = bbox if bbox else (0, 0, img.width, img.height)
    height = y1 - y0
    if height <= 0:
        return
    draw = ImageDraw.Draw(img, "RGBA")
    for y in range(y0, y1):
        t = (y - y0) / max(height - 1, 1)
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        a = int(top_color[3] + (bottom_color[3] - top_color[3]) * t)
        draw.line([(x0, y), (x1 - 1, y)], fill=(r, g, b, a))


def horizontal_gradient(
    img: Image.Image,
    left_color: Color,
    right_color: Color,
    bbox: Tuple[int, int, int, int] | None = None,
) -> None:
    """Fill a region with a horizontal (left-to-right) linear gradient.

    Args:
        img:         Target RGBA image.
        left_color:  RGBA colour at the left edge.
        right_color: RGBA colour at the right edge.
        bbox:        Optional (x0, y0, x1, y1) sub-region; defaults to full image.
    """
    x0, y0, x1, y1 = bbox if bbox else (0, 0, img.width, img.height)
    width = x1 - x0
    if width <= 0:
        return
    draw = ImageDraw.Draw(img, "RGBA")
    for x in range(x0, x1):
        t = (x - x0) / max(width - 1, 1)
        r = int(left_color[0] + (right_color[0] - left_color[0]) * t)
        g = int(left_color[1] + (right_color[1] - left_color[1]) * t)
        b = int(left_color[2] + (right_color[2] - left_color[2]) * t)
        a = int(left_color[3] + (right_color[3] - left_color[3]) * t)
        draw.line([(x, y0), (x, y1 - 1)], fill=(r, g, b, a))


# ---------------------------------------------------------------------------
# Hatching / patterns
# ---------------------------------------------------------------------------

def crosshatch(
    img: Image.Image,
    spacing: int = 6,
    color: Color = (0, 0, 0, 128),
    width: int = 1,
    bbox: Tuple[int, int, int, int] | None = None,
    angle_degrees: float = 45.0,
) -> None:
    """Overlay a cross-hatch pattern onto a region of *img*.

    Draws two families of parallel lines at +angle and -angle.

    Args:
        img:           Target RGBA image.
        spacing:       Pixel distance between adjacent parallel lines.
        color:         RGBA line colour.
        width:         Line width in pixels.
        bbox:          Optional (x0, y0, x1, y1) sub-region; defaults to full image.
        angle_degrees: Hatch angle (default 45). Lines are drawn at both
                       +angle and -angle from horizontal.
    """
    import math

    x0, y0, x1, y1 = bbox if bbox else (0, 0, img.width, img.height)
    region_w = x1 - x0
    region_h = y1 - y0
    if region_w <= 0 or region_h <= 0:
        return

    draw = ImageDraw.Draw(img, "RGBA")
    angle_rad = math.radians(angle_degrees)

    # Direction vector along the hatch line and its perpendicular.
    dx = math.cos(angle_rad)
    dy = math.sin(angle_rad)

    # We need to cover the full diagonal of the bbox, so compute the
    # maximum extent of lines that must be drawn.
    diag = math.hypot(region_w, region_h)

    # Number of lines needed to tile the region along the perpendicular.
    n_lines = int(diag / max(spacing, 1)) + 2

    def _draw_family(dx: float, dy: float) -> None:
        # Perpendicular direction (for stepping between parallel lines).
        px, py = -dy, dx
        # Centre of the region.
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        for i in range(-n_lines, n_lines + 1):
            # Origin of this particular line, offset along perpendicular.
            ox = cx + px * i * spacing
            oy = cy + py * i * spacing
            # Endpoints far enough to span the region.
            lx0 = ox - dx * diag
            ly0 = oy - dy * diag
            lx1 = ox + dx * diag
            ly1 = oy + dy * diag
            # Clip to bbox (Pillow clips for us, but avoid huge coords).
            draw.line(
                [(lx0, ly0), (lx1, ly1)],
                fill=color,
                width=width,
            )

    _draw_family(dx, dy)
    _draw_family(dx, -dy)


# ---------------------------------------------------------------------------
# Ellipses
# ---------------------------------------------------------------------------

def filled_ellipse(
    img: Image.Image,
    bbox: Tuple[int, int, int, int],
    fill: Color = (255, 255, 255, 255),
) -> None:
    """Draw a filled ellipse within the given bounding box.

    Args:
        img:  Target RGBA image.
        bbox: (x0, y0, x1, y1) bounding rectangle.
        fill: RGBA fill colour.
    """
    draw = ImageDraw.Draw(img, "RGBA")
    draw.ellipse(bbox, fill=fill)


def outlined_ellipse(
    img: Image.Image,
    bbox: Tuple[int, int, int, int],
    outline: Color = (255, 255, 255, 255),
    width: int = 1,
) -> None:
    """Draw an ellipse outline (no fill) within the given bounding box.

    Args:
        img:     Target RGBA image.
        bbox:    (x0, y0, x1, y1) bounding rectangle.
        outline: RGBA stroke colour.
        width:   Line width in pixels.
    """
    draw = ImageDraw.Draw(img, "RGBA")
    draw.ellipse(bbox, outline=outline, width=width)


# ---------------------------------------------------------------------------
# High-level shape factories — each returns a new RGBA Image
# ---------------------------------------------------------------------------

def solid_rect(w: int, h: int, color: Color) -> Image.Image:
    """Create a filled rectangle on a transparent background.

    Args:
        w:     Width in pixels.
        h:     Height in pixels.
        color: RGBA fill colour.

    Returns:
        New RGBA ``Image`` of size (w, h).
    """
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle((0, 0, w - 1, h - 1), fill=color)
    return img


def labeled_rect(w: int, h: int, color: Color, label: str) -> Image.Image:
    """Create a filled rectangle with a centred text label.

    Auto-picks text colour: white on dark backgrounds, dark grey on
    light backgrounds (based on perceived luminance).

    Args:
        w:     Width in pixels.
        h:     Height in pixels.
        color: RGBA fill colour for the rectangle.
        label: Text to draw centred on the rectangle.

    Returns:
        New RGBA ``Image`` of size (w, h).
    """
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle((0, 0, w - 1, h - 1), fill=color)

    # Choose contrasting text colour.
    luminance = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
    text_color: Color = (255, 255, 255, 255) if luminance < 140 else (40, 40, 40, 255)

    font = ImageFont.load_default()
    bbox = font.getbbox(label)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (w - tw) // 2
    ty = (h - th) // 2
    draw.text((tx, ty), label, fill=text_color, font=font)
    return img


def triangle(w: int, h: int, color: Color) -> Image.Image:
    """Create an isosceles triangle (apex centre-top, base at bottom).

    Args:
        w:     Width in pixels.
        h:     Height in pixels.
        color: RGBA fill colour.

    Returns:
        New RGBA ``Image`` of size (w, h).
    """
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    points = [(w // 2, 0), (w, h), (0, h)]
    filled_polygon(img, points, fill=color)
    return img


def circle(diameter: int, color: Color) -> Image.Image:
    """Create a filled ellipse (circle) on a transparent background.

    Args:
        diameter: Width and height in pixels.
        color:    RGBA fill colour.

    Returns:
        New RGBA ``Image`` of size (diameter, diameter).
    """
    img = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    filled_ellipse(img, (0, 0, diameter - 1, diameter - 1), fill=color)
    return img


def ring(diameter: int, outline_color: Color, width: int = 2) -> Image.Image:
    """Create a circle outline (ring) on a transparent background.

    Args:
        diameter:      Width and height in pixels.
        outline_color: RGBA stroke colour.
        width:         Line width in pixels.

    Returns:
        New RGBA ``Image`` of size (diameter, diameter).
    """
    img = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    outlined_ellipse(img, (0, 0, diameter - 1, diameter - 1),
                     outline=outline_color, width=width)
    return img
