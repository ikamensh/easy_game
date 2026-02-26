"""Screenshot regression tests for Stage 10 Composable Actions.

Run from the project root::

    pytest tests/screenshot/test_action_screenshots.py -v

Requires pyglet (GPU context) and pre-generated assets
(``python generate_assets.py``).  Excluded from the normal ``pytest tests/``
run by ``collect_ignore`` in ``tests/conftest.py``.

Each test creates a Scene, attaches an Action to a sprite, advances the
game loop a calculated number of ticks, then captures and compares a
screenshot.  Golden images are auto-created on first run.

Tests use the knight and skeleton assets (walk cycles, idle frames) that
are already present in ``assets/images/sprites/``.
"""

from __future__ import annotations

import pytest

from easygame import (
    AnimationDef,
    Delay,
    FadeOut,
    MoveTo,
    Parallel,
    PlayAnim,
    Scene,
    Sequence,
    Sprite,
)
from easygame.rendering.layers import RenderLayer, SpriteAnchor

from tests.screenshot.harness import assert_screenshot, render_scene


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RESOLUTION = (320, 240)


class EmptyScene(Scene):
    """Minimal scene that keeps the scene stack non-empty."""
    pass


# Reusable animation definitions.
_KNIGHT_WALK = AnimationDef(
    frames=[
        "sprites/knight_walk_01",
        "sprites/knight_walk_02",
        "sprites/knight_walk_03",
        "sprites/knight_walk_04",
    ],
    frame_duration=0.1,
    loop=True,
)

_WARRIOR_WALK = AnimationDef(
    frames=[
        "sprites/warrior_walk_01",
        "sprites/warrior_walk_02",
        "sprites/warrior_walk_03",
        "sprites/warrior_walk_04",
    ],
    frame_duration=0.1,
    loop=True,
)


# ---------------------------------------------------------------------------
# 1. Parallel walk + animate — start position
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_action_walk_start() -> None:
    """Knight with Parallel(PlayAnim(walk), MoveTo) captured at the start.

    The knight is placed at (20, 120) and will walk rightward to (280, 120)
    at 200 px/s.  We capture after 1 tick — the sprite should still be at
    approximately its start position with the walk animation's first frame
    visible.

    Expected: knight sprite near the left edge, walk_01 frame displayed.
    """

    def setup(game):
        game.push(EmptyScene())
        knight = Sprite(
            "sprites/knight_walk_01",
            position=(20, 120),
            anchor=SpriteAnchor.TOP_LEFT,
            layer=RenderLayer.UNITS,
        )
        knight.do(Parallel(
            PlayAnim(_KNIGHT_WALK),
            MoveTo((280, 120), speed=200),
        ))

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "action_walk_start")


# ---------------------------------------------------------------------------
# 2. Parallel walk + animate — mid-walk
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_action_walk_mid() -> None:
    """Knight with Parallel(PlayAnim(walk), MoveTo) captured mid-walk.

    Start at (20, 120), target (280, 120) at 200 px/s.
    Distance = 260 px.  Duration = 260 / 200 = 1.3 s.

    We tick 39 frames (39 × 1/60 = 0.65 s — halfway through the movement).
    Expected x ≈ 20 + 200 * 0.65 = 150.  The walk animation should be on a
    mid-cycle frame.

    Expected: knight sprite roughly centred horizontally, mid-walk frame.
    """

    def setup(game):
        game.push(EmptyScene())
        knight = Sprite(
            "sprites/knight_walk_01",
            position=(20, 120),
            anchor=SpriteAnchor.TOP_LEFT,
            layer=RenderLayer.UNITS,
        )
        knight.do(Parallel(
            PlayAnim(_KNIGHT_WALK),
            MoveTo((280, 120), speed=200),
        ))

    # 39 ticks × (1/60) ≈ 0.65s — roughly half of the 1.3s walk
    image = render_scene(setup, tick_count=39, resolution=_RESOLUTION)
    assert_screenshot(image, "action_walk_mid")


# ---------------------------------------------------------------------------
# 3. FadeOut — before and after
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_action_fadeout_before() -> None:
    """Skeleton sprite at full opacity before FadeOut begins.

    The skeleton is at (128, 100) with a FadeOut(1.0) action.  We capture
    after only 1 tick (≈0.017 s) — the sprite should be nearly fully opaque.

    Expected: skeleton clearly visible at full (or near-full) opacity.
    """

    def setup(game):
        game.push(EmptyScene())
        skel = Sprite(
            "sprites/skeleton_idle_01",
            position=(128, 100),
            anchor=SpriteAnchor.TOP_LEFT,
            layer=RenderLayer.UNITS,
        )
        skel.do(FadeOut(1.0))

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "action_fadeout_before")


@pytest.mark.screenshot
def test_action_fadeout_after() -> None:
    """Skeleton sprite after FadeOut completes — fully transparent.

    FadeOut(1.0) on a skeleton at (128, 100).  We tick 65 frames
    (65 × 1/60 ≈ 1.083 s) — past the 1.0 s duration.  The sprite should
    be at opacity 0 (invisible).

    Expected: empty screen (skeleton fully transparent).
    """

    def setup(game):
        game.push(EmptyScene())
        skel = Sprite(
            "sprites/skeleton_idle_01",
            position=(128, 100),
            anchor=SpriteAnchor.TOP_LEFT,
            layer=RenderLayer.UNITS,
        )
        skel.do(FadeOut(1.0))

    # 65 ticks × (1/60) ≈ 1.083s — well past the 1.0s fade
    image = render_scene(setup, tick_count=65, resolution=_RESOLUTION)
    assert_screenshot(image, "action_fadeout_after")


# ---------------------------------------------------------------------------
# 4. Battle sequence — walk right, delay, walk back
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_action_battle_start() -> None:
    """Battle sequence: warrior at start position before the attack run.

    Warrior starts at (20, 100).  The sequence is:
        Parallel(PlayAnim(walk), MoveTo((260, 100), speed=300))
        → Delay(0.3)
        → Parallel(PlayAnim(walk), MoveTo((20, 100), speed=300))

    We capture after 1 tick — the warrior should still be near x=20.

    Expected: warrior sprite near the left edge, walk_01 frame.
    """

    def setup(game):
        game.push(EmptyScene())
        warrior = Sprite(
            "sprites/warrior_walk_01",
            position=(20, 100),
            anchor=SpriteAnchor.TOP_LEFT,
            layer=RenderLayer.UNITS,
        )
        warrior.do(Sequence(
            Parallel(PlayAnim(_WARRIOR_WALK), MoveTo((260, 100), speed=300)),
            Delay(0.3),
            Parallel(PlayAnim(_WARRIOR_WALK), MoveTo((20, 100), speed=300)),
        ))

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "action_battle_start")


@pytest.mark.screenshot
def test_action_battle_at_target() -> None:
    """Battle sequence: warrior at the target after the forward walk.

    Distance = 240 px, speed = 300 px/s, duration = 240/300 = 0.8 s.
    We tick 50 frames (50 × 1/60 ≈ 0.833 s) — the forward MoveTo should
    be complete and the warrior should be near x=260, in the Delay phase.

    Expected: warrior sprite near the right edge, on a walk frame (the
    animation was stopped when Parallel ended).
    """

    def setup(game):
        game.push(EmptyScene())
        warrior = Sprite(
            "sprites/warrior_walk_01",
            position=(20, 100),
            anchor=SpriteAnchor.TOP_LEFT,
            layer=RenderLayer.UNITS,
        )
        warrior.do(Sequence(
            Parallel(PlayAnim(_WARRIOR_WALK), MoveTo((260, 100), speed=300)),
            Delay(0.3),
            Parallel(PlayAnim(_WARRIOR_WALK), MoveTo((20, 100), speed=300)),
        ))

    # 50 ticks × (1/60) ≈ 0.833s — past 0.8s forward walk, in the delay
    image = render_scene(setup, tick_count=50, resolution=_RESOLUTION)
    assert_screenshot(image, "action_battle_at_target")


@pytest.mark.screenshot
def test_action_battle_returning() -> None:
    """Battle sequence: warrior partway through the return walk.

    Forward walk = 0.8 s, Delay = 0.3 s → return starts at ≈ 1.1 s.
    Return walk: 240 px at 300 px/s = 0.8 s → finishes at ≈ 1.9 s.

    We tick 84 frames (84 × 1/60 = 1.4 s) — the warrior should be in the
    return walk, roughly halfway back.
    Time in return walk = 1.4 - 1.1 = 0.3 s.
    Expected x ≈ 260 - 300 * 0.3 = 170 — roughly centre-right.

    Expected: warrior sprite in the centre area, mid-walk frame.
    """

    def setup(game):
        game.push(EmptyScene())
        warrior = Sprite(
            "sprites/warrior_walk_01",
            position=(20, 100),
            anchor=SpriteAnchor.TOP_LEFT,
            layer=RenderLayer.UNITS,
        )
        warrior.do(Sequence(
            Parallel(PlayAnim(_WARRIOR_WALK), MoveTo((260, 100), speed=300)),
            Delay(0.3),
            Parallel(PlayAnim(_WARRIOR_WALK), MoveTo((20, 100), speed=300)),
        ))

    # 84 ticks × (1/60) = 1.4s — in the return walk
    image = render_scene(setup, tick_count=84, resolution=_RESOLUTION)
    assert_screenshot(image, "action_battle_returning")
