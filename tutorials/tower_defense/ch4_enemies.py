"""Chapter 4 — Enemy Waves
===========================

Building on Chapter 3, this chapter adds **enemies and wave spawning**:

*   **Enemy definitions** — two types: a slow/tanky Basic soldier and a
    quick/fragile Fast scout, each with HP, speed, and gold reward.
*   **Wave definitions** — three escalating waves that specify enemy type,
    count, spawn interval, and delay before the wave starts.
*   **Path-following** — enemies spawn at the first waypoint of ENEMY_PATH
    and follow it using ``sprite.move_to()`` with chained arrival callbacks,
    advancing one waypoint at a time.
*   **Enemy FSM** — a simple state machine with ``walking``, ``dying``,
    and ``dead`` states.  ``dying`` triggers a ``FadeOut`` + ``Remove``
    action sequence.
*   **Wave spawning** — ``self.after()`` timers schedule enemy spawns.
    Scene-owned timers are auto-cancelled on scene exit.
*   **Player lives** — starting at 20.  Enemies that reach the path end
    deduct 1 life and are removed.  Lives are shown in the HUD.
*   **Gold rewards** — enemies killed (reaching 0 HP) award gold.  For now,
    only the "reach path end" path triggers removal (combat comes in ch5).
*   **Auto-start** — wave 1 starts a couple seconds after entering the
    game scene.  The next wave starts a few seconds after all enemies from
    the current wave are gone.

Towers from ch3 are still placeable but don't shoot yet — that's Chapter 5.

Run from the project root::

    python tutorials/tower_defense/ch4_enemies.py

Controls:
    Title Screen — Enter or click Play → start game.
                   Escape or click Quit → exit.
    Game Screen  — Click a Buy button → enter placement mode.
                   Left-click on a tower slot → place the tower.
                   Right-click or Escape → cancel placement / return to menu.
                   Arrow keys → scroll the camera.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup — same pattern as Chapters 1–3.
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
# Saga2D imports
# ---------------------------------------------------------------------------
from saga2d import (  # noqa: E402
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

# Starting resources.
STARTING_GOLD = 200
STARTING_LIVES = 20


# ======================================================================
# Tower definitions (same as ch3)
# ======================================================================

TOWER_DEFS: list[dict[str, Any]] = [
    {
        "name": "Basic",
        "image": "tower_basic",
        "cost": 50,
        "range_px": 96,
    },
    {
        "name": "Sniper",
        "image": "tower_sniper",
        "cost": 100,
        "range_px": 160,
    },
    {
        "name": "Splash",
        "image": "tower_splash",
        "cost": 75,
        "range_px": 80,
    },
]


# ======================================================================
# Enemy definitions
# ======================================================================

# Each enemy type is a dict with:
#   name:        Display name (for future tooltips / wave banner).
#   image:       Asset name for the sprite.
#   hp:          Hit points.
#   speed:       Movement speed in pixels per second.
#   gold_reward: Gold awarded when the enemy is killed.

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
# Wave definitions
# ======================================================================

# Each wave is a dict with:
#   enemy_def:      Index into ENEMY_DEFS.
#   count:          Number of enemies to spawn.
#   spawn_interval: Seconds between each spawn.
#   delay:          Seconds to wait before the first spawn of this wave.

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
# Map definition (identical to ch3 — kept inline for standalone running)
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
# Enemies walk to the centre of each tile, not the top-left corner.
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
# TitleScene (reused from ch3, updated subtitle)
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
            "Chapter 4 — Enemy Waves",
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
# GameScene — tile map + camera + HUD + tower placement + enemy waves
# ======================================================================

class GameScene(Scene):
    """Gameplay scene with tower placement and enemy waves.

    This chapter extends ch3's GameScene with enemy spawning and movement:

    *   Enemies spawn at the first waypoint and follow ``ENEMY_PATH``
        using ``sprite.move_to()`` with chained arrival callbacks.
    *   A ``StateMachine`` tracks each enemy's state: walking → dying → dead.
    *   Waves are scheduled via ``self.after()`` (scene-owned timers).
    *   Player has lives (shown in HUD); enemies reaching the end cost 1 life.

    Tower placement from ch3 still works — towers just don't shoot yet.
    """

    show_hud = True

    def on_enter(self) -> None:
        """Set up map, camera, HUD, build menu, enemies, and wave system."""

        # -----------------------------------------------------------------
        # Game state
        # -----------------------------------------------------------------
        self._gold = STARTING_GOLD
        self._lives = STARTING_LIVES
        self._current_wave = 0       # 0-based index into WAVE_DEFS
        self._wave_active = False     # True while enemies are being spawned
        self._wave_spawned = 0        # Enemies spawned so far this wave
        self._game_over = False

        # -----------------------------------------------------------------
        # Placement state machine (from ch3).
        # -----------------------------------------------------------------
        self._placing_tower_def: dict[str, Any] | None = None

        # -----------------------------------------------------------------
        # Placed towers: (col, row) → tower info dict.
        # -----------------------------------------------------------------
        self._placed_towers: dict[tuple[int, int], dict[str, Any]] = {}

        # -----------------------------------------------------------------
        # Slot sprites: (col, row) → Sprite for lookup when placing.
        # -----------------------------------------------------------------
        self._slot_sprites: dict[tuple[int, int], Sprite] = {}

        # -----------------------------------------------------------------
        # Enemy tracking.
        #
        # Each enemy is a dict with:
        #   "sprite":      The Sprite instance.
        #   "fsm":         StateMachine (walking / dying / dead).
        #   "hp":          Current HP.
        #   "max_hp":      Maximum HP.
        #   "speed":       Movement speed in px/sec.
        #   "path_index":  Current waypoint index in ENEMY_PATH_PX.
        #   "gold_reward": Gold awarded on kill.
        #   "def":         Reference to the ENEMY_DEFS entry.
        # -----------------------------------------------------------------
        self._enemies: list[dict[str, Any]] = []

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
    # Tile map creation (same as ch3)
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
    # Tower slot markers (same as ch3)
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
    # HUD (top bar) — now includes lives
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
    # Build menu (right side panel — same as ch3)
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
    # Buy button callbacks (same as ch3)
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
    # Placement logic (same as ch3)
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

        self._placed_towers[(col, row)] = {
            "def": tower_def,
            "sprite": tower_sprite,
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
    # HUD hint text helper
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
    # Enemy spawning and wave management
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

        # Schedule the first spawn.
        self._schedule_next_spawn()

    def _schedule_next_spawn(self) -> None:
        """Schedule the next enemy spawn for the current wave."""
        if self._current_wave >= len(WAVE_DEFS):
            return

        wave = WAVE_DEFS[self._current_wave]
        if self._wave_spawned >= wave["count"]:
            # All enemies for this wave have been spawned.  The wave
            # is still "active" until all enemies are dead or escaped.
            return

        interval = wave["spawn_interval"]
        self.after(interval, self._spawn_enemy)

    def _spawn_enemy(self) -> None:
        """Spawn one enemy for the current wave and schedule the next."""
        if self._current_wave >= len(WAVE_DEFS) or self._game_over:
            return

        wave = WAVE_DEFS[self._current_wave]
        edef = ENEMY_DEFS[wave["enemy_def"]]

        # Create the enemy sprite at the first waypoint.
        start_x, start_y = ENEMY_PATH_PX[0]
        sprite = self.add_sprite(
            Sprite(
                edef["image"],
                position=(start_x, start_y),
                anchor=SpriteAnchor.CENTER,
                layer=RenderLayer.OBJECTS,
            )
        )

        # Create the FSM for this enemy.
        fsm = StateMachine(
            states=["walking", "dying", "dead"],
            initial="walking",
            transitions={
                "walking": {"die": "dying"},
                "dying": {"finish": "dead"},
            },
        )

        # Build the enemy record.
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

        # Start walking to the next waypoint.
        self._walk_to_next(enemy)

        # Track how many have been spawned this wave.
        self._wave_spawned += 1

        # Schedule the next spawn (if more enemies remain in this wave).
        self._schedule_next_spawn()

    # ------------------------------------------------------------------
    # Enemy movement
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
            # Reached the end of the path — enemy escapes.
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

        # Immediately remove the enemy (no death animation for escapees).
        self._remove_enemy(enemy)

        if self._lives <= 0 and not self._game_over:
            self._game_over = True
            self._update_hint_text()
            print("Game Over!")

        # Check if wave is complete.
        self._check_wave_complete()

    def _kill_enemy(self, enemy: dict[str, Any]) -> None:
        """Kill an enemy (HP reached 0): award gold, play death sequence.

        In this chapter, enemies only die when their HP drops to 0.
        Since towers don't shoot yet, this is wired up for future use.
        """
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
    # Wave completion
    # ------------------------------------------------------------------

    def _check_wave_complete(self) -> None:
        """Check if all enemies from the current wave are gone.

        If so, advance to the next wave (or declare victory).
        """
        if not self._wave_active:
            return

        wave = WAVE_DEFS[self._current_wave]

        # Wave is complete when all enemies have been spawned AND
        # no enemies from this wave are still alive.
        if self._wave_spawned < wave["count"]:
            return  # Still spawning.

        # Check if any enemies are still alive (walking or dying).
        alive = [e for e in self._enemies if e["fsm"].state in ("walking", "dying")]
        if alive:
            return  # Still enemies on the map.

        # Wave complete!
        self._wave_active = False
        self._current_wave += 1

        if self._game_over:
            return

        if self._current_wave >= len(WAVE_DEFS):
            self._update_hint_text()
            print("All waves cleared! You win!")
            return

        # Schedule the next wave after a brief pause.
        self._hint_label.text = "Next wave incoming..."
        wave_delay = WAVE_DEFS[self._current_wave]["delay"]
        self.after(wave_delay, self._start_next_wave)

    # ------------------------------------------------------------------
    # Update — check for game-over (no per-frame enemy polling needed
    # since movement is handled by composable actions).
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Per-frame update.

        Enemy movement is driven by ``sprite.move_to()`` with chained
        callbacks — no manual position polling needed.  This method is
        reserved for future per-frame logic (tower targeting, health bar
        updates, etc.).
        """
        pass

    # ------------------------------------------------------------------
    # Input handling (extended from ch3)
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

    Same setup pattern as Chapters 1–3.
    """
    game = Game(
        "Tower Defense — Chapter 4",
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
