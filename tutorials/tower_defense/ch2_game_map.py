"""Chapter 2 — Game Map
=======================

Building on Chapter 1, this chapter adds the actual game screen with:

*   A **tile-based map** rendered from a 2D array using :class:`Sprite` objects.
*   A :class:`Camera` for the play area (world can be larger than the screen).
*   **Scene transitions** — the Play button pushes a :class:`GameScene`,
    Escape pops back to the title screen.
*   A simple **HUD** showing "Wave: 1" and "Gold: 100" labels.

You'll learn:

*   How to define a map as a 2D list of integers and render it with sprites.
*   How :class:`SpriteAnchor.TOP_LEFT` works for tile grids.
*   How :class:`Camera` scrolls the world and clamps to world bounds.
*   How :meth:`Game.push` / :meth:`Game.pop` manage the scene stack.
*   How the HUD layer persists across scenes.

Run from the project root::

    python tutorials/tower_defense/ch2_game_map.py

Controls:
    Title Screen — Enter or click Play → start game.
                   Escape or click Quit → exit.
    Game Screen  — Escape → return to title.
                   Arrow keys → scroll the camera.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — same pattern as Chapter 1.
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

# Tile size in pixels.  Our grass and path PNGs are 32×32.
TILE_SIZE = 32

# Camera scroll speed in pixels per second (for arrow-key scrolling).
CAMERA_SCROLL_SPEED = 200.0

# Colour palette
BG_COLOR = (25, 30, 40, 255)
TITLE_COLOR = (255, 220, 80, 255)
SUBTITLE_COLOR = (180, 180, 190, 255)
HUD_TEXT_COLOR = (220, 220, 230, 255)
GOLD_COLOR = (255, 210, 50, 255)


# ======================================================================
# Map definition
# ======================================================================

# Tile types — simple integer codes.
GRASS = 0
PATH = 1

# The map is a 2D list: map_data[row][col].
# 0 = grass, 1 = path.
#
# This serpentine path enters from the left edge (row 5) and winds its
# way across to the right edge (row 17).  Enemies will follow this path
# in later chapters.
#
# The map is 40 columns × 22 rows = 1280 × 704 pixels — larger than
# our 960×540 viewport, so the camera can scroll around the map.

MAP_DATA: list[list[int]] = [
    # 0  1  2  3  4  5  6  7  8  9  0  1  2  3  4  5  6  7  8  9  0  1  2  3  4  5  6  7  8  9  0  1  2  3  4  5  6  7  8  9
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # row 0
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # row 1
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # row 2
    [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # row 3
    [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # row 4
    [1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # row 5  ← entry
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # row 6
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # row 7
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0],  # row 8
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],  # row 9
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],  # row 10
    [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0],  # row 11
    [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # row 12
    [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # row 13
    [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0],  # row 14
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],  # row 15
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],  # row 16
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1],  # row 17  ← exit
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # row 18
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # row 19
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # row 20
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # row 21
]

# Derive map dimensions from the data.
MAP_ROWS = len(MAP_DATA)
MAP_COLS = len(MAP_DATA[0])
MAP_WIDTH_PX = MAP_COLS * TILE_SIZE   # 40 × 32 = 1280
MAP_HEIGHT_PX = MAP_ROWS * TILE_SIZE  # 22 × 32 = 704

# The enemy path as a sequence of (col, row) waypoints.
# Enemies follow this path from the entry point to the exit.
# (We define it explicitly because path-finding is game code, not framework.)
ENEMY_PATH: list[tuple[int, int]] = [
    # Enter from left edge (row 5)
    (0, 5), (1, 5), (2, 5), (3, 5), (4, 5), (5, 5), (6, 5),
    # Go up
    (6, 4), (6, 3),
    # Go right across top
    (7, 3), (8, 3), (9, 3), (10, 3), (11, 3), (12, 3), (13, 3),
    (14, 3), (15, 3), (16, 3), (17, 3), (18, 3),
    # Go down
    (18, 4), (18, 5), (18, 6), (18, 7), (18, 8),
    # Go right
    (19, 8), (20, 8), (21, 8), (22, 8), (23, 8), (24, 8), (25, 8),
    (26, 8), (27, 8), (28, 8), (29, 8), (30, 8), (31, 8), (32, 8),
    # Go down
    (32, 9), (32, 10), (32, 11),
    # Go left across middle
    (31, 11), (30, 11), (29, 11), (28, 11), (27, 11), (26, 11), (25, 11),
    (24, 11), (23, 11), (22, 11), (21, 11), (20, 11), (19, 11), (18, 11),
    (17, 11), (16, 11), (15, 11), (14, 11), (13, 11), (12, 11), (11, 11),
    (10, 11), (9, 11), (8, 11), (7, 11), (6, 11),
    # Go down
    (6, 12), (6, 13), (6, 14),
    # Go right across bottom
    (7, 14), (8, 14), (9, 14), (10, 14), (11, 14), (12, 14), (13, 14),
    (14, 14), (15, 14), (16, 14), (17, 14), (18, 14), (19, 14), (20, 14),
    (21, 14), (22, 14), (23, 14), (24, 14), (25, 14), (26, 14), (27, 14),
    (28, 14), (29, 14), (30, 14), (31, 14), (32, 14),
    # Go down
    (32, 15), (32, 16), (32, 17),
    # Exit right
    (33, 17), (34, 17), (35, 17), (36, 17), (37, 17), (38, 17), (39, 17),
]

# Tower build slots — positions (col, row) where the player can place towers.
# These are grass tiles adjacent to the path, chosen for strategic interest.
TOWER_SLOTS: list[tuple[int, int]] = [
    (4, 4),   # near entry path bend
    (8, 2),   # above first horizontal segment
    (14, 2),  # above first horizontal, right of center
    (17, 6),  # beside first vertical drop
    (22, 7),  # above second horizontal
    (28, 7),  # above second horizontal, right side
    (33, 10), # beside second vertical drop
    (10, 12), # below long leftward segment
    (20, 12), # below middle of leftward segment
    (8, 13),  # near third bend
    (20, 15), # below fourth horizontal
    (28, 15), # below fourth horizontal, right side
    (31, 16), # near exit bend
]


# ======================================================================
# TitleScene (reused from ch1, but Play now transitions to GameScene)
# ======================================================================

class TitleScene(Scene):
    """Title screen — same as Chapter 1, but Play pushes GameScene.

    Changes from ch1:
    *   ``_on_play_clicked`` calls ``self.game.push(GameScene())`` instead
        of just printing.
    *   We use ``push`` (not ``replace``) so ESC in GameScene pops back here.
    """

    background_color = BG_COLOR

    def on_enter(self) -> None:
        title_label = Label(
            "Tower Defense",
            font_size=48,
            text_color=TITLE_COLOR,
        )
        subtitle_label = Label(
            "Chapter 2 — Game Map",
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
        # -----------------------------------------------------------------
        # Scene transition: push GameScene on top of TitleScene.
        #
        # push() leaves the TitleScene on the stack underneath.  When the
        # player presses ESC in GameScene, we pop() back here — the title
        # screen is revealed without rebuilding it.
        #
        # Alternative approaches:
        #   game.replace(GameScene())    — swaps title for game (no going back)
        #   game.clear_and_push(scene)   — wipes the stack first
        # -----------------------------------------------------------------
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
# GameScene — tile map + camera + HUD
# ======================================================================

class GameScene(Scene):
    """The main gameplay scene — a tile-based map with camera scrolling.

    This scene demonstrates:

    1. **Tile rendering** — a 2D array of integers is converted into
       :class:`Sprite` objects placed at grid positions.
    2. **Camera** — the world can be larger than the screen.  The camera
       is clamped to world bounds so it can't scroll past the edges.
    3. **Scene stacking** — Escape pops back to the TitleScene.
    4. **HUD labels** — "Wave" and "Gold" displayed at fixed screen
       positions via the scene's UI tree.
    """

    # Tell the scene stack to hide the HUD when this scene is covered
    # by an overlay (not relevant yet, but good practice).
    show_hud = True

    def on_enter(self) -> None:
        """Set up camera, render the tile map, and build the HUD."""
        # Game state (placeholders for future chapters).
        self._wave = 1
        self._gold = 100

        # -----------------------------------------------------------------
        # 1. Camera setup
        #
        # The Camera defines a viewport into a larger world.  It's pure
        # math — it tells the renderer how to offset sprite positions.
        #
        # Parameters:
        #   viewport_size = (SCREEN_W, SCREEN_H) — matches our logical
        #                   resolution.
        #   world_bounds = (left, top, right, bottom) — clamps the camera
        #                  so it can't scroll past the map edges.
        #
        # Setting ``self.camera`` on the scene tells the Game to use this
        # camera during rendering.  The Game automatically offsets all
        # sprites by the camera position and hides sprites outside the
        # viewport (frustum culling).
        # -----------------------------------------------------------------
        self.camera = Camera(
            (SCREEN_W, SCREEN_H),
            world_bounds=(0, 0, MAP_WIDTH_PX, MAP_HEIGHT_PX),
        )
        self.camera.center_on(MAP_WIDTH_PX / 2, MAP_HEIGHT_PX / 2)
        self.camera.enable_key_scroll(speed=CAMERA_SCROLL_SPEED)

        # -----------------------------------------------------------------
        # 2. Render the tile map
        #
        # We iterate over the 2D map array and create one Sprite per tile.
        # Each sprite is positioned at (col * TILE_SIZE, row * TILE_SIZE)
        # with SpriteAnchor.TOP_LEFT so the sprite's top-left corner sits
        # exactly at the grid position.
        #
        # All tiles go on RenderLayer.BACKGROUND — they draw behind
        # everything else.
        # -----------------------------------------------------------------
        self._create_tile_map()

        # -----------------------------------------------------------------
        # 3. Render tower build slots
        #
        # Tower slots are displayed as semi-transparent green markers on
        # specific grass tiles.  They sit on RenderLayer.OBJECTS so they
        # draw above the terrain but below units.
        # -----------------------------------------------------------------
        self._create_tower_slots()

        # -----------------------------------------------------------------
        # 4. Build the HUD
        #
        # UI components added to ``self.ui`` are drawn in screen space —
        # they don't move with the camera.  This is perfect for HUD
        # elements like wave counters and gold displays.
        #
        # We use a horizontal panel anchored to the top of the screen.
        # -----------------------------------------------------------------
        self._build_hud()

    # ------------------------------------------------------------------
    # Tile map creation
    # ------------------------------------------------------------------

    def _create_tile_map(self) -> None:
        """Create one Sprite per tile from MAP_DATA.

        Tile types map to asset names:
            0 (GRASS) → ``"grass"``     (resolved to assets/images/grass.png)
            1 (PATH)  → ``"path_straight"``  (resolved to assets/images/path_straight.png)
        """
        # Map tile type integers to asset names.
        tile_images = {
            GRASS: "grass",
            PATH: "path_straight",
        }

        for row in range(MAP_ROWS):
            for col in range(MAP_COLS):
                tile_type = MAP_DATA[row][col]
                image_name = tile_images[tile_type]

                # World position: pixel coordinates of this tile's top-left.
                world_x = col * TILE_SIZE
                world_y = row * TILE_SIZE

                # Create the sprite.  Key parameters:
                #   anchor=TOP_LEFT — position is the tile's top-left corner.
                #   layer=BACKGROUND — tiles draw behind everything.
                sprite = Sprite(
                    image_name,
                    position=(world_x, world_y),
                    anchor=SpriteAnchor.TOP_LEFT,
                    layer=RenderLayer.BACKGROUND,
                )
                self.add_sprite(sprite)

    # ------------------------------------------------------------------
    # Tower slot markers
    # ------------------------------------------------------------------

    def _create_tower_slots(self) -> None:
        """Place tower_slot markers at each buildable position."""
        for col, row in TOWER_SLOTS:
            world_x = col * TILE_SIZE
            world_y = row * TILE_SIZE

            sprite = Sprite(
                "tower_slot",
                position=(world_x, world_y),
                anchor=SpriteAnchor.TOP_LEFT,
                layer=RenderLayer.OBJECTS,
            )
            self.add_sprite(sprite)

    # ------------------------------------------------------------------
    # HUD
    # ------------------------------------------------------------------

    def _build_hud(self) -> None:
        """Build a top-bar HUD with wave and gold labels.

        The HUD is built using the scene's UI tree (``self.ui``).
        UI components are always rendered in screen space — they don't
        scroll with the camera.
        """
        # Wave label — top left
        self._wave_label = Label(
            f"Wave: {self._wave}",
            font_size=20,
            text_color=HUD_TEXT_COLOR,
        )

        # Gold label — shows current gold with a gold tint
        self._gold_label = Label(
            f"Gold: {self._gold}",
            font_size=20,
            text_color=GOLD_COLOR,
        )

        # Hint label — reminds the player of controls
        hint_label = Label(
            "Arrow keys: scroll | ESC: menu",
            font_size=14,
            text_color=(140, 140, 150, 255),
        )

        # Top bar panel — horizontal layout, anchored to top of screen.
        hud_panel = Panel(
            layout=Layout.HORIZONTAL,
            spacing=40,
            anchor=Anchor.TOP,
            margin=8,
            style=Style(
                background_color=(20, 22, 35, 200),
                padding=10,
            ),
            children=[self._wave_label, self._gold_label, hint_label],
        )
        self.ui.add(hud_panel)

    def _update_hud_labels(self) -> None:
        """Refresh HUD label text from current game state."""
        self._wave_label.text = f"Wave: {self._wave}"
        self._gold_label.text = f"Gold: {self._gold}"

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def handle_input(self, event: InputEvent) -> bool:
        """Handle keyboard input for scene navigation.

        Arrow-key scrolling is handled by :meth:`Camera.enable_key_scroll` —
        we only need to handle Escape here.
        """
        if event.action == "cancel":
            self.game.pop()
            return True
        return False


# ======================================================================
# Main — entry point
# ======================================================================

def main() -> None:
    """Create the Game and run with the title screen.

    Same setup pattern as Chapter 1 — create Game with asset_path,
    customise Theme, then ``game.run(TitleScene())``.
    """
    game = Game(
        "Tower Defense — Chapter 2",
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
