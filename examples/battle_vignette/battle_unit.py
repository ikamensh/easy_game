"""Tactical battle units — rich wrappers around Saga2D sprites.

:class:`BaseUnit` wraps a :class:`Sprite` (composition, not inheritance — the
framework's design treats Sprite as visual-only) and adds RPG stats, grid
position, health bar, selection ring, damage logic, and attack choreography.

Concrete subclasses :class:`WarriorUnit` and :class:`SkeletonUnit` configure
stats and animation prefixes.

Usage (inside a Scene)::

    warrior = WarriorUnit.spawn(scene, col=1, row=2, grid=grid, team="friendly")
    skeleton = SkeletonUnit.spawn(scene, col=6, row=2, grid=grid, team="enemy")

    # Damage
    skeleton.take_damage(warrior.atk - skeleton.def_)

    # Attack choreography (returns an Action for sprite.do())
    action = warrior.get_attack_action(skeleton)
    warrior.sprite.do(action)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from saga2d import (
    AnimationDef,
    Delay,
    Do,
    Ease,
    FadeOut,
    MoveTo,
    Parallel,
    ParticleEmitter,
    PlayAnim,
    Remove,
    RenderLayer,
    Sequence,
    Sprite,
    SpriteAnchor,
    tween,
)

from examples.battle_vignette.battle_grid import TILE_SIZE

if TYPE_CHECKING:
    from saga2d import Scene
    from saga2d.actions import Action

    from examples.battle_vignette.battle_grid import SquareGrid


# ======================================================================
# Constants
# ======================================================================

SPRITE_SIZE: int = 64
"""All battle sprites are 64×64."""

MOVE_SPEED: float = 400.0
"""Walk speed in pixels per second."""

# Health bar geometry (drawn via Scene.draw_rect / draw_world_rect)
HEALTH_BAR_WIDTH: int = 48
HEALTH_BAR_HEIGHT: int = 6
HEALTH_BAR_Y_OFFSET: int = -8
"""Y offset above the sprite's position for the health bar."""

HEALTH_BAR_BG: tuple[int, int, int, int] = (40, 40, 40, 200)
HEALTH_BAR_FG: tuple[int, int, int, int] = (50, 200, 50, 220)
HEALTH_BAR_LOW: tuple[int, int, int, int] = (220, 60, 40, 220)
"""Foreground colour when HP drops below 30%."""

# Floating damage number settings
FLOAT_RISE: float = 60.0
"""How many pixels damage numbers float upward."""
FLOAT_DURATION: float = 0.8


# ======================================================================
# FloatingNumber (ephemeral world-positioned text)
# ======================================================================

class FloatingNumber:
    """A damage/heal number that floats up and fades out.

    Attributes ``x``, ``y``, ``opacity`` are tweened by the tween system.
    The owning scene draws these each frame via ``backend.draw_text()``.
    """

    def __init__(self, text: str, x: float, y: float, color: tuple[int, int, int, int]) -> None:
        self.text = text
        self.x = x
        self.y = y
        self.color = color
        self.opacity: float = 255.0
        self.alive = True


# ======================================================================
# BaseUnit
# ======================================================================

class BaseUnit:
    """Rich game-logic wrapper around a Saga2D :class:`Sprite`.

    Parameters:
        sprite:   The visual sprite (created externally or via :meth:`spawn`).
        scene:    The owning :class:`Scene`.
        grid:     The :class:`SquareGrid` for occupancy tracking.
        team:     Team identifier (e.g. ``"friendly"`` or ``"enemy"``).
        col:      Initial grid column.
        row:      Initial grid row.
        hp:       Maximum (and starting) hit points.
        atk:      Attack power.
        def_:     Defence value.
        mov:      Movement range in grid steps.
        rng:      Attack range (Chebyshev distance).
    """

    # Subclasses override these with their AnimationDef instances.
    anim_idle: AnimationDef
    anim_walk: AnimationDef
    anim_attack: AnimationDef
    anim_hit: AnimationDef
    anim_death: AnimationDef

    def __init__(
        self,
        sprite: Sprite,
        scene: Scene,
        grid: SquareGrid,
        team: str,
        col: int,
        row: int,
        *,
        hp: int,
        atk: int,
        def_: int,
        mov: int,
        rng: int,
    ) -> None:
        self.sprite = sprite
        self.scene = scene
        self.grid = grid
        self.team = team

        # Grid position
        self.col = col
        self.row = row

        # Stats
        self.max_hp = hp
        self.hp = hp
        self.atk = atk
        self.def_ = def_
        self.mov = mov
        self.rng = rng

        # State
        self.alive = True
        self.selected = False

        # Visual children
        self._select_ring: Sprite | None = None
        self._ring_tween_ids: list[int] = []

        # Floating damage numbers owned by this unit (drawn by the scene)
        self.floaters: list[FloatingNumber] = []

        # Start idle animation
        self.sprite.play(self.anim_idle)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def spawn(
        cls,
        scene: Scene,
        col: int,
        row: int,
        grid: SquareGrid,
        team: str,
    ) -> BaseUnit:
        """Create a unit at ``(col, row)`` on the grid.

        The sprite is registered via ``scene.add_sprite()`` for automatic
        cleanup.  The unit is placed in the grid's occupancy map.
        """
        world_x, world_y = grid.grid_to_world_center(col, row)
        # Position sprite at the bottom-center of the cell.
        sprite_y = grid.origin_y + (row + 1) * TILE_SIZE
        sprite = Sprite(
            cls._idle_image(),
            position=(world_x, sprite_y),
            layer=RenderLayer.UNITS,
            anchor=SpriteAnchor.BOTTOM_CENTER,
        )
        scene.add_sprite(sprite)
        unit = cls(
            sprite, scene, grid, team, col, row,
            hp=cls._default_hp(),
            atk=cls._default_atk(),
            def_=cls._default_def(),
            mov=cls._default_mov(),
            rng=cls._default_rng(),
        )
        grid.place_unit(col, row, unit)
        return unit

    # Subclasses override these class methods for stats defaults.
    @classmethod
    def _idle_image(cls) -> str:
        raise NotImplementedError

    @classmethod
    def _default_hp(cls) -> int:
        raise NotImplementedError

    @classmethod
    def _default_atk(cls) -> int:
        raise NotImplementedError

    @classmethod
    def _default_def(cls) -> int:
        raise NotImplementedError

    @classmethod
    def _default_mov(cls) -> int:
        raise NotImplementedError

    @classmethod
    def _default_rng(cls) -> int:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Grid position
    # ------------------------------------------------------------------

    def set_grid_pos(self, col: int, row: int) -> None:
        """Move the unit to ``(col, row)`` in the grid and update the sprite.

        Updates the grid's occupancy map (old cell cleared, new cell set)
        and snaps the sprite to the new world position.
        """
        # Clear old occupancy
        if self.grid.in_bounds(self.col, self.row):
            self.grid.remove_unit(self.col, self.row)

        self.col = col
        self.row = row
        self.grid.place_unit(col, row, self)

        # Snap sprite to new cell center (bottom-center anchor)
        world_x, _ = self.grid.grid_to_world_center(col, row)
        sprite_y = self.grid.origin_y + (row + 1) * TILE_SIZE
        self.sprite.position = (world_x, sprite_y)

    @property
    def world_pos(self) -> tuple[float, float]:
        """Current world-pixel position of the sprite."""
        return self.sprite.position

    # ------------------------------------------------------------------
    # Selection ring
    # ------------------------------------------------------------------

    def select(self) -> None:
        """Show a golden selection ring beneath the sprite."""
        if self.selected:
            return
        self.selected = True
        sx, sy = self.sprite.position
        self._select_ring = Sprite(
            "sprites/select_ring",
            position=(sx, sy),
            layer=RenderLayer.UI_WORLD,
            anchor=SpriteAnchor.BOTTOM_CENTER,
        )
        self.scene.add_sprite(self._select_ring)
        self._start_ring_pulse()

    def deselect(self) -> None:
        """Hide the selection ring."""
        if not self.selected:
            return
        self.selected = False
        self._stop_ring_pulse()
        if self._select_ring is not None:
            self._select_ring.remove()
            self._select_ring = None

    def _start_ring_pulse(self) -> None:
        if self._select_ring is None:
            return

        ring = self._select_ring

        def pulse_up() -> None:
            if ring.is_removed:
                return
            self._ring_tween_ids.append(tween(
                ring, "opacity", 120.0, 255.0, 0.6,
                ease=Ease.EASE_IN_OUT, on_complete=pulse_down,
            ))

        def pulse_down() -> None:
            if ring.is_removed:
                return
            self._ring_tween_ids.append(tween(
                ring, "opacity", 255.0, 120.0, 0.6,
                ease=Ease.EASE_IN_OUT, on_complete=pulse_up,
            ))

        self._ring_tween_ids.append(tween(
            ring, "opacity", 255.0, 120.0, 0.6,
            ease=Ease.EASE_IN_OUT, on_complete=pulse_up,
        ))

    def _stop_ring_pulse(self) -> None:
        for tid in self._ring_tween_ids:
            self.scene.game.cancel_tween(tid)
        self._ring_tween_ids.clear()

    # ------------------------------------------------------------------
    # Health bar (drawn each frame by the scene)
    # ------------------------------------------------------------------

    def draw_health_bar(self, scene: Scene) -> None:
        """Draw the health bar above the unit sprite.

        Call from :meth:`Scene.draw`.  Uses ``draw_rect`` (screen-space)
        or ``draw_world_rect`` (camera-aware) depending on the scene.
        """
        if not self.alive:
            return

        draw_fn = scene.draw_world_rect if scene.camera is not None else scene.draw_rect

        sx, sy = self.sprite.position
        bar_x = sx - HEALTH_BAR_WIDTH / 2
        bar_y = sy - SPRITE_SIZE + HEALTH_BAR_Y_OFFSET

        # Background
        draw_fn(bar_x, bar_y, HEALTH_BAR_WIDTH, HEALTH_BAR_HEIGHT, HEALTH_BAR_BG)

        # Fill
        hp_ratio = max(0.0, self.hp / self.max_hp)
        fill_w = max(1, int(HEALTH_BAR_WIDTH * hp_ratio))
        fg_color = HEALTH_BAR_LOW if hp_ratio < 0.3 else HEALTH_BAR_FG
        draw_fn(bar_x, bar_y, fill_w, HEALTH_BAR_HEIGHT, fg_color)

    # ------------------------------------------------------------------
    # Floating damage numbers (drawn each frame by the scene)
    # ------------------------------------------------------------------

    def draw_floaters(self, scene: Scene) -> None:
        """Draw floating damage numbers.  Call from :meth:`Scene.draw`."""
        backend = scene.game.backend
        for f in self.floaters:
            if not f.alive:
                continue
            alpha = max(0, min(255, int(f.opacity)))
            r, g, b, _ = f.color
            backend.draw_text(
                f.text, int(f.x), int(f.y), 24,
                (r, g, b, alpha),
                font="Arial",
            )
        self.floaters = [f for f in self.floaters if f.alive]

    # ------------------------------------------------------------------
    # Damage
    # ------------------------------------------------------------------

    def take_damage(
        self,
        amount: int,
        *,
        on_death: Callable[[], Any] | None = None,
    ) -> None:
        """Apply damage, spawn floating number, play hit / death animations.

        Damage is clamped to a minimum of 1 (attacks always deal at least
        1 point).  If HP drops to 0 the unit dies: death animation plays
        followed by fade-out and removal.

        Parameters:
            amount:   Raw damage (before defence is applied).
            on_death: Optional callback fired after the death animation finishes.
        """
        if not self.alive:
            return

        actual = max(1, amount - self.def_)
        self.hp = max(0, self.hp - actual)

        # Sound effect, damage flash, and screen shake
        self.scene.game.audio.play_sound("sounds/sword_hit", optional=True)
        if hasattr(self.scene, "_flash_opacity"):
            self.scene._flash_opacity = 1.0
            tween(self.scene, "_flash_opacity", 1.0, 0.0, 0.2, ease=Ease.EASE_OUT)
        if self.scene.camera is not None:
            self.scene.camera.shake(6.0, 0.15, 2.0)

        # Hit sparkle particles
        sx, sy = self.sprite.position
        self.scene.add_emitter(ParticleEmitter(
            ["particles/spark", "particles/blood"],
            position=(sx, sy - SPRITE_SIZE // 2),
            count=8,
            speed=(40, 150),
            direction=(0, 360),
            lifetime=(0.15, 0.4),
            fade_out=True,
        )).burst()

        # Spawn floating damage number
        floater = FloatingNumber(
            text=f"-{actual}",
            x=sx,
            y=sy - SPRITE_SIZE,
            color=(255, 80, 80, 255),
        )
        self.floaters.append(floater)
        tween(floater, "y", floater.y, floater.y - FLOAT_RISE, FLOAT_DURATION,
              ease=Ease.EASE_OUT)
        tween(floater, "opacity", 255.0, 0.0, FLOAT_DURATION,
              ease=Ease.EASE_IN,
              on_complete=lambda: setattr(floater, "alive", False))

        if self.hp <= 0:
            self._die(on_death)
        else:
            self.sprite.do(Sequence(
                PlayAnim(self.anim_hit),
                Do(lambda: self.sprite.play(self.anim_idle)),
            ))

    def _die(self, on_death: Callable[[], Any] | None = None) -> None:
        """Play death animation, fade out, and remove the sprite."""
        self.alive = False
        self.deselect()
        self.scene.game.audio.play_sound("sounds/death", optional=True)

        # Death dust burst
        sx, sy = self.sprite.position
        self.scene.add_emitter(ParticleEmitter(
            "particles/dust",
            position=(sx, sy - SPRITE_SIZE // 2),
            count=15,
            speed=(20, 100),
            direction=(180, 360),  # upward fan
            lifetime=(0.3, 0.8),
            fade_out=True,
        )).burst()

        # Clear occupancy
        if self.grid.in_bounds(self.col, self.row):
            self.grid.remove_unit(self.col, self.row)

        actions: list[Action] = [
            PlayAnim(self.anim_hit),
            PlayAnim(self.anim_death),
            FadeOut(0.5),
            Remove(),
        ]
        if on_death is not None:
            actions.append(Do(on_death))

        self.sprite.do(Sequence(*actions))

    # ------------------------------------------------------------------
    # Attack choreography
    # ------------------------------------------------------------------

    def get_attack_action(
        self,
        target: BaseUnit,
        *,
        on_complete: Callable[[], Any] | None = None,
    ) -> Action:
        """Return a :class:`Sequence` action for a full attack choreography.

        The sequence:

        1. Walk toward the target (walk anim + MoveTo in parallel).
        2. Play attack animation.
        3. Brief pause.
        4. Apply damage to target (hit / death handled by ``take_damage``).
        5. Walk back home and resume idle.
        6. Fire optional *on_complete* callback.

        The caller should execute this via ``self.sprite.do(action)``.

        Note: step 5 (walk home) is scheduled on the next frame via
        ``game.after(0, ...)`` to avoid conflicting with the ``Do()``
        callback's Sequence context.
        """
        # Compute melee stand-off position (80 px from target)
        tx, ty = target.sprite.position
        sx, _ = self.sprite.position
        approach_x = tx - 80 if sx < tx else tx + 80

        home_pos = self.sprite.position

        attacker = self

        def apply_hit() -> None:
            def walk_home() -> None:
                attacker.sprite.do(Sequence(
                    Parallel(
                        PlayAnim(attacker.anim_walk),
                        MoveTo(home_pos, speed=MOVE_SPEED),
                    ),
                    Do(lambda: attacker.sprite.play(attacker.anim_idle)),
                    *([] if on_complete is None else [Do(on_complete)]),
                ))

            target.take_damage(attacker.atk, on_death=walk_home)

            if target.alive:
                # Target survived — walk home immediately (next frame)
                attacker.scene.game.after(0, walk_home)

        return Sequence(
            # Phase 1: Walk toward enemy
            Parallel(
                PlayAnim(self.anim_walk),
                MoveTo((approach_x, ty), speed=MOVE_SPEED),
            ),
            # Phase 2: Attack animation
            PlayAnim(self.anim_attack),
            # Phase 3: Brief pause before hit lands
            Delay(0.3),
            # Phase 4: Apply hit → triggers walk home via callback
            Do(apply_hit),
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def remove(self) -> None:
        """Remove the unit and all its visual elements."""
        self.deselect()
        if self.grid.in_bounds(self.col, self.row):
            self.grid.remove_unit(self.col, self.row)
        if not self.sprite.is_removed:
            self.sprite.remove()
        self.alive = False
        self.floaters.clear()


# ======================================================================
# WarriorUnit
# ======================================================================

class WarriorUnit(BaseUnit):
    """Armoured melee warrior.  120 HP / 25 ATK / 10 DEF / 3 MOV / 1 RNG."""

    anim_idle = AnimationDef(
        frames=["sprites/warrior_idle_01"],
        frame_duration=1.0,
        loop=True,
    )
    anim_walk = AnimationDef(
        frames="sprites/warrior_walk",
        frame_duration=0.12,
        loop=True,
    )
    anim_attack = AnimationDef(
        frames="sprites/warrior_attack",
        frame_duration=0.1,
        loop=False,
    )
    # Warriors reuse the idle frame for hit (no dedicated hit frames)
    anim_hit = AnimationDef(
        frames=["sprites/warrior_idle_01"],
        frame_duration=0.2,
        loop=False,
    )
    # Warriors reuse the idle frame for death (no dedicated death frames)
    anim_death = AnimationDef(
        frames=["sprites/warrior_idle_01"],
        frame_duration=0.3,
        loop=False,
    )

    @classmethod
    def _idle_image(cls) -> str:
        return "sprites/warrior_idle_01"

    @classmethod
    def _default_hp(cls) -> int:
        return 120

    @classmethod
    def _default_atk(cls) -> int:
        return 25

    @classmethod
    def _default_def(cls) -> int:
        return 10

    @classmethod
    def _default_mov(cls) -> int:
        return 3

    @classmethod
    def _default_rng(cls) -> int:
        return 1


# ======================================================================
# SkeletonUnit
# ======================================================================

class SkeletonUnit(BaseUnit):
    """Undead ranged skeleton.  80 HP / 20 ATK / 5 DEF / 4 MOV / 2 RNG."""

    anim_idle = AnimationDef(
        frames=["sprites/skeleton_idle_01"],
        frame_duration=1.0,
        loop=True,
    )
    anim_walk = AnimationDef(
        frames="sprites/skeleton_walk",
        frame_duration=0.12,
        loop=True,
    )
    anim_attack = AnimationDef(
        frames="sprites/skeleton_walk",  # skeletons lack attack frames; reuse walk
        frame_duration=0.1,
        loop=False,
    )
    anim_hit = AnimationDef(
        frames="sprites/skeleton_hit",
        frame_duration=0.1,
        loop=False,
    )
    anim_death = AnimationDef(
        frames="sprites/skeleton_death",
        frame_duration=0.2,
        loop=False,
    )

    @classmethod
    def _idle_image(cls) -> str:
        return "sprites/skeleton_idle_01"

    @classmethod
    def _default_hp(cls) -> int:
        return 80

    @classmethod
    def _default_atk(cls) -> int:
        return 20

    @classmethod
    def _default_def(cls) -> int:
        return 5

    @classmethod
    def _default_mov(cls) -> int:
        return 4

    @classmethod
    def _default_rng(cls) -> int:
        return 2
