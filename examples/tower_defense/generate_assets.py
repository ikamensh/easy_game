"""Generate all placeholder assets for the Tower Defense example.

Each public ``make_*`` function returns a ``PIL.Image.Image`` (RGBA mode).
``generate(output_dir)`` saves all files and returns the list of paths.

Assets generated::

    Terrain (32x32):
        grass.png            -- green grass tile with subtle texture
        path_straight.png    -- tan/brown walkable path
        path_turn.png        -- path corner piece

    Towers (32x32):
        tower_basic.png      -- simple turret (grey base + barrel)
        tower_sniper.png     -- long-range tower (narrow barrel, blue tint)
        tower_splash.png     -- area-of-effect tower (wide barrel, red tint)
        tower_slot.png       -- empty buildable slot marker

    Enemies (24x24):
        enemy_basic.png      -- red foot soldier
        enemy_fast.png       -- orange scout (smaller, triangular)
        enemy_tank.png       -- dark-red heavy (armoured look)

    Projectiles (8x8):
        projectile_basic.png -- yellow dot
        projectile_sniper.png -- cyan bolt
        projectile_splash.png -- orange ball

    Effects (various):
        explosion.png        -- 16x16 orange/yellow burst
        range_indicator.png  -- 64x64 semi-transparent circle

    UI elements:
        btn_normal.png       -- 80x32 dark button
        btn_hover.png        -- 80x32 lighter button
        btn_pressed.png      -- 80x32 darker pressed button
        panel_bg.png         -- 120x200 dark UI panel
        health_bar_bg.png    -- 24x4 dark health bar background
        health_bar_fill.png  -- 24x4 green health bar fill
        coin_icon.png        -- 16x16 gold coin
        heart_icon.png       -- 16x16 red heart
        wave_banner.png      -- 160x40 wave announcement banner

    HUD:
        hud_top_bar.png      -- 320x24 top HUD bar background

    Sound effects (WAV, assets/sounds/):
        sfx_shoot.wav        -- short click/pop for tower firing
        sfx_hit.wav          -- thud for projectile impact
        sfx_death.wav        -- descending tone for enemy death
        sfx_wave.wav         -- rising alert for wave start
        sfx_lose_life.wav    -- low buzz for life lost

    Music (WAV, assets/music/):
        bgm_game.wav         -- short looping placeholder

Run standalone::

    python examples/tower_defense/generate_assets.py
"""

from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so `assetgen` is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from assetgen.primitives import (  # noqa: E402
    filled_ellipse,
    filled_polygon,
    outlined_ellipse,
    outlined_polygon,
    vertical_gradient,
)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Color = Tuple[int, int, int, int]  # RGBA

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

# Terrain
GRASS_GREEN = (60, 140, 50, 255)
GRASS_LIGHT = (75, 160, 65, 255)
GRASS_DARK = (45, 110, 35, 255)
PATH_TAN = (180, 155, 110, 255)
PATH_DARK = (145, 120, 85, 255)
PATH_LIGHT = (200, 175, 135, 255)

# Towers
TOWER_GREY = (120, 120, 130, 255)
TOWER_DARK = (80, 80, 90, 255)
TOWER_LIGHT = (160, 160, 170, 255)
TOWER_SNIPER_TINT = (100, 130, 180, 255)
TOWER_SPLASH_TINT = (180, 100, 90, 255)
SLOT_GREEN = (80, 180, 80, 100)
SLOT_BORDER = (100, 200, 100, 180)

# Enemies
ENEMY_RED = (200, 50, 50, 255)
ENEMY_RED_DARK = (150, 30, 30, 255)
ENEMY_ORANGE = (220, 140, 40, 255)
ENEMY_ORANGE_DARK = (180, 100, 20, 255)
ENEMY_TANK_RED = (140, 30, 30, 255)
ENEMY_TANK_DARK = (100, 20, 20, 255)

# Projectiles
PROJ_YELLOW = (255, 230, 50, 255)
PROJ_CYAN = (80, 220, 255, 255)
PROJ_ORANGE = (255, 160, 40, 255)

# Effects
EXPLOSION_ORANGE = (255, 160, 30, 220)
EXPLOSION_YELLOW = (255, 230, 80, 200)
RANGE_INDICATOR_COLOR = (100, 200, 255, 50)
RANGE_BORDER = (100, 200, 255, 100)

# UI
UI_DARK = (30, 30, 40, 230)
UI_MID = (50, 50, 65, 230)
UI_LIGHT = (70, 70, 90, 230)
UI_BORDER = (90, 90, 110, 255)
GOLD = (255, 210, 50, 255)
GOLD_DARK = (200, 160, 30, 255)
HEALTH_GREEN = (60, 200, 60, 255)
HEALTH_BG = (40, 40, 40, 200)
HEART_RED = (220, 40, 60, 255)
HEART_DARK = (170, 20, 40, 255)
BANNER_BORDER = (180, 150, 60, 255)
HUD_BG = (20, 20, 30, 220)


# ===================================================================
# Terrain tiles (32x32)
# ===================================================================

def make_grass() -> Image.Image:
    """32x32 grass tile with subtle texture variation."""
    img = Image.new("RGBA", (32, 32), GRASS_GREEN)
    draw = ImageDraw.Draw(img, "RGBA")

    tufts = [
        (4, 6), (18, 3), (26, 12), (8, 20), (22, 24),
        (14, 14), (2, 28), (28, 28), (12, 8), (24, 18),
    ]
    for tx, ty in tufts:
        draw.line([(tx, ty), (tx, ty - 3)], fill=GRASS_LIGHT, width=1)
        draw.line([(tx - 1, ty), (tx - 1, ty - 2)], fill=GRASS_LIGHT, width=1)

    dark_spots = [(10, 25), (25, 7), (6, 14), (20, 20)]
    for dx, dy in dark_spots:
        draw.point((dx, dy), fill=GRASS_DARK)
        draw.point((dx + 1, dy), fill=GRASS_DARK)

    return img


def make_path_straight() -> Image.Image:
    """32x32 straight path tile -- tan with darker edges."""
    img = Image.new("RGBA", (32, 32), PATH_TAN)
    draw = ImageDraw.Draw(img, "RGBA")

    for y in range(3):
        draw.line([(0, y), (31, y)], fill=PATH_DARK, width=1)
        draw.line([(0, 31 - y), (31, 31 - y)], fill=PATH_DARK, width=1)

    for y in range(14, 18):
        draw.line([(2, y), (29, y)], fill=PATH_LIGHT, width=1)

    pebbles = [(6, 8), (20, 12), (12, 22), (26, 26)]
    for px, py in pebbles:
        draw.point((px, py), fill=PATH_DARK)

    return img


def make_path_turn() -> Image.Image:
    """32x32 path corner tile -- top-to-right turn."""
    img = Image.new("RGBA", (32, 32), GRASS_GREEN)
    draw = ImageDraw.Draw(img, "RGBA")

    draw.rectangle((6, 0, 25, 18), fill=PATH_TAN)
    draw.rectangle((14, 6, 31, 25), fill=PATH_TAN)

    draw.line([(6, 0), (6, 18)], fill=PATH_DARK, width=1)
    draw.line([(6, 18), (14, 18)], fill=PATH_DARK, width=1)
    draw.line([(14, 18), (14, 25)], fill=PATH_DARK, width=1)
    draw.line([(14, 25), (31, 25)], fill=PATH_DARK, width=1)
    draw.line([(25, 0), (25, 6)], fill=PATH_DARK, width=1)
    draw.line([(25, 6), (31, 6)], fill=PATH_DARK, width=1)

    return img


# ===================================================================
# Tower sprites (32x32)
# ===================================================================

def _draw_tower_base(img: Image.Image, base_color: Color, accent: Color) -> None:
    """Draw a common tower platform/base onto *img*."""
    draw = ImageDraw.Draw(img, "RGBA")

    draw.rectangle((6, 18, 25, 30), fill=base_color)
    draw.line([(6, 18), (25, 18)], fill=accent, width=1)
    r, g, b, a = base_color
    dark = (max(0, r - 40), max(0, g - 40), max(0, b - 40), a)
    draw.line([(6, 30), (25, 30)], fill=dark, width=1)

    for bx in (7, 13, 19):
        draw.rectangle((bx, 15, bx + 4, 18), fill=base_color)
        draw.line([(bx, 15), (bx + 4, 15)], fill=accent, width=1)


def make_tower_basic() -> Image.Image:
    """32x32 basic tower -- grey base with simple barrel pointing up."""
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    _draw_tower_base(img, TOWER_GREY, TOWER_LIGHT)

    draw.rectangle((13, 4, 18, 17), fill=TOWER_DARK)
    draw.line([(13, 4), (18, 4)], fill=TOWER_LIGHT, width=1)
    draw.rectangle((12, 2, 19, 5), fill=TOWER_GREY)

    return img


def make_tower_sniper() -> Image.Image:
    """32x32 sniper tower -- blue-tinted, long narrow barrel."""
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    _draw_tower_base(img, TOWER_SNIPER_TINT, (140, 170, 220, 255))

    draw.rectangle((14, 1, 17, 17), fill=(60, 90, 140, 255))
    draw.line([(14, 1), (17, 1)], fill=(120, 160, 220, 255), width=1)
    draw.point((15, 1), fill=PROJ_CYAN)
    draw.point((16, 1), fill=PROJ_CYAN)

    return img


def make_tower_splash() -> Image.Image:
    """32x32 splash tower -- red-tinted, wide barrel (cannon look)."""
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    _draw_tower_base(img, TOWER_SPLASH_TINT, (220, 140, 130, 255))

    draw.rectangle((11, 6, 20, 17), fill=(140, 60, 50, 255))
    draw.line([(11, 6), (20, 6)], fill=(200, 120, 110, 255), width=1)
    draw.rectangle((9, 4, 22, 7), fill=(160, 80, 70, 255))

    return img


def make_tower_slot() -> Image.Image:
    """32x32 empty tower slot -- semi-transparent green marker."""
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    draw.rectangle((2, 2, 29, 29), fill=SLOT_GREEN)
    outlined_polygon(
        img,
        [(2, 2), (29, 2), (29, 29), (2, 29)],
        outline=SLOT_BORDER,
        width=1,
    )

    draw.line([(12, 16), (20, 16)], fill=SLOT_BORDER, width=2)
    draw.line([(16, 12), (16, 20)], fill=SLOT_BORDER, width=2)

    return img


# ===================================================================
# Enemy sprites (24x24)
# ===================================================================

def make_enemy_basic() -> Image.Image:
    """24x24 basic enemy -- red circle with darker core."""
    img = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    filled_ellipse(img, (2, 2, 21, 21), fill=ENEMY_RED)
    filled_ellipse(img, (6, 6, 17, 17), fill=ENEMY_RED_DARK)
    draw.point((9, 9), fill=(255, 255, 255, 255))
    draw.point((14, 9), fill=(255, 255, 255, 255))

    return img


def make_enemy_fast() -> Image.Image:
    """24x24 fast enemy -- orange diamond/arrow shape."""
    img = Image.new("RGBA", (24, 24), (0, 0, 0, 0))

    points = [(2, 12), (10, 3), (22, 12), (10, 21)]
    filled_polygon(img, points, fill=ENEMY_ORANGE)
    inner = [(6, 12), (11, 6), (18, 12), (11, 18)]
    filled_polygon(img, inner, fill=ENEMY_ORANGE_DARK)

    return img


def make_enemy_tank() -> Image.Image:
    """24x24 tank enemy -- dark red armoured square."""
    img = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    draw.rectangle((2, 2, 21, 21), fill=ENEMY_TANK_RED)
    draw.rectangle((4, 4, 19, 19), fill=ENEMY_TANK_DARK)
    draw.line([(4, 12), (19, 12)], fill=ENEMY_TANK_RED, width=2)
    draw.line([(12, 4), (12, 19)], fill=ENEMY_TANK_RED, width=2)
    for rx, ry in [(5, 5), (18, 5), (5, 18), (18, 18)]:
        draw.point((rx, ry), fill=(180, 60, 60, 255))

    return img


# ===================================================================
# Projectiles (8x8)
# ===================================================================

def make_projectile_basic() -> Image.Image:
    """8x8 basic projectile -- bright yellow dot with glow."""
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    filled_ellipse(img, (0, 0, 7, 7), fill=(255, 230, 50, 120))
    filled_ellipse(img, (2, 2, 5, 5), fill=PROJ_YELLOW)
    return img


def make_projectile_sniper() -> Image.Image:
    """8x8 sniper projectile -- cyan bolt."""
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.line([(1, 4), (6, 4)], fill=PROJ_CYAN, width=2)
    draw.point((7, 4), fill=(200, 255, 255, 255))
    draw.line([(0, 4), (2, 4)], fill=(80, 220, 255, 100), width=1)
    return img


def make_projectile_splash() -> Image.Image:
    """8x8 splash projectile -- orange ball."""
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    filled_ellipse(img, (0, 0, 7, 7), fill=(255, 160, 40, 100))
    filled_ellipse(img, (1, 1, 6, 6), fill=PROJ_ORANGE)
    return img


# ===================================================================
# Effects
# ===================================================================

def make_explosion() -> Image.Image:
    """16x16 explosion burst -- orange/yellow radial effect."""
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    filled_ellipse(img, (0, 0, 15, 15), fill=EXPLOSION_ORANGE)
    filled_ellipse(img, (3, 3, 12, 12), fill=EXPLOSION_YELLOW)
    filled_ellipse(img, (5, 5, 10, 10), fill=(255, 255, 200, 255))

    cx, cy = 8, 8
    spike_color = (255, 200, 60, 180)
    for angle_deg in range(0, 360, 45):
        angle = math.radians(angle_deg)
        ex = cx + int(7 * math.cos(angle))
        ey = cy + int(7 * math.sin(angle))
        draw.line([(cx, cy), (ex, ey)], fill=spike_color, width=1)

    return img


def make_range_indicator() -> Image.Image:
    """64x64 semi-transparent range circle for tower placement preview."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    filled_ellipse(img, (1, 1, 62, 62), fill=RANGE_INDICATOR_COLOR)
    outlined_ellipse(img, (1, 1, 62, 62), outline=RANGE_BORDER, width=1)
    return img


# ===================================================================
# UI elements
# ===================================================================

def _make_button(w: int, h: int, base: Color, lighter: Color, darker: Color) -> Image.Image:
    """Internal helper: create a beveled button image."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    draw.rectangle((0, 0, w - 1, h - 1), fill=base)
    draw.line([(0, 0), (w - 1, 0)], fill=lighter, width=1)
    draw.line([(0, 0), (0, h - 1)], fill=lighter, width=1)
    draw.line([(0, h - 1), (w - 1, h - 1)], fill=darker, width=1)
    draw.line([(w - 1, 0), (w - 1, h - 1)], fill=darker, width=1)

    return img


def make_btn_normal() -> Image.Image:
    """80x32 button in normal/idle state."""
    return _make_button(80, 32, base=UI_MID, lighter=UI_LIGHT, darker=(25, 25, 35, 230))


def make_btn_hover() -> Image.Image:
    """80x32 button in hover state."""
    return _make_button(80, 32, base=UI_LIGHT, lighter=(100, 100, 120, 230), darker=UI_MID)


def make_btn_pressed() -> Image.Image:
    """80x32 button in pressed state."""
    return _make_button(80, 32, base=UI_DARK, lighter=(20, 20, 30, 230), darker=UI_LIGHT)


def make_panel_bg() -> Image.Image:
    """120x200 dark UI panel with subtle border."""
    w, h = 120, 200
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    draw.rectangle((0, 0, w - 1, h - 1), fill=UI_DARK)
    outlined_polygon(
        img,
        [(0, 0), (w - 1, 0), (w - 1, h - 1), (0, h - 1)],
        outline=UI_BORDER, width=1,
    )
    draw.line([(1, 1), (w - 2, 1)], fill=UI_MID, width=1)

    return img


def make_health_bar_bg() -> Image.Image:
    """24x4 dark health bar background."""
    return Image.new("RGBA", (24, 4), HEALTH_BG)


def make_health_bar_fill() -> Image.Image:
    """24x4 green health bar fill."""
    img = Image.new("RGBA", (24, 4), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle((0, 0, 23, 3), fill=HEALTH_GREEN)
    draw.line([(0, 0), (23, 0)], fill=(100, 240, 100, 255), width=1)
    return img


def make_coin_icon() -> Image.Image:
    """16x16 gold coin icon."""
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    filled_ellipse(img, (1, 1, 14, 14), fill=GOLD)
    outlined_ellipse(img, (3, 3, 12, 12), outline=GOLD_DARK, width=1)
    draw.line([(8, 5), (8, 11)], fill=GOLD_DARK, width=1)
    draw.line([(6, 7), (10, 7)], fill=GOLD_DARK, width=1)
    draw.line([(6, 9), (10, 9)], fill=GOLD_DARK, width=1)

    return img


def make_heart_icon() -> Image.Image:
    """16x16 red heart icon."""
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))

    filled_ellipse(img, (1, 2, 9, 9), fill=HEART_RED)
    filled_ellipse(img, (7, 2, 15, 9), fill=HEART_RED)
    filled_polygon(img, [(1, 6), (15, 6), (8, 14)], fill=HEART_RED)
    filled_polygon(img, [(3, 8), (13, 8), (8, 14)], fill=HEART_DARK)

    draw = ImageDraw.Draw(img, "RGBA")
    draw.point((4, 4), fill=(255, 120, 140, 255))
    draw.point((5, 3), fill=(255, 120, 140, 255))

    return img


def make_wave_banner() -> Image.Image:
    """160x40 wave announcement banner background."""
    w, h = 160, 40
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    vertical_gradient(img, (50, 40, 70, 220), (30, 20, 50, 220))
    outlined_polygon(
        img,
        [(0, 0), (w - 1, 0), (w - 1, h - 1), (0, h - 1)],
        outline=BANNER_BORDER, width=2,
    )
    outlined_polygon(
        img,
        [(3, 3), (w - 4, 3), (w - 4, h - 4), (3, h - 4)],
        outline=(120, 100, 40, 180), width=1,
    )

    return img


def make_hud_top_bar() -> Image.Image:
    """320x24 top HUD bar background."""
    w, h = 320, 24
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    draw.rectangle((0, 0, w - 1, h - 1), fill=HUD_BG)
    draw.line([(0, h - 1), (w - 1, h - 1)], fill=UI_BORDER, width=1)

    return img


# ===================================================================
# Audio helpers -- generate minimal WAV files
# ===================================================================

_AUDIO_SAMPLE_RATE = 22050


def _write_wav(
    path: Path,
    samples: list[int],
    sample_rate: int = _AUDIO_SAMPLE_RATE,
) -> None:
    """Write 16-bit mono WAV from a list of signed 16-bit sample values."""
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        data = struct.pack(f"<{len(samples)}h", *samples)
        wf.writeframes(data)


def _sine_samples(freq: float, duration: float, volume: float = 0.5) -> list[int]:
    """Generate sine wave samples."""
    n = int(_AUDIO_SAMPLE_RATE * duration)
    amp = int(32767 * volume)
    return [
        int(amp * math.sin(2 * math.pi * freq * i / _AUDIO_SAMPLE_RATE))
        for i in range(n)
    ]


def _fade(samples: list[int], fade_in: int = 0, fade_out: int = 0) -> list[int]:
    """Apply linear fade-in and fade-out to samples."""
    result = list(samples)
    for i in range(min(fade_in, len(result))):
        result[i] = int(result[i] * i / fade_in)
    for i in range(min(fade_out, len(result))):
        idx = len(result) - 1 - i
        result[idx] = int(result[idx] * i / fade_out)
    return result


def generate_sfx_shoot(path: Path) -> None:
    """Short high-pitched click -- tower firing."""
    samples = _sine_samples(800, 0.06, volume=0.4)
    samples = _fade(samples, fade_out=len(samples) // 2)
    _write_wav(path, samples)


def generate_sfx_hit(path: Path) -> None:
    """Low thud -- projectile impact."""
    samples = _sine_samples(200, 0.1, volume=0.5)
    samples = _fade(samples, fade_out=len(samples) * 2 // 3)
    _write_wav(path, samples)


def generate_sfx_death(path: Path) -> None:
    """Descending tone -- enemy death."""
    n = int(_AUDIO_SAMPLE_RATE * 0.25)
    amp = int(32767 * 0.4)
    samples = []
    for i in range(n):
        t = i / _AUDIO_SAMPLE_RATE
        freq = 600 - 1800 * t
        samples.append(int(amp * math.sin(2 * math.pi * freq * t)))
    samples = _fade(samples, fade_in=100, fade_out=n // 2)
    _write_wav(path, samples)


def generate_sfx_wave(path: Path) -> None:
    """Rising alert tone -- new wave starting."""
    n = int(_AUDIO_SAMPLE_RATE * 0.3)
    amp = int(32767 * 0.35)
    samples = []
    for i in range(n):
        t = i / _AUDIO_SAMPLE_RATE
        freq = 400 + 1667 * t
        samples.append(int(amp * math.sin(2 * math.pi * freq * t)))
    samples = _fade(samples, fade_in=200, fade_out=n // 3)
    _write_wav(path, samples)


def generate_sfx_lose_life(path: Path) -> None:
    """Low warning buzz -- life lost."""
    n = int(_AUDIO_SAMPLE_RATE * 0.2)
    amp = int(32767 * 0.3)
    samples = []
    for i in range(n):
        t = i / _AUDIO_SAMPLE_RATE
        val = math.sin(2 * math.pi * 120 * t)
        samples.append(int(amp * (1 if val > 0 else -1)))
    samples = _fade(samples, fade_in=100, fade_out=n // 2)
    _write_wav(path, samples)


def generate_bgm_game(path: Path) -> None:
    """Short looping background music placeholder -- gentle arpeggio."""
    notes = [262, 330, 392, 523]  # C4, E4, G4, C5
    note_dur = 1.0
    all_samples: list[int] = []
    for freq in notes:
        samps = _sine_samples(freq, note_dur, volume=0.15)
        samps = _fade(samps, fade_in=500, fade_out=2000)
        all_samples.extend(samps)
    _write_wav(path, all_samples)


# Audio file manifest: (subdir, filename, generator_func)
AUDIO_MANIFEST: list[tuple[str, str, callable]] = [
    ("sounds", "sfx_shoot.wav", generate_sfx_shoot),
    ("sounds", "sfx_hit.wav", generate_sfx_hit),
    ("sounds", "sfx_death.wav", generate_sfx_death),
    ("sounds", "sfx_wave.wav", generate_sfx_wave),
    ("sounds", "sfx_lose_life.wav", generate_sfx_lose_life),
    ("music", "bgm_game.wav", generate_bgm_game),
]


# ===================================================================
# Manifest and batch generation
# ===================================================================

MANIFEST: list[tuple[str, callable]] = [
    # Terrain
    ("grass.png", make_grass),
    ("path_straight.png", make_path_straight),
    ("path_turn.png", make_path_turn),
    # Towers
    ("tower_basic.png", make_tower_basic),
    ("tower_sniper.png", make_tower_sniper),
    ("tower_splash.png", make_tower_splash),
    ("tower_slot.png", make_tower_slot),
    # Enemies
    ("enemy_basic.png", make_enemy_basic),
    ("enemy_fast.png", make_enemy_fast),
    ("enemy_tank.png", make_enemy_tank),
    # Projectiles
    ("projectile_basic.png", make_projectile_basic),
    ("projectile_sniper.png", make_projectile_sniper),
    ("projectile_splash.png", make_projectile_splash),
    # Effects
    ("explosion.png", make_explosion),
    ("range_indicator.png", make_range_indicator),
    # UI
    ("btn_normal.png", make_btn_normal),
    ("btn_hover.png", make_btn_hover),
    ("btn_pressed.png", make_btn_pressed),
    ("panel_bg.png", make_panel_bg),
    ("health_bar_bg.png", make_health_bar_bg),
    ("health_bar_fill.png", make_health_bar_fill),
    ("coin_icon.png", make_coin_icon),
    ("heart_icon.png", make_heart_icon),
    ("wave_banner.png", make_wave_banner),
    # HUD
    ("hud_top_bar.png", make_hud_top_bar),
]


def generate(output_dir: Path | None = None) -> List[Path]:
    """Generate all Tower Defense assets and save to *output_dir*.

    Image files go into ``<output_dir>/images/``, sound effects into
    ``<output_dir>/sounds/``, and music into ``<output_dir>/music/``.

    Args:
        output_dir: Asset base directory.  Defaults to
                    ``examples/tower_defense/assets/``.

    Returns:
        List of ``Path`` objects for every file written.
    """
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "assets"

    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []

    # --- Image assets ---
    for filename, factory in MANIFEST:
        img = factory()
        path = images_dir / filename
        img.save(path)
        print(f"  Created {path}")
        written.append(path)

    # --- Audio assets ---
    for subdir, filename, gen_func in AUDIO_MANIFEST:
        audio_dir = output_dir / subdir
        audio_dir.mkdir(parents=True, exist_ok=True)
        path = audio_dir / filename
        gen_func(path)
        print(f"  Created {path}")
        written.append(path)

    return written


def main() -> None:
    """Entry point for standalone execution."""
    print("=== Tower Defense Example Assets ===\n")
    files = generate()
    print(f"\n{'=' * 50}")
    print(f"Generated {len(files)} asset files.")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
