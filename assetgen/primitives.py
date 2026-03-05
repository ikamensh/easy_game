"""
Reusable Pillow-based drawing helpers for procedural asset generation.

Three API layers:

**Low-level** — operate on an existing ``PIL.Image.Image`` (RGBA mode):
    ``filled_polygon``, ``outlined_polygon``, ``vertical_gradient``,
    ``horizontal_gradient``, ``crosshatch``, ``filled_ellipse``,
    ``outlined_ellipse``, ``linear_gradient``, ``radial_gradient``.

**Effects** — accept and return ``PIL.Image.Image``:
    ``apply_blur``, ``apply_drop_shadow``, ``apply_glow``, ``apply_noise``.

**High-level** — *return* a new ``PIL.Image.Image`` (RGBA, transparent bg):
    ``solid_rect``, ``labeled_rect``, ``triangle``, ``circle``, ``ring``.

**Color utilities** — pure functions on RGBA tuples:
    ``lighten``, ``darken``, ``adjust_alpha``.

**Supersampling** — context manager for anti-aliased rendering:
    ``supersample``.

Coordinates use top-left origin, matching Pillow and Saga2D conventions.
"""

from __future__ import annotations

import contextlib
from typing import Callable, Generator, List, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Color = Tuple[int, int, int, int]  # RGBA
Point = Tuple[float, float]        # (x, y)
ColorStop = Tuple[float, Color]    # (position 0..1, RGBA)


# ===================================================================
# Color utilities
# ===================================================================

def lighten(color: Color, amount: float = 0.2) -> Color:
    """Return *color* lightened toward white by *amount* (0.0–1.0).

    Linearly interpolates each RGB channel toward 255.  Alpha is preserved.

    Args:
        color:  RGBA colour tuple.
        amount: Blend factor — 0.0 = unchanged, 1.0 = pure white.

    Returns:
        New RGBA tuple.

    Example::

        >>> lighten((100, 50, 0, 255), 0.5)
        (178, 153, 128, 255)
    """
    amount = max(0.0, min(1.0, amount))
    r = int(color[0] + (255 - color[0]) * amount)
    g = int(color[1] + (255 - color[1]) * amount)
    b = int(color[2] + (255 - color[2]) * amount)
    return (r, g, b, color[3])


def darken(color: Color, amount: float = 0.2) -> Color:
    """Return *color* darkened toward black by *amount* (0.0–1.0).

    Linearly interpolates each RGB channel toward 0.  Alpha is preserved.

    Args:
        color:  RGBA colour tuple.
        amount: Blend factor — 0.0 = unchanged, 1.0 = pure black.

    Returns:
        New RGBA tuple.

    Example::

        >>> darken((100, 200, 150, 255), 0.5)
        (50, 100, 75, 255)
    """
    amount = max(0.0, min(1.0, amount))
    r = int(color[0] * (1.0 - amount))
    g = int(color[1] * (1.0 - amount))
    b = int(color[2] * (1.0 - amount))
    return (r, g, b, color[3])


def adjust_alpha(color: Color, alpha: int) -> Color:
    """Return *color* with its alpha channel replaced by *alpha*.

    Args:
        color: RGBA colour tuple.
        alpha: New alpha value (0–255).

    Returns:
        New RGBA tuple.

    Example::

        >>> adjust_alpha((255, 0, 0, 255), 128)
        (255, 0, 0, 128)
    """
    return (color[0], color[1], color[2], max(0, min(255, alpha)))


# ===================================================================
# Supersampling
# ===================================================================

@contextlib.contextmanager
def supersample(
    width: int,
    height: int,
    factor: int = 4,
) -> Generator[Image.Image, None, None]:
    """Context manager that renders at *factor* × resolution and downsamples.

    Yields an oversized RGBA ``Image`` for the caller to draw into.
    On exit the image is **replaced in-place** by a ``LANCZOS``-downsampled
    version at the original (*width*, *height*) size.

    Because ``Image`` objects cannot be mutated to a different size, the
    downsampled result is stored in the ``_result`` attribute of the yielded
    image.  Retrieve it after the ``with`` block::

        with supersample(64, 64) as big:
            filled_ellipse(big, (0, 0, big.width - 1, big.height - 1),
                           fill=(255, 0, 0, 255))
        final = big._result  # 64 × 64, anti-aliased

    Or use the helper :func:`supersample_draw` for a simpler one-shot API.

    Args:
        width:  Desired output width in pixels.
        height: Desired output height in pixels.
        factor: Supersampling multiplier (default 4 — i.e. 4 × 4 = 16× pixels).

    Yields:
        Oversize RGBA ``Image`` of size (width * factor, height * factor).
    """
    big = Image.new("RGBA", (width * factor, height * factor), (0, 0, 0, 0))
    yield big
    # Downsample with high-quality resampling.
    big._result = big.resize((width, height), Image.LANCZOS)  # type: ignore[attr-defined]


def supersample_draw(
    width: int,
    height: int,
    draw_fn: Callable[[Image.Image], None],
    factor: int = 4,
) -> Image.Image:
    """One-shot supersampled rendering.

    Calls *draw_fn(big_image)* on an image that is *factor* × larger,
    then downsamples to (*width*, *height*) with ``LANCZOS``.

    Args:
        width:   Desired output width.
        height:  Desired output height.
        draw_fn: A callable that draws onto the oversized image.
        factor:  Supersampling multiplier (default 4).

    Returns:
        Downsampled RGBA ``Image`` of size (width, height).

    Example::

        def paint(img):
            filled_ellipse(img, (0, 0, img.width - 1, img.height - 1),
                           fill=(0, 200, 100, 255))

        smooth_circle = supersample_draw(64, 64, paint)
    """
    with supersample(width, height, factor) as big:
        draw_fn(big)
    return big._result  # type: ignore[attr-defined]


# ===================================================================
# Polygons
# ===================================================================

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


# ===================================================================
# Gradient fills
# ===================================================================

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


def linear_gradient(
    img: Image.Image,
    stops: Sequence[ColorStop],
    start: Point = (0.0, 0.0),
    end: Point = (1.0, 0.0),
    bbox: Tuple[int, int, int, int] | None = None,
) -> None:
    """Fill a region with a multi-stop linear gradient (numpy-accelerated).

    The gradient direction is defined by *start* and *end* in normalised
    coordinates (0.0–1.0) relative to the bounding box.

    Args:
        img:   Target RGBA image.
        stops: Sequence of ``(position, (r, g, b, a))`` tuples.
               Positions must be in [0, 1] and sorted ascending.
               At least two stops are required.
        start: Gradient origin in normalised bbox coordinates.
        end:   Gradient terminus in normalised bbox coordinates.
        bbox:  Optional (x0, y0, x1, y1) sub-region; defaults to full image.

    Example::

        linear_gradient(img, [
            (0.0, (255, 0, 0, 255)),
            (0.5, (255, 255, 0, 255)),
            (1.0, (0, 0, 255, 255)),
        ])
    """
    if len(stops) < 2:
        raise ValueError("linear_gradient requires at least 2 colour stops")

    x0, y0, x1, y1 = bbox if bbox else (0, 0, img.width, img.height)
    w = x1 - x0
    h = y1 - y0
    if w <= 0 or h <= 0:
        return

    # Build coordinate grids for the sub-region.
    ys, xs = np.mgrid[0:h, 0:w]  # shape (h, w) each

    # Gradient direction vector in pixel space.
    sx, sy = start[0] * w, start[1] * h
    ex, ey = end[0] * w, end[1] * h
    dx, dy = ex - sx, ey - sy
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-9:
        return

    # Project every pixel onto the gradient axis → parameter t ∈ [0, 1].
    t = ((xs - sx) * dx + (ys - sy) * dy) / length_sq  # (h, w)
    t = np.clip(t, 0.0, 1.0)

    # Unpack stops.
    positions = np.array([s[0] for s in stops], dtype=np.float64)
    colors = np.array([s[1] for s in stops], dtype=np.float64)  # (N, 4)

    # Interpolate each channel.
    result = np.zeros((h, w, 4), dtype=np.uint8)
    for ch in range(4):
        channel_values = np.interp(t, positions, colors[:, ch])
        result[:, :, ch] = np.clip(channel_values, 0, 255).astype(np.uint8)

    # Paste onto image.
    patch = Image.fromarray(result, "RGBA")
    img.paste(patch, (x0, y0), patch)


def radial_gradient(
    img: Image.Image,
    center: Point,
    radius: float,
    stops: Sequence[ColorStop],
    bbox: Tuple[int, int, int, int] | None = None,
) -> None:
    """Fill a region with a multi-stop radial gradient (numpy-accelerated).

    The gradient radiates outward from *center*.  Pixels beyond *radius*
    are filled with the colour of the last stop.

    Args:
        img:    Target RGBA image.
        center: Centre point in pixel coordinates (relative to image, not bbox).
        radius: Outer radius of the gradient in pixels.
        stops:  Sequence of ``(position, (r, g, b, a))`` tuples.
                Positions in [0, 1]: 0 = centre, 1 = edge at *radius*.
                At least two stops required.
        bbox:   Optional (x0, y0, x1, y1) sub-region; defaults to full image.

    Example::

        radial_gradient(img, (32, 32), 30, [
            (0.0, (255, 255, 255, 255)),
            (1.0, (0, 0, 0, 255)),
        ])
    """
    if len(stops) < 2:
        raise ValueError("radial_gradient requires at least 2 colour stops")
    if radius <= 0:
        return

    x0, y0, x1, y1 = bbox if bbox else (0, 0, img.width, img.height)
    w = x1 - x0
    h = y1 - y0
    if w <= 0 or h <= 0:
        return

    # Coordinate grids in image-space.
    ys, xs = np.mgrid[y0:y1, x0:x1]  # shape (h, w)

    # Distance from centre → normalised parameter t.
    dist = np.sqrt((xs - center[0]) ** 2 + (ys - center[1]) ** 2)
    t = np.clip(dist / radius, 0.0, 1.0)

    # Unpack stops.
    positions = np.array([s[0] for s in stops], dtype=np.float64)
    colors = np.array([s[1] for s in stops], dtype=np.float64)

    # Interpolate each channel.
    result = np.zeros((h, w, 4), dtype=np.uint8)
    for ch in range(4):
        channel_values = np.interp(t, positions, colors[:, ch])
        result[:, :, ch] = np.clip(channel_values, 0, 255).astype(np.uint8)

    patch = Image.fromarray(result, "RGBA")
    img.paste(patch, (x0, y0), patch)


# ===================================================================
# Hatching / patterns
# ===================================================================

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


# ===================================================================
# Ellipses
# ===================================================================

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


# ===================================================================
# Effects
# ===================================================================

def apply_blur(
    img: Image.Image,
    radius: float = 2.0,
) -> Image.Image:
    """Apply a Gaussian blur to *img*.

    Args:
        img:    Source RGBA image.
        radius: Blur radius in pixels (default 2.0).

    Returns:
        New blurred RGBA ``Image`` (same size as input).
    """
    return img.filter(ImageFilter.GaussianBlur(radius=radius))


def apply_drop_shadow(
    img: Image.Image,
    offset: Tuple[int, int] = (4, 4),
    blur_radius: float = 4.0,
    shadow_color: Color = (0, 0, 0, 128),
    expand: int = 0,
) -> Image.Image:
    """Return *img* composited over a soft drop shadow.

    The returned image is larger than the input by ``2 * expand`` pixels
    in each dimension to accommodate the shadow without clipping.

    Args:
        img:          Source RGBA image.
        offset:       (dx, dy) shadow offset in pixels.
        blur_radius:  Gaussian blur radius for the shadow.
        shadow_color: RGBA colour of the shadow.
        expand:       Extra padding in pixels around all edges (default 0).

    Returns:
        New RGBA ``Image``.
    """
    src_w, src_h = img.size
    out_w = src_w + 2 * expand
    out_h = src_h + 2 * expand

    # Build shadow layer: use the source alpha channel as the shadow mask.
    shadow = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    # Extract the alpha channel from the source and tint it with shadow_color.
    alpha = img.split()[3]  # 'L' mode
    shadow_fill = Image.new("RGBA", img.size, shadow_color)
    shadow_fill.putalpha(alpha)

    shadow_x = expand + offset[0]
    shadow_y = expand + offset[1]
    shadow.paste(shadow_fill, (shadow_x, shadow_y), shadow_fill)

    # Blur the shadow.
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Composite original on top.
    shadow.paste(img, (expand, expand), img)
    return shadow


def apply_glow(
    img: Image.Image,
    radius: float = 6.0,
    glow_color: Color | None = None,
    intensity: float = 0.6,
) -> Image.Image:
    """Return *img* with a soft glow effect around opaque regions.

    Works by blurring a tinted copy of the source and compositing the
    original on top.

    Args:
        img:        Source RGBA image.
        radius:     Gaussian blur radius for the glow.
        glow_color: RGBA colour for the glow.  ``None`` = derive from the
                    source (white glow).
        intensity:  Opacity multiplier for the glow layer (0.0–1.0).

    Returns:
        New RGBA ``Image`` (same size as input).
    """
    if glow_color is None:
        glow_color = (255, 255, 255, 255)

    # Build a tinted copy using only the source's alpha mask.
    alpha = img.split()[3]
    glow_layer = Image.new("RGBA", img.size, glow_color)
    glow_layer.putalpha(alpha)

    # Scale glow alpha by intensity.
    if intensity < 1.0:
        glow_a = glow_layer.split()[3]
        glow_a = glow_a.point(lambda v: int(v * intensity))
        glow_layer.putalpha(glow_a)

    # Blur the glow layer.
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=radius))

    # Composite: glow behind, original on top.
    result = Image.new("RGBA", img.size, (0, 0, 0, 0))
    result = Image.alpha_composite(result, glow_layer)
    result = Image.alpha_composite(result, img)
    return result


# ===================================================================
# Texture
# ===================================================================

def apply_noise(
    img: Image.Image,
    amount: float = 0.1,
    monochrome: bool = True,
    seed: int | None = None,
) -> Image.Image:
    """Apply subtle noise / grain to *img* (numpy-accelerated).

    Adds random pixel-level variation to give flat colours a textured,
    hand-painted feel — useful for procedural game sprites.

    Args:
        img:        Source RGBA image.
        amount:     Noise strength (0.0 = none, 1.0 = full random).
                    Typical values: 0.05–0.2.
        monochrome: If ``True``, the same noise value is applied to R, G, B.
                    If ``False``, independent noise per channel.
        seed:       Optional RNG seed for reproducibility.

    Returns:
        New RGBA ``Image`` (same size as input).
    """
    rng = np.random.default_rng(seed)
    arr = np.array(img, dtype=np.float64)  # (H, W, 4)
    h, w = arr.shape[:2]

    # Noise range: +-128 * amount.
    strength = 128.0 * amount

    if monochrome:
        noise = rng.uniform(-strength, strength, (h, w, 1))
        noise = np.broadcast_to(noise, (h, w, 3))
    else:
        noise = rng.uniform(-strength, strength, (h, w, 3))

    # Apply to RGB channels only — leave alpha untouched.
    arr[:, :, :3] = np.clip(arr[:, :, :3] + noise, 0, 255)

    return Image.fromarray(arr.astype(np.uint8), "RGBA")


# ===================================================================
# High-level shape factories — each returns a new RGBA Image
# ===================================================================

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
