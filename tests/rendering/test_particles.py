"""Comprehensive tests for the ParticleEmitter system (Stage 11).

Tests use the MockBackend (backend="mock") to verify particle spawning,
movement, lifetime, fade-out, continuous rate, burst mode, stop/remove,
and Game.tick() integration — all headless, no GPU required.
"""

from __future__ import annotations

import math
import random

import pytest

from easygame import Game, Scene, Sprite
from easygame.backends.mock_backend import MockBackend
from easygame.rendering.layers import RenderLayer, SpriteAnchor
from easygame.rendering.particles import ParticleEmitter, _Particle


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def game() -> Game:
    """Fresh Game with mock backend."""
    return Game("ParticleTest", backend="mock", resolution=(800, 600))


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestConstruction:
    """ParticleEmitter creation and default state."""

    def test_create_with_defaults(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(100, 200))
        assert em.position == (100.0, 200.0)
        assert em.is_active is False  # no particles spawned yet
        assert em._count == 10
        assert em._speed == (50, 200)
        assert em._direction == (0, 360)
        assert em._lifetime == (0.3, 0.8)
        assert em._fade_out is True
        assert em._layer == RenderLayer.EFFECTS

    def test_create_with_custom_params(self, game: Game) -> None:
        em = ParticleEmitter(
            image=["sprites/knight", "sprites/enemy"],
            position=(50, 75),
            count=20,
            speed=(10, 50),
            direction=(45, 135),
            lifetime=(1.0, 2.0),
            fade_out=False,
            layer=RenderLayer.UNITS,
        )
        assert em._images == ["sprites/knight", "sprites/enemy"]
        assert em._count == 20
        assert em._speed == (10, 50)
        assert em._direction == (45, 135)
        assert em._lifetime == (1.0, 2.0)
        assert em._fade_out is False
        assert em._layer == RenderLayer.UNITS

    def test_create_single_image_stored_as_list(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(0, 0))
        assert em._images == ["sprites/knight"]

    def test_auto_registers_in_game(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(100, 200))
        assert em in game._particle_emitters

    def test_no_game_raises(self) -> None:
        """Creating a ParticleEmitter without an active Game raises RuntimeError."""
        import easygame.rendering.sprite as mod
        old = mod._current_game
        mod._current_game = None
        try:
            with pytest.raises(RuntimeError, match="No active Game"):
                ParticleEmitter("sprites/knight", position=(0, 0))
        finally:
            mod._current_game = old


# ---------------------------------------------------------------------------
# Position property
# ---------------------------------------------------------------------------

class TestPosition:
    def test_get_position(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(100, 200))
        assert em.position == (100.0, 200.0)

    def test_set_position(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(0, 0))
        em.position = (300, 400)
        assert em.position == (300.0, 400.0)

    def test_particles_spawn_at_current_position(self, game: Game) -> None:
        """After moving the emitter, burst() spawns at the new position."""
        em = ParticleEmitter("sprites/knight", position=(0, 0))
        em.position = (500, 600)
        random.seed(42)
        em.burst(1)
        assert len(em._particles) == 1
        p = em._particles[0]
        assert p.sprite._x == 500.0
        assert p.sprite._y == 600.0


# ---------------------------------------------------------------------------
# Burst mode
# ---------------------------------------------------------------------------

class TestBurst:
    def test_burst_default_count(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(0, 0), count=5)
        em.burst()
        assert len(em._particles) == 5

    def test_burst_explicit_count(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(0, 0), count=5)
        em.burst(3)
        assert len(em._particles) == 3

    def test_burst_zero_is_noop(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(0, 0))
        em.burst(0)
        assert len(em._particles) == 0

    def test_burst_creates_sprites_on_effects_layer(self, game: Game, backend: MockBackend) -> None:
        em = ParticleEmitter("sprites/knight", position=(100, 100))
        em.burst(1)
        p = em._particles[0]
        assert p.sprite.layer == RenderLayer.EFFECTS

    def test_burst_creates_sprites_with_center_anchor(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(100, 100))
        em.burst(1)
        p = em._particles[0]
        assert p.sprite.anchor == SpriteAnchor.CENTER

    def test_burst_creates_sprites_in_all_sprites(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(100, 100))
        initial = len(game._all_sprites)
        em.burst(5)
        assert len(game._all_sprites) == initial + 5

    def test_burst_is_active_after(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(0, 0))
        assert em.is_active is False
        em.burst(3)
        assert em.is_active is True

    def test_burst_custom_layer(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0), layer=RenderLayer.UNITS,
        )
        em.burst(1)
        assert em._particles[0].sprite.layer == RenderLayer.UNITS

    def test_burst_image_variety(self, game: Game) -> None:
        """With a list of images, particles get random choices."""
        random.seed(0)
        em = ParticleEmitter(
            image=["sprites/knight", "sprites/enemy", "sprites/crate"],
            position=(0, 0),
        )
        em.burst(30)
        names = {p.sprite._image_name for p in em._particles}
        # With 30 particles and 3 choices, extremely unlikely to get only 1
        assert len(names) > 1

    def test_multiple_bursts_accumulate(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(0, 0))
        em.burst(3)
        em.burst(2)
        assert len(em._particles) == 5


# ---------------------------------------------------------------------------
# Particle velocity & direction
# ---------------------------------------------------------------------------

class TestVelocity:
    def test_velocity_within_speed_range(self, game: Game) -> None:
        """Particle speed magnitude should be within the configured range."""
        random.seed(42)
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            speed=(100, 200), direction=(0, 360),
        )
        em.burst(20)
        for p in em._particles:
            speed = math.hypot(p.vx, p.vy)
            assert 100.0 <= speed <= 200.0 + 1e-6

    def test_direction_range(self, game: Game) -> None:
        """Particles spawned with direction=(0, 0) should all move rightward."""
        random.seed(42)
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            speed=(100, 100), direction=(0, 0),
        )
        em.burst(5)
        for p in em._particles:
            # cos(0) = 1, sin(0) = 0
            assert abs(p.vx - 100.0) < 1e-6
            assert abs(p.vy) < 1e-6

    def test_direction_90_moves_down(self, game: Game) -> None:
        """direction=(90, 90) with y-down means vy > 0."""
        random.seed(42)
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            speed=(100, 100), direction=(90, 90),
        )
        em.burst(1)
        p = em._particles[0]
        assert abs(p.vx) < 1e-6
        assert abs(p.vy - 100.0) < 1e-6


# ---------------------------------------------------------------------------
# Particle lifetime
# ---------------------------------------------------------------------------

class TestLifetime:
    def test_lifetime_within_range(self, game: Game) -> None:
        random.seed(42)
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(0.5, 1.5),
        )
        em.burst(20)
        for p in em._particles:
            assert 0.5 <= p.total_lifetime <= 1.5
            assert p.remaining == p.total_lifetime

    def test_particles_die_after_lifetime(self, game: Game, backend: MockBackend) -> None:
        """After enough time, particles should be removed."""
        em = ParticleEmitter(
            "sprites/knight", position=(100, 100),
            lifetime=(0.1, 0.1),  # fixed 0.1s lifetime
            speed=(0, 0),  # stationary
        )
        em.burst(3)
        assert len(em._particles) == 3
        sprites_before = len(backend.sprites)

        # Tick past the lifetime
        em.update(0.15)
        assert len(em._particles) == 0
        # Sprites should have been removed from backend
        assert len(backend.sprites) == sprites_before - 3

    def test_particles_survive_before_lifetime(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(1.0, 1.0),
            speed=(0, 0),
        )
        em.burst(5)
        em.update(0.5)
        assert len(em._particles) == 5  # still alive

    def test_is_active_false_after_all_dead(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(0.1, 0.1),
            speed=(0, 0),
        )
        em.burst(2)
        assert em.is_active is True
        em.update(0.2)
        assert len(em._particles) == 0
        assert em.is_active is False


# ---------------------------------------------------------------------------
# Particle movement
# ---------------------------------------------------------------------------

class TestMovement:
    def test_particle_moves_each_update(self, game: Game) -> None:
        """Stationary particles at known velocity should move predictably."""
        em = ParticleEmitter(
            "sprites/knight", position=(100, 100),
            speed=(100, 100), direction=(0, 0),  # rightward at 100 px/s
            lifetime=(10.0, 10.0),
        )
        em.burst(1)
        p = em._particles[0]
        assert p.sprite._x == 100.0

        em.update(0.5)
        # Should move 50px to the right
        assert abs(p.sprite._x - 150.0) < 1e-3
        assert abs(p.sprite._y - 100.0) < 1e-3

    def test_multiple_updates_accumulate(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            speed=(200, 200), direction=(0, 0),
            lifetime=(10.0, 10.0),
        )
        em.burst(1)
        p = em._particles[0]

        em.update(0.1)  # +20px
        em.update(0.1)  # +20px
        em.update(0.1)  # +20px
        assert abs(p.sprite._x - 60.0) < 1e-3

    def test_diagonal_movement(self, game: Game) -> None:
        """45-degree direction at speed 100 should move ~70.7 on each axis."""
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            speed=(100, 100), direction=(45, 45),
            lifetime=(10.0, 10.0),
        )
        em.burst(1)
        p = em._particles[0]

        em.update(1.0)
        expected = 100.0 * math.cos(math.radians(45))
        assert abs(p.sprite._x - expected) < 1e-3
        assert abs(p.sprite._y - expected) < 1e-3


# ---------------------------------------------------------------------------
# Fade-out opacity
# ---------------------------------------------------------------------------

class TestFadeOut:
    def test_fade_out_opacity_decreases(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(1.0, 1.0),
            fade_out=True,
            speed=(0, 0),
        )
        em.burst(1)
        p = em._particles[0]
        assert p.sprite.opacity == 255

        em.update(0.5)  # halfway through
        # remaining=0.5, total=1.0 → ratio=0.5 → opacity≈127
        assert 120 <= p.sprite.opacity <= 135

    def test_fade_out_reaches_zero_at_death(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(1.0, 1.0),
            fade_out=True,
            speed=(0, 0),
        )
        em.burst(1)
        p = em._particles[0]

        # Update to just before death
        em.update(0.95)
        assert p.sprite.opacity < 20

    def test_no_fade_out(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(1.0, 1.0),
            fade_out=False,
            speed=(0, 0),
        )
        em.burst(1)
        p = em._particles[0]

        em.update(0.5)
        assert p.sprite.opacity == 255  # unchanged

    def test_fade_proportional_to_remaining(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(2.0, 2.0),
            fade_out=True,
            speed=(0, 0),
        )
        em.burst(1)
        p = em._particles[0]

        em.update(1.0)  # remaining=1.0, total=2.0 → 50%
        expected = int(255 * 0.5)
        assert abs(p.sprite.opacity - expected) <= 1


# ---------------------------------------------------------------------------
# Continuous mode
# ---------------------------------------------------------------------------

class TestContinuous:
    def test_continuous_spawns_over_time(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(10.0, 10.0),  # long-lived so they don't die
            speed=(0, 0),
        )
        em.continuous(rate=10)  # 10 particles per second
        assert em.is_active is True

        em.update(0.5)  # should spawn ~5 particles
        assert len(em._particles) == 5

    def test_continuous_accumulates_fractional(self, game: Game) -> None:
        """Fractional particle counts accumulate across updates."""
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(10.0, 10.0),
            speed=(0, 0),
        )
        em.continuous(rate=3)  # 3/sec

        em.update(0.1)  # accum = 0.3 → 0 spawned
        assert len(em._particles) == 0

        em.update(0.1)  # accum = 0.6 → 0 spawned
        assert len(em._particles) == 0

        em.update(0.2)  # accum = 1.2 → 1 spawned, accum = 0.2
        assert len(em._particles) == 1

    def test_continuous_high_rate(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(10.0, 10.0),
            speed=(0, 0),
        )
        em.continuous(rate=60)
        em.update(1.0)  # should spawn exactly 60
        assert len(em._particles) == 60

    def test_stop_halts_continuous(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(10.0, 10.0),
            speed=(0, 0),
        )
        em.continuous(rate=10)
        em.update(0.5)
        count_before = len(em._particles)

        em.stop()
        em.update(0.5)
        # No new particles spawned
        assert len(em._particles) == count_before

    def test_continuous_then_burst(self, game: Game) -> None:
        """Burst works after stop — particles accumulate."""
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(10.0, 10.0),
            speed=(0, 0),
        )
        em.continuous(rate=10)
        em.update(0.5)  # 5 particles
        em.stop()
        em.burst(3)  # 3 more
        assert len(em._particles) == 8

    def test_continuous_rate_zero_no_spawn(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(10.0, 10.0),
            speed=(0, 0),
        )
        em.continuous(rate=0)
        em.update(1.0)
        assert len(em._particles) == 0


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------

class TestStop:
    def test_stop_preserves_existing_particles(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(10.0, 10.0),
            speed=(0, 0),
        )
        em.burst(5)
        em.stop()
        assert len(em._particles) == 5

    def test_stop_existing_particles_still_move(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            speed=(100, 100), direction=(0, 0),
            lifetime=(10.0, 10.0),
        )
        em.burst(1)
        em.stop()

        p = em._particles[0]
        x_before = p.sprite._x
        em.update(0.1)
        assert p.sprite._x > x_before  # still moving

    def test_stop_existing_particles_eventually_die(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(0.1, 0.1),
            speed=(0, 0),
        )
        em.burst(3)
        em.stop()
        em.update(0.2)
        assert len(em._particles) == 0
        assert em.is_active is False

    def test_stop_then_burst_resumes(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(10.0, 10.0),
            speed=(0, 0),
        )
        em.continuous(rate=10)
        em.stop()
        em.burst(5)
        assert len(em._particles) == 5
        assert em.is_active is True


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------

class TestRemove:
    def test_remove_kills_all_particles(self, game: Game, backend: MockBackend) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(10.0, 10.0),
            speed=(0, 0),
        )
        em.burst(5)
        assert len(em._particles) == 5
        sprites_before = len(backend.sprites)

        em.remove()
        assert len(em._particles) == 0
        assert len(backend.sprites) == sprites_before - 5

    def test_remove_stops_continuous(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(10.0, 10.0),
            speed=(0, 0),
        )
        em.continuous(rate=10)
        em.remove()
        assert em._continuous_rate == 0.0

    def test_remove_deregisters_from_game(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(0, 0))
        em.burst(1)
        assert em in game._particle_emitters
        em.remove()
        assert em not in game._particle_emitters

    def test_remove_is_active_false(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(0, 0))
        em.burst(5)
        em.remove()
        assert em.is_active is False

    def test_remove_clears_from_all_sprites(self, game: Game) -> None:
        initial = len(game._all_sprites)
        em = ParticleEmitter("sprites/knight", position=(0, 0))
        em.burst(3)
        assert len(game._all_sprites) == initial + 3
        em.remove()
        assert len(game._all_sprites) == initial


# ---------------------------------------------------------------------------
# Game.tick() integration
# ---------------------------------------------------------------------------

class TestGameIntegration:
    def test_tick_updates_particles(self, game: Game) -> None:
        """game.tick() calls _update_particles which moves particles."""
        game.push(Scene())  # need a scene for tick to work
        em = ParticleEmitter(
            "sprites/knight", position=(100, 100),
            speed=(100, 100), direction=(0, 0),
            lifetime=(10.0, 10.0),
        )
        em.burst(1)
        p = em._particles[0]
        x_before = p.sprite._x

        game.tick(dt=0.1)
        assert p.sprite._x > x_before

    def test_tick_removes_dead_particles(self, game: Game) -> None:
        game.push(Scene())
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(0.01, 0.01),
            speed=(0, 0),
        )
        em.burst(3)
        assert len(em._particles) == 3

        game.tick(dt=0.1)
        assert len(em._particles) == 0

    def test_tick_deregisters_inactive_emitter(self, game: Game) -> None:
        game.push(Scene())
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(0.01, 0.01),
            speed=(0, 0),
        )
        em.burst(1)
        assert em in game._particle_emitters

        game.tick(dt=0.1)
        assert em not in game._particle_emitters

    def test_tick_continuous_spawning(self, game: Game) -> None:
        game.push(Scene())
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(10.0, 10.0),
            speed=(0, 0),
        )
        em.continuous(rate=60)  # 1 per tick at 60fps

        game.tick(dt=1.0 / 60.0)
        assert len(em._particles) == 1

        game.tick(dt=1.0 / 60.0)
        assert len(em._particles) == 2

    def test_tick_continuous_keeps_emitter_registered(self, game: Game) -> None:
        game.push(Scene())
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(10.0, 10.0),
            speed=(0, 0),
        )
        em.continuous(rate=10)
        game.tick(dt=0.1)
        assert em in game._particle_emitters  # still active


# ---------------------------------------------------------------------------
# is_active edge cases
# ---------------------------------------------------------------------------

class TestIsActive:
    def test_new_emitter_not_active(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(0, 0))
        assert em.is_active is False

    def test_active_with_particles(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(0, 0))
        em.burst(1)
        assert em.is_active is True

    def test_active_with_continuous(self, game: Game) -> None:
        em = ParticleEmitter("sprites/knight", position=(0, 0))
        em.continuous(rate=5)
        assert em.is_active is True  # rate > 0

    def test_not_active_after_all_dead(self, game: Game) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(0.05, 0.05), speed=(0, 0),
        )
        em.burst(3)
        em.update(0.1)
        assert em.is_active is False

    def test_active_continuous_no_particles_yet(self, game: Game) -> None:
        """Continuous mode is active even if no particles spawned yet."""
        em = ParticleEmitter("sprites/knight", position=(0, 0))
        em.continuous(rate=0.5)  # very slow rate
        # No update yet, no particles
        assert em.is_active is True


# ---------------------------------------------------------------------------
# Particle dataclass
# ---------------------------------------------------------------------------

class TestParticleDataclass:
    def test_particle_fields(self, game: Game) -> None:
        sprite = Sprite("sprites/knight", position=(0, 0))
        p = _Particle(
            sprite=sprite,
            vx=10.0,
            vy=-20.0,
            remaining=1.5,
            total_lifetime=2.0,
            fade_out=True,
        )
        assert p.vx == 10.0
        assert p.vy == -20.0
        assert p.remaining == 1.5
        assert p.total_lifetime == 2.0
        assert p.fade_out is True


# ---------------------------------------------------------------------------
# Re-registration after auto-removal
# ---------------------------------------------------------------------------

class TestReRegistration:
    def test_burst_after_auto_deregister(self, game: Game) -> None:
        """burst() re-registers an emitter that was auto-removed."""
        game.push(Scene())
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(0.01, 0.01), speed=(0, 0),
        )
        em.burst(1)
        game.tick(dt=0.1)  # kills particle, deregisters
        assert em not in game._particle_emitters

        em.burst(2)
        assert em in game._particle_emitters
        assert len(em._particles) == 2

    def test_continuous_after_auto_deregister(self, game: Game) -> None:
        game.push(Scene())
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(0.01, 0.01), speed=(0, 0),
        )
        em.burst(1)
        game.tick(dt=0.1)
        assert em not in game._particle_emitters

        em.continuous(rate=10)
        assert em in game._particle_emitters


# ---------------------------------------------------------------------------
# Backend sprite state
# ---------------------------------------------------------------------------

class TestBackendState:
    def test_particle_sprites_have_correct_position(self, game: Game, backend: MockBackend) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(200, 300),
            speed=(0, 0), lifetime=(10.0, 10.0),
        )
        em.burst(1)
        p = em._particles[0]
        sid = p.sprite.sprite_id
        # Sprite position should be at emitter position (adjusted for anchor)
        assert sid in backend.sprites
        rec = backend.sprites[sid]
        assert rec["visible"] is True

    def test_dead_particles_removed_from_backend(self, game: Game, backend: MockBackend) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(0.05, 0.05), speed=(0, 0),
        )
        em.burst(2)
        sids = [p.sprite.sprite_id for p in em._particles]
        for sid in sids:
            assert sid in backend.sprites

        em.update(0.1)
        for sid in sids:
            assert sid not in backend.sprites

    def test_fading_particle_opacity_in_backend(self, game: Game, backend: MockBackend) -> None:
        em = ParticleEmitter(
            "sprites/knight", position=(0, 0),
            lifetime=(1.0, 1.0), fade_out=True, speed=(0, 0),
        )
        em.burst(1)
        p = em._particles[0]
        sid = p.sprite.sprite_id

        em.update(0.5)
        rec = backend.sprites[sid]
        assert rec["opacity"] < 255
        assert rec["opacity"] > 0
