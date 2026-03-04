"""Tower Defense -- a complete example game built with Saga2D.

This file demonstrates a fully playable tower defense game using 12+
distinct Saga2D subsystems:

    1.  **Scene stack**      -- TitleScene, GameScene, ChoiceScreen, MessageScreen
    2.  **Sprite**           -- tiles, towers, enemies, projectiles, range indicator
    3.  **Camera**           -- scrollable world view with key-scroll
    4.  **Actions**          -- Sequence, FadeOut, Do, Remove for death animations
    5.  **Scene timers**     -- self.after() / self.every() with auto-cancel
    6.  **UI widgets**       -- Panel, Label, Button with Layout & Anchor
    7.  **Audio**            -- play_sound/play_music with optional=True
    8.  **Particles**        -- ParticleEmitter for projectile impact bursts
    9.  **StateMachine**     -- enemy FSM (walking -> dying -> dead)
    10. **Theme**            -- global UI theme for consistent styling
    11. **draw_world_rect**  -- camera-aware health bar rendering
    12. **Scene.add_sprite** -- automatic sprite lifecycle management
    13. **RenderLayer**      -- layered draw order (BACKGROUND, OBJECTS, EFFECTS)
    14. **InputEvent**       -- unified input handling (keyboard + mouse)

Stage 5 API improvements used:
    - Scene.after() / Scene.every() -- no manual timer cleanup
    - Scene.draw_world_rect()       -- camera-aware rectangle drawing
    - play_sound(optional=True)     -- silent fallback for missing audio
    - Scene.add_sprite()            -- auto-cleanup on scene exit

Run from the project root::

    python examples/tower_defense/main.py

Controls:
    Title Screen  -- Enter or click Play to start; Escape or click Quit to exit
    Game Screen   -- Click Buy to enter placement mode
                     Left-click a tower slot to place the tower
                     Right-click or Escape to cancel placement
                     Arrow keys to scroll the camera
                     Space to toggle 2x speed
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ---------------------------------------------------------------------------
# Auto-generate assets if missing
# ---------------------------------------------------------------------------
_asset_dir = Path(__file__).resolve().parent / "assets"
if not _asset_dir.exists() or not (_asset_dir / "images").exists():
    print("Assets not found -- generating placeholder art...")
    from examples.tower_defense.generate_assets import generate

    generate(_asset_dir)
    print()

# ---------------------------------------------------------------------------
# Saga2D imports
# ---------------------------------------------------------------------------
from saga2d import (  # noqa: E402
    Anchor,
    Button,
    Camera,
    ChoiceScreen,
    Do,
    FadeOut,
    Game,
    InputEvent,
    Label,
    Layout,
    MessageScreen,
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
TILE_SIZE = 32
CAMERA_SCROLL_SPEED = 200.0

# Colour palette
BG_COLOR = (25, 30, 40, 255)
TITLE_COLOR = (255, 220, 80, 255)
SUBTITLE_COLOR = (180, 180, 190, 255)
HUD_TEXT_COLOR = (220, 220, 230, 255)
GOLD_COLOR = (255, 210, 50, 255)
LIVES_COLOR = (255, 100, 100, 255)
SCORE_COLOR = (120, 220, 255, 255)

# Health bar
HEALTH_BAR_BG_COLOR = (80, 20, 20, 200)
HEALTH_BAR_FG_COLOR = (40, 200, 40, 220)
HEALTH_BAR_WIDTH = 22
HEALTH_BAR_HEIGHT = 3
HEALTH_BAR_Y_OFFSET = -14

# Starting resources
STARTING_GOLD = 200
STARTING_LIVES = 20

# Projectile speed
PROJECTILE_SPEED = 300.0


# ======================================================================
# Tower definitions
# ======================================================================

TOWER_DEFS: list[dict[str, Any]] = [
    {
        "name": "Basic",
        "image": "tower_basic",
        "cost": 50,
        "range_px": 96,
        "damage": 15,
        "fire_rate": 1.5,
        "splash_radius": 0,
        "projectile": "projectile_basic",
    },
    {
        "name": "Sniper",
        "image": "tower_sniper",
        "cost": 100,
        "range_px": 160,
        "damage": 50,
        "fire_rate": 0.5,
        "splash_radius": 0,
        "projectile": "projectile_sniper",
    },
    {
        "name": "Splash",
        "image": "tower_splash",
        "cost": 75,
        "range_px": 80,
        "damage": 10,
        "fire_rate": 1.0,
        "splash_radius": 48,
        "projectile": "projectile_splash",
    },
]


# ======================================================================
# Enemy definitions
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
    {
        "name": "Tank",
        "image": "enemy_tank",
        "hp": 200,
        "speed": 25,
        "gold_reward": 30,
    },
]


# ======================================================================
# Wave definitions -- 5 escalating waves
# ======================================================================

WAVE_DEFS: list[dict[str, Any]] = [
    # Wave 1: Introductory -- slow soldiers, generous spacing.
    {"enemy_def": 0, "count": 6, "spawn_interval": 1.2, "delay": 2.0},
    # Wave 2: Scout rush -- fast, fragile enemies.
    {"enemy_def": 1, "count": 10, "spawn_interval": 0.7, "delay": 3.0},
    # Wave 3: Heavy assault -- tanky enemies that soak damage.
    {"enemy_def": 2, "count": 4, "spawn_interval": 2.0, "delay": 3.0},
    # Wave 4: Mixed -- soldiers, faster pace.
    {"enemy_def": 0, "count": 12, "spawn_interval": 0.8, "delay": 3.0},
    # Wave 5: Final -- large tank wave.
    {"enemy_def": 2, "count": 8, "spawn_interval": 1.5, "delay": 3.0},
]


# ======================================================================
# Map definition -- 40x22 tile grid
# ======================================================================

GRASS = 0
PATH = 1

# fmt: off
MAP_DATA: list[list[int]] = [
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
]
# fmt: on

MAP_ROWS = len(MAP_DATA)
MAP_COLS = len(MAP_DATA[0])
MAP_WIDTH_PX = MAP_COLS * TILE_SIZE
MAP_HEIGHT_PX = MAP_ROWS * TILE_SIZE

# Enemy path -- tile coordinates (col, row) from spawn to exit.
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

# Tower build slots -- (col, row) positions adjacent to the enemy path.
TOWER_SLOTS: list[tuple[int, int]] = [
    (4, 4), (8, 2), (14, 2), (17, 6), (22, 7),
    (28, 7), (33, 10), (10, 12), (20, 12), (8, 13),
    (20, 15), (28, 15), (31, 16),
]


# ======================================================================
# Audio helpers -- safe sound playback using optional=True
# ======================================================================

def _play_sfx(game: Game, name: str) -> None:
    """Play a sound effect, silently ignoring missing assets."""
    game.audio.play_sound(name, optional=True)


def _play_music(game: Game, name: str) -> None:
    """Start background music, silently ignoring missing assets."""
    game.audio.play_music(name, optional=True)


def _stop_music(game: Game) -> None:
    """Stop background music."""
    game.audio.stop_music()


# ======================================================================
# TitleScene
# ======================================================================

class TitleScene(Scene):
    """Title screen with Play / Quit buttons.

    Subsystems demonstrated:
        - Scene lifecycle (on_enter, on_exit, handle_input)
        - UI widgets (Panel, Label, Button with Layout & Anchor)
        - Audio (play_music with optional=True)
        - Theme (inherited from Game.theme)
    """

    background_color = BG_COLOR

    def on_enter(self) -> None:
        title_label = Label(
            "Tower Defense",
            font_size=48,
            text_color=TITLE_COLOR,
        )
        subtitle_label = Label(
            "An Saga2D Example",
            font_size=18,
            text_color=SUBTITLE_COLOR,
        )
        play_button = Button("Play", on_click=self._on_play)
        quit_button = Button("Quit", on_click=self._on_quit)

        menu_panel = Panel(
            layout=Layout.VERTICAL,
            spacing=20,
            anchor=Anchor.CENTER,
            style=Style(background_color=(30, 35, 50, 220), padding=40),
            children=[title_label, subtitle_label, play_button, quit_button],
        )
        self.ui.add(menu_panel)

    def on_exit(self) -> None:
        _stop_music(self.game)

    def _on_play(self) -> None:
        self.game.push(GameScene())

    def _on_quit(self) -> None:
        self.game.quit()

    def handle_input(self, event: InputEvent) -> bool:
        if event.action == "confirm":
            self._on_play()
            return True
        if event.action == "cancel":
            self._on_quit()
            return True
        return False


# ======================================================================
# GameScene -- the complete game
# ======================================================================

class GameScene(Scene):
    """Gameplay scene: tower placement, enemy waves, combat, win/lose.

    This scene exercises all major Saga2D subsystems:

    - **Sprites** for tiles, towers, enemies, projectiles, range indicator
    - **Camera** with key-scrolling and world bounds
    - **Scene timers** (self.after) for wave scheduling with auto-cancel
    - **StateMachine** for enemy states (walking -> dying -> dead)
    - **Actions** for death animations (Sequence + FadeOut + Do + Remove)
    - **ParticleEmitter** for projectile impact bursts
    - **draw_world_rect** for camera-aware health bars
    - **add_sprite** for automatic sprite lifecycle management
    - **UI widgets** for HUD (wave, gold, lives, score) and build menu
    - **Audio** with optional=True for SFX and music
    - **RenderLayer** for layered draw order
    - **InputEvent** for mouse clicks (placement) and keyboard (speed toggle)
    """

    show_hud = True

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self) -> None:
        """Set up the complete game state."""

        # Game state
        self._gold = STARTING_GOLD
        self._lives = STARTING_LIVES
        self._score = 0
        self._current_wave = 0
        self._wave_active = False
        self._wave_spawned = 0
        self._game_over = False
        self._game_won = False
        self._speed_multiplier = 1.0

        # Placement state
        self._placing_tower_def: dict[str, Any] | None = None

        # Placed towers: (col, row) -> tower info dict
        self._placed_towers: dict[tuple[int, int], dict[str, Any]] = {}

        # Slot sprites: (col, row) -> Sprite
        self._slot_sprites: dict[tuple[int, int], Sprite] = {}

        # Enemy tracking
        self._enemies: list[dict[str, Any]] = []

        # Projectile tracking
        self._projectiles: list[dict[str, Any]] = []

        # --- Camera (subsystem #3) ---
        self.camera = Camera(
            (SCREEN_W, SCREEN_H),
            world_bounds=(0, 0, MAP_WIDTH_PX, MAP_HEIGHT_PX),
        )
        self.camera.center_on(MAP_WIDTH_PX / 2, MAP_HEIGHT_PX / 2)
        self.camera.enable_key_scroll(speed=CAMERA_SCROLL_SPEED)

        # --- Tile map (subsystem #2: Sprite, #12: add_sprite) ---
        self._create_tile_map()

        # --- Tower slot markers ---
        self._create_tower_slots()

        # --- UI (subsystem #6) ---
        self._build_hud()
        self._build_menu()

        # --- Range indicator (subsystem #2, #13: RenderLayer) ---
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

        # --- Background music (subsystem #7: Audio) ---
        _play_music(self.game, "bgm_game")

        # --- Schedule wave 1 (subsystem #5: Scene timers) ---
        self.after(2.0, self._start_next_wave)

    def on_exit(self) -> None:
        """Stop music.  Timers and sprites are auto-cleaned by the framework."""
        _stop_music(self.game)

    # ------------------------------------------------------------------
    # Tile map
    # ------------------------------------------------------------------

    def _create_tile_map(self) -> None:
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
    # Tower slots
    # ------------------------------------------------------------------

    def _create_tower_slots(self) -> None:
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
    # HUD -- wave, gold, lives, score, hint, speed indicator
    # ------------------------------------------------------------------

    def _build_hud(self) -> None:
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
        self._score_label = Label(
            f"Score: {self._score}",
            font_size=20,
            text_color=SCORE_COLOR,
        )
        self._hint_label = Label(
            "Wave starting soon...",
            font_size=14,
            text_color=(140, 140, 150, 255),
        )
        self._speed_label = Label(
            "",
            font_size=14,
            text_color=(200, 200, 100, 255),
        )
        hud_panel = Panel(
            layout=Layout.HORIZONTAL,
            spacing=24,
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
                self._score_label,
                self._hint_label,
                self._speed_label,
            ],
        )
        self.ui.add(hud_panel)

    # ------------------------------------------------------------------
    # Build menu
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
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
                style=Style(font_size=16, padding=6),
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
        speed_hint = Label(
            "Space: toggle 2\u00d7 speed",
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
            children=[menu_title, *tower_rows, cancel_label, speed_hint],
        )
        self.ui.add(build_panel)

        self._refresh_buy_buttons()

    # ------------------------------------------------------------------
    # Buy button callback
    # ------------------------------------------------------------------

    def _on_buy_clicked(self, tower_def: dict[str, Any]) -> None:
        self._placing_tower_def = tower_def
        if self._range_indicator is not None:
            self._range_indicator.visible = True
        cost = tower_def["cost"]
        name = tower_def["name"]
        self._hint_label.text = f"Placing {name} ({cost}g) -- click a slot"

    # ------------------------------------------------------------------
    # Tower placement
    # ------------------------------------------------------------------

    def _cancel_placement(self) -> None:
        self._placing_tower_def = None
        if self._range_indicator is not None:
            self._range_indicator.visible = False
            self._range_indicator.position = (-9999, -9999)
        self._update_hint_text()

    def _try_place_tower(self, world_x: float, world_y: float) -> bool:
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

        self._gold -= cost

        # Replace the slot marker with the tower sprite.
        slot_sprite = self._slot_sprites.pop((col, row))
        slot_sprite.remove()

        tower_sprite = Sprite(
            tower_def["image"],
            position=(col * TILE_SIZE, row * TILE_SIZE),
            anchor=SpriteAnchor.TOP_LEFT,
            layer=RenderLayer.OBJECTS,
        )
        self.add_sprite(tower_sprite)

        self._placed_towers[(col, row)] = {
            "def": tower_def,
            "sprite": tower_sprite,
            "cooldown": 0.0,
        }

        self._gold_label.text = f"Gold: {self._gold}"
        self._refresh_buy_buttons()
        self._cancel_placement()

        return True

    def _refresh_buy_buttons(self) -> None:
        for i, tdef in enumerate(TOWER_DEFS):
            can_afford = self._gold >= tdef["cost"]
            self._buy_buttons[i].enabled = can_afford

    def _snap_to_nearest_slot(
        self, world_x: float, world_y: float,
    ) -> tuple[float, float] | None:
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
    # HUD hint text
    # ------------------------------------------------------------------

    def _update_hint_text(self) -> None:
        if self._game_over:
            self._hint_label.text = "Game Over!"
        elif self._game_won:
            self._hint_label.text = "Victory!"
        elif self._wave_active:
            self._hint_label.text = "Enemies incoming!"
        elif self._current_wave >= len(WAVE_DEFS):
            self._hint_label.text = "All waves cleared!"
        else:
            self._hint_label.text = "Select a tower to build"

    # ==================================================================
    # Enemy spawning and wave management
    # ==================================================================

    def _start_next_wave(self) -> None:
        if self._current_wave >= len(WAVE_DEFS) or self._game_over:
            self._update_hint_text()
            return

        self._wave_active = True
        self._wave_spawned = 0
        wave = WAVE_DEFS[self._current_wave]

        self._wave_label.text = (
            f"Wave: {self._current_wave + 1}/{len(WAVE_DEFS)}"
        )
        self._update_hint_text()

        _play_sfx(self.game, "sfx_wave")

        print(
            f"Wave {self._current_wave + 1} starting -- "
            f"{wave['count']}x {ENEMY_DEFS[wave['enemy_def']]['name']}"
        )

        self._schedule_next_spawn()

    def _schedule_next_spawn(self) -> None:
        if self._current_wave >= len(WAVE_DEFS) or self._game_over:
            return
        wave = WAVE_DEFS[self._current_wave]
        if self._wave_spawned >= wave["count"]:
            return
        interval = wave["spawn_interval"]
        self.after(interval, self._spawn_enemy)

    def _spawn_enemy(self) -> None:
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

        # --- StateMachine (subsystem #9) ---
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
    # Enemy movement
    # ------------------------------------------------------------------

    def _walk_to_next(self, enemy: dict[str, Any]) -> None:
        """Move enemy to next waypoint via sprite.move_to()."""
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
        if enemy["fsm"].state != "walking":
            return

        self._lives -= 1
        if self._lives < 0:
            self._lives = 0
        self._lives_label.text = f"Lives: {self._lives}"

        _play_sfx(self.game, "sfx_lose_life")

        self._remove_enemy(enemy)

        if self._lives <= 0 and not self._game_over:
            self._trigger_game_over()

        self._check_wave_complete()

    def _kill_enemy(self, enemy: dict[str, Any]) -> None:
        if enemy["fsm"].state != "walking":
            return

        enemy["fsm"].trigger("die")

        # Award gold and score.
        reward = enemy["gold_reward"]
        self._gold += reward
        self._score += reward
        self._gold_label.text = f"Gold: {self._gold}"
        self._score_label.text = f"Score: {self._score}"
        self._refresh_buy_buttons()

        _play_sfx(self.game, "sfx_death")

        # --- Actions (subsystem #4) ---
        enemy["sprite"].do(
            Sequence(
                FadeOut(0.4),
                Do(lambda e=enemy: self._finish_dying(e)),
                Remove(),
            )
        )

    def _finish_dying(self, enemy: dict[str, Any]) -> None:
        enemy["fsm"].trigger("finish")
        if enemy in self._enemies:
            self._enemies.remove(enemy)
        self._check_wave_complete()

    def _remove_enemy(self, enemy: dict[str, Any]) -> None:
        sprite = enemy["sprite"]
        if not sprite.is_removed:
            sprite.remove()
        if enemy in self._enemies:
            self._enemies.remove(enemy)

    # ------------------------------------------------------------------
    # Wave completion
    # ------------------------------------------------------------------

    def _check_wave_complete(self) -> None:
        if not self._wave_active:
            return

        wave = WAVE_DEFS[self._current_wave]
        if self._wave_spawned < wave["count"]:
            return

        alive = [
            e for e in self._enemies
            if e["fsm"].state in ("walking", "dying")
        ]
        if alive:
            return

        # Wave complete!
        self._wave_active = False
        self._current_wave += 1

        if self._game_over:
            return

        if self._current_wave >= len(WAVE_DEFS):
            self._check_victory()
            return

        self._hint_label.text = "Next wave incoming..."
        wave_delay = WAVE_DEFS[self._current_wave]["delay"]
        self.after(wave_delay, self._start_next_wave)

    def _check_victory(self) -> None:
        """Check if the player has won (all waves done, no enemies alive)."""
        if self._game_over or self._game_won:
            return

        alive = [
            e for e in self._enemies
            if e["fsm"].state in ("walking", "dying")
        ]
        if alive:
            return

        self._game_won = True
        self._update_hint_text()
        _stop_music(self.game)

        print(f"Victory! Final score: {self._score}")

        self.game.push(MessageScreen(
            f"Victory!  Score: {self._score}",
            on_dismiss=lambda: self.game.pop(),
        ))

    # ==================================================================
    # Game Over / Win
    # ==================================================================

    def _trigger_game_over(self) -> None:
        """Handle game-over state: push choice overlay."""
        self._game_over = True
        self._update_hint_text()

        _stop_music(self.game)

        print(f"Game Over! Score: {self._score}")

        # Push a ChoiceScreen overlay (subsystem #1: Scene stack).
        self.game.push(ChoiceScreen(
            f"Game Over!  Score: {self._score}",
            ["Retry", "Quit to Title"],
            on_choice=self._on_game_over_choice,
        ))

    def _on_game_over_choice(self, index: int) -> None:
        """Handle the player's choice on the game-over screen.

        This callback fires *before* ChoiceScreen pops itself.  We
        schedule the follow-up action one tick later so the pop resolves
        first, leaving GameScene on top where we can replace it.

        NOTE: We intentionally use ``self.game.after()`` instead of
        ``self.after()`` because these callbacks must survive the
        scene exit that occurs when ChoiceScreen pops.
        """
        if index == 0:
            # Retry -- replace GameScene with a fresh one, one tick later.
            self.game.after(0, lambda: self.game.replace(GameScene()))
        else:
            # Quit to title -- pop GameScene (one tick later).
            self.game.after(0, lambda: self.game.pop())

    # ==================================================================
    # Tower combat
    # ==================================================================

    def _tower_center(self, col: int, row: int) -> tuple[float, float]:
        return (
            col * TILE_SIZE + TILE_SIZE / 2,
            row * TILE_SIZE + TILE_SIZE / 2,
        )

    def _distance(
        self, x1: float, y1: float, x2: float, y2: float,
    ) -> float:
        dx = x2 - x1
        dy = y2 - y1
        return math.sqrt(dx * dx + dy * dy)

    def _update_towers(self, dt: float) -> None:
        for (col, row), tower in self._placed_towers.items():
            tower["cooldown"] -= dt
            if tower["cooldown"] > 0:
                continue

            tdef = tower["def"]
            tx, ty = self._tower_center(col, row)
            range_px = tdef["range_px"]

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
                continue

            self._fire_projectile(tower, col, row, best_enemy)
            tower["cooldown"] = 1.0 / tdef["fire_rate"]

    def _fire_projectile(
        self,
        tower: dict[str, Any],
        col: int,
        row: int,
        target_enemy: dict[str, Any],
    ) -> None:
        tdef = tower["def"]
        tx, ty = self._tower_center(col, row)

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

        proj_sprite.move_to(
            target_pos,
            speed=PROJECTILE_SPEED,
            on_arrive=lambda p=proj: self._projectile_arrived(p),
        )

        _play_sfx(self.game, "sfx_shoot")

    def _projectile_arrived(self, proj: dict[str, Any]) -> None:
        if proj in self._projectiles:
            self._projectiles.remove(proj)

        sprite = proj["sprite"]
        if sprite.is_removed:
            return

        impact_x, impact_y = proj["target_pos"]

        if proj["splash_radius"] > 0:
            self._apply_splash_damage(
                impact_x, impact_y,
                proj["splash_radius"],
                proj["damage"],
            )
        else:
            target = proj["target_enemy"]
            if (target["fsm"].state == "walking"
                    and not target["sprite"].is_removed):
                self._deal_damage(target, proj["damage"])

        _play_sfx(self.game, "sfx_hit")

        # --- ParticleEmitter (subsystem #8) ---
        ParticleEmitter(
            "explosion",
            position=(impact_x, impact_y),
            count=8,
            speed=(30, 80),
            lifetime=(0.15, 0.35),
            fade_out=True,
        ).burst()

        sprite.remove()

    def _apply_splash_damage(
        self, x: float, y: float, radius: float, damage: int,
    ) -> None:
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
        if enemy["fsm"].state != "walking":
            return
        enemy["hp"] -= damage
        if enemy["hp"] <= 0:
            enemy["hp"] = 0
            self._kill_enemy(enemy)

    def _cleanup_orphan_projectiles(self) -> None:
        self._projectiles = [
            p for p in self._projectiles if not p["sprite"].is_removed
        ]

    # ==================================================================
    # Update
    # ==================================================================

    def update(self, dt: float) -> None:
        """Per-frame update with optional speed multiplier."""
        if self._game_over or self._game_won:
            return

        effective_dt = dt * self._speed_multiplier
        self._update_towers(effective_dt)
        self._cleanup_orphan_projectiles()

    # ==================================================================
    # Draw -- health bars using draw_world_rect (subsystem #11)
    # ==================================================================

    def draw(self) -> None:
        for enemy in self._enemies:
            if enemy["fsm"].state != "walking":
                continue

            hp = enemy["hp"]
            max_hp = enemy["max_hp"]
            if hp >= max_hp:
                continue

            esp = enemy["sprite"]
            if esp.is_removed:
                continue

            # World-space health bar position (camera transform is automatic).
            bar_x = esp._x - HEALTH_BAR_WIDTH / 2
            bar_y = esp._y + HEALTH_BAR_Y_OFFSET

            self.draw_world_rect(
                bar_x, bar_y,
                HEALTH_BAR_WIDTH, HEALTH_BAR_HEIGHT,
                HEALTH_BAR_BG_COLOR,
            )

            hp_ratio = max(0.0, hp / max_hp)
            fill_width = max(1, int(HEALTH_BAR_WIDTH * hp_ratio))

            self.draw_world_rect(
                bar_x, bar_y,
                fill_width, HEALTH_BAR_HEIGHT,
                HEALTH_BAR_FG_COLOR,
            )

    # ------------------------------------------------------------------
    # Input handling (subsystem #14)
    # ------------------------------------------------------------------

    def handle_input(self, event: InputEvent) -> bool:
        # Escape -- cancel placement first, then pop to title.
        if event.action == "cancel":
            if self._placing_tower_def is not None:
                self._cancel_placement()
                return True
            self.game.pop()
            return True

        # Right-click -- cancel placement.
        if event.type == "click" and event.button == "right":
            if self._placing_tower_def is not None:
                self._cancel_placement()
                return True
            return False

        # Left-click -- tower placement.
        if event.type == "click" and event.button == "left":
            if (self._placing_tower_def is not None
                    and event.world_x is not None
                    and event.world_y is not None):
                self._try_place_tower(event.world_x, event.world_y)
                return True
            return False

        # Mouse movement -- range indicator.
        if event.type in ("move", "drag"):
            if (self._placing_tower_def is not None
                    and self._range_indicator is not None
                    and event.world_x is not None
                    and event.world_y is not None):
                wx, wy = event.world_x, event.world_y
                snap = self._snap_to_nearest_slot(wx, wy)
                if snap is not None:
                    self._range_indicator.position = snap
                else:
                    self._range_indicator.position = (wx, wy)
                return True
            return False

        # Space -- toggle 2x speed.
        if event.type == "key_press" and getattr(event, "key", None) == "space":
            if self._speed_multiplier == 1.0:
                self._speed_multiplier = 2.0
                self._speed_label.text = "[2\u00d7 SPEED]"
            else:
                self._speed_multiplier = 1.0
                self._speed_label.text = ""
            return True

        return False


# ======================================================================
# Main -- entry point
# ======================================================================

def main() -> None:
    """Create the Game and run with the title screen."""
    game = Game(
        "Tower Defense",
        resolution=(SCREEN_W, SCREEN_H),
        fullscreen=False,
        backend="pyglet",
        asset_path=_asset_dir,
    )

    # --- Theme (subsystem #10) ---
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
