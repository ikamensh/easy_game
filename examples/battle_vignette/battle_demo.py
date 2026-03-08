"""Playable tactical battle — turn-based combat on an 8x6 grid.

Run from the project root::

    python examples/battle_vignette/battle_demo.py

Controls:
    PLAYER_SELECT  — Left-click a warrior to select it.
    PLAYER_MOVE    — Left-click a blue cell to move, or the warrior's own
                     cell to stay.  Right-click / Escape to cancel selection.
    PLAYER_ATTACK  — Left-click a red-highlighted skeleton to attack, or
                     click elsewhere / press Escape to skip the attack.
    End Turn       — Click the "End Turn" button (or press E) to finish
                     the player phase and start the AI turn.
    Escape         — Cancel current selection / skip attack / quit on title.

The demo places 4 warriors (left) vs 4 skeletons (right) on a procedurally
generated terrain grid.  After all player warriors have acted (or the player
clicks End Turn), the AI moves and attacks with each skeleton sequentially.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from saga2d import (  # noqa: E402
    Anchor,
    AssetManager,
    Button,
    Camera,
    Do,
    Game,
    InputEvent,
    Label,
    Layout,
    MoveTo,
    Parallel,
    Panel,
    PlayAnim,
    RenderLayer,
    Scene,
    Sequence,
    Sprite,
    SpriteAnchor,
    StateMachine,
    Style,
    tween,
)

# Screen-shake parameters for attacks
SHAKE_INTENSITY = 6.0
SHAKE_DURATION = 0.15
SHAKE_DECAY = 2.0

from examples.battle_vignette.battle_ai import BattleAI  # noqa: E402
from examples.battle_vignette.battle_grid import (  # noqa: E402
    TILE_SIZE,
    SquareGrid,
)
from examples.battle_vignette.battle_unit import (  # noqa: E402
    MOVE_SPEED,
    BaseUnit,
    SkeletonUnit,
    WarriorUnit,
)

# ======================================================================
# Constants
# ======================================================================

SCREEN_W, SCREEN_H = 1920, 1080

# Warrior ATK (25) minus Skeleton DEF (5) = 20 damage per hit.
ATTACK_DAMAGE = 20

# Grid placement — centred on screen with some vertical padding
GRID_COLS, GRID_ROWS = 8, 6
GRID_ORIGIN_X = (SCREEN_W - GRID_COLS * TILE_SIZE) / 2
GRID_ORIGIN_Y = (SCREEN_H - GRID_ROWS * TILE_SIZE) / 2

# FSM states
S_PLAYER_SELECT = "player_select"
S_PLAYER_MOVE = "player_move"
S_PLAYER_ATTACK = "player_attack"
S_UNIT_ACTING = "unit_acting"
S_AI_TURN = "ai_turn"
S_GAME_OVER = "game_over"

# FSM events
E_SELECT = "select"
E_MOVE = "move"
E_ATTACK = "attack"
E_SKIP = "skip"
E_ACTION_START = "action_start"
E_ACTION_DONE = "action_done"
E_END_TURN = "end_turn"
E_AI_START = "ai_start"
E_AI_DONE = "ai_done"
E_WIN = "win"
E_LOSE = "lose"
E_CANCEL = "cancel"


# ======================================================================
# BattleScene
# ======================================================================

class BattleScene(Scene):
    """Playable tactical battle with FSM-driven turn flow."""

    background_color = (50, 60, 40, 255)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self) -> None:
        # Core state
        self.warriors: list[WarriorUnit] = []
        self.skeletons: list[SkeletonUnit] = []
        self.all_units: list[BaseUnit] = []
        self.selected_unit: BaseUnit | None = None
        self.acted_this_turn: set[int] = set()  # ids of warriors that acted

        # Highlight cells (recomputed on selection)
        self._move_cells: set[tuple[int, int]] = set()
        self._attack_cells: set[tuple[int, int]] = set()

        # Damage flash overlay (set by units on hit, fades via tween)
        self._flash_opacity: float = 0.0

        # AI
        self._ai = BattleAI()
        self._ai_queue: list[BaseUnit] = []
        self._turn_number = 1

        # Camera (for screen shake)
        self.camera = Camera(
            viewport_size=(SCREEN_W, SCREEN_H),
        )

        # Grid
        self.grid = SquareGrid(
            self,
            cols=GRID_COLS,
            rows=GRID_ROWS,
            origin_x=GRID_ORIGIN_X,
            origin_y=GRID_ORIGIN_Y,
            seed=7,
        )

        # Place obstacles before spawning units
        self._place_obstacles()

        self.grid.create_terrain_sprites()

        # Spawn units
        self._spawn_units()

        # Build UI
        self._build_ui()

        # FSM — created last so on_enter callbacks can reference UI
        self.fsm = self._build_fsm()

    def on_exit(self) -> None:
        # Deselect to clean up ring tweens
        self._deselect()

    # ------------------------------------------------------------------
    # Obstacle placement
    # ------------------------------------------------------------------

    def _place_obstacles(self) -> None:
        """Randomly place 3-5 obstacles on the grid.

        Obstacles are rocks that block movement and attacks. They are placed
        in the center columns (3-4) to create tactical chokepoints, avoiding
        unit spawn positions on the edges.
        """
        import random
        rng = random.Random(42)  # Fixed seed for reproducible layout

        # Reserved positions for units
        warrior_positions = {(1, 1), (1, 2), (1, 3), (1, 4)}
        skeleton_positions = {(6, 1), (6, 2), (6, 3), (6, 4)}
        reserved = warrior_positions | skeleton_positions

        # Candidate obstacle positions (center area, avoiding edges)
        candidates = []
        for col in range(2, 6):  # columns 2-5 (center area)
            for row in range(GRID_ROWS):
                if (col, row) not in reserved:
                    candidates.append((col, row))

        # Place 3-5 obstacles randomly
        num_obstacles = rng.randint(3, 5)
        obstacle_positions = rng.sample(candidates, num_obstacles)

        for col, row in obstacle_positions:
            self.grid.place_obstacle(col, row)

    # ------------------------------------------------------------------
    # Unit spawning
    # ------------------------------------------------------------------

    def _spawn_units(self) -> None:
        """Place 4 warriors on the left and 4 skeletons on the right."""
        warrior_positions = [(1, 1), (1, 2), (1, 3), (1, 4)]
        for col, row in warrior_positions:
            w = WarriorUnit.spawn(self, col=col, row=row, grid=self.grid, team="friendly")
            self.warriors.append(w)
            self.all_units.append(w)

        skeleton_positions = [(6, 1), (6, 2), (6, 3), (6, 4)]
        for col, row in skeleton_positions:
            s = SkeletonUnit.spawn(self, col=col, row=row, grid=self.grid, team="enemy")
            self.skeletons.append(s)
            self.all_units.append(s)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Turn indicator — top centre
        self._turn_label = Label(
            "Player Turn",
            font_size=32,
            font="Arial",
            text_color=(255, 255, 255, 255),
            anchor=Anchor.TOP,
            margin=16,
        )
        self.ui.add(self._turn_label)

        # Hint label — below turn indicator
        self._hint_label = Label(
            "Select a warrior",
            font_size=20,
            font="Arial",
            text_color=(200, 200, 200, 200),
            anchor=Anchor.TOP,
            margin=60,
        )
        self.ui.add(self._hint_label)

        # End Turn button — bottom right
        self._end_turn_btn = Button(
            "End Turn",
            on_click=self._on_end_turn_click,
            style=Style(
                font_size=24,
                background_color=(60, 80, 120, 220),
                text_color=(255, 255, 255, 255),
                hover_color=(80, 110, 160, 240),
                press_color=(40, 60, 90, 240),
                padding=16,
            ),
            anchor=Anchor.BOTTOM_RIGHT,
            margin=24,
        )
        self.ui.add(self._end_turn_btn)

        # Game-over overlay (initially hidden)
        self._game_over_title = Label(
            "",
            font_size=72,
            font="Arial",
            text_color=(255, 230, 60, 255),
        )
        self._game_over_sub = Label(
            "Press Enter to restart  |  Escape to quit",
            font_size=24,
            font="Arial",
            text_color=(200, 200, 200, 255),
        )
        self._game_over_panel = Panel(
            layout=Layout.VERTICAL,
            spacing=30,
            anchor=Anchor.CENTER,
            style=Style(
                background_color=(20, 20, 30, 220),
                padding=60,
            ),
            children=[self._game_over_title, self._game_over_sub],
            visible=False,
        )
        self.ui.add(self._game_over_panel)

    # ------------------------------------------------------------------
    # FSM
    # ------------------------------------------------------------------

    def _build_fsm(self) -> StateMachine:
        states = [
            S_PLAYER_SELECT, S_PLAYER_MOVE, S_PLAYER_ATTACK,
            S_UNIT_ACTING, S_AI_TURN, S_GAME_OVER,
        ]
        transitions = {
            S_PLAYER_SELECT: {
                E_SELECT: S_PLAYER_MOVE,
                E_END_TURN: S_AI_TURN,
                E_WIN: S_GAME_OVER,
                E_LOSE: S_GAME_OVER,
            },
            S_PLAYER_MOVE: {
                E_MOVE: S_PLAYER_ATTACK,
                E_CANCEL: S_PLAYER_SELECT,
                E_ACTION_START: S_UNIT_ACTING,
            },
            S_PLAYER_ATTACK: {
                E_ATTACK: S_UNIT_ACTING,
                E_SKIP: S_PLAYER_SELECT,
                E_CANCEL: S_PLAYER_SELECT,
            },
            S_UNIT_ACTING: {
                E_ACTION_DONE: S_PLAYER_SELECT,
                E_MOVE: S_PLAYER_ATTACK,  # move animation finished → attack phase
                E_WIN: S_GAME_OVER,
                E_LOSE: S_GAME_OVER,
                E_AI_DONE: S_PLAYER_SELECT,
            },
            S_AI_TURN: {
                E_AI_START: S_UNIT_ACTING,
                E_AI_DONE: S_PLAYER_SELECT,
                E_WIN: S_GAME_OVER,
                E_LOSE: S_GAME_OVER,
            },
            S_GAME_OVER: {},
        }
        return StateMachine(
            states=states,
            initial=S_PLAYER_SELECT,
            transitions=transitions,
            on_enter={
                S_PLAYER_SELECT: self._enter_player_select,
                S_PLAYER_MOVE: self._enter_player_move,
                S_PLAYER_ATTACK: self._enter_player_attack,
                S_AI_TURN: self._enter_ai_turn,
                S_GAME_OVER: self._enter_game_over,
            },
            on_exit={
                S_PLAYER_MOVE: self._exit_player_move,
                S_PLAYER_ATTACK: self._exit_player_attack,
            },
        )

    # ------------------------------------------------------------------
    # FSM on_enter / on_exit callbacks
    # ------------------------------------------------------------------

    def _enter_player_select(self) -> None:
        self._deselect()
        self._update_turn_label()
        self._hint_label.text = "Select a warrior"
        self._end_turn_btn.visible = True
        self._end_turn_btn.enabled = True

    def _enter_player_move(self) -> None:
        if self.selected_unit is None:
            return
        u = self.selected_unit
        self._move_cells = self.grid.movement_range(u.col, u.row, u.mov)
        self._hint_label.text = "Click a blue cell to move (right-click to cancel)"
        self._end_turn_btn.enabled = False

    def _exit_player_move(self) -> None:
        self._move_cells = set()

    def _enter_player_attack(self) -> None:
        if self.selected_unit is None:
            return
        u = self.selected_unit
        atk_cells = self.grid.attack_range(u.col, u.row, u.rng)
        # Only highlight cells occupied by living enemies
        self._attack_cells = {
            (c, r) for c, r in atk_cells
            if self.grid.unit_at(c, r) is not None
            and self.grid.unit_at(c, r).team == "enemy"
            and self.grid.unit_at(c, r).alive
        }
        if self._attack_cells:
            self._hint_label.text = "Click a red cell to attack (click elsewhere to skip)"
        else:
            self._hint_label.text = "No targets in range — click anywhere to skip"

    def _exit_player_attack(self) -> None:
        self._attack_cells = set()

    def _enter_ai_turn(self) -> None:
        self._deselect()
        self._hint_label.text = "Enemy turn..."
        self._end_turn_btn.enabled = False
        self._turn_label.text = "Enemy Turn"
        self.game.audio.play_sound("sounds/turn_change", optional=True)

        # Queue living skeletons
        self._ai_queue = [s for s in self.skeletons if s.alive]
        # Start processing after a short delay for visual clarity
        self.after(0.4, self._process_next_ai)

    def _enter_game_over(self) -> None:
        self._deselect()
        self._hint_label.visible = False
        self._end_turn_btn.visible = False

    # ------------------------------------------------------------------
    # Win / lose checks
    # ------------------------------------------------------------------

    def _check_game_over(self) -> bool:
        """Check for victory or defeat.  Returns True if game ended."""
        if not any(s.alive for s in self.skeletons):
            self._game_over_result = "victory"
            self.fsm.trigger(E_WIN)
            self._show_game_over("VICTORY!")
            return True
        if not any(w.alive for w in self.warriors):
            self._game_over_result = "defeat"
            self.fsm.trigger(E_LOSE)
            self._show_game_over("DEFEAT")
            return True
        return False

    def _show_game_over(self, text: str) -> None:
        self._game_over_title.text = text
        self._game_over_panel.visible = True
        self._turn_label.text = text

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _select(self, unit: BaseUnit) -> None:
        self._deselect()
        self.selected_unit = unit
        unit.select()
        self.game.audio.play_sound("sounds/select", optional=True)

    def _deselect(self) -> None:
        if self.selected_unit is not None:
            self.selected_unit.deselect()
        self.selected_unit = None
        self._move_cells = set()
        self._attack_cells = set()

    def _update_turn_label(self) -> None:
        acted = len(self.acted_this_turn)
        total = sum(1 for w in self.warriors if w.alive)
        self._turn_label.text = f"Player Turn {self._turn_number}  ({acted}/{total} acted)"

    # ------------------------------------------------------------------
    # Player click handling
    # ------------------------------------------------------------------

    def _on_end_turn_click(self) -> None:
        if self.fsm.state in (S_PLAYER_SELECT, S_PLAYER_MOVE, S_PLAYER_ATTACK):
            self._deselect()
            # Force transition to AI turn
            if self.fsm.state == S_PLAYER_MOVE:
                self.fsm.trigger(E_CANCEL)
            elif self.fsm.state == S_PLAYER_ATTACK:
                self.fsm.trigger(E_CANCEL)
            self.fsm.trigger(E_END_TURN)

    def _handle_player_select_click(self, col: int, row: int) -> None:
        """PLAYER_SELECT: click a friendly warrior to select it."""
        unit = self.grid.unit_at(col, row)
        if (
            unit is not None
            and unit.alive
            and unit.team == "friendly"
            and id(unit) not in self.acted_this_turn
        ):
            self._select(unit)
            self.fsm.trigger(E_SELECT)

    def _handle_player_move_click(self, col: int, row: int) -> None:
        """PLAYER_MOVE: click a blue cell to move (or current cell to stay)."""
        if (col, row) not in self._move_cells:
            return
        u = self.selected_unit
        if u is None:
            return

        if (col, row) == (u.col, u.row):
            # Stay in place — skip move, go straight to attack phase
            self.fsm.trigger(E_MOVE)
            return

        # Animate the walk, then snap grid position and transition
        self.game.audio.play_sound("sounds/move", optional=True)
        target_x, _ = self.grid.grid_to_world_center(col, row)
        target_y = self.grid.origin_y + (row + 1) * TILE_SIZE

        # Temporarily clear occupancy from old cell
        self.grid.remove_unit(u.col, u.row)

        def on_arrive() -> None:
            u.set_grid_pos(col, row)
            self.fsm.trigger(E_MOVE)

        self.fsm.trigger(E_ACTION_START)
        u.sprite.do(Sequence(
            Parallel(
                PlayAnim(u.anim_walk),
                MoveTo((target_x, target_y), speed=MOVE_SPEED),
            ),
            Do(lambda: u.sprite.play(u.anim_idle)),
            Do(on_arrive),
        ))

    def _handle_player_attack_click(self, col: int, row: int) -> None:
        """PLAYER_ATTACK: click a red cell to attack an enemy."""
        if (col, row) not in self._attack_cells:
            # Clicked outside attack range — skip attack
            self._finish_player_action()
            return

        u = self.selected_unit
        if u is None:
            return

        target = self.grid.unit_at(col, row)
        if target is None or not target.alive:
            self._finish_player_action()
            return

        def on_attack_done() -> None:
            self.acted_this_turn.add(id(u))
            if not self._check_game_over():
                self.fsm.trigger(E_ACTION_DONE)

        action = u.get_attack_action(target, on_complete=on_attack_done)
        self.fsm.trigger(E_ATTACK)
        u.sprite.do(action)

    def _finish_player_action(self) -> None:
        """Mark the current warrior as acted and return to select."""
        if self.selected_unit is not None:
            self.acted_this_turn.add(id(self.selected_unit))
        self.fsm.trigger(E_SKIP)

    # ------------------------------------------------------------------
    # AI turn processing
    # ------------------------------------------------------------------

    def _process_next_ai(self) -> None:
        """Process the next AI unit in the queue."""
        # Skip dead units
        while self._ai_queue and not self._ai_queue[0].alive:
            self._ai_queue.pop(0)

        if not self._ai_queue:
            self._finish_ai_turn()
            return

        ai_unit = self._ai_queue.pop(0)

        # Briefly highlight the acting AI unit
        ai_unit.select()
        self._hint_label.text = f"Skeleton at ({ai_unit.col},{ai_unit.row}) acting..."

        decision = self._ai.compute_turn(self.grid, ai_unit, self.warriors)
        kind = decision[0]

        if kind == "wait":
            ai_unit.deselect()
            self.after(0.2, self._process_next_ai)
            return

        if kind == "attack":
            target = decision[1]
            self._ai_execute_attack(ai_unit, target)

        elif kind == "move_attack":
            cell = decision[1]
            target = decision[2]
            self._ai_execute_move_then_attack(ai_unit, cell, target)

        elif kind == "move":
            cell = decision[1]
            self._ai_execute_move(ai_unit, cell)

    def _ai_execute_attack(self, ai_unit: BaseUnit, target: BaseUnit) -> None:
        """AI attacks a target from current position."""
        def on_done() -> None:
            ai_unit.deselect()
            if not self._check_game_over():
                self.after(0.3, self._process_next_ai)

        action = ai_unit.get_attack_action(target, on_complete=on_done)
        ai_unit.sprite.do(action)

    def _ai_execute_move_then_attack(
        self,
        ai_unit: BaseUnit,
        cell: tuple[int, int],
        target: BaseUnit,
    ) -> None:
        """AI moves to cell, then attacks target."""
        self.game.audio.play_sound("sounds/move", optional=True)
        col, row = cell
        target_x, _ = self.grid.grid_to_world_center(col, row)
        target_y = self.grid.origin_y + (row + 1) * TILE_SIZE

        self.grid.remove_unit(ai_unit.col, ai_unit.row)

        def on_arrive() -> None:
            ai_unit.set_grid_pos(col, row)
            # Now attack
            if target.alive:
                self._ai_execute_attack(ai_unit, target)
            else:
                if not self._check_game_over():
                    self.after(0.3, self._process_next_ai)

        ai_unit.sprite.do(Sequence(
            Parallel(
                PlayAnim(ai_unit.anim_walk),
                MoveTo((target_x, target_y), speed=MOVE_SPEED),
            ),
            Do(lambda: ai_unit.sprite.play(ai_unit.anim_idle)),
            Do(on_arrive),
        ))

    def _ai_execute_move(self, ai_unit: BaseUnit, cell: tuple[int, int]) -> None:
        """AI moves toward enemies (no attack possible)."""
        self.game.audio.play_sound("sounds/move", optional=True)
        col, row = cell
        target_x, _ = self.grid.grid_to_world_center(col, row)
        target_y = self.grid.origin_y + (row + 1) * TILE_SIZE

        self.grid.remove_unit(ai_unit.col, ai_unit.row)

        def on_arrive() -> None:
            ai_unit.set_grid_pos(col, row)
            ai_unit.deselect()
            self.after(0.3, self._process_next_ai)

        ai_unit.sprite.do(Sequence(
            Parallel(
                PlayAnim(ai_unit.anim_walk),
                MoveTo((target_x, target_y), speed=MOVE_SPEED),
            ),
            Do(lambda: ai_unit.sprite.play(ai_unit.anim_idle)),
            Do(on_arrive),
        ))

    def _finish_ai_turn(self) -> None:
        """All AI units have acted — start a new player turn."""
        self._turn_number += 1
        self.acted_this_turn.clear()
        if not self._check_game_over():
            self.game.audio.play_sound("sounds/turn_change", optional=True)
            self.fsm.trigger(E_AI_DONE)

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def handle_input(self, event: InputEvent) -> bool:
        state = self.fsm.state

        # Game over — Enter to restart, Escape to quit
        if state == S_GAME_OVER:
            if event.action == "confirm":
                self.game.replace(BattleScene())
                return True
            if event.action == "cancel":
                self.game.pop()
                return True
            return True  # consume all input

        # Escape — cancel selection / skip attack
        if event.action == "cancel":
            if state == S_PLAYER_MOVE:
                self.fsm.trigger(E_CANCEL)
                return True
            if state == S_PLAYER_ATTACK:
                self._finish_player_action()
                return True
            if state == S_PLAYER_SELECT:
                self.game.pop()
                return True
            return False

        # "E" key — end turn shortcut
        if event.type == "key_press" and event.key == "e":
            if state in (S_PLAYER_SELECT, S_PLAYER_MOVE, S_PLAYER_ATTACK):
                self._on_end_turn_click()
                return True

        # Right-click — cancel in move/attack
        if event.type == "click" and event.button == "right":
            if state == S_PLAYER_MOVE:
                self.fsm.trigger(E_CANCEL)
                return True
            if state == S_PLAYER_ATTACK:
                self._finish_player_action()
                return True
            return False

        # Left-click — state-dependent
        if event.type == "click" and event.button == "left":
            # Convert screen coords to grid
            wx = event.world_x if event.world_x is not None else float(event.x)
            wy = event.world_y if event.world_y is not None else float(event.y)
            col, row = self.grid.world_to_grid(wx, wy)

            if col < 0 or row < 0:
                # Clicked outside grid
                if state == S_PLAYER_ATTACK:
                    self._finish_player_action()
                    return True
                return False

            if state == S_PLAYER_SELECT:
                self._handle_player_select_click(col, row)
                return True
            elif state == S_PLAYER_MOVE:
                self._handle_player_move_click(col, row)
                return True
            elif state == S_PLAYER_ATTACK:
                self._handle_player_attack_click(col, row)
                return True

        return False

    # ------------------------------------------------------------------
    # Draw — highlights, health bars, floating damage numbers
    # ------------------------------------------------------------------

    def draw(self) -> None:
        state = self.fsm.state

        # Grid border (in world space so it shakes with the grid)
        border_pad = 4
        gx = GRID_ORIGIN_X - border_pad
        gy = GRID_ORIGIN_Y - border_pad
        gw = GRID_COLS * TILE_SIZE + border_pad * 2
        gh = GRID_ROWS * TILE_SIZE + border_pad * 2
        if self.camera is not None:
            self.draw_world_rect(gx, gy, gw, gh, (80, 100, 60, 120))
        else:
            self.draw_rect(gx, gy, gw, gh, (80, 100, 60, 120))

        # Grid highlights
        move_hl = self._move_cells if state == S_PLAYER_MOVE else None
        atk_hl = self._attack_cells if state == S_PLAYER_ATTACK else None
        self.grid.draw_highlights(self, move_hl, atk_hl)

        # Side panels — team info
        self._draw_side_panels()

        # Health bars and floating numbers for all units
        for unit in self.all_units:
            unit.draw_health_bar(self)
            unit.draw_floaters(self)

        # Damage flash overlay (in world space to match grid)
        if self._flash_opacity > 0:
            alpha = int(self._flash_opacity * 40)  # subtle red flash
            flash_color = (255, 60, 40, max(0, min(255, alpha)))
            if self.camera is not None:
                self.draw_world_rect(
                    GRID_ORIGIN_X, GRID_ORIGIN_Y,
                    GRID_COLS * TILE_SIZE, GRID_ROWS * TILE_SIZE,
                    flash_color,
                )
            else:
                self.draw_rect(
                    GRID_ORIGIN_X, GRID_ORIGIN_Y,
                    GRID_COLS * TILE_SIZE, GRID_ROWS * TILE_SIZE,
                    flash_color,
                )

        # Selected unit info bar
        self._draw_selected_unit_bar()

    def _draw_selected_unit_bar(self) -> None:
        """Draw a bottom info bar showing the selected unit's details."""
        u = self.selected_unit
        if u is None:
            return
        backend = self.game._backend
        cx = "center"

        bar_h = 50
        bar_y = SCREEN_H - bar_h
        self.draw_rect(0, bar_y, SCREEN_W, bar_h, (20, 25, 35, 220))

        # Unit type
        unit_type = "Warrior" if u.team == "friendly" else "Skeleton"
        name_color = (100, 180, 255, 255) if u.team == "friendly" else (255, 120, 100, 255)
        backend.draw_text(
            unit_type, 30, bar_y + 14, 22,
            name_color, font="Arial",
        )

        # HP bar
        hp_label_x = 200
        max_hp = 120 if u.team == "friendly" else 80
        backend.draw_text(
            f"HP: {u.hp}/{max_hp}", hp_label_x, bar_y + 16, 16,
            (200, 200, 200, 255), font="Arial",
        )
        bar_x = hp_label_x + 110
        bar_w = 160
        frac = u.hp / max_hp
        self.draw_rect(bar_x, bar_y + 16, bar_w, 12, (40, 40, 40, 200))
        fill = max(1, int(bar_w * frac))
        bar_color = (60, 200, 60, 255) if frac > 0.5 else (
            (220, 180, 40, 255) if frac > 0.25 else (220, 60, 60, 255)
        )
        self.draw_rect(bar_x, bar_y + 16, fill, 12, bar_color)

        # Stats
        backend.draw_text(
            f"ATK {u.atk}  |  DEF {u.def_}  |  MOV {u.mov}  |  RNG {u.rng}",
            550, bar_y + 16, 16,
            (180, 180, 190, 220), font="Arial",
        )

        # Grid position
        backend.draw_text(
            f"Position: ({u.col}, {u.row})",
            900, bar_y + 16, 14,
            (140, 140, 150, 200), font="Arial",
        )

    def _draw_side_panels(self) -> None:
        """Draw team info panels flanking the grid."""
        backend = self.game._backend
        panel_w = int(GRID_ORIGIN_X - 40)
        if panel_w < 100:
            return  # not enough space

        cx = "center"  # anchor shorthand

        # --- Left panel (Warriors) ---
        lx = 20
        ly = int(GRID_ORIGIN_Y)
        self.draw_rect(lx, ly, panel_w, 260, (30, 40, 60, 180))

        backend.draw_text(
            "WARRIORS", lx + panel_w // 2, ly + 16, 24,
            (100, 180, 255, 255), font="Arial", anchor_x=cx,
        )
        alive_w = sum(1 for w in self.warriors if w.alive)
        backend.draw_text(
            f"{alive_w} / {len(self.warriors)} alive",
            lx + panel_w // 2, ly + 50, 16,
            (180, 200, 220, 200), font="Arial", anchor_x=cx,
        )

        # Unit status pips
        w_max_hp = self.warriors[0]._default_hp() if self.warriors else 120
        pip_w = min(80, (panel_w - 40) // max(1, len(self.warriors)))
        for i, w in enumerate(self.warriors):
            pip_x = lx + 20 + i * pip_w
            pip_y = ly + 80
            bar_pixel_w = pip_w - 8
            if w.alive:
                frac = w.hp / w_max_hp
                self.draw_rect(pip_x, pip_y, bar_pixel_w, 8, (40, 40, 40, 200))
                fill_w = max(1, int(bar_pixel_w * frac))
                color = (60, 200, 60, 255) if frac > 0.5 else (
                    (220, 180, 40, 255) if frac > 0.25 else (220, 60, 60, 255)
                )
                self.draw_rect(pip_x, pip_y, fill_w, 8, color)
                backend.draw_text(
                    f"{w.hp}", pip_x + bar_pixel_w // 2, pip_y + 16, 12,
                    (200, 200, 200, 200), font="Arial", anchor_x=cx,
                )
            else:
                self.draw_rect(pip_x, pip_y, bar_pixel_w, 8, (80, 30, 30, 180))
                backend.draw_text(
                    "KO", pip_x + bar_pixel_w // 2, pip_y + 16, 12,
                    (160, 60, 60, 200), font="Arial", anchor_x=cx,
                )

        # Stats summary (from first living warrior)
        w_ref = next((w for w in self.warriors if w.alive), None)
        if w_ref:
            backend.draw_text(
                f"ATK {w_ref.atk}  DEF {w_ref.def_}  MOV {w_ref.mov}",
                lx + panel_w // 2, ly + 130, 13,
                (160, 170, 180, 180), font="Arial", anchor_x=cx,
            )
            rng_text = "Melee" if w_ref.rng <= 1 else f"{w_ref.rng} cells"
            backend.draw_text(
                f"Range: {rng_text}", lx + panel_w // 2, ly + 152, 13,
                (160, 170, 180, 180), font="Arial", anchor_x=cx,
            )

        # Turn info
        backend.draw_text(
            f"Turn {self._turn_number}", lx + panel_w // 2, ly + 190, 18,
            (255, 220, 80, 230), font="Arial", anchor_x=cx,
        )
        acted = len(self.acted_this_turn)
        backend.draw_text(
            f"{acted}/{alive_w} acted", lx + panel_w // 2, ly + 218, 14,
            (180, 180, 180, 200), font="Arial", anchor_x=cx,
        )

        # --- Right panel (Skeletons) ---
        rx = int(GRID_ORIGIN_X + GRID_COLS * TILE_SIZE + 20)
        ry = int(GRID_ORIGIN_Y)
        self.draw_rect(rx, ry, panel_w, 260, (50, 30, 30, 180))

        backend.draw_text(
            "SKELETONS", rx + panel_w // 2, ry + 16, 24,
            (255, 120, 100, 255), font="Arial", anchor_x=cx,
        )
        alive_s = sum(1 for s in self.skeletons if s.alive)
        backend.draw_text(
            f"{alive_s} / {len(self.skeletons)} alive",
            rx + panel_w // 2, ry + 50, 16,
            (220, 180, 180, 200), font="Arial", anchor_x=cx,
        )

        # Unit status pips
        s_max_hp = self.skeletons[0]._default_hp() if self.skeletons else 80
        pip_w_s = min(80, (panel_w - 40) // max(1, len(self.skeletons)))
        for i, s in enumerate(self.skeletons):
            pip_x = rx + 20 + i * pip_w_s
            pip_y = ry + 80
            bar_pixel_w = pip_w_s - 8
            if s.alive:
                frac = s.hp / s_max_hp
                self.draw_rect(pip_x, pip_y, bar_pixel_w, 8, (40, 40, 40, 200))
                fill_w = max(1, int(bar_pixel_w * frac))
                color = (60, 200, 60, 255) if frac > 0.5 else (
                    (220, 180, 40, 255) if frac > 0.25 else (220, 60, 60, 255)
                )
                self.draw_rect(pip_x, pip_y, fill_w, 8, color)
                backend.draw_text(
                    f"{s.hp}", pip_x + bar_pixel_w // 2, pip_y + 16, 12,
                    (200, 200, 200, 200), font="Arial", anchor_x=cx,
                )
            else:
                self.draw_rect(pip_x, pip_y, bar_pixel_w, 8, (80, 30, 30, 180))
                backend.draw_text(
                    "KO", pip_x + bar_pixel_w // 2, pip_y + 16, 12,
                    (160, 60, 60, 200), font="Arial", anchor_x=cx,
                )

        # Stats summary (from first living skeleton)
        s_ref = next((s for s in self.skeletons if s.alive), None)
        if s_ref:
            backend.draw_text(
                f"ATK {s_ref.atk}  DEF {s_ref.def_}  MOV {s_ref.mov}",
                rx + panel_w // 2, ry + 130, 13,
                (180, 160, 160, 180), font="Arial", anchor_x=cx,
            )
            rng_text = "Melee" if s_ref.rng <= 1 else f"{s_ref.rng} cells"
            backend.draw_text(
                f"Range: {rng_text}", rx + panel_w // 2, ry + 152, 13,
                (180, 160, 160, 180), font="Arial", anchor_x=cx,
            )


# ======================================================================
# TitleScene
# ======================================================================

class TitleScene(Scene):
    """Title screen with decorative sprites and game info."""

    background_color = (15, 18, 30, 255)

    def on_enter(self) -> None:
        # Decorative warrior sprites (left side)
        for i, row_y in enumerate([340, 480, 620]):
            s = Sprite(
                "sprites/warrior_idle_01",
                position=(SCREEN_W // 2 - 340 - i * 20, row_y),
                layer=RenderLayer.UNITS,
                anchor=SpriteAnchor.BOTTOM_CENTER,
            )
            self.add_sprite(s)

        # Decorative skeleton sprites (right side)
        for i, row_y in enumerate([340, 480, 620]):
            s = Sprite(
                "sprites/skeleton_idle_01",
                position=(SCREEN_W // 2 + 340 + i * 20, row_y),
                layer=RenderLayer.UNITS,
                anchor=SpriteAnchor.BOTTOM_CENTER,
            )
            self.add_sprite(s)

        # Title
        self.ui.add(Label(
            "TACTICAL BATTLE",
            font_size=72,
            font="Arial",
            text_color=(255, 220, 80, 255),
            anchor=Anchor.TOP,
            margin=180,
        ))

        # Subtitle
        self.ui.add(Label(
            "Warriors vs Skeletons",
            font_size=32,
            font="Arial",
            text_color=(180, 170, 140, 255),
            anchor=Anchor.TOP,
            margin=270,
        ))

        # Controls info panel
        self.ui.add(Panel(
            layout=Layout.VERTICAL,
            spacing=8,
            anchor=Anchor.CENTER,
            margin=60,
            style=Style(
                background_color=(25, 25, 40, 180),
                padding=30,
            ),
            children=[
                Label(
                    "Click to select, move, and attack",
                    font_size=20, font="Arial",
                    text_color=(180, 180, 180, 255),
                ),
                Label(
                    "Right-click or ESC to cancel  |  E to end turn",
                    font_size=18, font="Arial",
                    text_color=(150, 150, 160, 220),
                ),
            ],
        ))

        # Start prompt
        self.ui.add(Label(
            "Press ENTER to start",
            font_size=28,
            font="Arial",
            text_color=(200, 200, 200, 255),
            anchor=Anchor.TOP,
            margin=640,
        ))
        self.ui.add(Label(
            "ESC to quit",
            font_size=20,
            font="Arial",
            text_color=(120, 120, 130, 200),
            anchor=Anchor.TOP,
            margin=680,
        ))

    def handle_input(self, event: InputEvent) -> bool:
        if event.action == "confirm":
            self.game.push(BattleScene())
            return True
        if event.action == "cancel":
            self.game.quit()
            return True
        return False


# ======================================================================
# Main
# ======================================================================

def main() -> None:
    asset_path = Path(__file__).resolve().parent / "assets"

    game = Game(
        "Tactical Battle",
        resolution=(SCREEN_W, SCREEN_H),
        fullscreen=False,
        backend="pyglet",
    )
    game.assets = AssetManager(
        game.backend,
        base_path=asset_path,
    )

    game.run(TitleScene())


if __name__ == "__main__":
    main()
