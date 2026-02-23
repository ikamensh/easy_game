"""Chapter 5 — Tower Combat
============================

Building on Chapter 4, this chapter adds **tower combat**:

*   **Combat stats** on towers — damage, fire rate (shots per second),
    and optional splash radius.
*   **Tower targeting** — each frame, towers find the closest walking
    enemy within range and fire a projectile at it.
*   **Projectile system** — each projectile is a small sprite that moves
    toward the target position via ``sprite.move_to()``.  On arrival it
    deals damage, spawns a :class:`ParticleEmitter` burst, and removes
    itself.  Splash towers damage all enemies within a radius.
*   **Enemy HP** tracking — when HP drops to 0, the enemy enters the
    ``dying`` state, awards gold, and plays a fade-out death animation.
*   **Health bars** — drawn per-frame via ``self.draw_world_rect()`` in
    the scene's ``draw()`` method.  A red background bar and green
    foreground bar (proportional to current HP) appear above enemies
    whose HP is below maximum.
*   **Tower differentiation** — Basic (medium damage, medium rate, medium
    range), Sniper (high damage, slow rate, long range), Splash (low
    per-target damage with area splash, short range).

Run from the project root::

    python tutorials/tower_defense/ch5_combat.py

Controls:
    Title Screen — Enter or click Play → start game.
                   Escape or click Quit → exit.
    Game Screen  — Click a Buy button → enter placement mode.
                   Left-click on a tower slot → place the tower.
                   Right-click or Escape → cancel placement / return to menu.
                   Arrow keys → scroll the camera.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup — same pattern as Chapters 1–4.
# ---------------------------------------------------------------------------
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ---------------------------------------------------------------------------
# Auto-generate assets if the assets/ folder is missing.
# ---------------------------------------------------------------------------
_asset_dir = Path(__file__).resolve().parent / "assets"
if not _asset_dir.exists() or not (_asset_dir / "images").exists():
    print("Assets not found — generating placeholder art...")
    from tutorials.tower_defense.generate_td_assets import generate

    generate(_asset_dir)
    print()

# ---------------------------------------------------------------------------
# EasyGame imports
# ---------------------------------------------------------------------------
from easygame import (  # noqa: E402
    Anchor,
    Button,
    Camera,
    Do,
    FadeOut,
    Game,
    InputEvent,
    Label,
    Layout,
    Panel,
    ParticleEmitter,
    Remove,
    RenderLayer,
    Scene,
    Sequence,
    Sprite,
    SpriteAnchor,
    StateMachine,
    Style,
    Theme,
)


# ======================================================================
# Constants
# ======================================================================

SCREEN_W, SCREEN_H = 960, 540

# Tile size in pixels.
TILE_SIZE = 32

# Camera scroll speed in pixels per second.
CAMERA_SCROLL_SPEED = 200.0

# Colour palette
BG_COLOR = (25, 30, 40, 255)
TITLE_COLOR = (255, 220, 80, 255)
SUBTITLE_COLOR = (180, 180, 190, 255)
HUD_TEXT_COLOR = (220, 220, 230, 255)
GOLD_COLOR = (255, 210, 50, 255)
LIVES_COLOR = (255, 100, 100, 255)

# Health bar colours and dimensions.
HEALTH_BAR_BG_COLOR = (80, 20, 20, 200)       # Dark red background
HEALTH_BAR_FG_COLOR = (40, 200, 40, 220)       # Green fill
HEALTH_BAR_WIDTH = 22                           # Pixels wide
HEALTH_BAR_HEIGHT = 3                           # Pixels tall
HEALTH_BAR_Y_OFFSET = -14                       # Above the enemy centre

# Starting resources.
STARTING_GOLD = 200
STARTING_LIVES = 20

# Projectile speed in pixels per second.
PROJECTILE_SPEED = 300.0


# ======================================================================
# Tower definitions (extended with combat stats)
# ======================================================================

# Each tower type now includes combat parameters:
#   damage:       Hit points removed per shot.
#   fire_rate:    Shots per second.
#   range_px:     Attack range in pixels.
#   splash_radius: Area-of-effect radius in pixels (0 = single target).
#   projectile:   Asset name for the projectile sprite.

TOWER_DEFS: list[dict[str, Any]] = [
    {
        "name": "Basic",
        "image": "tower_basic",
        "cost": 50,
        "range_px": 96,
        "damage": 15,
        "fire_rate": 1.5,        # 1.5 shots/sec — medium
        "splash_radius": 0,
        "projectile": "projectile_basic",
    },
    {
        "name": "Sniper",
        "image": "tower_sniper",
        "cost": 100,
        "range_px": 160,
        "damage": 50,
        "fire_rate": 0.5,        # 0.5 shots/sec — slow
        "splash_radius": 0,
        "projectile": "projectile_sniper",
    },
    {
        "name": "Splash",
        "image": "tower_splash",
        "cost": 75,
        "range_px": 80,
        "damage": 10,
        "fire_rate": 1.0,        # 1 shot/sec
        "splash_radius": 48,     # 1.5 tiles
        "projectile": "projectile_splash",
    },
]


# ======================================================================
# Enemy definitions (same as ch4)
# ======================================================================

ENEMY_DEFS: list[dict[str, Any]] = [
    {
        "name": "Soldier",
        "image": "enemy_basic",
        "hp": 80,
        "speed": 40,
        "gold_reward": 10,
    },
    {
        "name": "Scout",
        "image": "enemy_fast",
        "hp": 40,
        "speed": 80,
        "gold_reward": 15,
    },
]


# ======================================================================
# Wave definitions (same as ch4)
# ======================================================================

WAVE_DEFS: list[dict[str, Any]] = [
    {
        "enemy_def": 0,       # Soldier
        "count": 6,
        "spawn_interval": 1.2,
        "delay": 2.0,
    },
    {
        "enemy_def": 1,       # Scout
        "count": 8,
        "spawn_interval": 0.8,
        "delay": 3.0,
    },
    {
        "enemy_def": 0,       # Soldier
        "count": 10,
        "spawn_interval": 1.0,
        "delay": 3.0,
    },
]


# ======================================================================
# Map definition (identical to ch3/ch4)
# ======================================================================

GRASS = 0
PATH = 1

MAP_DATA: list[list[int]] = [
    # fmt: off
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],  # row 0
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],  # row 1
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],  # row 2
    [0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],  # row 3
    [0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],  # row 4
    [1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],  # row 5
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],  # row 6
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],  # row 7
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0],  # row 8
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],  # row 9
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],  # row 10
    [0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0],  # row 11
    [0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],  # row 12
    [0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],  # row 13
    [0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0],  # row 14
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],  # row 15
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],  # row 16
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1],  # row 17
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],  # row 18
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],  # row 19
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],  # row 20
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],  # row 21
    # fmt: on
]

MAP_ROWS = len(MAP_DATA)
MAP_COLS = len(MAP_DATA[0])
MAP_WIDTH_PX = MAP_COLS * TILE_SIZE   # 40 * 32 = 1280
MAP_HEIGHT_PX = MAP_ROWS * TILE_SIZE  # 22 * 32 = 704

# Enemy path — tile coordinates (col, row) from spawn to exit.
ENEMY_PATH: list[tuple[int, int]] = [
    (0, 5), (1, 5), (2, 5), (3, 5), (4, 5), (5, 5), (6, 5),
    (6, 4), (6, 3),
    (7, 3), (8, 3), (9, 3), (10, 3), (11, 3), (12, 3), (13, 3),
    (14, 3), (15, 3), (16, 3), (17, 3), (18, 3),
    (18, 4), (18, 5), (18, 6), (18, 7), (18, 8),
    (19, 8), (20, 8), (21, 8), (22, 8), (23, 8), (24, 8), (25, 8),
    (26, 8), (27, 8), (28, 8), (29, 8), (30, 8), (31, 8), (32, 8),
    (32, 9), (32, 10), (32, 11),
    (31, 11), (30, 11), (29, 11), (28, 11), (27, 11), (26, 11), (25, 11),
    (24, 11), (23, 11), (22, 11), (21, 11), (20, 11), (19, 11), (18, 11),
    (17, 11), (16, 11), (15, 11), (14, 11), (13, 11), (12, 11), (11, 11),
    (10, 11), (9, 11), (8, 11), (7, 11), (6, 11),
    (6, 12), (6, 13), (6, 14),
    (7, 14), (8, 14), (9, 14), (10, 14), (11, 14), (12, 14), (13, 14),
    (14, 14), (15, 14), (16, 14), (17, 14), (18, 14), (19, 14), (20, 14),
    (21, 14), (22, 14), (23, 14), (24, 14), (25, 14), (26, 14), (27, 14),
    (28, 14), (29, 14), (30, 14), (31, 14), (32, 14),
    (32, 15), (32, 16), (32, 17),
    (33, 17), (34, 17), (35, 17), (36, 17), (37, 17), (38, 17), (39, 17),
]

# Pre-compute pixel-centre positions for each waypoint.
ENEMY_PATH_PX: list[tuple[float, float]] = [
    (col * TILE_SIZE + TILE_SIZE / 2, row * TILE_SIZE + TILE_SIZE / 2)
    for col, row in ENEMY_PATH
]

# Tower build slots — (col, row) positions where towers can be placed.
TOWER_SLOTS: list[tuple[int, int]] = [
    (4, 4),
    (8, 2),
    (14, 2),
    (17, 6),
    (22, 7),
    (28, 7),
    (33, 10),
    (10, 12),
    (20, 12),
    (8, 13),
    (20, 15),
    (28, 15),
    (31, 16),
]


# ======================================================================
# TitleScene (reused from ch4, updated subtitle)
# ======================================================================

class TitleScene(Scene):
    """Title screen — Play pushes GameScene, Quit exits."""

    background_color = BG_COLOR

    def on_enter(self) -> None:
        title_label = Label(
            "Tower Defense",
            font_size=48,
            text_color=TITLE_COLOR,
        )
        subtitle_label = Label(
            "Chapter 5 — Tower Combat",
            font_size=18,
            text_color=SUBTITLE_COLOR,
        )
        play_button = Button("Play", on_click=self._on_play_clicked)
        quit_button = Button("Quit", on_click=self._on_quit_clicked)

        menu_panel = Panel(
            layout=Layout.VERTICAL,
            spacing=20,
            anchor=Anchor.CENTER,
            style=Style(background_color=(30, 35, 50, 220), padding=40),
            children=[title_label, subtitle_label, play_button, quit_button],
        )
        self.ui.add(menu_panel)

    def _on_play_clicked(self) -> None:
        self.game.push(GameScene())

    def _on_quit_clicked(self) -> None:
        self.game.quit()

    def handle_input(self, event: InputEvent) -> bool:
        if event.action == "confirm":
            self._on_play_clicked()
            return True
        if event.action == "cancel":
            self._on_quit_clicked()
            return True
        return False


# ======================================================================
# GameScene — tile map + camera + HUD + tower placement + enemies + combat
# ======================================================================

class GameScene(Scene):
    """Gameplay scene with tower placement, enemy waves, and tower combat.

    This chapter extends ch4's GameScene with a full combat system:

    *   Towers target the closest walking enemy in range each frame.
    *   Projectiles fly from tower to target position and deal damage
        on arrival.
    *   Splash towers damage all enemies within a radius at impact.
    *   Enemy health bars are drawn via ``self.draw_world_rect()`` each frame.
    *   Enemies that reach 0 HP enter the ``dying`` FSM state, award
        gold, and fade out.
    """

    show_hud = True

    def on_enter(self) -> None:
        """Set up map, camera, HUD, build menu, enemies, and wave system."""

        # -----------------------------------------------------------------
        # Game state
        # -----------------------------------------------------------------
        self._gold = STARTING_GOLD
        self._lives = STARTING_LIVES
        self._current_wave = 0
        self._wave_active = False
        self._wave_spawned = 0
        self._game_over = False

        # -----------------------------------------------------------------
        # Placement state machine (from ch3).
        # -----------------------------------------------------------------
        self._placing_tower_def: dict[str, Any] | None = None

        # -----------------------------------------------------------------
        # Placed towers: (col, row) → tower info dict.
        #
        # Each entry now includes a ``"cooldown"`` float that tracks
        # time remaining until the tower can fire again.
        # -----------------------------------------------------------------
        self._placed_towers: dict[tuple[int, int], dict[str, Any]] = {}

        # -----------------------------------------------------------------
        # Slot sprites: (col, row) → Sprite for lookup when placing.
        # -----------------------------------------------------------------
        self._slot_sprites: dict[tuple[int, int], Sprite] = {}

        # -----------------------------------------------------------------
        # Enemy tracking (same as ch4).
        # -----------------------------------------------------------------
        self._enemies: list[dict[str, Any]] = []

        # -----------------------------------------------------------------
        # Projectile tracking.
        #
        # Each projectile is a dict with:
        #   "sprite":        The projectile Sprite.
        #   "target_enemy":  Reference to the target enemy dict (may
        #                    already be dead/removed by arrival time).
        #   "target_pos":    (x, y) world position the projectile is
        #                    flying toward (snapshot at fire time).
        #   "damage":        Damage to deal on arrival.
        #   "splash_radius": 0 for single-target, > 0 for area damage.
        # -----------------------------------------------------------------
        self._projectiles: list[dict[str, Any]] = []

        # -----------------------------------------------------------------
        # 1. Camera
        # -----------------------------------------------------------------
        self.camera = Camera(
            (SCREEN_W, SCREEN_H),
            world_bounds=(0, 0, MAP_WIDTH_PX, MAP_HEIGHT_PX),
        )
        self.camera.center_on(MAP_WIDTH_PX / 2, MAP_HEIGHT_PX / 2)
        self.camera.enable_key_scroll(speed=CAMERA_SCROLL_SPEED)

        # -----------------------------------------------------------------
        # 2. Tile map
        # -----------------------------------------------------------------
        self._create_tile_map()

        # -----------------------------------------------------------------
        # 3. Tower slot markers
        # -----------------------------------------------------------------
        self._create_tower_slots()

        # -----------------------------------------------------------------
        # 4. HUD and build menu
        # -----------------------------------------------------------------
        self._build_hud()
        self._build_menu()

        # -----------------------------------------------------------------
        # 5. Range indicator (hidden until placement mode).
        # -----------------------------------------------------------------
        self._range_indicator = self.add_sprite(
            Sprite(
                "range_indicator",
                position=(-9999, -9999),
                anchor=SpriteAnchor.CENTER,
                layer=RenderLayer.EFFECTS,
                opacity=120,
                visible=False,
            )
        )

        # -----------------------------------------------------------------
        # 6. Schedule wave 1 to start after a short delay.
        # -----------------------------------------------------------------
        self.after(2.0, self._start_next_wave)

    # ------------------------------------------------------------------
    # Tile map creation (same as ch3/ch4)
    # ------------------------------------------------------------------

    def _create_tile_map(self) -> None:
        """Create one Sprite per tile from MAP_DATA."""
        tile_images = {GRASS: "grass", PATH: "path_straight"}
        for row in range(MAP_ROWS):
            for col in range(MAP_COLS):
                tile_type = MAP_DATA[row][col]
                sprite = Sprite(
                    tile_images[tile_type],
                    position=(col * TILE_SIZE, row * TILE_SIZE),
                    anchor=SpriteAnchor.TOP_LEFT,
                    layer=RenderLayer.BACKGROUND,
                )
                self.add_sprite(sprite)

    # ------------------------------------------------------------------
    # Tower slot markers (same as ch3/ch4)
    # ------------------------------------------------------------------

    def _create_tower_slots(self) -> None:
        """Place tower_slot markers at each buildable position."""
        for col, row in TOWER_SLOTS:
            sprite = Sprite(
                "tower_slot",
                position=(col * TILE_SIZE, row * TILE_SIZE),
                anchor=SpriteAnchor.TOP_LEFT,
                layer=RenderLayer.OBJECTS,
            )
            self.add_sprite(sprite)
            self._slot_sprites[(col, row)] = sprite

    # ------------------------------------------------------------------
    # HUD (top bar) — wave, gold, lives, hint
    # ------------------------------------------------------------------

    def _build_hud(self) -> None:
        """Build a top-bar HUD with wave, gold, lives, and hint labels."""
        self._wave_label = Label(
            f"Wave: {self._current_wave + 1}/{len(WAVE_DEFS)}",
            font_size=20,
            text_color=HUD_TEXT_COLOR,
        )
        self._gold_label = Label(
            f"Gold: {self._gold}",
            font_size=20,
            text_color=GOLD_COLOR,
        )
        self._lives_label = Label(
            f"Lives: {self._lives}",
            font_size=20,
            text_color=LIVES_COLOR,
        )
        self._hint_label = Label(
            "Wave starting soon...",
            font_size=14,
            text_color=(140, 140, 150, 255),
        )
        hud_panel = Panel(
            layout=Layout.HORIZONTAL,
            spacing=30,
            anchor=Anchor.TOP,
            margin=8,
            style=Style(
                background_color=(20, 22, 35, 200),
                padding=10,
            ),
            children=[
                self._wave_label,
                self._gold_label,
                self._lives_label,
                self._hint_label,
            ],
        )
        self.ui.add(hud_panel)

    # ------------------------------------------------------------------
    # Build menu (right side panel — same as ch3/ch4)
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        """Build the tower build menu on the right side of the screen."""
        self._buy_buttons: list[Button] = []

        menu_title = Label(
            "Build Tower",
            font_size=22,
            text_color=TITLE_COLOR,
        )

        tower_rows: list[Panel] = []
        for i, tdef in enumerate(TOWER_DEFS):
            info_label = Label(
                f"{tdef['name']}  {tdef['cost']}g",
                font_size=16,
                text_color=HUD_TEXT_COLOR,
            )
            buy_button = Button(
                "Buy",
                on_click=lambda td=tdef: self._on_buy_clicked(td),
                style=Style(
                    font_size=16,
                    padding=6,
                ),
            )
            self._buy_buttons.append(buy_button)

            row = Panel(
                layout=Layout.HORIZONTAL,
                spacing=12,
                style=Style(
                    background_color=(35, 40, 55, 180),
                    padding=8,
                ),
                children=[info_label, buy_button],
            )
            tower_rows.append(row)

        cancel_label = Label(
            "Right-click: cancel",
            font_size=12,
            text_color=(120, 120, 130, 255),
        )

        build_panel = Panel(
            layout=Layout.VERTICAL,
            spacing=10,
            anchor=Anchor.RIGHT,
            margin=8,
            style=Style(
                background_color=(20, 22, 35, 220),
                padding=14,
            ),
            children=[menu_title, *tower_rows, cancel_label],
        )
        self.ui.add(build_panel)

        self._refresh_buy_buttons()

    # ------------------------------------------------------------------
    # Buy button callbacks (same as ch3/ch4)
    # ------------------------------------------------------------------

    def _on_buy_clicked(self, tower_def: dict[str, Any]) -> None:
        """Enter placement mode for the selected tower type."""
        self._placing_tower_def = tower_def

        if self._range_indicator is not None:
            self._range_indicator.visible = True

        cost = tower_def["cost"]
        name = tower_def["name"]
        self._hint_label.text = f"Placing {name} ({cost}g) — click a slot"

    # ------------------------------------------------------------------
    # Placement logic (extended from ch3/ch4 — stores cooldown)
    # ------------------------------------------------------------------

    def _cancel_placement(self) -> None:
        """Exit placement mode and hide the range indicator."""
        self._placing_tower_def = None
        if self._range_indicator is not None:
            self._range_indicator.visible = False
            self._range_indicator.position = (-9999, -9999)
        self._update_hint_text()

    def _try_place_tower(self, world_x: float, world_y: float) -> bool:
        """Attempt to place the currently selected tower at world coords.

        Returns True if placement succeeded, False otherwise.
        """
        if self._placing_tower_def is None:
            return False

        col = int(world_x) // TILE_SIZE
        row = int(world_y) // TILE_SIZE

        if (col, row) not in self._slot_sprites:
            return False

        if (col, row) in self._placed_towers:
            return False

        tower_def = self._placing_tower_def
        cost = tower_def["cost"]

        if self._gold < cost:
            return False

        # Place the tower.
        self._gold -= cost

        slot_sprite = self._slot_sprites.pop((col, row))
        slot_sprite.remove()

        tower_sprite = Sprite(
            tower_def["image"],
            position=(col * TILE_SIZE, row * TILE_SIZE),
            anchor=SpriteAnchor.TOP_LEFT,
            layer=RenderLayer.OBJECTS,
        )
        self.add_sprite(tower_sprite)

        # Store tower data including combat cooldown.
        self._placed_towers[(col, row)] = {
            "def": tower_def,
            "sprite": tower_sprite,
            "cooldown": 0.0,   # Ready to fire immediately
        }

        self._gold_label.text = f"Gold: {self._gold}"
        self._refresh_buy_buttons()

        self._cancel_placement()

        print(
            f"Placed {tower_def['name']} tower at ({col}, {row}) "
            f"— gold remaining: {self._gold}"
        )
        return True

    def _refresh_buy_buttons(self) -> None:
        """Enable/disable Buy buttons based on current gold."""
        for i, tdef in enumerate(TOWER_DEFS):
            can_afford = self._gold >= tdef["cost"]
            self._buy_buttons[i].enabled = can_afford

    def _snap_to_nearest_slot(
        self, world_x: float, world_y: float
    ) -> tuple[float, float] | None:
        """Find the nearest unoccupied tower slot within snap range."""
        snap_range = TILE_SIZE * 1.5
        best_dist = snap_range
        best_pos: tuple[float, float] | None = None

        for col, row in self._slot_sprites:
            cx = col * TILE_SIZE + TILE_SIZE / 2
            cy = row * TILE_SIZE + TILE_SIZE / 2
            dx = world_x - cx
            dy = world_y - cy
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_pos = (cx, cy)

        return best_pos

    # ------------------------------------------------------------------
    # HUD hint text helper (same as ch4)
    # ------------------------------------------------------------------

    def _update_hint_text(self) -> None:
        """Update the hint label based on current game state."""
        if self._game_over:
            self._hint_label.text = "Game Over — press Escape"
        elif self._wave_active:
            self._hint_label.text = "Enemies incoming!"
        elif self._current_wave >= len(WAVE_DEFS):
            self._hint_label.text = "All waves cleared!"
        else:
            self._hint_label.text = "Select a tower to build"

    # ==================================================================
    # Enemy spawning and wave management (same as ch4)
    # ==================================================================

    def _start_next_wave(self) -> None:
        """Begin spawning enemies for the current wave."""
        if self._current_wave >= len(WAVE_DEFS):
            self._update_hint_text()
            return

        self._wave_active = True
        self._wave_spawned = 0
        wave = WAVE_DEFS[self._current_wave]

        self._wave_label.text = (
            f"Wave: {self._current_wave + 1}/{len(WAVE_DEFS)}"
        )
        self._update_hint_text()

        print(f"Wave {self._current_wave + 1} starting — "
              f"{wave['count']}x {ENEMY_DEFS[wave['enemy_def']]['name']}")

        self._schedule_next_spawn()

    def _schedule_next_spawn(self) -> None:
        """Schedule the next enemy spawn for the current wave."""
        if self._current_wave >= len(WAVE_DEFS):
            return

        wave = WAVE_DEFS[self._current_wave]
        if self._wave_spawned >= wave["count"]:
            return

        interval = wave["spawn_interval"]
        self.after(interval, self._spawn_enemy)

    def _spawn_enemy(self) -> None:
        """Spawn one enemy for the current wave and schedule the next."""
        if self._current_wave >= len(WAVE_DEFS) or self._game_over:
            return

        wave = WAVE_DEFS[self._current_wave]
        edef = ENEMY_DEFS[wave["enemy_def"]]

        start_x, start_y = ENEMY_PATH_PX[0]
        sprite = self.add_sprite(
            Sprite(
                edef["image"],
                position=(start_x, start_y),
                anchor=SpriteAnchor.CENTER,
                layer=RenderLayer.OBJECTS,
            )
        )

        fsm = StateMachine(
            states=["walking", "dying", "dead"],
            initial="walking",
            transitions={
                "walking": {"die": "dying"},
                "dying": {"finish": "dead"},
            },
        )

        enemy: dict[str, Any] = {
            "sprite": sprite,
            "fsm": fsm,
            "hp": edef["hp"],
            "max_hp": edef["hp"],
            "speed": edef["speed"],
            "path_index": 0,
            "gold_reward": edef["gold_reward"],
            "def": edef,
        }
        self._enemies.append(enemy)

        self._walk_to_next(enemy)

        self._wave_spawned += 1
        self._schedule_next_spawn()

    # ------------------------------------------------------------------
    # Enemy movement (same as ch4)
    # ------------------------------------------------------------------

    def _walk_to_next(self, enemy: dict[str, Any]) -> None:
        """Start the enemy walking to the next waypoint.

        Uses ``sprite.move_to()`` with an ``on_arrive`` callback that
        advances to the next waypoint.  We use ``move_to`` (the tween-based
        method) rather than a composable ``Sequence(MoveTo, Do)`` because
        the arrival callback fires *after* the action completes — this
        avoids a re-entrancy issue where ``sprite.do()`` inside a ``Do``
        action would be immediately overwritten by the parent Sequence
        finishing.
        """
        if enemy["fsm"].state != "walking":
            return

        idx = enemy["path_index"] + 1
        if idx >= len(ENEMY_PATH_PX):
            self._enemy_reached_end(enemy)
            return

        enemy["path_index"] = idx
        target = ENEMY_PATH_PX[idx]

        enemy["sprite"].move_to(
            target,
            speed=enemy["speed"],
            on_arrive=lambda e=enemy: self._walk_to_next(e),
        )

    def _enemy_reached_end(self, enemy: dict[str, Any]) -> None:
        """Handle an enemy reaching the exit — lose a life, remove enemy."""
        if enemy["fsm"].state != "walking":
            return

        self._lives -= 1
        if self._lives < 0:
            self._lives = 0
        self._lives_label.text = f"Lives: {self._lives}"
        print(f"Enemy escaped! Lives: {self._lives}")

        self._remove_enemy(enemy)

        if self._lives <= 0 and not self._game_over:
            self._game_over = True
            self._update_hint_text()
            print("Game Over!")

        self._check_wave_complete()

    def _kill_enemy(self, enemy: dict[str, Any]) -> None:
        """Kill an enemy (HP reached 0): award gold, play death sequence."""
        if enemy["fsm"].state != "walking":
            return

        enemy["fsm"].trigger("die")

        # Award gold.
        self._gold += enemy["gold_reward"]
        self._gold_label.text = f"Gold: {self._gold}"
        self._refresh_buy_buttons()

        print(
            f"Enemy killed! +{enemy['gold_reward']}g — "
            f"gold: {self._gold}"
        )

        # Death animation: fade out, then remove.
        enemy["sprite"].do(
            Sequence(
                FadeOut(0.4),
                Do(lambda e=enemy: self._finish_dying(e)),
                Remove(),
            )
        )

    def _finish_dying(self, enemy: dict[str, Any]) -> None:
        """Transition FSM to dead and clean up the enemy record."""
        enemy["fsm"].trigger("finish")
        if enemy in self._enemies:
            self._enemies.remove(enemy)
        self._check_wave_complete()

    def _remove_enemy(self, enemy: dict[str, Any]) -> None:
        """Immediately remove an enemy (no animation)."""
        sprite = enemy["sprite"]
        if not sprite.is_removed:
            sprite.remove()
        if enemy in self._enemies:
            self._enemies.remove(enemy)

    # ------------------------------------------------------------------
    # Wave completion (same as ch4)
    # ------------------------------------------------------------------

    def _check_wave_complete(self) -> None:
        """Check if all enemies from the current wave are gone."""
        if not self._wave_active:
            return

        wave = WAVE_DEFS[self._current_wave]

        if self._wave_spawned < wave["count"]:
            return

        alive = [e for e in self._enemies if e["fsm"].state in ("walking", "dying")]
        if alive:
            return

        self._wave_active = False
        self._current_wave += 1

        if self._game_over:
            return

        if self._current_wave >= len(WAVE_DEFS):
            self._update_hint_text()
            print("All waves cleared! You win!")
            return

        self._hint_label.text = "Next wave incoming..."
        wave_delay = WAVE_DEFS[self._current_wave]["delay"]
        self.after(wave_delay, self._start_next_wave)

    # ==================================================================
    # Tower combat — targeting, projectiles, damage
    # ==================================================================

    def _tower_center(self, col: int, row: int) -> tuple[float, float]:
        """Return the world-pixel centre of a tower at (col, row)."""
        return (
            col * TILE_SIZE + TILE_SIZE / 2,
            row * TILE_SIZE + TILE_SIZE / 2,
        )

    def _distance(
        self,
        x1: float, y1: float,
        x2: float, y2: float,
    ) -> float:
        """Euclidean distance between two points."""
        dx = x2 - x1
        dy = y2 - y1
        return math.sqrt(dx * dx + dy * dy)

    # ------------------------------------------------------------------
    # Tower targeting — called each frame from update()
    # ------------------------------------------------------------------

    def _update_towers(self, dt: float) -> None:
        """For each placed tower, reduce cooldown and fire if ready.

        Targeting policy: closest *walking* enemy within range.
        """
        for (col, row), tower in self._placed_towers.items():
            # Reduce cooldown.
            tower["cooldown"] -= dt
            if tower["cooldown"] > 0:
                continue

            tdef = tower["def"]
            tx, ty = self._tower_center(col, row)
            range_px = tdef["range_px"]

            # Find the closest walking enemy in range.
            best_enemy: dict[str, Any] | None = None
            best_dist = float("inf")

            for enemy in self._enemies:
                if enemy["fsm"].state != "walking":
                    continue
                esp = enemy["sprite"]
                if esp.is_removed:
                    continue
                ex, ey = esp._x, esp._y
                dist = self._distance(tx, ty, ex, ey)
                if dist <= range_px and dist < best_dist:
                    best_dist = dist
                    best_enemy = enemy

            if best_enemy is None:
                continue  # No target in range — wait.

            # Fire!
            self._fire_projectile(tower, col, row, best_enemy)

            # Reset cooldown based on fire rate.
            tower["cooldown"] = 1.0 / tdef["fire_rate"]

    # ------------------------------------------------------------------
    # Projectile creation
    # ------------------------------------------------------------------

    def _fire_projectile(
        self,
        tower: dict[str, Any],
        col: int,
        row: int,
        target_enemy: dict[str, Any],
    ) -> None:
        """Create a projectile sprite aimed at *target_enemy*'s current pos.

        The projectile moves toward the target's position at the time of
        firing (a "dumb" projectile that doesn't track the enemy).
        """
        tdef = tower["def"]
        tx, ty = self._tower_center(col, row)

        # Snapshot the target's current position.
        esp = target_enemy["sprite"]
        target_pos = (esp._x, esp._y)

        proj_sprite = self.add_sprite(
            Sprite(
                tdef["projectile"],
                position=(tx, ty),
                anchor=SpriteAnchor.CENTER,
                layer=RenderLayer.EFFECTS,
            )
        )

        proj: dict[str, Any] = {
            "sprite": proj_sprite,
            "target_enemy": target_enemy,
            "target_pos": target_pos,
            "damage": tdef["damage"],
            "splash_radius": tdef["splash_radius"],
        }
        self._projectiles.append(proj)

        # Move the projectile toward the target position.
        # The on_arrive callback handles damage, particles, and cleanup.
        proj_sprite.move_to(
            target_pos,
            speed=PROJECTILE_SPEED,
            on_arrive=lambda p=proj: self._projectile_arrived(p),
        )

    # ------------------------------------------------------------------
    # Projectile arrival — damage + particles
    # ------------------------------------------------------------------

    def _projectile_arrived(self, proj: dict[str, Any]) -> None:
        """Handle a projectile reaching its target position.

        1. Deal damage (single-target or splash).
        2. Spawn a ParticleEmitter burst at the impact point.
        3. Remove the projectile sprite.
        """
        # 1. Remove from tracking list.
        if proj in self._projectiles:
            self._projectiles.remove(proj)

        sprite = proj["sprite"]
        if sprite.is_removed:
            return

        impact_x, impact_y = proj["target_pos"]

        # 2. Deal damage.
        if proj["splash_radius"] > 0:
            self._apply_splash_damage(
                impact_x, impact_y,
                proj["splash_radius"],
                proj["damage"],
            )
        else:
            # Single-target: damage the target enemy if still walking.
            target = proj["target_enemy"]
            if target["fsm"].state == "walking" and not target["sprite"].is_removed:
                self._deal_damage(target, proj["damage"])

        # 3. Spawn impact particles.
        ParticleEmitter(
            "explosion",
            position=(impact_x, impact_y),
            count=8,
            speed=(30, 80),
            lifetime=(0.15, 0.35),
            fade_out=True,
        ).burst()

        # 4. Remove the projectile sprite.
        sprite.remove()

    def _apply_splash_damage(
        self,
        x: float, y: float,
        radius: float,
        damage: int,
    ) -> None:
        """Deal *damage* to all walking enemies within *radius* of (x, y)."""
        for enemy in list(self._enemies):
            if enemy["fsm"].state != "walking":
                continue
            esp = enemy["sprite"]
            if esp.is_removed:
                continue
            dist = self._distance(x, y, esp._x, esp._y)
            if dist <= radius:
                self._deal_damage(enemy, damage)

    def _deal_damage(self, enemy: dict[str, Any], damage: int) -> None:
        """Subtract *damage* from the enemy's HP.  Kill if HP <= 0."""
        if enemy["fsm"].state != "walking":
            return
        enemy["hp"] -= damage
        if enemy["hp"] <= 0:
            enemy["hp"] = 0
            self._kill_enemy(enemy)

    # ------------------------------------------------------------------
    # Projectile cleanup — remove orphaned projectiles
    # ------------------------------------------------------------------

    def _cleanup_orphan_projectiles(self) -> None:
        """Remove projectiles whose sprites have been removed.

        This handles edge cases where a projectile's sprite is cleaned
        up (e.g. scene exit) before arrival.
        """
        still_alive: list[dict[str, Any]] = []
        for proj in self._projectiles:
            if proj["sprite"].is_removed:
                continue
            still_alive.append(proj)
        self._projectiles = still_alive

    # ==================================================================
    # Update — tower targeting + projectile cleanup
    # ==================================================================

    def update(self, dt: float) -> None:
        """Per-frame update: tower combat and projectile management.

        Tower targeting and firing runs each frame.  Projectile movement
        is handled by ``sprite.move_to()`` — no manual position polling
        needed.
        """
        if self._game_over:
            return

        self._update_towers(dt)
        self._cleanup_orphan_projectiles()

    # ==================================================================
    # Draw — health bars above damaged enemies
    # ==================================================================

    def draw(self) -> None:
        """Custom per-frame rendering: enemy health bars.

        Uses ``self.draw_world_rect()`` to draw a red background and
        green foreground bar above each enemy that has taken damage.
        World-space coordinates are automatically transformed by the
        camera — no manual ``world_to_screen()`` needed.
        """
        for enemy in self._enemies:
            if enemy["fsm"].state not in ("walking",):
                continue  # Don't show health bars on dying enemies.

            hp = enemy["hp"]
            max_hp = enemy["max_hp"]

            if hp >= max_hp:
                continue  # Full health — no bar needed.

            esp = enemy["sprite"]
            if esp.is_removed:
                continue

            # Centre the health bar above the enemy (world-space coords).
            bar_x = esp._x - HEALTH_BAR_WIDTH / 2
            bar_y = esp._y + HEALTH_BAR_Y_OFFSET

            # Background bar (dark red).
            self.draw_world_rect(
                bar_x, bar_y,
                HEALTH_BAR_WIDTH, HEALTH_BAR_HEIGHT,
                HEALTH_BAR_BG_COLOR,
            )

            # Foreground bar (green) — proportional to remaining HP.
            hp_ratio = max(0.0, hp / max_hp)
            fill_width = max(1, int(HEALTH_BAR_WIDTH * hp_ratio))

            self.draw_world_rect(
                bar_x, bar_y,
                fill_width, HEALTH_BAR_HEIGHT,
                HEALTH_BAR_FG_COLOR,
            )

    # ------------------------------------------------------------------
    # Input handling (same as ch3/ch4)
    # ------------------------------------------------------------------

    def handle_input(self, event: InputEvent) -> bool:
        """Handle mouse clicks, mouse movement, and keyboard input."""

        # -----------------------------------------------------------------
        # Escape — cancel placement first, then pop to title if idle.
        # -----------------------------------------------------------------
        if event.action == "cancel":
            if self._placing_tower_def is not None:
                self._cancel_placement()
                return True
            self.game.pop()
            return True

        # -----------------------------------------------------------------
        # Right-click — cancel placement mode.
        # -----------------------------------------------------------------
        if event.type == "click" and event.button == "right":
            if self._placing_tower_def is not None:
                self._cancel_placement()
                return True
            return False

        # -----------------------------------------------------------------
        # Left-click — attempt tower placement.
        # -----------------------------------------------------------------
        if event.type == "click" and event.button == "left":
            if self._placing_tower_def is not None and event.world_x is not None and event.world_y is not None:
                self._try_place_tower(event.world_x, event.world_y)
                return True
            return False

        # -----------------------------------------------------------------
        # Mouse movement — update range indicator.
        # -----------------------------------------------------------------
        if event.type in ("move", "drag"):
            if self._placing_tower_def is not None and self._range_indicator is not None and event.world_x is not None and event.world_y is not None:
                wx, wy = event.world_x, event.world_y
                snap = self._snap_to_nearest_slot(wx, wy)
                if snap is not None:
                    self._range_indicator.position = snap
                else:
                    self._range_indicator.position = (wx, wy)
                return True
            return False

        return False


# ======================================================================
# Main — entry point
# ======================================================================

def main() -> None:
    """Create the Game and run with the title screen.

    Same setup pattern as Chapters 1–4.
    """
    game = Game(
        "Tower Defense — Chapter 5",
        resolution=(SCREEN_W, SCREEN_H),
        fullscreen=False,
        backend="pyglet",
        asset_path=_asset_dir,
    )

    game.theme = Theme(
        font="serif",
        font_size=24,
        text_color=(220, 220, 230, 255),
        panel_background_color=(30, 35, 50, 220),
        panel_padding=16,
        button_background_color=(50, 55, 80, 255),
        button_hover_color=(70, 80, 120, 255),
        button_press_color=(35, 40, 60, 255),
        button_text_color=(220, 220, 230, 255),
        button_padding=14,
        button_font_size=26,
        button_min_width=220,
    )

    game.run(TitleScene())


if __name__ == "__main__":
    main()
