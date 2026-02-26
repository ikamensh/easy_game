"""Visual demo of Stage 11: Particles, ColorSwap, Cursor.

Run from project root::

    python tests/visual/test_stage11_visual.py

Demonstrates:
1. Particle burst — press B to trigger a burst of sparks at center
2. Color swap — two knight sprites side by side (red vs blue team)
3. Cursor — press C to toggle custom crosshair cursor, D for default

Creates minimal assets in a temp dir. Close window or ESC to exit.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root on path when run as script
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from PIL import Image  # noqa: E402

from easygame import ColorSwap, Game, ParticleEmitter, Scene, Sprite  # noqa: E402
from easygame.assets import AssetManager  # noqa: E402
from easygame.input import InputEvent  # noqa: E402
from easygame.backends.pyglet_backend import PygletBackend  # noqa: E402


def _create_assets(tmp: Path) -> None:
    """Create minimal PNG assets for the demo."""
    sprites = tmp / "images" / "sprites"
    ui = tmp / "images" / "ui"
    sprites.mkdir(parents=True)
    ui.mkdir(parents=True)

    # Spark: small orange/yellow square for particles
    spark = Image.new("RGBA", (8, 8), (255, 180, 50, 255))
    spark.save(sprites / "spark.png")

    # Knight: 64x64 with red (255,0,0) and dark red (200,0,0) for color swap
    knight = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    px = knight.load()
    for y in range(16, 48):
        for x in range(16, 48):
            px[x, y] = (255, 0, 0, 255)
    for y in range(24, 40):
        for x in range(24, 40):
            px[x, y] = (200, 0, 0, 255)
    knight.save(sprites / "knight.png")

    # Cursor: simple 24x24 crosshair
    cursor_img = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    cp = cursor_img.load()
    for i in range(24):
        cp[11, i] = (255, 255, 255, 255)
        cp[i, 11] = (255, 255, 255, 255)
    cp[11, 11] = (0, 0, 0, 255)
    cursor_img.save(ui / "cursor_cross.png")


class Stage11Scene(Scene):
    """Scene demonstrating particles, color swap, and cursor."""

    def on_enter(self) -> None:
        backend = self.game.backend

        # Background
        bg = backend.create_solid_color_image(
            30, 35, 45, 255,
            backend.logical_width, backend.logical_height,
        )
        self._bg_sprite = backend.create_sprite(bg, -1)
        backend.update_sprite(self._bg_sprite, 0, 0)

        # 1. Particle emitter at center — burst on B
        self._emitter = ParticleEmitter(
            "sprites/spark",
            position=(400, 300),
            count=40,
            speed=(80, 250),
            direction=(0, 360),
            lifetime=(0.4, 1.0),
            fade_out=True,
        )

        # 2. Two sprites with different color swaps
        red_swap = ColorSwap(
            source_colors=[(255, 0, 0), (200, 0, 0)],
            target_colors=[(255, 80, 80), (200, 60, 60)],
        )
        blue_swap = ColorSwap(
            source_colors=[(255, 0, 0), (200, 0, 0)],
            target_colors=[(80, 80, 255), (60, 60, 200)],
        )
        self._red_knight = Sprite(
            "sprites/knight",
            position=(250, 200),
            color_swap=red_swap,
        )
        self._blue_knight = Sprite(
            "sprites/knight",
            position=(550, 200),
            color_swap=blue_swap,
        )

        # 3. Cursor — register custom cursor
        self.game.cursor.register(
            "crosshair",
            "ui/cursor_cross",
            hotspot=(12, 12),
        )

    def on_exit(self) -> None:
        self._emitter.remove()
        self._red_knight.remove()
        self._blue_knight.remove()
        self.game.backend.remove_sprite(self._bg_sprite)

    def draw(self) -> None:
        backend = self.game.backend
        backend.update_sprite(self._bg_sprite, 0, 0)
        backend.draw_text(
            "B = particle burst  |  C = custom cursor  |  D = default cursor  |  ESC = quit",
            20, backend.logical_height - 25,
            20,
            (255, 255, 255, 255),
            font="Arial",
        )
        backend.draw_text(
            "Red team (left) | Blue team (right) | Sparks burst at center",
            20, backend.logical_height - 48,
            20,
            (200, 200, 200, 255),
            font="Arial",
        )

    def handle_input(self, event: InputEvent) -> bool:
        if event.type != "key_press":
            return False

        if event.action == "cancel":
            self.game.quit()
            return True

        if event.key == "b":
            self._emitter.burst(40)
            return True

        if event.key == "c":
            self.game.cursor.set("crosshair")
            return True

        if event.key == "d":
            self.game.cursor.set("default")
            return True

        return False


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        asset_dir = Path(tmp)
        _create_assets(asset_dir)

        backend = PygletBackend()
        game = Game(
            "Stage 11 Visual — Particles, ColorSwap, Cursor",
            resolution=(800, 600),
            fullscreen=False,
            backend=backend,
        )
        game.assets = AssetManager(backend, base_path=asset_dir)
        game.run(Stage11Scene())


@pytest.mark.visual
def test_stage11_visual() -> None:
    """Run the Stage 11 demo as a pytest test.

    Requires display and pyglet. Excluded from normal pytest run via
    collect_ignore in tests/conftest.py.
    """
    main()


if __name__ == "__main__":
    main()
