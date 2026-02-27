"""Headless tests for the battle vignette demo.

Uses ``Game(backend="mock")`` to validate the demo's choreography
without a display.  The asset_root points to the real demo sprites so
``AssetManager`` can discover numbered animation frames.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from easygame import Game
from easygame.assets import AssetManager
from easygame.backends.mock_backend import MockBackend

# Import the demo's scene and constants directly.
from examples.battle_vignette.battle_demo import (
    ATTACK_DAMAGE,
    BattleScene,
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
    # tick once to flush the push and run on_enter
    game.tick(dt=0.0)
    return s


# ======================================================================
# Helpers
# ======================================================================

def _tick_many(game: Game, n: int, dt: float = 1 / 60) -> None:
    """Tick the game *n* times at *dt* seconds each."""
    for _ in range(n):
        game.tick(dt=dt)


def _warriors(scene: BattleScene):
    return [u for u in scene.units if u.team == "friendly"]


def _skeletons(scene: BattleScene):
    return [u for u in scene.units if u.team == "enemy"]


def _alive_skeletons(scene: BattleScene):
    return [u for u in _skeletons(scene) if u.alive]


def _click_unit(backend: MockBackend, game: Game, unit) -> None:
    """Inject a left-click at a unit's position and tick to process it."""
    ux, uy = unit.sprite.position
    backend.inject_click(int(ux), int(uy))
    game.tick(dt=0.0)


def _run_full_attack(game: Game, backend: MockBackend, scene: BattleScene,
                     attacker, defender) -> None:
    """Select attacker, click defender, then tick until busy clears."""
    _click_unit(backend, game, attacker)
    _click_unit(backend, game, defender)
    # Tick until the full attack sequence completes.
    # The sequence involves: walk to target, attack anim, 0.3s delay,
    # hit reaction anim, (optional death + fade), walk home.
    # A generous upper bound of 15 seconds covers any distance.
    dt = 1 / 60
    for _ in range(15 * 60):
        game.tick(dt=dt)
        if not scene.busy:
            break
    assert not scene.busy, "Attack sequence did not complete in 15s"


# ======================================================================
# 1. Scene initializes with correct number of units
# ======================================================================

class TestSceneInit:
    def test_six_units_spawned(self, scene: BattleScene) -> None:
        """Scene starts with exactly 6 units."""
        assert len(scene.units) == 6

    def test_three_warriors(self, scene: BattleScene) -> None:
        """3 units belong to the 'friendly' team."""
        assert len(_warriors(scene)) == 3

    def test_three_skeletons(self, scene: BattleScene) -> None:
        """3 units belong to the 'enemy' team."""
        assert len(_skeletons(scene)) == 3

    def test_all_alive(self, scene: BattleScene) -> None:
        """All units start alive with 100 HP."""
        for u in scene.units:
            assert u.alive is True
            assert u.hp == 100

    def test_no_selection(self, scene: BattleScene) -> None:
        """Nothing is selected initially."""
        assert scene.selected is None
        assert scene.select_ring is None

    def test_not_busy(self, scene: BattleScene) -> None:
        """Not busy initially."""
        assert scene.busy is False

    def test_sprites_registered_in_backend(
        self, scene: BattleScene, backend: MockBackend,
    ) -> None:
        """All 6 unit sprites exist in the backend."""
        for u in scene.units:
            assert u.sprite.sprite_id in backend.sprites


# ======================================================================
# 2. Clicking a warrior selects it (selection ring appears)
# ======================================================================

class TestSelection:
    def test_click_warrior_selects(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """Left-clicking a warrior sets scene.selected."""
        warrior = _warriors(scene)[0]
        _click_unit(backend, game, warrior)

        assert scene.selected is warrior

    def test_selection_ring_appears(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """A selection ring sprite is created at the warrior's position."""
        warrior = _warriors(scene)[0]
        _click_unit(backend, game, warrior)

        assert scene.select_ring is not None
        assert scene.select_ring.sprite_id in backend.sprites

    def test_selection_ring_position(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """The selection ring is placed at the warrior's position."""
        warrior = _warriors(scene)[0]
        _click_unit(backend, game, warrior)

        assert scene.select_ring.position == warrior.sprite.position


# ======================================================================
# 3. Clicking a different warrior changes selection
# ======================================================================

class TestSelectionChange:
    def test_reselect_changes_selected(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """Clicking a second warrior changes scene.selected."""
        w1, w2 = _warriors(scene)[:2]
        _click_unit(backend, game, w1)
        assert scene.selected is w1

        _click_unit(backend, game, w2)
        assert scene.selected is w2

    def test_old_ring_removed(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """The old selection ring is removed from the backend."""
        w1, w2 = _warriors(scene)[:2]
        _click_unit(backend, game, w1)
        old_ring_id = scene.select_ring.sprite_id

        _click_unit(backend, game, w2)
        assert old_ring_id not in backend.sprites

    def test_new_ring_at_new_position(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """The new ring appears at the new warrior's position."""
        w1, w2 = _warriors(scene)[:2]
        _click_unit(backend, game, w1)
        _click_unit(backend, game, w2)

        assert scene.select_ring is not None
        assert scene.select_ring.position == w2.sprite.position

    def test_click_empty_deselects(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """Clicking empty space clears the selection."""
        warrior = _warriors(scene)[0]
        _click_unit(backend, game, warrior)
        assert scene.selected is not None

        # Click far from any unit
        backend.inject_click(960, 100)
        game.tick(dt=0.0)

        assert scene.selected is None
        assert scene.select_ring is None


# ======================================================================
# 4. Clicking an enemy with a warrior selected starts an attack
# ======================================================================

class TestAttackStart:
    def test_clicking_enemy_sets_busy(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """Clicking an enemy with a warrior selected sets busy=True."""
        warrior = _warriors(scene)[0]
        skeleton = _skeletons(scene)[0]

        _click_unit(backend, game, warrior)
        _click_unit(backend, game, skeleton)

        assert scene.busy is True

    def test_selection_cleared_on_attack(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """Selection is cleared when an attack begins."""
        warrior = _warriors(scene)[0]
        skeleton = _skeletons(scene)[0]

        _click_unit(backend, game, warrior)
        _click_unit(backend, game, skeleton)

        assert scene.selected is None
        assert scene.select_ring is None

    def test_clicking_enemy_without_selection_does_nothing(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """Clicking an enemy without a warrior selected has no effect."""
        skeleton = _skeletons(scene)[0]
        _click_unit(backend, game, skeleton)

        assert scene.busy is False
        assert scene.selected is None


# ======================================================================
# 5. Ticking through the full attack sequence completes without errors
# ======================================================================

class TestFullAttackSequence:
    def test_attack_completes(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """A full attack sequence runs to completion (busy→False)."""
        warrior = _warriors(scene)[0]
        skeleton = _skeletons(scene)[0]

        _run_full_attack(game, backend, scene, warrior, skeleton)
        assert not scene.busy

    def test_defender_takes_damage(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """After one attack, defender HP decreases by ATTACK_DAMAGE."""
        warrior = _warriors(scene)[0]
        skeleton = _skeletons(scene)[0]
        original_hp = skeleton.hp

        _run_full_attack(game, backend, scene, warrior, skeleton)
        assert skeleton.hp == original_hp - ATTACK_DAMAGE

    def test_attacker_returns_home(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """After the attack, warrior is back at its home position."""
        warrior = _warriors(scene)[0]
        skeleton = _skeletons(scene)[0]
        home = warrior.home_pos

        _run_full_attack(game, backend, scene, warrior, skeleton)

        # Position should be very close to home (floating point tolerance)
        wx, wy = warrior.sprite.position
        assert abs(wx - home[0]) < 2
        assert abs(wy - home[1]) < 2

    def test_no_crash_on_idle_ticks(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """Extra ticks after attack completes cause no errors."""
        warrior = _warriors(scene)[0]
        skeleton = _skeletons(scene)[0]

        _run_full_attack(game, backend, scene, warrior, skeleton)
        _tick_many(game, 60)  # one second of idle ticking


# ======================================================================
# 6. After enough attacks, a skeleton dies and is removed
# ======================================================================

class TestSkeletonDeath:
    def test_skeleton_dies(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """After enough attacks, skeleton.alive becomes False and its
        sprite is removed from the backend."""
        warrior = _warriors(scene)[0]
        skeleton = _skeletons(scene)[0]

        attacks_needed = math.ceil(skeleton.hp / ATTACK_DAMAGE)
        for _ in range(attacks_needed):
            _run_full_attack(game, backend, scene, warrior, skeleton)

        assert skeleton.hp <= 0
        assert skeleton.alive is False
        assert skeleton.sprite.is_removed

    def test_dead_skeleton_sprite_gone(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """Dead skeleton's sprite_id is removed from the backend."""
        warrior = _warriors(scene)[0]
        skeleton = _skeletons(scene)[0]
        sid = skeleton.sprite.sprite_id

        attacks_needed = math.ceil(skeleton.hp / ATTACK_DAMAGE)
        for _ in range(attacks_needed):
            _run_full_attack(game, backend, scene, warrior, skeleton)

        assert sid not in backend.sprites

    def test_alive_count_decreases(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """Killing one skeleton leaves 2 alive."""
        warrior = _warriors(scene)[0]
        skeleton = _skeletons(scene)[0]

        attacks_needed = math.ceil(skeleton.hp / ATTACK_DAMAGE)
        for _ in range(attacks_needed):
            _run_full_attack(game, backend, scene, warrior, skeleton)

        assert len(_alive_skeletons(scene)) == 2


# ======================================================================
# 7. Multiple attack rounds work without state corruption
# ======================================================================

class TestMultipleAttackRounds:
    def test_two_attacks_same_target(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """Two sequential attacks on the same target both deal damage."""
        warrior = _warriors(scene)[0]
        skeleton = _skeletons(scene)[0]

        _run_full_attack(game, backend, scene, warrior, skeleton)
        assert skeleton.hp == 100 - ATTACK_DAMAGE

        _run_full_attack(game, backend, scene, warrior, skeleton)
        assert skeleton.hp == 100 - 2 * ATTACK_DAMAGE

    def test_different_attackers(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """Different warriors can attack the same skeleton sequentially."""
        w1, w2 = _warriors(scene)[:2]
        skeleton = _skeletons(scene)[0]

        _run_full_attack(game, backend, scene, w1, skeleton)
        _run_full_attack(game, backend, scene, w2, skeleton)

        assert skeleton.hp == 100 - 2 * ATTACK_DAMAGE

    def test_attack_different_targets(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """Warrior can attack different skeletons in sequence."""
        warrior = _warriors(scene)[0]
        s1, s2 = _skeletons(scene)[:2]

        _run_full_attack(game, backend, scene, warrior, s1)
        _run_full_attack(game, backend, scene, warrior, s2)

        assert s1.hp == 100 - ATTACK_DAMAGE
        assert s2.hp == 100 - ATTACK_DAMAGE

    def test_kill_then_attack_another(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """After killing one skeleton, the warrior can attack a different one."""
        warrior = _warriors(scene)[0]
        s1, s2 = _skeletons(scene)[:2]

        # Kill s1
        attacks_to_kill = math.ceil(s1.hp / ATTACK_DAMAGE)
        for _ in range(attacks_to_kill):
            _run_full_attack(game, backend, scene, warrior, s1)

        assert not s1.alive

        # Attack s2 — should work without error
        _run_full_attack(game, backend, scene, warrior, s2)
        assert s2.hp == 100 - ATTACK_DAMAGE
        assert s2.alive


# ======================================================================
# 8. Clicking while busy is ignored
# ======================================================================

class TestBusyIgnored:
    def test_click_warrior_while_busy(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """Clicking a warrior during an attack sequence is ignored."""
        warrior = _warriors(scene)[0]
        skeleton = _skeletons(scene)[0]

        # Start attack
        _click_unit(backend, game, warrior)
        _click_unit(backend, game, skeleton)
        assert scene.busy is True

        # Click another warrior — should be ignored
        w2 = _warriors(scene)[1]
        _click_unit(backend, game, w2)
        assert scene.selected is None  # no selection change

    def test_click_enemy_while_busy(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """Clicking an enemy during an attack is ignored (no second attack)."""
        warrior = _warriors(scene)[0]
        s1, s2 = _skeletons(scene)[:2]

        # Start attack on s1
        _click_unit(backend, game, warrior)
        _click_unit(backend, game, s1)
        assert scene.busy is True

        # Try to click s2 — should be ignored
        _click_unit(backend, game, s2)
        assert s2.hp == 100  # no damage dealt to s2

    def test_busy_clears_after_attack(
        self, scene: BattleScene, game: Game, backend: MockBackend,
    ) -> None:
        """After the attack completes, busy is False and input works again."""
        warrior = _warriors(scene)[0]
        skeleton = _skeletons(scene)[0]

        _run_full_attack(game, backend, scene, warrior, skeleton)
        assert not scene.busy

        # Should be able to select again
        _click_unit(backend, game, warrior)
        assert scene.selected is warrior
