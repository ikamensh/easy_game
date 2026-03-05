"""Generate 20 PNG sprite assets for the tactical battle vignette demo.

Each public ``make_*`` function returns a ``PIL.Image.Image`` (RGBA mode).
``generate(output_dir)`` saves all 20 files and returns the list of paths.

Filenames and sizes match the architecture contract::

    warrior_idle_01.png          64x64
    warrior_walk_{01..04}.png    64x64
    warrior_attack_{01..03}.png  64x64
    skeleton_idle_01.png         64x64
    skeleton_walk_{01..04}.png   64x64
    skeleton_hit_{01..03}.png    64x64
    skeleton_death_{01..03}.png  64x64
    select_ring.png              72x72

Run from project root::

    python -m assetgen.generate_all --battle
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw

from assetgen.primitives import (
    adjust_alpha,
    apply_blur,
    apply_drop_shadow,
    apply_glow,
    apply_noise,
    darken,
    filled_ellipse,
    filled_polygon,
    lighten,
    linear_gradient,
    outlined_ellipse,
    outlined_polygon,
    radial_gradient,
    supersample_draw,
)
from assetgen.wireframe import (
    octahedron,
    render_wireframe,
    rotate_x,
    rotate_y,
    rotate_z,
)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
# Warrior — steel-blue armour tones
BLUE = (30, 144, 255, 255)        # warrior primary (armour)
BLUE_DARK = (15, 80, 160, 255)    # warrior shadow / shield
BLUE_LIGHT = (80, 180, 255, 255)  # warrior highlight / rim light

# Metallic shades for armour gradients
STEEL_HIGHLIGHT = (190, 210, 230, 255)
STEEL_MID = (120, 140, 165, 255)
STEEL_SHADOW = (55, 70, 95, 255)

# Sword / blade
BLADE_SILVER = (200, 210, 220, 255)
BLADE_EDGE = (160, 170, 180, 255)
BLADE_SHINE = (240, 245, 255, 255)

# Shield gem
GEM_CYAN = (0, 255, 220, 255)
GEM_CORE = (180, 255, 245, 255)
GEM_DARK = (0, 120, 100, 255)

# Skeleton — bone tones and undead accents
RED = (220, 20, 60, 255)          # skeleton body / ribcage fill
RED_DARK = (140, 10, 30, 255)     # skeleton deep shadow
RED_LIGHT = (255, 80, 100, 255)   # skeleton highlight / hit flash tint
WHITE = (255, 255, 255, 255)
YELLOW = (255, 255, 0, 255)       # select ring
GOLD_BRIGHT = (255, 230, 80, 255)  # ring highlight (inner edge)
GOLD_MID = (255, 200, 0, 255)     # ring body mid-tone
GOLD_DARK = (200, 150, 0, 255)    # ring shadow (outer edge)
GOLD_GLOW = (255, 240, 120, 100)  # radial glow around ring

# Bone palette — gradient-ready
BONE_LIGHT = (245, 238, 220, 255)  # bone highlight (top of skull)
BONE = (230, 220, 200, 255)        # bone mid-tone
BONE_MID = (210, 198, 175, 255)    # bone mid-dark
BONE_DARK = (180, 170, 150, 255)   # bone shadow
BONE_DEEP = (130, 120, 100, 255)   # deep bone crevice

SKULL_WHITE = (240, 235, 225, 255)

# Eye sockets — glowing red
EYE_RED_CORE = (255, 60, 30, 255)   # bright centre
EYE_RED_MID = (220, 20, 0, 255)     # mid glow
EYE_RED_OUTER = (120, 0, 0, 200)    # dark edge

SIZE = (64, 64)  # all battle sprites are 64x64
CX, CY = 32, 32  # centre

# Supersampling factor — all warrior rendering is done at SS×
_SS = 4


# ===================================================================
# Warrior internal drawing helpers (operate at supersampled scale)
# ===================================================================

def _s(v: float) -> float:
    """Scale a 1× coordinate to supersampled space."""
    return v * _SS


def _si(v: float) -> int:
    """Scale a 1× coordinate to supersampled space (integer)."""
    return int(v * _SS)


# -------------------------------------------------------------------
# Helmet
# -------------------------------------------------------------------

def _draw_helmet(
    img: Image.Image,
    cx: float,
    head_y: float,
) -> None:
    """Draw a rounded helmet with a metallic gradient and visor slit.

    The helmet is an ellipse with a vertical linear gradient (bright at
    top, dark at base) to suggest a curved metal surface.  A rim-light
    highlight is drawn along the upper-left edge.
    """
    hw = _s(7.5)   # half-width
    hh = _s(8.0)   # half-height
    x0 = cx - hw
    y0 = head_y - hh
    x1 = cx + hw
    y1 = head_y + hh

    # Base fill — dark steel
    filled_ellipse(img, (int(x0), int(y0), int(x1), int(y1)), fill=BLUE)

    # Metallic gradient overlay (on a temp layer, masked to the ellipse)
    hbox = (int(x0), int(y0), int(x1), int(y1))
    grad_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    linear_gradient(
        grad_layer,
        stops=[
            (0.0, BLUE_LIGHT),
            (0.4, BLUE),
            (1.0, BLUE_DARK),
        ],
        start=(0.0, 0.0),
        end=(0.0, 1.0),
        bbox=hbox,
    )
    # Mask the gradient to the helmet ellipse
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    md.ellipse(hbox, fill=255)
    img.paste(Image.composite(grad_layer, img, mask), (0, 0))

    # Visor slit
    draw = ImageDraw.Draw(img, "RGBA")
    visor_y = head_y + _s(1)
    draw.line(
        [(cx - _s(4), visor_y), (cx + _s(4), visor_y)],
        fill=STEEL_SHADOW,
        width=max(1, _si(1.5)),
    )

    # Rim light — bright crescent on upper-left
    rim = adjust_alpha(BLUE_LIGHT, 140)
    draw.arc(
        (int(x0 + _s(1)), int(y0 + _s(0.5)),
         int(x1 - _s(1)), int(y1 - _s(1))),
        start=200, end=320,
        fill=rim,
        width=max(1, _si(1)),
    )


# -------------------------------------------------------------------
# Torso (chestplate)
# -------------------------------------------------------------------

def _draw_torso(
    img: Image.Image,
    cx: float,
    torso_top: float,
    torso_bottom: float,
    shoulder_half: float = 11.0,
    hip_half: float = 8.5,
) -> None:
    """Draw the chestplate with a metallic vertical gradient.

    The torso is a trapezoidal polygon (wider at shoulders) filled with a
    multi-stop gradient simulating curved plate armour.  A bright outline
    provides a rim-light effect.
    """
    sh = _s(shoulder_half)
    hh = _s(hip_half)
    top = torso_top
    bot = torso_bottom

    torso_pts = [
        (cx - sh, top),   # left shoulder
        (cx + sh, top),   # right shoulder
        (cx + hh, bot),   # right hip
        (cx - hh, bot),   # left hip
    ]

    # Flat fill first (polygon baseline)
    filled_polygon(img, torso_pts, fill=BLUE)

    # Gradient overlay masked to the torso shape
    bbox = (int(cx - sh) - 1, int(top) - 1, int(cx + sh) + 1, int(bot) + 1)
    grad = Image.new("RGBA", img.size, (0, 0, 0, 0))
    linear_gradient(
        grad,
        stops=[
            (0.0, BLUE_LIGHT),
            (0.25, BLUE),
            (0.75, BLUE_DARK),
            (1.0, darken(BLUE_DARK, 0.3)),
        ],
        start=(0.0, 0.0),
        end=(0.0, 1.0),
        bbox=bbox,
    )
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    md.polygon([(int(p[0]), int(p[1])) for p in torso_pts], fill=255)
    img.paste(Image.composite(grad, img, mask), (0, 0))

    # Rim-light outline
    outlined_polygon(img, torso_pts, outline=BLUE_LIGHT, width=max(1, _si(0.8)))


# -------------------------------------------------------------------
# Arms
# -------------------------------------------------------------------

def _draw_arm(
    img: Image.Image,
    shoulder: Tuple[float, float],
    hand: Tuple[float, float],
    color: Tuple[int, int, int, int],
    width: int = 0,
) -> None:
    """Draw a single arm as a thick line segment with rounded ends."""
    draw = ImageDraw.Draw(img, "RGBA")
    w = width if width > 0 else max(2, _si(3))
    draw.line(
        [(shoulder[0], shoulder[1]), (hand[0], hand[1])],
        fill=color,
        width=w,
    )
    # Small round pauldron at shoulder
    r = _s(2.5)
    filled_ellipse(
        img,
        (int(shoulder[0] - r), int(shoulder[1] - r),
         int(shoulder[0] + r), int(shoulder[1] + r)),
        fill=lighten(color, 0.15),
    )


# -------------------------------------------------------------------
# Legs
# -------------------------------------------------------------------

def _draw_legs(
    img: Image.Image,
    cx: float,
    hip_y: float,
    left_foot_x: float,
    right_foot_x: float,
    foot_y: float,
) -> None:
    """Draw two legs with subtle gradient shading and boot caps."""
    draw = ImageDraw.Draw(img, "RGBA")

    leg_w = max(2, _si(3))
    boot_h = _s(3)
    boot_hw = _s(3.5)

    for foot_x, hip_offset in [(left_foot_x, -_s(4)), (right_foot_x, _s(4))]:
        hip_x = cx + hip_offset
        # Thigh
        draw.line(
            [(hip_x, hip_y), (foot_x, foot_y - boot_h)],
            fill=BLUE_DARK,
            width=leg_w,
        )
        # Boot
        filled_polygon(
            img,
            [
                (foot_x - boot_hw, foot_y - boot_h),
                (foot_x + boot_hw, foot_y - boot_h),
                (foot_x + boot_hw, foot_y),
                (foot_x - boot_hw, foot_y),
            ],
            fill=darken(BLUE_DARK, 0.25),
        )


# -------------------------------------------------------------------
# Shield (kite shape with gradient + glowing gem)
# -------------------------------------------------------------------

def _draw_shield(
    img: Image.Image,
    cx: float,
    cy: float,
    size: float = 13.0,
    gem_angle: int = 0,
) -> None:
    """Draw a kite shield with a metallic gradient and a glowing gem.

    The shield uses a vertical linear gradient and a bright rim outline.
    The gem at the centre uses ``radial_gradient`` on a constrained bbox
    and gets a rotating octahedron wireframe whose colour/glow varies
    with *gem_angle*.
    """
    s = _s(size)
    # Kite-shield vertices
    top = (cx, cy - s)
    left = (cx - s * 0.55, cy - s * 0.15)
    bottom = (cx, cy + s * 0.55)
    right = (cx + s * 0.55, cy - s * 0.15)
    pts = [top, right, bottom, left]

    # Base fill
    filled_polygon(img, pts, fill=BLUE_DARK)

    # Gradient overlay masked to shield polygon
    bbox = (int(cx - s * 0.6), int(cy - s - 1),
            int(cx + s * 0.6), int(cy + s * 0.6 + 1))
    grad = Image.new("RGBA", img.size, (0, 0, 0, 0))
    linear_gradient(
        grad,
        stops=[
            (0.0, lighten(BLUE_DARK, 0.35)),
            (0.5, BLUE_DARK),
            (1.0, darken(BLUE_DARK, 0.4)),
        ],
        start=(0.0, 0.0),
        end=(0.0, 1.0),
        bbox=bbox,
    )
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    md.polygon([(int(p[0]), int(p[1])) for p in pts], fill=255)
    img.paste(Image.composite(grad, img, mask), (0, 0))

    # Rim outline
    outlined_polygon(img, pts, outline=BLUE_LIGHT, width=max(1, _si(0.8)))

    # --- Gem ---
    gem_r = _s(3.5)
    gem_cx, gem_cy = cx, cy - s * 0.15

    # Glow halo — rendered on a separate layer with a tight bbox so it
    # does not bleed across the entire canvas.
    halo_r = gem_r * 2.0
    phase = gem_angle * math.pi / 4
    pulse = 0.6 + 0.4 * math.sin(phase)  # pulsing intensity
    halo_alpha = int(70 * pulse)

    halo_bbox = (
        max(0, int(gem_cx - halo_r) - 1),
        max(0, int(gem_cy - halo_r) - 1),
        min(img.width, int(gem_cx + halo_r) + 2),
        min(img.height, int(gem_cy + halo_r) + 2),
    )
    halo_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    radial_gradient(
        halo_layer,
        (gem_cx, gem_cy),
        halo_r,
        stops=[
            (0.0, adjust_alpha(GEM_CYAN, min(255, halo_alpha + 100))),
            (0.5, adjust_alpha(GEM_CYAN, halo_alpha)),
            (1.0, (0, 0, 0, 0)),
        ],
        bbox=halo_bbox,
    )
    img.paste(Image.alpha_composite(
        img.crop(halo_bbox).copy(),
        halo_layer.crop(halo_bbox),
    ), (halo_bbox[0], halo_bbox[1]))

    # Gem body — radial gradient (tight bbox)
    gem_bbox = (
        max(0, int(gem_cx - gem_r) - 1),
        max(0, int(gem_cy - gem_r) - 1),
        min(img.width, int(gem_cx + gem_r) + 2),
        min(img.height, int(gem_cy + gem_r) + 2),
    )
    radial_gradient(
        img,
        (gem_cx, gem_cy),
        gem_r,
        stops=[
            (0.0, GEM_CORE),
            (0.4, GEM_CYAN),
            (1.0, GEM_DARK),
        ],
        bbox=gem_bbox,
    )

    # Octahedron wireframe overlay
    verts, edges = octahedron()
    angle = phase
    rotated = []
    for v in verts:
        v2 = rotate_x(v, angle * 0.7)
        v2 = rotate_y(v2, angle)
        v2 = rotate_z(v2, angle * 0.3)
        rotated.append(v2)

    wire_alpha = int(180 + 75 * math.sin(phase * 1.5))
    wire_color = adjust_alpha(GEM_CYAN, min(255, wire_alpha))
    render_wireframe(
        img,
        rotated,
        edges,
        color=wire_color,
        width=max(1, _si(0.6)),
        projection="orthographic",
        ortho_scale=1.0,
        center=(gem_cx, gem_cy),
        scale=gem_r * 0.7,
    )


# -------------------------------------------------------------------
# Sword
# -------------------------------------------------------------------

def _draw_sword(
    img: Image.Image,
    hand_x: float,
    hand_y: float,
    blade_angle_deg: float = 60.0,
    blade_length: float = 14.0,
) -> None:
    """Draw a metallic sword with a gradient blade and edge glow.

    *blade_angle_deg* controls the sword angle (60 = resting downward,
    10 = near-horizontal thrust).  *blade_length* in 1× pixels.
    """
    draw = ImageDraw.Draw(img, "RGBA")
    angle = math.radians(blade_angle_deg)
    blen = _s(blade_length)
    tip_x = hand_x + blen * math.cos(angle)
    tip_y = hand_y - blen * math.sin(angle)

    # Blade body (wider line)
    blade_w = max(2, _si(2.5))
    draw.line([(hand_x, hand_y), (tip_x, tip_y)], fill=BLADE_SILVER, width=blade_w)
    # Edge highlight (thin bright centre line)
    draw.line([(hand_x, hand_y), (tip_x, tip_y)], fill=BLADE_SHINE, width=max(1, _si(0.8)))

    # Crossguard
    perp_x = -math.sin(angle) * _s(3.5)
    perp_y = -math.cos(angle) * _s(3.5)
    draw.line(
        [(hand_x - perp_x, hand_y - perp_y),
         (hand_x + perp_x, hand_y + perp_y)],
        fill=BLUE_DARK,
        width=max(2, _si(2)),
    )

    # Pommel (small circle)
    pommel_x = hand_x - math.cos(angle) * _s(2)
    pommel_y = hand_y + math.sin(angle) * _s(2)
    pr = _s(1.5)
    filled_ellipse(
        img,
        (int(pommel_x - pr), int(pommel_y - pr),
         int(pommel_x + pr), int(pommel_y + pr)),
        fill=BLUE_DARK,
    )


# -------------------------------------------------------------------
# Unified warrior renderer
# -------------------------------------------------------------------

def _draw_warrior(
    img: Image.Image,
    *,
    leg_offset: float = 0.0,
    body_bob: float = 0.0,
    shield_arm_angle: float = 0.0,
    sword_arm_angle: float = 0.0,
    blade_angle: float = 60.0,
    blade_length: float = 14.0,
    gem_angle: int = 0,
) -> None:
    """Draw the complete warrior onto *img* (at supersampled scale).

    All coordinates are in 1× space but automatically scaled by ``_s()``.

    Args:
        leg_offset:      Signed pixel shift for left/right foot spread.
        body_bob:         Vertical offset for torso/head (walk bobbing).
        shield_arm_angle: Extra downward offset for the shield arm.
        sword_arm_angle:  Extra downward offset for the sword arm.
        blade_angle:      Sword blade angle in degrees (60=resting, 10=thrust).
        blade_length:     Sword blade length in 1× pixels.
        gem_angle:        Gem rotation index (different per frame).
    """
    bob = _s(body_bob)

    # Key anchor positions (1× scaled to SS)
    head_y = _s(15) + bob
    torso_top = _s(22) + bob
    torso_bottom = _s(42) + bob
    hip_y = torso_bottom
    foot_y = _s(59)

    # --- Legs (drawn first — behind body) ---
    left_foot_x = _s(CX - 6 + leg_offset)
    right_foot_x = _s(CX + 6 - leg_offset)
    _draw_legs(img, _s(CX), hip_y, left_foot_x, right_foot_x, foot_y)

    # --- Torso (chestplate) ---
    _draw_torso(img, _s(CX), torso_top, torso_bottom)

    # --- Shield arm (left side) ---
    l_shoulder = (_s(CX) - _s(10), torso_top + _s(2))
    l_hand_y = _s(32) + _s(shield_arm_angle) + bob
    l_hand = (_s(CX) - _s(17), l_hand_y)
    _draw_arm(img, l_shoulder, l_hand, BLUE)

    # --- Shield + gem ---
    shield_cx = _s(CX) - _s(17)
    shield_cy = l_hand_y - _s(1)
    _draw_shield(img, shield_cx, shield_cy, size=11.0, gem_angle=gem_angle)

    # --- Sword arm (right side) ---
    r_shoulder = (_s(CX) + _s(10), torso_top + _s(2))
    r_hand_y = _s(30) + _s(sword_arm_angle) + bob
    r_hand = (_s(CX) + _s(17), r_hand_y)
    _draw_arm(img, r_shoulder, r_hand, BLUE)

    # --- Sword ---
    _draw_sword(
        img,
        hand_x=r_hand[0],
        hand_y=r_hand[1],
        blade_angle_deg=blade_angle,
        blade_length=blade_length,
    )

    # --- Helmet (drawn last — in front) ---
    _draw_helmet(img, _s(CX), head_y)


# -------------------------------------------------------------------
# Post-processing: rim light + drop shadow
# -------------------------------------------------------------------

def _post_process(sprite: Image.Image) -> Image.Image:
    """Apply rim lighting and a soft drop shadow, cropped back to 64×64.

    Rim lighting is a faint glow composited behind the sprite.
    The drop shadow is subtle — just enough to ground the character.
    """
    # Subtle rim glow
    result = apply_glow(
        sprite,
        radius=1.2,
        glow_color=BLUE_LIGHT,
        intensity=0.25,
    )

    # Soft drop shadow — rendered with expansion then cropped back to 64×64
    # so the shadow doesn't overwhelm the small canvas.
    padded = apply_drop_shadow(
        result,
        offset=(2, 2),
        blur_radius=2.5,
        shadow_color=(0, 0, 0, 70),
        expand=4,
    )
    # Crop the expanded image back to 64×64, centred.
    return padded.crop((4, 4, 4 + SIZE[0], 4 + SIZE[1]))


# ===================================================================
# Warrior sprites (8 images) — public API
# ===================================================================

def make_warrior_idle() -> Image.Image:
    """Warrior idle frame — standing at rest with shield and sword.

    All rendering is 4× supersampled and LANCZOS-downsampled to 64×64.
    Includes metallic gradient armour, a pulsing gem, rim lighting,
    and a soft drop shadow.
    """
    def paint(big: Image.Image) -> None:
        _draw_warrior(
            big,
            leg_offset=0.0,
            body_bob=0.0,
            blade_angle=60.0,
            blade_length=13.0,
            gem_angle=0,
        )

    sprite = supersample_draw(SIZE[0], SIZE[1], paint, factor=_SS)
    return _post_process(sprite)


def make_warrior_walk(frame: int) -> Image.Image:
    """Warrior walk frame *frame* (1–4).

    Four-phase walk cycle with natural weight shift:
        Frame 1: contact (left foot forward, body dips)
        Frame 2: passing (neutral, body rises)
        Frame 3: contact (right foot forward, body dips)
        Frame 4: passing (neutral, body rises higher)

    Each frame has a distinct gem rotation angle.
    """
    # Walk cycle parameters — sinusoidal bobbing + leg stride
    # Asymmetric values ensure every frame is visually distinct, even
    # between the two "contact" frames (1 and 3).
    #                       leg_off  bob    gem
    cycle = {
        1: (  7.0,  1.5,  1),  # left foot forward, deep dip
        2: (  2.0, -0.5,  2),  # passing, slight rise
        3: ( -5.0,  2.5,  3),  # right foot forward, deeper dip
        4: ( -2.0, -1.0,  4),  # passing, rise
    }
    leg_off, bob, gem = cycle[frame]

    def paint(big: Image.Image) -> None:
        _draw_warrior(
            big,
            leg_offset=leg_off,
            body_bob=bob,
            blade_angle=55.0,
            blade_length=13.0,
            gem_angle=gem,
        )

    sprite = supersample_draw(SIZE[0], SIZE[1], paint, factor=_SS)
    return _post_process(sprite)


def make_warrior_attack(frame: int) -> Image.Image:
    """Warrior attack frame *frame* (1–3).

    Three-phase attack with sword arc and semi-transparent motion trail:
        Frame 1: wind-up (sword pulled back, arm raised)
        Frame 2: mid-swing (sword sweeping forward)
        Frame 3: full thrust (sword extended, impact)

    Attack frames include a blurred motion trail of the previous pose
    composited behind the current frame for a sense of motion.
    """
    #                   arm_off  blade_angle  blade_len  gem
    phases = {
        1: (-5.0,   80.0,  13.0,  5),  # wind-up
        2: (-2.0,   35.0,  16.0,  6),  # mid-swing
        3: ( 3.0,   10.0,  20.0,  7),  # thrust
    }
    arm_off, b_angle, b_len, gem = phases[frame]

    def paint(big: Image.Image) -> None:
        _draw_warrior(
            big,
            leg_offset=0.0,
            body_bob=0.5 if frame == 3 else 0.0,
            sword_arm_angle=arm_off,
            blade_angle=b_angle,
            blade_length=b_len,
            gem_angle=gem,
        )

    sprite = supersample_draw(SIZE[0], SIZE[1], paint, factor=_SS)

    # --- Motion trail for frames 2 and 3 ---
    if frame >= 2:
        prev = phases[frame - 1]
        p_arm, p_bangle, p_blen, p_gem = prev

        def paint_prev(big: Image.Image) -> None:
            _draw_warrior(
                big,
                leg_offset=0.0,
                body_bob=0.0,
                sword_arm_angle=p_arm,
                blade_angle=p_bangle,
                blade_length=p_blen,
                gem_angle=p_gem,
            )

        ghost = supersample_draw(SIZE[0], SIZE[1], paint_prev, factor=_SS)
        ghost = apply_blur(ghost, radius=3.0)
        # Reduce alpha to make it a faint trail
        ghost_arr = ghost.split()
        faded_alpha = ghost_arr[3].point(lambda v: int(v * 0.3))
        ghost.putalpha(faded_alpha)
        # Composite: trail behind, then current frame on top
        result = Image.new("RGBA", SIZE, (0, 0, 0, 0))
        result = Image.alpha_composite(result, ghost)
        result = Image.alpha_composite(result, sprite)
        sprite = result

    return _post_process(sprite)


# ===================================================================
# Unified entry point (optional convenience)
# ===================================================================

def make_warrior_frame(pose: str, frame_idx: int = 1) -> Image.Image:
    """Unified factory for any warrior pose.

    Args:
        pose:      One of ``"idle"``, ``"walk"``, ``"attack"``.
        frame_idx: 1-based frame index (ignored for idle).

    Returns:
        64×64 RGBA ``Image``.

    Raises:
        ValueError: If *pose* is not recognised.
    """
    if pose == "idle":
        return make_warrior_idle()
    elif pose == "walk":
        return make_warrior_walk(frame_idx)
    elif pose == "attack":
        return make_warrior_attack(frame_idx)
    else:
        raise ValueError(f"Unknown warrior pose {pose!r}")


# ===================================================================
# Skeleton internal drawing helpers (operate at supersampled scale)
# ===================================================================

# -------------------------------------------------------------------
# Skull
# -------------------------------------------------------------------

def _draw_skull(
    img: Image.Image,
    cx: float,
    head_y: float,
    body_alpha: int = 255,
) -> None:
    """Draw a rounded skull with bone gradient, eye sockets, and jaw.

    The skull is wider than the warrior helmet to read as "bare bone"
    rather than armoured.  A vertical gradient runs from pale highlight
    at the crown to a darker shadow at the jaw line.
    """
    hw = _s(8.5)   # slightly wider than warrior helmet
    hh = _s(8.0)
    x0 = cx - hw
    y0 = head_y - hh
    x1 = cx + hw
    y1 = head_y + hh
    hbox = (int(x0), int(y0), int(x1), int(y1))

    # Base fill
    skull_base = adjust_alpha(BONE, body_alpha)
    filled_ellipse(img, hbox, fill=skull_base)

    # Bone gradient overlay masked to skull ellipse
    grad = Image.new("RGBA", img.size, (0, 0, 0, 0))
    linear_gradient(
        grad,
        stops=[
            (0.0, adjust_alpha(BONE_LIGHT, body_alpha)),
            (0.4, adjust_alpha(BONE, body_alpha)),
            (0.8, adjust_alpha(BONE_MID, body_alpha)),
            (1.0, adjust_alpha(BONE_DARK, body_alpha)),
        ],
        start=(0.0, 0.0),
        end=(0.0, 1.0),
        bbox=hbox,
    )
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    md.ellipse(hbox, fill=255)
    img.paste(Image.composite(grad, img, mask), (0, 0))

    # Rim-light crescent on upper-left
    if body_alpha > 80:
        draw = ImageDraw.Draw(img, "RGBA")
        rim = adjust_alpha(BONE_LIGHT, min(255, int(body_alpha * 0.6)))
        draw.arc(
            (int(x0 + _s(1.5)), int(y0 + _s(0.5)),
             int(x1 - _s(1.5)), int(y1 - _s(2))),
            start=200, end=320,
            fill=rim,
            width=max(1, _si(1)),
        )

    # --- Eye sockets (glowing red) ---
    if body_alpha > 60:
        eye_r = _s(2.8)
        eye_y = head_y + _s(0.5)
        eye_spacing = _s(4.5)

        for ex in [cx - eye_spacing, cx + eye_spacing]:
            # Glow halo — tight bbox on a separate layer
            halo_r = eye_r * 2.0
            halo_bbox = (
                max(0, int(ex - halo_r) - 1),
                max(0, int(eye_y - halo_r) - 1),
                min(img.width, int(ex + halo_r) + 2),
                min(img.height, int(eye_y + halo_r) + 2),
            )
            halo_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            glow_a = int(body_alpha * 0.4)
            radial_gradient(
                halo_layer,
                (ex, eye_y),
                halo_r,
                stops=[
                    (0.0, adjust_alpha(EYE_RED_CORE, min(255, glow_a + 60))),
                    (0.5, adjust_alpha(EYE_RED_MID, glow_a)),
                    (1.0, (0, 0, 0, 0)),
                ],
                bbox=halo_bbox,
            )
            img.paste(Image.alpha_composite(
                img.crop(halo_bbox).copy(),
                halo_layer.crop(halo_bbox),
            ), (halo_bbox[0], halo_bbox[1]))

            # Eye socket core — small radial gradient
            core_bbox = (
                max(0, int(ex - eye_r) - 1),
                max(0, int(eye_y - eye_r) - 1),
                min(img.width, int(ex + eye_r) + 2),
                min(img.height, int(eye_y + eye_r) + 2),
            )
            radial_gradient(
                img,
                (ex, eye_y),
                eye_r,
                stops=[
                    (0.0, adjust_alpha(EYE_RED_CORE, body_alpha)),
                    (0.6, adjust_alpha(EYE_RED_MID, body_alpha)),
                    (1.0, adjust_alpha(EYE_RED_OUTER, int(body_alpha * 0.7))),
                ],
                bbox=core_bbox,
            )

    # --- Jaw line ---
    if body_alpha > 80:
        draw = ImageDraw.Draw(img, "RGBA")
        jaw_y = head_y + _s(5)
        jaw_color = adjust_alpha(BONE_DARK, body_alpha)
        draw.line(
            [(cx - _s(5), jaw_y), (cx + _s(5), jaw_y)],
            fill=jaw_color,
            width=max(1, _si(1)),
        )
        # Teeth suggestion — tiny vertical lines
        for tx in range(-3, 4, 2):
            draw.line(
                [(cx + _s(tx), jaw_y), (cx + _s(tx), jaw_y + _s(1.5))],
                fill=adjust_alpha(BONE_MID, body_alpha),
                width=max(1, _si(0.6)),
            )


# -------------------------------------------------------------------
# Ribcage
# -------------------------------------------------------------------

def _draw_ribcage(
    img: Image.Image,
    cx: float,
    top_y: float,
    bottom_y: float,
    body_alpha: int = 255,
) -> None:
    """Draw a diamond-shaped ribcage with gradient and rib lines.

    The ribcage uses a dark-red base with bone-coloured rib lines,
    distinct from the warrior's solid blue chestplate.
    """
    half_w = _s(12)
    mid_y = (top_y + bottom_y) / 2.0

    pts = [
        (cx, top_y),             # top
        (cx + half_w, mid_y),    # right
        (cx, bottom_y),          # bottom
        (cx - half_w, mid_y),    # left
    ]

    # Base fill — dark red
    base_color = adjust_alpha(RED_DARK, body_alpha)
    filled_polygon(img, pts, fill=base_color)

    # Gradient overlay — masked to diamond
    bbox = (int(cx - half_w) - 1, int(top_y) - 1,
            int(cx + half_w) + 1, int(bottom_y) + 1)
    grad = Image.new("RGBA", img.size, (0, 0, 0, 0))
    linear_gradient(
        grad,
        stops=[
            (0.0, adjust_alpha(RED, body_alpha)),
            (0.3, adjust_alpha(RED_DARK, body_alpha)),
            (1.0, adjust_alpha(darken(RED_DARK, 0.4), body_alpha)),
        ],
        start=(0.0, 0.0),
        end=(0.0, 1.0),
        bbox=bbox,
    )
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    md.polygon([(int(p[0]), int(p[1])) for p in pts], fill=255)
    img.paste(Image.composite(grad, img, mask), (0, 0))

    # Rib lines — bone-coloured horizontal stripes that narrow toward top/bottom
    if body_alpha > 60:
        draw = ImageDraw.Draw(img, "RGBA")
        height = bottom_y - top_y
        for i, t in enumerate([0.2, 0.35, 0.5, 0.65, 0.8]):
            ry = top_y + height * t
            # Width of rib at this height (widest at centre)
            dist_from_mid = abs(t - 0.5)
            rib_half_w = half_w * (1.0 - dist_from_mid * 2.0) * 0.85
            rib_color = adjust_alpha(BONE, min(body_alpha, 220 - i * 10))
            draw.line(
                [(cx - rib_half_w, ry), (cx + rib_half_w, ry)],
                fill=rib_color,
                width=max(1, _si(1)),
            )

    # Outline
    if body_alpha > 80:
        outlined_polygon(
            img, pts,
            outline=adjust_alpha(BONE_DARK, int(body_alpha * 0.5)),
            width=max(1, _si(0.6)),
        )


# -------------------------------------------------------------------
# Bone limbs (arms / legs)
# -------------------------------------------------------------------

def _draw_bone_limb(
    img: Image.Image,
    start: Tuple[float, float],
    end: Tuple[float, float],
    body_alpha: int = 255,
    width_scale: float = 1.0,
) -> None:
    """Draw a single bone limb segment with small joint circles at each end.

    Much thinner than the warrior's armoured limbs to emphasise the
    skeletal nature.
    """
    draw = ImageDraw.Draw(img, "RGBA")
    limb_color = adjust_alpha(BONE, body_alpha)
    limb_dark = adjust_alpha(BONE_DARK, body_alpha)
    w = max(1, _si(1.8 * width_scale))

    # Main bone shaft
    draw.line(
        [(start[0], start[1]), (end[0], end[1])],
        fill=limb_color,
        width=w,
    )
    # Dark edge for depth
    draw.line(
        [(start[0] + _s(0.3), start[1] + _s(0.3)),
         (end[0] + _s(0.3), end[1] + _s(0.3))],
        fill=limb_dark,
        width=max(1, w - 1),
    )

    # Joint circles at start and end
    jr = _s(1.8 * width_scale)
    for jx, jy in [start, end]:
        filled_ellipse(
            img,
            (int(jx - jr), int(jy - jr), int(jx + jr), int(jy + jr)),
            fill=limb_color,
        )


# -------------------------------------------------------------------
# Unified skeleton renderer
# -------------------------------------------------------------------

def _draw_skeleton(
    img: Image.Image,
    *,
    leg_offset: float = 0.0,
    body_bob: float = 0.0,
    body_alpha: int = 255,
    scatter: float = 0.0,
) -> None:
    """Draw the complete skeleton onto *img* (at supersampled scale).

    All coordinates are in 1× space but automatically scaled by ``_s()``.

    Args:
        leg_offset:  Signed pixel shift for left/right foot spread.
        body_bob:    Vertical offset for torso/head (walk bobbing).
        body_alpha:  Alpha for the entire skeleton (0–255, for death fade).
        scatter:     Decomposition factor (0.0=intact, 1.0=fully scattered).
    """
    bob = _s(body_bob)
    sdx = _s(scatter * 6)   # scatter horizontal drift
    sdy = _s(scatter * 4)   # scatter vertical drift

    # Key anchor positions
    head_y = _s(15) + bob + _s(scatter * -8)
    head_cx = _s(CX) + _s(scatter * 3)
    torso_top = _s(22) + bob - sdy
    torso_bottom = _s(44) + bob + sdy
    hip_y = torso_bottom
    foot_y = _s(59)

    # --- Legs (drawn first — behind body) ---
    left_foot = (
        _s(CX - 7 + leg_offset) + _s(scatter * -5),
        foot_y + sdy * 2,
    )
    right_foot = (
        _s(CX + 7 - leg_offset) + _s(scatter * 7),
        foot_y + sdy * 2,
    )
    left_hip = (_s(CX) - _s(5) + sdx, hip_y)
    right_hip = (_s(CX) + _s(5) + sdx, hip_y)

    _draw_bone_limb(img, left_hip, left_foot, body_alpha=body_alpha)
    _draw_bone_limb(img, right_hip, right_foot, body_alpha=body_alpha)

    # --- Ribcage ---
    ribcage_cx = _s(CX) + sdx
    _draw_ribcage(img, ribcage_cx, torso_top, torso_bottom,
                  body_alpha=body_alpha)

    # --- Arms ---
    l_shoulder = (ribcage_cx - _s(12), torso_top + _s(3))
    l_hand = (
        ribcage_cx - _s(20) + _s(scatter * -8),
        _s(38) + bob + sdy,
    )
    r_shoulder = (ribcage_cx + _s(12), torso_top + _s(3))
    r_hand = (
        ribcage_cx + _s(20) + _s(scatter * 10),
        _s(38) + bob + sdy,
    )
    _draw_bone_limb(img, l_shoulder, l_hand, body_alpha=body_alpha,
                    width_scale=0.85)
    _draw_bone_limb(img, r_shoulder, r_hand, body_alpha=body_alpha,
                    width_scale=0.85)

    # --- Skull (drawn last — in front) ---
    _draw_skull(img, head_cx, head_y, body_alpha=body_alpha)


# -------------------------------------------------------------------
# Skeleton post-processing
# -------------------------------------------------------------------

def _skeleton_post_process(
    sprite: Image.Image,
    noise_amount: float = 0.06,
    noise_seed: int | None = None,
) -> Image.Image:
    """Apply bone-texture noise, eye glow, and a soft drop shadow.

    Distinct from ``_post_process`` (warrior): uses a warm-white glow
    and subtle grain to suggest aged bone texture.
    """
    # Subtle bone-texture noise
    if noise_amount > 0:
        sprite = apply_noise(sprite, amount=noise_amount, monochrome=True,
                             seed=noise_seed)

    # Faint warm glow (from the eyes — red-ish)
    sprite = apply_glow(
        sprite,
        radius=1.0,
        glow_color=EYE_RED_MID,
        intensity=0.15,
    )

    # Soft drop shadow
    padded = apply_drop_shadow(
        sprite,
        offset=(2, 2),
        blur_radius=2.5,
        shadow_color=(0, 0, 0, 60),
        expand=4,
    )
    return padded.crop((4, 4, 4 + SIZE[0], 4 + SIZE[1]))


# -------------------------------------------------------------------
# Flash helper for hit effect (at supersampled scale)
# -------------------------------------------------------------------

def _draw_skeleton_flash(
    img: Image.Image,
    flash_color: Tuple[int, int, int, int] = WHITE,
    x_shift: float = 0.0,
    y_shift: float = 0.0,
) -> None:
    """Draw the skeleton silhouette in a single flat colour at SS scale.

    Used for the damage-flash effect in hit frames.
    """
    draw = ImageDraw.Draw(img, "RGBA")
    fc = flash_color
    dx, dy = _s(x_shift), _s(y_shift)
    cx = _s(CX) + dx

    # Skull
    hw, hh = _s(8.5), _s(8.0)
    filled_ellipse(
        img,
        (int(cx - hw), int(_s(15) - hh + dy),
         int(cx + hw), int(_s(15) + hh + dy)),
        fill=fc,
    )

    # Diamond ribcage
    half_w = _s(12)
    top_y = _s(22) + dy
    bot_y = _s(44) + dy
    mid_y = (top_y + bot_y) / 2
    filled_polygon(
        img,
        [(cx, top_y), (cx + half_w, mid_y),
         (cx, bot_y), (cx - half_w, mid_y)],
        fill=fc,
    )

    # Arms
    limb_w = max(2, _si(2.5))
    draw.line([(cx - _s(12), _s(25) + dy),
               (cx - _s(20), _s(38) + dy)], fill=fc, width=limb_w)
    draw.line([(cx + _s(12), _s(25) + dy),
               (cx + _s(20), _s(38) + dy)], fill=fc, width=limb_w)

    # Legs
    draw.line([(cx - _s(5), _s(44) + dy),
               (cx - _s(7), _s(59) + dy)], fill=fc, width=limb_w)
    draw.line([(cx + _s(5), _s(44) + dy),
               (cx + _s(7), _s(59) + dy)], fill=fc, width=limb_w)


# ===================================================================
# Skeleton sprites (12 images) — public API
# ===================================================================

def make_skeleton_idle() -> Image.Image:
    """Skeleton idle frame — standing at rest.

    4× supersampled with bone-gradient skull, glowing red eyes,
    diamond ribcage, and thin bony limbs.
    """
    def paint(big: Image.Image) -> None:
        _draw_skeleton(big, leg_offset=0.0, body_bob=0.0)

    sprite = supersample_draw(SIZE[0], SIZE[1], paint, factor=_SS)
    return _skeleton_post_process(sprite, noise_seed=100)


def make_skeleton_walk(frame: int) -> Image.Image:
    """Skeleton walk frame *frame* (1–4).

    Four-phase walk cycle with slight bobbing and leg movement.
    The skeleton's gait is jerkier than the warrior's — shorter
    stride, sharper bob — suggesting undead stiffness.
    """
    #                      leg_off  bob   seed
    cycle = {
        1: ( 5.0,  1.0,  101),  # left forward, dip
        2: ( 1.5, -0.5,  102),  # passing
        3: (-4.0,  1.5,  103),  # right forward, dip
        4: (-1.5, -0.8,  104),  # passing
    }
    leg_off, bob, seed = cycle[frame]

    def paint(big: Image.Image) -> None:
        _draw_skeleton(big, leg_offset=leg_off, body_bob=bob)

    sprite = supersample_draw(SIZE[0], SIZE[1], paint, factor=_SS)
    return _skeleton_post_process(sprite, noise_seed=seed)


def make_skeleton_hit(frame: int) -> Image.Image:
    """Skeleton hit frame *frame* (1–3).

    Frame 1: white flash — full silhouette.
    Frame 2: red recoil — skeleton with slight shift and red overlay.
    Frame 3: recovery flash — shifted silhouette to distinguish from frame 1.
    """
    if frame == 1:
        # White flash
        def paint(big: Image.Image) -> None:
            _draw_skeleton_flash(big, flash_color=WHITE)

        sprite = supersample_draw(SIZE[0], SIZE[1], paint, factor=_SS)
        return _skeleton_post_process(sprite, noise_amount=0.0)

    elif frame == 2:
        # Red recoil — normal skeleton with red tint
        def paint(big: Image.Image) -> None:
            _draw_skeleton(big, leg_offset=3.0, body_bob=0.0)

        sprite = supersample_draw(SIZE[0], SIZE[1], paint, factor=_SS)
        sprite = _skeleton_post_process(sprite, noise_seed=110)

        # Red tint overlay
        overlay = Image.new("RGBA", SIZE, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay, "RGBA")
        od.rectangle((0, 0, SIZE[0], SIZE[1]), fill=(255, 0, 0, 50))
        return Image.alpha_composite(sprite, overlay)

    else:
        # Recovery flash — shifted
        def paint(big: Image.Image) -> None:
            _draw_skeleton_flash(big, flash_color=WHITE,
                                 x_shift=3.0, y_shift=2.0)

        sprite = supersample_draw(SIZE[0], SIZE[1], paint, factor=_SS)
        return _skeleton_post_process(sprite, noise_amount=0.0)


def make_skeleton_death(frame: int) -> Image.Image:
    """Skeleton death frame *frame* (1–3).

    Progressive crumbling / dissolving:
        Frame 1: intact, light noise (beginning to crack).
        Frame 2: scattering outward, moderate noise, fading (alpha 170).
        Frame 3: heavily scattered, strong noise grain, very faded (alpha 85).

    Uses ``apply_noise`` with increasing intensity to simulate
    disintegration into dust.
    """
    #                       alpha  scatter  noise_amt  seed
    phases = {
        1: (255,  0.0,  0.08,  120),
        2: (170,  0.4,  0.18,  121),
        3: ( 85,  1.0,  0.35,  122),
    }
    alpha, scatter, noise_amt, seed = phases[frame]

    def paint(big: Image.Image) -> None:
        _draw_skeleton(big, leg_offset=0.0, body_bob=0.0,
                       body_alpha=alpha, scatter=scatter)

    sprite = supersample_draw(SIZE[0], SIZE[1], paint, factor=_SS)

    # Apply heavier noise for disintegration effect
    sprite = _skeleton_post_process(sprite, noise_amount=noise_amt,
                                    noise_seed=seed)

    # Additional blur on later frames for a dissolving look
    if frame >= 2:
        blur_radius = 0.5 if frame == 2 else 1.5
        sprite = apply_blur(sprite, radius=blur_radius)

    return sprite


# ===================================================================
# Unified skeleton entry point
# ===================================================================

def make_skeleton_frame(pose: str, frame_idx: int = 1) -> Image.Image:
    """Unified factory for any skeleton pose.

    Args:
        pose:      One of ``"idle"``, ``"walk"``, ``"hit"``, ``"death"``.
        frame_idx: 1-based frame index (ignored for idle).

    Returns:
        64×64 RGBA ``Image``.

    Raises:
        ValueError: If *pose* is not recognised.
    """
    if pose == "idle":
        return make_skeleton_idle()
    elif pose == "walk":
        return make_skeleton_walk(frame_idx)
    elif pose == "hit":
        return make_skeleton_hit(frame_idx)
    elif pose == "death":
        return make_skeleton_death(frame_idx)
    else:
        raise ValueError(f"Unknown skeleton pose {pose!r}")


# ===================================================================
# Select ring
# ===================================================================

RING_SIZE = (72, 72)

# The ring ellipse in 1× space: (x0, y0, x1, y1)
# Wider than tall to suggest a ground-plane perspective.
_RING_BBOX_1X = (4, 16, 67, 55)


def _draw_select_ring(img: Image.Image) -> None:
    """Draw the selection ring onto *img* at supersampled scale.

    Paints a glowing magical ring with:
    1. Soft radial glow halo along the ellipse path.
    2. Outer accent ring (thin, semi-transparent gold).
    3. Main ring body with a multi-stop linear gradient (gold).
    4. Inner accent ring (thin, bright highlight).
    """
    # Scale the 1× ellipse bbox to supersampled space
    bx0 = _RING_BBOX_1X[0] * _SS
    by0 = _RING_BBOX_1X[1] * _SS
    bx1 = _RING_BBOX_1X[2] * _SS
    by1 = _RING_BBOX_1X[3] * _SS

    ecx = (bx0 + bx1) / 2.0  # ellipse centre x
    ecy = (by0 + by1) / 2.0  # ellipse centre y
    erx = (bx1 - bx0) / 2.0  # ellipse radius x
    ery = (by1 - by0) / 2.0  # ellipse radius y

    # --- 1. Soft radial glow halo (beneath everything) ---
    # We use a radial gradient centred on the ellipse, with radius covering
    # the full ring area.  Since radial_gradient draws circles and our ring
    # is elliptical, we paint the glow on a separate layer that is vertically
    # stretched to match the ellipse aspect ratio.
    glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    glow_radius = max(erx, ery) + _s(6)
    glow_bbox = (
        max(0, int(ecx - glow_radius) - 2),
        max(0, int(ecy - glow_radius) - 2),
        min(img.width, int(ecx + glow_radius) + 3),
        min(img.height, int(ecy + glow_radius) + 3),
    )
    radial_gradient(
        glow_layer,
        (ecx, ecy),
        glow_radius,
        stops=[
            (0.0, (0, 0, 0, 0)),               # transparent at centre
            (0.45, (0, 0, 0, 0)),               # transparent until ring zone
            (0.6, GOLD_GLOW),                   # gold glow at ring area
            (0.75, adjust_alpha(GOLD_GLOW, 60)),
            (1.0, (0, 0, 0, 0)),               # fade out
        ],
        bbox=glow_bbox,
    )
    img.paste(Image.alpha_composite(
        img.crop(glow_bbox).copy(),
        glow_layer.crop(glow_bbox),
    ), (glow_bbox[0], glow_bbox[1]))

    # --- 2. Outer accent ring (thin, darker gold) ---
    outer_pad = _si(2.0)
    outer_bbox = (bx0 - outer_pad, by0 - outer_pad,
                  bx1 + outer_pad, by1 + outer_pad)
    outlined_ellipse(
        img, outer_bbox,
        outline=adjust_alpha(GOLD_DARK, 140),
        width=max(2, _si(1.5)),
    )

    # --- 3. Main ring body with gradient ---
    # Draw the ring as a thick outlined ellipse, then overlay a gradient
    # masked to the ring shape for a metallic look.
    main_width = max(4, _si(3.5))
    main_bbox = (bx0, by0, bx1, by1)

    # Base fill: solid gold ellipse ring
    outlined_ellipse(img, main_bbox, outline=GOLD_MID, width=main_width)

    # Gradient overlay — vertical gradient from bright top to dark bottom,
    # masked to the ring pixels.
    grad_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    grad_region = (bx0 - main_width, by0 - main_width,
                   bx1 + main_width, by1 + main_width)
    linear_gradient(
        grad_layer,
        stops=[
            (0.0, GOLD_BRIGHT),
            (0.3, GOLD_MID),
            (0.7, GOLD_DARK),
            (1.0, darken(GOLD_DARK, 0.3)),
        ],
        start=(0.0, 0.0),
        end=(0.0, 1.0),
        bbox=grad_region,
    )

    # Build a ring-shaped mask: outer ellipse minus inner ellipse
    ring_mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(ring_mask)
    # Outer boundary of the ring stroke
    half_w = main_width // 2 + 1
    md.ellipse(
        (bx0 - half_w, by0 - half_w, bx1 + half_w, by1 + half_w),
        fill=255,
    )
    # Inner boundary of the ring stroke (cut out)
    md.ellipse(
        (bx0 + half_w, by0 + half_w, bx1 - half_w, by1 - half_w),
        fill=0,
    )
    img.paste(Image.composite(grad_layer, img, ring_mask), (0, 0))

    # --- 4. Inner accent ring (thin, bright highlight) ---
    inner_pad = _si(2.0)
    inner_bbox = (bx0 + inner_pad, by0 + inner_pad,
                  bx1 - inner_pad, by1 - inner_pad)
    outlined_ellipse(
        img, inner_bbox,
        outline=adjust_alpha(GOLD_BRIGHT, 180),
        width=max(1, _si(1.0)),
    )

    # --- 5. Small bright specular highlights on top-left of ring ---
    draw = ImageDraw.Draw(img, "RGBA")
    # Specular dot on the top edge (simulates light reflection)
    spec_x = ecx - erx * 0.3
    spec_y = by0 + _s(1)
    spec_r = _s(2.5)
    filled_ellipse(
        img,
        (int(spec_x - spec_r), int(spec_y - spec_r),
         int(spec_x + spec_r), int(spec_y + spec_r)),
        fill=adjust_alpha(WHITE, 120),
    )


def make_select_ring() -> Image.Image:
    """Magical golden selection ring — 72×72 transparent.

    The ring is elliptical (wider than tall) to suggest a ground-plane
    perspective.  Rendered at 4× supersampling for smooth anti-aliased
    edges, with:

    - Multi-stop gold gradient on the ring body (metallic look)
    - Outer and inner accent rings for depth
    - Soft radial glow halo for a magical aura
    - Subtle noise texture for visual richness
    - Specular highlight for reflected light

    Returns:
        72×72 RGBA ``Image``.
    """
    sprite = supersample_draw(
        RING_SIZE[0], RING_SIZE[1], _draw_select_ring, factor=_SS,
    )

    # Subtle noise for texture
    sprite = apply_noise(sprite, amount=0.04, monochrome=True, seed=200)

    # Gentle gold glow around the ring
    sprite = apply_glow(
        sprite,
        radius=2.0,
        glow_color=GOLD_MID,
        intensity=0.3,
    )

    return sprite


# ===================================================================
# generate() — save all 20 PNGs
# ===================================================================

def generate(output_dir: Path) -> List[Path]:
    """Create all 20 battle-vignette sprite PNGs in *output_dir*.

    Returns a list of the written file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []

    def _save(img: Image.Image, name: str) -> None:
        path = output_dir / name
        img.save(path)
        print(f"Created {path}")
        written.append(path)

    # --- Warrior (8 files) ---
    _save(make_warrior_idle(), "warrior_idle_01.png")

    for i in range(1, 5):
        _save(make_warrior_walk(i), f"warrior_walk_{i:02d}.png")

    for i in range(1, 4):
        _save(make_warrior_attack(i), f"warrior_attack_{i:02d}.png")

    # --- Skeleton (12 files) ---
    _save(make_skeleton_idle(), "skeleton_idle_01.png")

    for i in range(1, 5):
        _save(make_skeleton_walk(i), f"skeleton_walk_{i:02d}.png")

    for i in range(1, 4):
        _save(make_skeleton_hit(i), f"skeleton_hit_{i:02d}.png")

    for i in range(1, 4):
        _save(make_skeleton_death(i), f"skeleton_death_{i:02d}.png")

    # --- Select ring (1 file) ---
    _save(make_select_ring(), "select_ring.png")

    return written
