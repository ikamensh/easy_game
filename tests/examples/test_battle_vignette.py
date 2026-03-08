"""Headless tests for the battle vignette demo.

Uses ``Game(backend="mock")`` to validate the demo's choreography
without a display.  The asset_root points to the real demo sprites so
``AssetManager`` can discover numbered animation frames.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from saga2d import Game
from saga2d.assets import AssetManager
from saga2d.backends.mock_backend import MockBackend

# Import the demo's scene and constants directly.
from examples.battle_vignette.battle_demo import (
    ATTACK_DAMAGE,
    BattleScene,
    S_PLAYER_SELECT,
    S_PLAYER_MOVE,
    S_PLAYER_ATTACK,
    S_UNIT_ACTING,
    S_AI_TURN,
    S_GAME_OVER,
)


# ======================================================================
# Fixtures
# ======================================================================

ASSET_DIR = Path(__file__).resolve().parents[2] / "examples" / "battle_vignette" / "assets"


@pytest.fixture
def game() -> Game:
    """Game with mock backend and asset_root pointing at demo assets."""
    g = Game("Battle Test", backend="mock", resolution=(1920, 1080))
    g.assets = AssetManager(g.backend, base_path=ASSET_DIR)
    return g


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


@pytest.fixture
def scene(game: Game) -> BattleScene:
    """Push a BattleScene and return it (on_enter has already fired)."""
    s = BattleScene()
    game.push(s)
    game.tick(dt=0.0)
    return s


# ======================================================================
# Helpers
# ======================================================================

def _tick_many(game: Game, n: int, dt: float = 1 / 60) -> None:
    """Tick the game *n* times at *dt* seconds each."""
    for _ in range(n):
        game.tick(dt=dt)


def _click_grid_cell(backend: MockBackend, game: Game, scene: BattleScene,
                     col: int, row: int) -> None:
    """Inject a left-click at the center of grid cell (col, row)."""
    wx, wy = scene.grid.grid_to_world_center(col, row)
    backend.inject_click(int(wx), int(wy))
    game.tick(dt=0.0)


def _click_unit(backend: MockBackend, game: Game, scene: BattleScene, unit) -> None:
    """Inject a left-click at a unit's grid cell center."""
    _click_grid_cell(backend, game, scene, unit.col, unit.row)


def _select_and_stay(backend: MockBackend, game: Game, scene: BattleScene,
                     unit) -> None:
    """Select a warrior and stay in place (skip move phase).

    Leaves the FSM in PLAYER_ATTACK state.
    """
    _click_unit(backend, game, scene, unit)  # PLAYER_SELECT → PLAYER_MOVE
    _click_unit(backend, game, scene, unit)  # click own cell → PLAYER_ATTACK


def _teleport_adjacent(scene: BattleScene, attacker, defender) -> None:
    """Move attacker to the cell left of defender so it's in attack range."""
    scene.grid.remove_unit(attacker.col, attacker.row)
    target_col = defender.col - 1
    target_row = defender.row
    attacker.set_grid_pos(target_col, target_row)


def _run_full_attack(game: Game, backend: MockBackend, scene: BattleScene,
                     attacker, defender) -> None:
    """Teleport attacker adjacent, select, stay, attack, tick until done."""
    # Ensure attacker is adjacent to defender
    if abs(attacker.col - defender.col) > 1 or abs(attacker.row - defender.row) > 1:
        _teleport_adjacent(scene, attacker, defender)

    # Allow the attacker to act even if it already acted this turn
    scene.acted_this_turn.discard(id(attacker))

    _select_and_stay(backend, game, scene, attacker)
    _click_unit(backend, game, scene, defender)  # PLAYER_ATTACK → UNIT_ACTING
    # Tick until the action completes (generous 15s bound)
    dt = 1 / 60
    for _ in range(15 * 60):
        game.tick(dt=dt)
        if scene.fsm.state != S_UNIT_ACTING:
            break
    assert scene.fsm.state != S_UNIT_ACTING, "Attack sequence did not complete in 15s"


# ======================================================================
# 1. Scene initializes with correct number of units
# ======================================================================

class TestSceneInit:
    def test_eight_units_spawned(self, scene: BattleScene) -> None:
        """Scene starts with 4 warriors + 4 skeletons = 8 units."""
        assert len(scene.all_units) == 8

    def test_four_warriors(self, scene: BattleScene) -> None:
        assert len(scene.warriors) == 4

    def test_four_skeletons(self, scene: BattleScene) -> None:
        assert len(scene.skeletons) == 4

    def test_warriors_alive(self, scene: BattleScene) -> None:
        for w in scene.warriors:
            assert w.alive is True
            assert w.hp == 120

    def test_skeletons_alive(self, scene: BattleScene) -> None:
        for s in scene.skeletons:
            assert s.alive is True
            assert s.hp == 80

    def test_no_selection(self, scene: BattleScene) -> None:
        assert scene.selected_unit is None

    def test_starts_in_player_select(self, scene: BattleScene) -> None:
        assert scene.fsm.state == S_PLAYER_SELECT

    def test_sprites_registered_in_backend(
        self, scene: BattleScene, backend: MockBackend,
    ) -> None:
        for u in scene.all_units:
            assert u.sprite.sprite_id in backend.sprites


# ======================================================================
# 2. Clicking a warrior selects it
# ======================================================================

class TestSelection:
    def test_click_warrior_selects(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        warrior = scene.warriors[0]
        _click_unit(backend, game, scene, warrior)
        assert scene.selected_unit is warrior

    def test_fsm_moves_to_player_move(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        warrior = scene.warriors[0]
        _click_unit(backend, game, scene, warrior)
        assert scene.fsm.state == S_PLAYER_MOVE


# ======================================================================
# 3. Clicking a different warrior changes selection
# ======================================================================

class TestSelectionChange:
    def test_reselect_via_cancel_and_pick(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """Cancel current selection with right-click, then pick another."""
        w1, w2 = scene.warriors[:2]
        _click_unit(backend, game, scene, w1)
        assert scene.selected_unit is w1

        # Right-click to cancel → back to PLAYER_SELECT
        backend.inject_click(0, 0, button="right")
        game.tick(dt=0.0)
        assert scene.fsm.state == S_PLAYER_SELECT

        _click_unit(backend, game, scene, w2)
        assert scene.selected_unit is w2


# ======================================================================
# 4. Stay-in-place transitions to attack phase
# ======================================================================

class TestStayInPlace:
    def test_click_own_cell_goes_to_attack(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        warrior = scene.warriors[0]
        _select_and_stay(backend, game, scene, warrior)
        assert scene.fsm.state == S_PLAYER_ATTACK


# ======================================================================
# 5. Full attack sequence completes without errors
# ======================================================================

class TestFullAttackSequence:
    def test_attack_completes(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        warrior = scene.warriors[0]
        skeleton = scene.skeletons[0]
        _run_full_attack(game, backend, scene, warrior, skeleton)
        assert scene.fsm.state == S_PLAYER_SELECT

    def test_defender_takes_damage(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        warrior = scene.warriors[0]
        skeleton = scene.skeletons[0]
        original_hp = skeleton.hp

        _run_full_attack(game, backend, scene, warrior, skeleton)
        assert skeleton.hp == original_hp - ATTACK_DAMAGE

    def test_no_crash_on_idle_ticks(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        warrior = scene.warriors[0]
        skeleton = scene.skeletons[0]

        _run_full_attack(game, backend, scene, warrior, skeleton)
        _tick_many(game, 60)


# ======================================================================
# 6. After enough attacks, a skeleton dies
# ======================================================================

class TestSkeletonDeath:
    def test_skeleton_dies(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        warrior = scene.warriors[0]
        skeleton = scene.skeletons[0]

        attacks_needed = math.ceil(skeleton.hp / ATTACK_DAMAGE)
        for _ in range(attacks_needed):
            _run_full_attack(game, backend, scene, warrior, skeleton)

        assert skeleton.hp <= 0
        assert skeleton.alive is False

    def test_alive_count_decreases(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        warrior = scene.warriors[0]
        skeleton = scene.skeletons[0]

        attacks_needed = math.ceil(skeleton.hp / ATTACK_DAMAGE)
        for _ in range(attacks_needed):
            _run_full_attack(game, backend, scene, warrior, skeleton)

        alive = [s for s in scene.skeletons if s.alive]
        assert len(alive) == 3


# ======================================================================
# 7. Multiple attack rounds work without state corruption
# ======================================================================

class TestMultipleAttackRounds:
    def test_two_attacks_same_target(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        warrior = scene.warriors[0]
        skeleton = scene.skeletons[0]

        _run_full_attack(game, backend, scene, warrior, skeleton)
        assert skeleton.hp == 80 - ATTACK_DAMAGE

        _run_full_attack(game, backend, scene, warrior, skeleton)
        assert skeleton.hp == 80 - 2 * ATTACK_DAMAGE

    def test_attack_different_targets(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        warrior = scene.warriors[0]
        s1, s2 = scene.skeletons[:2]

        _run_full_attack(game, backend, scene, warrior, s1)
        _run_full_attack(game, backend, scene, warrior, s2)

        assert s1.hp == 80 - ATTACK_DAMAGE
        assert s2.hp == 80 - ATTACK_DAMAGE
