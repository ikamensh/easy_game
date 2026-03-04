"""Chapter 3 — Tower Placement
================================

Building on Chapter 2, this chapter adds **interactive tower placement**:

*   A **build menu** panel on the right side showing tower types, costs,
    and Buy buttons.
*   **Click-to-place** — select a tower from the menu, then click a valid
    tower-slot tile to place it.
*   **Gold tracking** — placing a tower deducts gold; Buy buttons disable
    when you can't afford the tower.
*   **Range indicator** — while in placement mode, a translucent range
    circle follows the cursor and snaps to tower slots.
*   **Cancel placement** — right-click or Escape exits placement mode.

You'll learn:

*   How to manage game state (gold, placed towers) and sync it with the UI.
*   How to handle mouse ``"click"`` and ``"move"`` events using
    ``event.world_x`` and ``event.world_y`` (auto-populated by the framework).
*   How to enable/disable :class:`Button` widgets dynamically.
*   How to create and update indicator sprites (range circle).
*   How placement mode works as a simple state machine.

Run from the project root::

    python tutorials/tower_defense/ch3_tower_placement.py

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
# Path setup — same pattern as Chapters 1 & 2.
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
    Game,
    InputEvent,
    Label,
    Layout,
    Panel,
    RenderLayer,
    Scene,
    Sprite,
    SpriteAnchor,
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

# Starting gold — enough for a couple of towers to experiment with.
STARTING_GOLD = 200


# ======================================================================
# Tower definitions
# ======================================================================

# Each tower type is a dict with:
#   name:       Display name in the build menu.
#   image:      Asset name for the placed-tower sprite.
#   cost:       Gold cost to place.
#   range_px:   Attack range in pixels (shown by the range indicator).
#
# In later chapters these will also have damage, fire_rate, etc.

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
# Map definition (identical to ch2 — kept inline for standalone running)
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

# Enemy path (same as ch2 — included for completeness).
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
# TitleScene (reused from ch2, updated subtitle)
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
            "Chapter 3 — Tower Placement",
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
# GameScene — tile map + camera + HUD + tower placement
# ======================================================================

class GameScene(Scene):
    """Gameplay scene with tower placement.

    This chapter extends ch2's GameScene with a **placement state machine**:

    1. **Idle** — no tower selected.  The build menu is visible.
       Clicking a Buy button transitions to Placing.
    2. **Placing** — a tower type is selected.  A range indicator follows
       the cursor, snapping to nearby tower slots.  Left-click on a valid
       slot places the tower.  Right-click or Escape cancels.

    State is tracked by ``self._placing_tower_def``:
    *   ``None`` → idle mode
    *   A tower def dict → placing mode
    """

    show_hud = True

    def on_enter(self) -> None:
        """Set up map, camera, HUD, build menu, and placement state."""

        # -----------------------------------------------------------------
        # Game state
        # -----------------------------------------------------------------
        self._gold = STARTING_GOLD
        self._wave = 1

        # Placement state machine.
        # When None → idle (build menu browsing).
        # When set → the player is placing this tower type.
        self._placing_tower_def: dict[str, Any] | None = None

        # -----------------------------------------------------------------
        # Track placed towers: maps (col, row) → tower info dict.
        # This lets us check whether a slot is already occupied.
        # -----------------------------------------------------------------
        self._placed_towers: dict[tuple[int, int], dict[str, Any]] = {}

        # -----------------------------------------------------------------
        # Slot sprites: (col, row) → Sprite for lookup when placing.
        # All sprites use add_sprite() so the scene cleans them up on exit.
        # -----------------------------------------------------------------
        self._slot_sprites: dict[tuple[int, int], Sprite] = {}

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
        # 4. Build the HUD (top bar) and the build menu (right side)
        # -----------------------------------------------------------------
        self._build_hud()
        self._build_menu()

        # -----------------------------------------------------------------
        # 5. Pre-create the range indicator sprite (hidden until needed).
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

    # ------------------------------------------------------------------
    # Tile map creation (same as ch2)
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
    # Tower slot markers
    # ------------------------------------------------------------------

    def _create_tower_slots(self) -> None:
        """Place tower_slot markers at each buildable position.

        Stored in a dict keyed by (col, row) so we can remove a slot's
        sprite when a tower is placed there.
        """
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
    # HUD (top bar)
    # ------------------------------------------------------------------

    def _build_hud(self) -> None:
        """Build a top-bar HUD with wave and gold labels."""
        self._wave_label = Label(
            f"Wave: {self._wave}",
            font_size=20,
            text_color=HUD_TEXT_COLOR,
        )
        self._gold_label = Label(
            f"Gold: {self._gold}",
            font_size=20,
            text_color=GOLD_COLOR,
        )
        self._hint_label = Label(
            "Select a tower to build",
            font_size=14,
            text_color=(140, 140, 150, 255),
        )
        hud_panel = Panel(
            layout=Layout.HORIZONTAL,
            spacing=40,
            anchor=Anchor.TOP,
            margin=8,
            style=Style(
                background_color=(20, 22, 35, 200),
                padding=10,
            ),
            children=[self._wave_label, self._gold_label, self._hint_label],
        )
        self.ui.add(hud_panel)

    # ------------------------------------------------------------------
    # Build menu (right side panel)
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        """Build the tower build menu on the right side of the screen.

        The menu is a vertical panel with one row per tower type.
        Each row shows:  Name — Cost — [Buy] button.

        The Buy buttons are stored in ``self._buy_buttons`` so we can
        enable/disable them when the player's gold changes.

        Layout::

            _UIRoot (full screen)
              ├── hud_panel (TOP, horizontal)
              └── build_panel (RIGHT, vertical)
                    ├── title_label ("Build Tower")
                    ├── tower_row_0   (HORIZONTAL)
                    │     ├── info_label ("Basic  50g")
                    │     └── buy_button  ("Buy")
                    ├── tower_row_1   …
                    ├── tower_row_2   …
                    └── cancel_label  ("Right-click: cancel")
        """
        # Keep references to Buy buttons so we can enable/disable them.
        self._buy_buttons: list[Button] = []

        # Title at the top of the build menu.
        menu_title = Label(
            "Build Tower",
            font_size=22,
            text_color=TITLE_COLOR,
        )

        # One row per tower type.
        tower_rows: list[Panel] = []
        for i, tdef in enumerate(TOWER_DEFS):
            info_label = Label(
                f"{tdef['name']}  {tdef['cost']}g",
                font_size=16,
                text_color=HUD_TEXT_COLOR,
            )

            # -----------------------------------------------------------------
            # Button callbacks.
            #
            # We capture ``tdef`` by creating a default-argument closure.
            # Without ``td=tdef``, all buttons would share the same ``tdef``
            # variable (the last one in the loop) — a classic Python gotcha.
            # -----------------------------------------------------------------
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

        # Cancel hint at the bottom.
        cancel_label = Label(
            "Right-click: cancel",
            font_size=12,
            text_color=(120, 120, 130, 255),
        )

        # Assemble the build panel — vertical layout, anchored right.
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

        # Initial button enable/disable based on starting gold.
        self._refresh_buy_buttons()

    # ------------------------------------------------------------------
    # Buy button callbacks
    # ------------------------------------------------------------------

    def _on_buy_clicked(self, tower_def: dict[str, Any]) -> None:
        """Enter placement mode for the selected tower type.

        The player will click a tower slot on the map to place it.
        """
        # If already placing, switch to the new type.
        self._placing_tower_def = tower_def

        # Show the range indicator.
        if self._range_indicator is not None:
            self._range_indicator.visible = True

        # Update hint text.
        cost = tower_def["cost"]
        name = tower_def["name"]
        self._hint_label.text = f"Placing {name} ({cost}g) — click a slot"

    # ------------------------------------------------------------------
    # Placement logic
    # ------------------------------------------------------------------

    def _cancel_placement(self) -> None:
        """Exit placement mode and hide the range indicator."""
        self._placing_tower_def = None
        if self._range_indicator is not None:
            self._range_indicator.visible = False
            self._range_indicator.position = (-9999, -9999)
        self._hint_label.text = "Select a tower to build"

    def _try_place_tower(self, world_x: float, world_y: float) -> bool:
        """Attempt to place the currently selected tower at world coords.

        Returns True if placement succeeded, False otherwise.

        The algorithm:
        1. Convert world pixel coords to tile (col, row).
        2. Check if (col, row) is in TOWER_SLOTS.
        3. Check if the slot is not already occupied.
        4. Check if the player can afford it.
        5. Deduct gold, create the tower sprite, remove the slot marker.
        """
        if self._placing_tower_def is None:
            return False

        # Convert pixel position to tile coordinates.
        col = int(world_x) // TILE_SIZE
        row = int(world_y) // TILE_SIZE

        # -----------------------------------------------------------------
        # Validation: is this a valid, unoccupied tower slot?
        # -----------------------------------------------------------------
        if (col, row) not in self._slot_sprites:
            # Not a tower slot, or already occupied (slot sprite removed).
            return False

        if (col, row) in self._placed_towers:
            # Already has a tower here (shouldn't happen if slot removed,
            # but belt-and-suspenders).
            return False

        tower_def = self._placing_tower_def
        cost = tower_def["cost"]

        if self._gold < cost:
            # Can't afford — don't place.
            return False

        # -----------------------------------------------------------------
        # Place the tower!
        # -----------------------------------------------------------------

        # 1. Deduct gold.
        self._gold -= cost

        # 2. Remove the slot marker sprite.
        slot_sprite = self._slot_sprites.pop((col, row))
        slot_sprite.remove()

        # 3. Create the tower sprite at the slot's position.
        tower_sprite = Sprite(
            tower_def["image"],
            position=(col * TILE_SIZE, row * TILE_SIZE),
            anchor=SpriteAnchor.TOP_LEFT,
            layer=RenderLayer.OBJECTS,
        )
        self.add_sprite(tower_sprite)

        # 4. Record that this slot is now occupied.
        self._placed_towers[(col, row)] = {
            "def": tower_def,
            "sprite": tower_sprite,
        }

        # 5. Update HUD and button states.
        self._gold_label.text = f"Gold: {self._gold}"
        self._refresh_buy_buttons()

        # 6. Exit placement mode so the player can see the result.
        #    (They can buy another tower from the menu if they want.)
        self._cancel_placement()

        print(
            f"Placed {tower_def['name']} tower at ({col}, {row}) "
            f"— gold remaining: {self._gold}"
        )
        return True

    def _refresh_buy_buttons(self) -> None:
        """Enable/disable Buy buttons based on current gold.

        A button is enabled only if the player can afford that tower type.
        Disabled buttons ignore clicks automatically (the framework
        handles this — ``Component.enabled = False`` blocks all input).
        """
        for i, tdef in enumerate(TOWER_DEFS):
            can_afford = self._gold >= tdef["cost"]
            self._buy_buttons[i].enabled = can_afford

    def _snap_to_nearest_slot(
        self, world_x: float, world_y: float
    ) -> tuple[float, float] | None:
        """Find the nearest unoccupied tower slot within snap range.

        Returns the world-pixel center of the slot, or None if no slot
        is close enough.  Snap range = 1.5 tiles (48 pixels).
        """
        snap_range = TILE_SIZE * 1.5
        best_dist = snap_range
        best_pos: tuple[float, float] | None = None

        for col, row in self._slot_sprites:
            # Center of the slot tile in world pixels.
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
    # Input handling
    # ------------------------------------------------------------------

    def handle_input(self, event: InputEvent) -> bool:
        """Handle mouse clicks, mouse movement, and keyboard input.

        New in this chapter:
        *   ``"click"`` + ``button="left"`` — place a tower (if in
            placement mode) using ``event.world_x`` / ``event.world_y``.
        *   ``"click"`` + ``button="right"`` — cancel placement mode.
        *   ``"move"`` — update the range indicator position.
        """

        # -----------------------------------------------------------------
        # Escape — cancel placement first, then pop to title if idle.
        #
        # This two-level Escape behaviour is common in strategy games:
        # first press cancels the current action, second press opens menu.
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
        #
        # ``event.world_x`` and ``event.world_y`` are camera-transformed
        # coordinates, populated automatically by the framework.
        # -----------------------------------------------------------------
        if event.type == "click" and event.button == "left":
            if self._placing_tower_def is not None and event.world_x is not None and event.world_y is not None:
                self._try_place_tower(event.world_x, event.world_y)
                return True
            return False

        # -----------------------------------------------------------------
        # Mouse movement — update range indicator to follow cursor.
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

    Same setup pattern as Chapters 1 & 2.
    """
    game = Game(
        "Tower Defense — Chapter 3",
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
