"""Screenshot regression tests for Stage 11 ParticleEmitter.

Run from the project root::

    pytest tests/screenshot/test_particles_screenshots.py -v

Requires pyglet (GPU context) and pre-generated assets
(``python generate_assets.py``).  Excluded from the normal ``pytest tests/``
run by ``collect_ignore`` in ``tests/conftest.py``.

Each test creates an emitter, fires a burst, advances time, then captures
and compares a screenshot.  Golden images are auto-created on first run.

Particle randomness is seeded for deterministic golden images.
"""

from __future__ import annotations

import random

import pytest

from easygame import Scene
from easygame.rendering.particles import ParticleEmitter

from tests.screenshot.harness import assert_screenshot, render_scene


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RESOLUTION = (320, 240)


class EmptyScene(Scene):
    """Minimal scene that keeps the scene stack non-empty."""
    pass


# ---------------------------------------------------------------------------
# 1. Particle burst captured mid-flight
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_particle_burst_mid_flight() -> None:
    """Burst of 20 particles from the centre, captured mid-flight.

    An emitter at (160, 120) fires 20 particles in all directions
    (0-360 degrees) with speed 80-160 px/s, lifetime 0.5-1.0 s, and
    fade_out enabled.  After 15 ticks (15 * 1/60 = 0.25 s) the
    particles should have spread outward from the centre, partially
    faded.

    Expected: a radial spray of knight sprites around the centre.
    """

    def setup(game):
        random.seed(42)
        game.push(EmptyScene())
        emitter = ParticleEmitter(
            "sprites/knight",
            position=(160, 120),
            count=20,
            speed=(80, 160),
            direction=(0, 360),
            lifetime=(0.5, 1.0),
            fade_out=True,
        )
        emitter.burst()

    image = render_scene(setup, tick_count=15, resolution=_RESOLUTION)
    assert_screenshot(image, "particle_burst_mid_flight")


# ---------------------------------------------------------------------------
# 2. Particle burst at start (just spawned)
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_particle_burst_start() -> None:
    """Burst of 15 particles captured immediately after spawning.

    Emitter at (160, 120), burst of 15.  Captured after 1 tick so
    particles have barely moved from the spawn point.

    Expected: a tight cluster of sprites at the centre.
    """

    def setup(game):
        random.seed(99)
        game.push(EmptyScene())
        emitter = ParticleEmitter(
            "sprites/crate",
            position=(160, 120),
            count=15,
            speed=(60, 120),
            direction=(0, 360),
            lifetime=(0.4, 0.8),
            fade_out=True,
        )
        emitter.burst()

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "particle_burst_start")


# ---------------------------------------------------------------------------
# 3. Particle burst late — most particles faded or dead
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_particle_burst_late() -> None:
    """Burst of 12 particles captured well into their lifetimes.

    Emitter at (160, 120) with lifetime 0.3-0.6 s.  After 30 ticks
    (30 * 1/60 = 0.5 s) most short-lived particles should be dead
    and the survivors heavily faded.

    Expected: a few faint sprites far from the centre, most gone.
    """

    def setup(game):
        random.seed(7)
        game.push(EmptyScene())
        emitter = ParticleEmitter(
            "sprites/enemy",
            position=(160, 120),
            count=12,
            speed=(100, 200),
            direction=(0, 360),
            lifetime=(0.3, 0.6),
            fade_out=True,
        )
        emitter.burst()

    image = render_scene(setup, tick_count=30, resolution=_RESOLUTION)
    assert_screenshot(image, "particle_burst_late")


# ---------------------------------------------------------------------------
# 4. Directional burst (upward fan)
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_particle_burst_directional() -> None:
    """Directional burst — particles firing upward in a 60-degree fan.

    Emitter at bottom-centre (160, 200).  Direction 250-310 degrees
    (roughly upward in y-down coords, since 270 = up).  After 10
    ticks the particles should form a fan shape above the emitter.

    Expected: fan of sprites above the bottom-centre.
    """

    def setup(game):
        random.seed(123)
        game.push(EmptyScene())
        emitter = ParticleEmitter(
            "sprites/knight",
            position=(160, 200),
            count=15,
            speed=(100, 180),
            direction=(250, 310),
            lifetime=(0.5, 1.0),
            fade_out=False,
        )
        emitter.burst()

    image = render_scene(setup, tick_count=10, resolution=_RESOLUTION)
    assert_screenshot(image, "particle_burst_directional")


# ---------------------------------------------------------------------------
# 5. Multi-image variety burst
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_particle_burst_multi_image() -> None:
    """Burst using multiple image names for particle variety.

    Emitter at (160, 120) with three different images (knight, enemy,
    crate).  Each particle randomly picks one.  After 10 ticks the
    result should show a mix of sprite types.

    Expected: a spread of different sprite images around the centre.
    """

    def setup(game):
        random.seed(55)
        game.push(EmptyScene())
        emitter = ParticleEmitter(
            ["sprites/knight", "sprites/enemy", "sprites/crate"],
            position=(160, 120),
            count=18,
            speed=(70, 150),
            direction=(0, 360),
            lifetime=(0.5, 1.0),
            fade_out=True,
        )
        emitter.burst()

    image = render_scene(setup, tick_count=10, resolution=_RESOLUTION)
    assert_screenshot(image, "particle_burst_multi_image")
