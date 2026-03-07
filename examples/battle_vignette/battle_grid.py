"""Square grid for tactical battle scenes.

Provides a reusable :class:`SquareGrid` that manages an 8x6 (default) tile
map with procedurally generated terrain, occupancy tracking, BFS-based
movement range, Chebyshev attack range, and rendering helpers.

Terrain tiles are created as Saga2D :class:`Sprite` objects on the
``BACKGROUND`` render layer.  Highlights (movement / attack overlays) are
drawn as semi-transparent rectangles via :meth:`Scene.draw_rect`.

Usage::

    grid = SquareGrid(scene, origin_x=128, origin_y=128)
    grid.create_terrain_sprites()

    # Query helpers
    neighbors = grid.neighbors(3, 2)
    move_cells = grid.movement_range(3, 2, steps=3)
    atk_cells  = grid.attack_range(3, 2, reach=2)

    # World ↔ grid conversion
    col, row = grid.world_to_grid(px, py)
    wx, wy   = grid.grid_to_world(col, row)

    # In Scene.draw():
    grid.draw_highlights(scene, move_cells, atk_cells)
"""

from __future__ import annotations

import random
from collections import deque
from typing import TYPE_CHECKING, Any

from saga2d import RenderLayer, Sprite, SpriteAnchor

if TYPE_CHECKING:
    from saga2d import Scene

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TILE_SIZE: int = 128
"""Side length of one grid cell in pixels."""

COLS: int = 8
"""Default number of columns."""

ROWS: int = 6
"""Default number of rows."""

# Terrain type probabilities (must sum to 1.0)
_TERRAIN_WEIGHTS: list[tuple[str, float]] = [
    ("grass", 0.80),
    ("stone", 0.10),
    ("dirt", 0.10),
]

# Tile asset keys (relative to the asset base path, no extension)
_TERRAIN_ASSETS: dict[str, str] = {
    "grass": "tiles/tile_grass",
    "stone": "tiles/tile_stone",
    "dirt": "tiles/tile_dirt",
}

# Highlight colours  (R, G, B, A)
HIGHLIGHT_MOVE: tuple[int, int, int, int] = (0, 180, 255, 80)
"""Semi-transparent blue overlay for reachable movement cells."""

HIGHLIGHT_ATTACK: tuple[int, int, int, int] = (255, 60, 60, 80)
"""Semi-transparent red overlay for cells in attack range."""


# ---------------------------------------------------------------------------
# SquareGrid
# ---------------------------------------------------------------------------

class SquareGrid:
    """An 8x6 (by default) square-tile grid for tactical battles.

    Parameters:
        scene:     The owning :class:`Scene` (used for ``add_sprite``).
        cols:      Number of columns (default 8).
        rows:      Number of rows (default 6).
        origin_x:  World-pixel x of the top-left corner of cell (0, 0).
        origin_y:  World-pixel y of the top-left corner of cell (0, 0).
        seed:      Optional RNG seed for reproducible terrain generation.
    """

    def __init__(
        self,
        scene: Scene,
        cols: int = COLS,
        rows: int = ROWS,
        origin_x: float = 0.0,
        origin_y: float = 0.0,
        seed: int | None = None,
    ) -> None:
        self.scene = scene
        self.cols = cols
        self.rows = rows
        self.origin_x = origin_x
        self.origin_y = origin_y

        # terrain[row][col] → terrain type string ("grass" / "stone" / "dirt")
        self.terrain: list[list[str]] = self._generate_terrain(seed)

        # occupancy[row][col] → unit reference or None
        self.occupancy: list[list[Any | None]] = [
            [None] * cols for _ in range(rows)
        ]

        # obstacles: set of (col, row) tuples for impassable cells
        self.obstacles: set[tuple[int, int]] = set()

        # Sprite handles for cleanup (filled by create_terrain_sprites)
        self._tile_sprites: list[Sprite] = []
        self._obstacle_sprites: list[Sprite] = []

    # ------------------------------------------------------------------
    # Terrain generation
    # ------------------------------------------------------------------

    def _generate_terrain(self, seed: int | None) -> list[list[str]]:
        """Procedurally assign terrain types using weighted random choice."""
        rng = random.Random(seed)
        types = [t for t, _ in _TERRAIN_WEIGHTS]
        weights = [w for _, w in _TERRAIN_WEIGHTS]

        return [
            rng.choices(types, weights=weights, k=self.cols)
            for _ in range(self.rows)
        ]

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------

    def grid_to_world(self, col: int, row: int) -> tuple[float, float]:
        """Return the world-pixel (x, y) of the **top-left** corner of a cell."""
        return (
            self.origin_x + col * TILE_SIZE,
            self.origin_y + row * TILE_SIZE,
        )

    def grid_to_world_center(self, col: int, row: int) -> tuple[float, float]:
        """Return the world-pixel (x, y) of the **center** of a cell."""
        return (
            self.origin_x + col * TILE_SIZE + TILE_SIZE / 2,
            self.origin_y + row * TILE_SIZE + TILE_SIZE / 2,
        )

    def world_to_grid(self, wx: float, wy: float) -> tuple[int, int]:
        """Convert a world-pixel position to a ``(col, row)`` cell index.

        Returns ``(-1, -1)`` if the point lies outside the grid.
        """
        col = int((wx - self.origin_x) // TILE_SIZE)
        row = int((wy - self.origin_y) // TILE_SIZE)
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return col, row
        return -1, -1

    # ------------------------------------------------------------------
    # Bounds checking
    # ------------------------------------------------------------------

    def in_bounds(self, col: int, row: int) -> bool:
        """Return ``True`` if ``(col, row)`` is inside the grid."""
        return 0 <= col < self.cols and 0 <= row < self.rows

    # ------------------------------------------------------------------
    # Neighbors (4-directional)
    # ------------------------------------------------------------------

    def neighbors(self, col: int, row: int) -> list[tuple[int, int]]:
        """Return in-bounds orthogonal neighbors of ``(col, row)``."""
        result: list[tuple[int, int]] = []
        for dc, dr in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nc, nr = col + dc, row + dr
            if self.in_bounds(nc, nr):
                result.append((nc, nr))
        return result

    # ------------------------------------------------------------------
    # Movement range (BFS)
    # ------------------------------------------------------------------

    def movement_range(
        self,
        col: int,
        row: int,
        steps: int,
        *,
        include_occupied: bool = False,
    ) -> set[tuple[int, int]]:
        """Return all cells reachable within *steps* orthogonal moves.

        Uses breadth-first search from ``(col, row)``.  Occupied cells block
        movement unless *include_occupied* is ``True``.  Obstacle cells always
        block movement.  The origin cell is always included.
        """
        visited: set[tuple[int, int]] = set()
        queue: deque[tuple[int, int, int]] = deque()
        queue.append((col, row, 0))
        visited.add((col, row))

        while queue:
            c, r, dist = queue.popleft()
            if dist >= steps:
                continue
            for nc, nr in self.neighbors(c, r):
                if (nc, nr) in visited:
                    continue
                # Obstacles always block movement
                if (nc, nr) in self.obstacles:
                    continue
                if not include_occupied and self.occupancy[nr][nc] is not None:
                    continue
                visited.add((nc, nr))
                queue.append((nc, nr, dist + 1))

        return visited

    # ------------------------------------------------------------------
    # Attack range (Chebyshev / king-move distance)
    # ------------------------------------------------------------------

    def attack_range(
        self,
        col: int,
        row: int,
        reach: int,
    ) -> set[tuple[int, int]]:
        """Return all cells within Chebyshev distance *reach* of ``(col, row)``.

        Chebyshev distance allows diagonal adjacency (like a king in chess).
        The origin cell is **excluded** from the result.
        """
        cells: set[tuple[int, int]] = set()
        for dc in range(-reach, reach + 1):
            for dr in range(-reach, reach + 1):
                if dc == 0 and dr == 0:
                    continue
                nc, nr = col + dc, row + dr
                if self.in_bounds(nc, nr):
                    cells.add((nc, nr))
        return cells

    # ------------------------------------------------------------------
    # Occupancy helpers
    # ------------------------------------------------------------------

    def place_unit(self, col: int, row: int, unit: Any) -> None:
        """Place *unit* in cell ``(col, row)``."""
        self.occupancy[row][col] = unit

    def remove_unit(self, col: int, row: int) -> None:
        """Clear the occupant from cell ``(col, row)``."""
        self.occupancy[row][col] = None

    def unit_at(self, col: int, row: int) -> Any | None:
        """Return the unit occupying ``(col, row)``, or ``None``."""
        if not self.in_bounds(col, row):
            return None
        return self.occupancy[row][col]

    # ------------------------------------------------------------------
    # Obstacle helpers
    # ------------------------------------------------------------------

    def place_obstacle(self, col: int, row: int) -> None:
        """Mark cell ``(col, row)`` as containing an obstacle."""
        self.obstacles.add((col, row))

    def remove_obstacle(self, col: int, row: int) -> None:
        """Remove the obstacle from cell ``(col, row)``."""
        self.obstacles.discard((col, row))

    def is_blocked(self, col: int, row: int) -> bool:
        """Return ``True`` if ``(col, row)`` is blocked by an obstacle or unit."""
        if not self.in_bounds(col, row):
            return True
        if (col, row) in self.obstacles:
            return True
        if self.occupancy[row][col] is not None:
            return True
        return False

    # ------------------------------------------------------------------
    # Rendering — terrain sprites
    # ------------------------------------------------------------------

    def create_terrain_sprites(self) -> None:
        """Create a :class:`Sprite` for every tile on the ``BACKGROUND`` layer.

        Call once during :meth:`Scene.on_enter`.  Sprites are registered
        with the scene via :meth:`Scene.add_sprite` for automatic cleanup.
        Also creates obstacle sprites for cells in ``self.obstacles``.
        """
        for row in range(self.rows):
            for col in range(self.cols):
                terrain_type = self.terrain[row][col]
                asset_key = _TERRAIN_ASSETS[terrain_type]
                wx, wy = self.grid_to_world(col, row)
                sprite = Sprite(
                    asset_key,
                    position=(wx, wy),
                    layer=RenderLayer.BACKGROUND,
                    anchor=SpriteAnchor.TOP_LEFT,
                )
                self.scene.add_sprite(sprite)
                self._tile_sprites.append(sprite)

        # Create obstacle sprites on top of terrain
        for col, row in self.obstacles:
            wx, wy = self.grid_to_world(col, row)
            obs_sprite = Sprite(
                "tiles/tile_obstacle",
                position=(wx, wy),
                layer=RenderLayer.BACKGROUND,
                anchor=SpriteAnchor.TOP_LEFT,
            )
            self.scene.add_sprite(obs_sprite)
            self._obstacle_sprites.append(obs_sprite)

    # ------------------------------------------------------------------
    # Rendering — highlights (call from Scene.draw)
    # ------------------------------------------------------------------

    def draw_highlights(
        self,
        scene: Scene,
        move_cells: set[tuple[int, int]] | None = None,
        attack_cells: set[tuple[int, int]] | None = None,
    ) -> None:
        """Draw semi-transparent overlays for movement and attack ranges.

        Call from :meth:`Scene.draw`.  Movement highlights are drawn first
        (blue), then attack highlights (red) on top so overlaps favour
        the attack colour.

        Uses :meth:`Scene.draw_rect` (screen-space) for scenes without a
        camera, and :meth:`Scene.draw_world_rect` for camera-aware scenes.
        """
        draw_fn = scene.draw_world_rect if scene.camera is not None else scene.draw_rect

        if move_cells:
            for col, row in move_cells:
                wx, wy = self.grid_to_world(col, row)
                draw_fn(wx, wy, TILE_SIZE, TILE_SIZE, HIGHLIGHT_MOVE)

        if attack_cells:
            for col, row in attack_cells:
                wx, wy = self.grid_to_world(col, row)
                draw_fn(wx, wy, TILE_SIZE, TILE_SIZE, HIGHLIGHT_ATTACK)

    # ------------------------------------------------------------------
    # Grid dimensions in pixels
    # ------------------------------------------------------------------

    @property
    def pixel_width(self) -> float:
        """Total width of the grid in world pixels."""
        return self.cols * TILE_SIZE

    @property
    def pixel_height(self) -> float:
        """Total height of the grid in world pixels."""
        return self.rows * TILE_SIZE
