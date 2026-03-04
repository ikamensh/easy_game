"""Tactical battle vignette — validates Stage 0–5 framework primitives.

Run from the project root::

    python examples/battle_vignette/battle_demo.py

Controls — Title Screen:
    Enter                       → start battle
    Escape                      → quit

Controls — Battle:
    Left-click a blue warrior   → select it
    Left-click a red skeleton   → attack with selected warrior
    Escape                      → return to title screen

The demo places 3 warriors (left) vs 3 skeletons (right) on a 1920×1080
screen.  Selecting a warrior shows a golden ring beneath it.  Clicking an
enemy triggers a 6-phase attack choreography using the Actions system:

    1. Warrior walks toward skeleton (MoveTo + PlayAnim in Parallel)
    2. Warrior plays attack animation (PlayAnim)
    3. Short delay (Delay)
    4. Skeleton plays hit reaction → death or recover
    5. If HP <= 0 → death anim + FadeOut + Remove
    6. Warrior walks home and plays idle
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path so ``import saga2d`` works
# when invoked as ``python examples/battle_vignette/battle_demo.py``.
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from saga2d import (  # noqa: E402
    Anchor,
    AnimationDef,
    AssetManager,
    Delay,
    Do,
    Ease,
    FadeOut,
    Game,
    InputEvent,
    Label,
    MoveTo,
    Parallel,
    PlayAnim,
    Remove,
    RenderLayer,
    Scene,
    Sequence,
    Sprite,
    SpriteAnchor,
    tween,
)


# ======================================================================
# Animation definitions (reusable templates, no handles yet)
# ======================================================================

WARRIOR_IDLE = AnimationDef(
    frames=["sprites/warrior_idle_01"],
    frame_duration=1.0,
    loop=True,
)
WARRIOR_WALK = AnimationDef(
    frames="sprites/warrior_walk",
    frame_duration=0.12,
    loop=True,
)
WARRIOR_ATTACK = AnimationDef(
    frames="sprites/warrior_attack",
    frame_duration=0.1,
    loop=False,
)

SKELETON_IDLE = AnimationDef(
    frames=["sprites/skeleton_idle_01"],
    frame_duration=1.0,
    loop=True,
)
SKELETON_WALK = AnimationDef(
    frames="sprites/skeleton_walk",
    frame_duration=0.12,
    loop=True,
)
SKELETON_HIT = AnimationDef(
    frames="sprites/skeleton_hit",
    frame_duration=0.1,
    loop=False,
)
SKELETON_DEATH = AnimationDef(
    frames="sprites/skeleton_death",
    frame_duration=0.2,
    loop=False,
)


# ======================================================================
# TitleScene
# ======================================================================

SCREEN_W, SCREEN_H = 1920, 1080


class TitleScene(Scene):
    """Animated title screen with decorative sprites.

    ENTER → push BattleScene, ESC → quit.
    """

    background_color = (25, 25, 40, 255)

    def on_enter(self) -> None:
        self._sprites: list[Sprite] = []
        self._tween_ids: list[int] = []

        self._create_ui()
        self._create_decorative_sprites()

    # ------------------------------------------------------------------
    # UI — Labels via the framework's UI component system
    # ------------------------------------------------------------------

    def _create_ui(self) -> None:
        self.ui.add(Label(
            "BATTLE VIGNETTE",
            font_size=64, font="Arial",
            text_color=(255, 220, 80, 255),
            anchor=Anchor.TOP, margin=80,
        ))
        self.ui.add(Label(
            "Press ENTER to start",
            font_size=28, font="Arial",
            text_color=(200, 200, 200, 255),
            anchor=Anchor.TOP, margin=200,
        ))
        self.ui.add(Label(
            "Press ESC to quit",
            font_size=28, font="Arial",
            text_color=(160, 160, 160, 255),
            anchor=Anchor.TOP, margin=245,
        ))

    # ------------------------------------------------------------------
    # Decorative animated sprites
    # ------------------------------------------------------------------

    def _create_decorative_sprites(self) -> None:
        """Place warriors and skeletons as title-screen decoration."""
        for i, (x, base_y) in enumerate([(400, 600), (550, 750)]):
            warrior = Sprite(
                "sprites/warrior_idle_01",
                position=(x, base_y),
                layer=RenderLayer.UNITS,
                anchor=SpriteAnchor.BOTTOM_CENTER,
            )
            warrior.play(WARRIOR_WALK)
            self._sprites.append(warrior)
            self._start_bob(warrior, base_y, 12, 1.2 + i * 0.3)

        for i, (x, base_y) in enumerate([(1370, 600), (1520, 750)]):
            skeleton = Sprite(
                "sprites/skeleton_idle_01",
                position=(x, base_y),
                layer=RenderLayer.UNITS,
                anchor=SpriteAnchor.BOTTOM_CENTER,
            )
            skeleton.play(SKELETON_WALK)
            self._sprites.append(skeleton)
            self._start_opacity_pulse(skeleton, 255, 160, 1.5 + i * 0.4)

    def _start_bob(self, sprite: Sprite, base_y: float, amount: float, duration: float) -> None:
        """Start a looping up-down bob tween."""
        def bob_down() -> None:
            self._tween_ids.append(tween(
                sprite, "y", base_y - amount, base_y, duration,
                ease=Ease.EASE_IN_OUT, on_complete=bob_up,
            ))

        def bob_up() -> None:
            self._tween_ids.append(tween(
                sprite, "y", base_y, base_y - amount, duration,
                ease=Ease.EASE_IN_OUT, on_complete=bob_down,
            ))

        self._tween_ids.append(tween(
            sprite, "y", float(base_y), base_y - amount, duration,
            ease=Ease.EASE_IN_OUT, on_complete=bob_down,
        ))

    def _start_opacity_pulse(self, sprite: Sprite, high: float, low: float, duration: float) -> None:
        """Start a looping opacity pulse tween."""
        def fade_in() -> None:
            self._tween_ids.append(tween(
                sprite, "opacity", low, high, duration,
                ease=Ease.EASE_IN_OUT, on_complete=fade_out,
            ))

        def fade_out() -> None:
            self._tween_ids.append(tween(
                sprite, "opacity", high, low, duration,
                ease=Ease.EASE_IN_OUT, on_complete=fade_in,
            ))

        self._tween_ids.append(tween(
            sprite, "opacity", high, low, duration,
            ease=Ease.EASE_IN_OUT, on_complete=fade_in,
        ))

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_input(self, event: InputEvent) -> bool:
        if event.action == "confirm":
            self.game.push(BattleScene())
            return True

        if event.action == "cancel":
            self.game.quit()
            return True

        return False

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def on_exit(self) -> None:
        for sprite in self._sprites:
            sprite.remove()
        self._sprites.clear()

        for tid in self._tween_ids:
            self.game.cancel_tween(tid)
        self._tween_ids.clear()


# ======================================================================
# Unit data holder
# ======================================================================

class Unit:
    """Simple data holder for a battlefield unit."""

    def __init__(
        self,
        sprite: Sprite,
        team: str,
        home_pos: tuple[float, float],
        hp: int = 100,
    ) -> None:
        self.sprite = sprite
        self.team = team
        self.home_pos = home_pos
        self.hp = hp
        self.alive = True


# ======================================================================
# Floating damage number (world-positioned ephemeral text)
# ======================================================================

class _FloatingNumber:
    """A damage number that floats up and fades out.

    Tweened by the tween system (x, y, opacity are settable attributes).
    Drawn each frame by the scene's ``draw()`` via ``backend.draw_text()``.

    Note: This uses raw ``draw_text()`` rather than a Label because damage
    numbers are world-positioned ephemeral text — the UI component system
    uses layout-based anchoring, not world coordinates.
    """

    def __init__(self, text: str, x: float, y: float) -> None:
        self.text = text
        self.x = x
        self.y = y
        self.opacity: float = 255.0
        self.alive = True


# ======================================================================
# BattleScene
# ======================================================================

MOVE_SPEED = 400  # pixels / second
ATTACK_DAMAGE = 40

# Sprite sizes (all 64×64 as generated)
SPRITE_W, SPRITE_H = 64, 64
HIT_RADIUS = SPRITE_W // 2 + 8  # generous click radius


class BattleScene(Scene):
    """Single-screen tactical battle with ground plane and idle animations."""

    background_color = (72, 85, 48, 255)

    def on_enter(self) -> None:
        self.units: list[Unit] = []
        self.selected: Unit | None = None
        self.select_ring: Sprite | None = None
        self._ring_tween_ids: list[int] = []
        self.busy = False  # True while an attack sequence is playing
        self.floaters: list[_FloatingNumber] = []

        # Per-unit idle-breathing tween ids: unit → list of active tween ids
        self._idle_tween_ids: dict[int, list[int]] = {}

        # Victory state
        self._victory: bool = False
        self._victory_label: Label | None = None
        self._victory_opacity: float = 0.0  # tweened 0→255 on win
        self._victory_timer_id: int | None = None

        self._create_ui()
        self._spawn_units()

    def _create_ui(self) -> None:
        """Add victory label (initially hidden)."""
        self._victory_label = Label(
            "VICTORY",
            font_size=96, font="Arial",
            text_color=(255, 230, 60, 255),
            anchor=Anchor.CENTER,
            visible=False,
        )
        self.ui.add(self._victory_label)

    def on_exit(self) -> None:
        """Remove all unit sprites, tweens, and selection ring."""
        self._deselect()

        if self._victory_timer_id is not None:
            self.game.cancel(self._victory_timer_id)
            self._victory_timer_id = None

        # Cancel all idle-breathing tweens
        for tween_list in self._idle_tween_ids.values():
            for tid in tween_list:
                self.game.cancel_tween(tid)
        self._idle_tween_ids.clear()

        for unit in self.units:
            if unit.alive:
                unit.sprite.remove()
        self.units.clear()
        self.floaters.clear()

    # ------------------------------------------------------------------
    # Spawning
    # ------------------------------------------------------------------

    def _spawn_units(self) -> None:
        """Place warriors on the left, skeletons on the right.

        Y positions are staggered so units lower on screen draw in front
        (demonstrating y-sort draw ordering).
        """
        warrior_positions = [
            (340, 340),   # top row — renders behind
            (280, 510),   # middle row
            (340, 680),   # bottom row — renders in front
        ]
        for pos in warrior_positions:
            sprite = Sprite(
                "sprites/warrior_idle_01",
                position=pos,
                layer=RenderLayer.UNITS,
                anchor=SpriteAnchor.BOTTOM_CENTER,
            )
            unit = Unit(sprite, "friendly", pos)
            self.units.append(unit)
            self._start_idle_breathing(unit)

        skeleton_positions = [
            (1580, 340),  # top row
            (1640, 510),  # middle row
            (1580, 680),  # bottom row
        ]
        for pos in skeleton_positions:
            sprite = Sprite(
                "sprites/skeleton_idle_01",
                position=pos,
                layer=RenderLayer.UNITS,
                anchor=SpriteAnchor.BOTTOM_CENTER,
            )
            unit = Unit(sprite, "enemy", pos)
            self.units.append(unit)
            self._start_idle_breathing(unit)

    # ------------------------------------------------------------------
    # Idle breathing — subtle y-bob tween loop
    # ------------------------------------------------------------------

    def _start_idle_breathing(self, unit: Unit) -> None:
        """Start a gentle up-down bob on an idle unit's sprite."""
        self._stop_idle_breathing(unit)
        base_y = float(unit.home_pos[1])
        bob = 4.0
        dur = 1.4

        def bob_down() -> None:
            if not unit.alive:
                return
            uid = id(unit)
            tid = tween(unit.sprite, "y", base_y - bob, base_y, dur,
                        ease=Ease.EASE_IN_OUT, on_complete=bob_up)
            self._idle_tween_ids.setdefault(uid, []).append(tid)

        def bob_up() -> None:
            if not unit.alive:
                return
            uid = id(unit)
            tid = tween(unit.sprite, "y", base_y, base_y - bob, dur,
                        ease=Ease.EASE_IN_OUT, on_complete=bob_down)
            self._idle_tween_ids.setdefault(uid, []).append(tid)

        uid = id(unit)
        tid = tween(unit.sprite, "y", base_y, base_y - bob, dur,
                    ease=Ease.EASE_IN_OUT, on_complete=bob_down)
        self._idle_tween_ids.setdefault(uid, []).append(tid)

    def _stop_idle_breathing(self, unit: Unit) -> None:
        """Cancel all idle-breathing tweens for a unit."""
        for tid in self._idle_tween_ids.pop(id(unit), []):
            self.game.cancel_tween(tid)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_input(self, event: InputEvent) -> bool:
        if event.action == "cancel" and not self._victory:
            self.game.pop()
            return True

        if self._victory:
            return True  # consume all input during victory

        if event.type == "click" and event.button == "left":
            self._handle_click(event.x, event.y)
            return True

        return False

    def _handle_click(self, mx: int, my: int) -> None:
        if self.busy:
            return

        clicked_unit = self._unit_at(mx, my)
        if clicked_unit is None:
            self._deselect()
            return

        if clicked_unit.team == "friendly":
            self._select(clicked_unit)
        elif clicked_unit.team == "enemy" and self.selected is not None:
            self._begin_attack(self.selected, clicked_unit)

    def _unit_at(self, mx: int, my: int) -> Unit | None:
        for unit in self.units:
            if not unit.alive:
                continue
            ux, uy = unit.sprite.position
            if abs(mx - ux) < HIT_RADIUS and abs(my - uy) < HIT_RADIUS:
                return unit
        return None

    # ------------------------------------------------------------------
    # Selection — ring with pulsing opacity
    # ------------------------------------------------------------------

    def _select(self, unit: Unit) -> None:
        self._deselect()
        self.selected = unit

        ux, uy = unit.sprite.position
        self.select_ring = Sprite(
            "sprites/select_ring",
            position=(ux, uy),
            layer=RenderLayer.UI_WORLD,
            anchor=SpriteAnchor.BOTTOM_CENTER,
        )
        self._start_ring_pulse()

    def _deselect(self) -> None:
        self._stop_ring_pulse()
        if self.select_ring is not None:
            self.select_ring.remove()
            self.select_ring = None
        self.selected = None

    def _start_ring_pulse(self) -> None:
        if self.select_ring is None:
            return

        def pulse_up() -> None:
            if self.select_ring is None:
                return
            self._ring_tween_ids.append(tween(
                self.select_ring, "opacity", 120.0, 255.0, 0.6,
                ease=Ease.EASE_IN_OUT, on_complete=pulse_down,
            ))

        def pulse_down() -> None:
            if self.select_ring is None:
                return
            self._ring_tween_ids.append(tween(
                self.select_ring, "opacity", 255.0, 120.0, 0.6,
                ease=Ease.EASE_IN_OUT, on_complete=pulse_up,
            ))

        self._ring_tween_ids.append(tween(
            self.select_ring, "opacity", 255.0, 120.0, 0.6,
            ease=Ease.EASE_IN_OUT, on_complete=pulse_up,
        ))

    def _stop_ring_pulse(self) -> None:
        for tid in self._ring_tween_ids:
            self.game.cancel_tween(tid)
        self._ring_tween_ids.clear()

    # ------------------------------------------------------------------
    # Attack choreography — Actions-based sequencing
    # ------------------------------------------------------------------

    def _begin_attack(self, attacker: Unit, defender: Unit) -> None:
        """Orchestrate a full attack using the Actions system.

        The entire 6-phase sequence is expressed as a single Sequence:
        walk → attack → delay → hit → (death or recover) → walk home.
        """
        self.busy = True
        self._deselect()
        self._stop_idle_breathing(attacker)

        dx, dy = defender.sprite.position
        target_x = dx - 80 if attacker.home_pos[0] < dx else dx + 80

        attacker.sprite.do(Sequence(
            # Phase 1: Walk toward enemy
            Parallel(PlayAnim(WARRIOR_WALK), MoveTo((target_x, dy), speed=MOVE_SPEED)),
            # Phase 2: Attack animation
            PlayAnim(WARRIOR_ATTACK),
            # Phase 3: Brief pause before hit lands
            Delay(0.3),
            # Phase 4: Apply hit and trigger defender reaction
            Do(lambda: self._apply_hit(attacker, defender)),
        ))

    def _apply_hit(self, attacker: Unit, defender: Unit) -> None:
        """Apply damage, spawn floating number, and chain defender reaction.

        Note: We use ``game.after(0, ...)`` to schedule the walk-home
        on the next frame.  Starting a new ``sprite.do()`` on the attacker
        from *inside* its own ``Do`` callback would conflict — the outer
        Sequence hasn't finished returning yet and would null out the new
        action.
        """
        if not defender.alive:
            self.game.after(0, lambda: self._walk_home(attacker))
            return

        defender.hp -= ATTACK_DAMAGE
        self._spawn_damage_number(defender)
        self._stop_idle_breathing(defender)

        if defender.hp <= 0:
            defender.alive = False
            defender.sprite.do(Sequence(
                PlayAnim(SKELETON_HIT),
                PlayAnim(SKELETON_DEATH),
                FadeOut(0.5),
                Remove(),
                Do(lambda: self._walk_home(attacker)),
            ))
        else:
            defender.sprite.do(Sequence(
                PlayAnim(SKELETON_HIT),
                Do(lambda: defender.sprite.play(SKELETON_IDLE)),
                Do(lambda: self._start_idle_breathing(defender)),
            ))
            self.game.after(0, lambda: self._walk_home(attacker))

    def _walk_home(self, attacker: Unit) -> None:
        """Walk the attacker back to its starting position."""
        attacker.sprite.do(Sequence(
            Parallel(PlayAnim(WARRIOR_WALK), MoveTo(attacker.home_pos, speed=MOVE_SPEED)),
            # Use Do() to switch to idle — PlayAnim(WARRIOR_IDLE) would block
            # the Sequence because looping animations are infinite.
            Do(lambda: attacker.sprite.play(WARRIOR_IDLE)),
            Do(lambda: self._on_attack_done(attacker)),
        ))

    def _on_attack_done(self, attacker: Unit) -> None:
        self._start_idle_breathing(attacker)
        self.busy = False

        if not self._victory and not any(
            u.alive for u in self.units if u.team == "enemy"
        ):
            self._trigger_victory()

    # ------------------------------------------------------------------
    # Victory
    # ------------------------------------------------------------------

    def _trigger_victory(self) -> None:
        self._victory = True
        if self._victory_label is not None:
            self._victory_label.visible = True

        self._victory_timer_id = self.game.after(3.0, self._victory_pop)

    def _victory_pop(self) -> None:
        self._victory_timer_id = None
        self.game.pop()

    # ------------------------------------------------------------------
    # Floating damage numbers
    # ------------------------------------------------------------------

    def _spawn_damage_number(self, target: Unit) -> None:
        """Spawn a floating "-40" above the defender."""
        tx, ty = target.sprite.position
        floater = _FloatingNumber(
            text=f"-{ATTACK_DAMAGE}",
            x=tx,
            y=ty - SPRITE_H,
        )
        self.floaters.append(floater)

        tween(floater, "y", floater.y, floater.y - 60, 0.8, ease=Ease.EASE_OUT)
        tween(
            floater, "opacity", 255.0, 0.0, 0.8,
            ease=Ease.EASE_IN,
            on_complete=lambda: setattr(floater, "alive", False),
        )

    # ------------------------------------------------------------------
    # Draw — only world-positioned ephemeral text (damage numbers)
    # ------------------------------------------------------------------

    def draw(self) -> None:
        backend = self.game.backend

        for f in self.floaters:
            if not f.alive:
                continue
            alpha = max(0, min(255, int(f.opacity)))
            backend.draw_text(
                f.text, int(f.x), int(f.y), 24,
                (255, 80, 80, alpha),
                font="Arial",
            )

        self.floaters = [f for f in self.floaters if f.alive]


# ======================================================================
# Main
# ======================================================================

def main() -> None:
    asset_path = Path(__file__).resolve().parent / "assets"

    game = Game(
        "Battle Vignette",
        resolution=(1920, 1080),
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
