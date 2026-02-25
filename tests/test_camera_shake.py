"""Tests for Camera shake behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from easygame import Game, Scene, Sprite
from easygame.assets import AssetManager
from easygame.backends.mock_backend import MockBackend
from easygame.rendering.camera import Camera
from easygame.rendering.layers import SpriteAnchor


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    """Temp asset dir with knight.png."""
    images = tmp_path / "images" / "sprites"
    images.mkdir(parents=True)
    (images / "knight.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def game(asset_dir: Path) -> Game:
    """Return a Game instance with assets pointing at the temp directory."""
    g = Game("Test", backend="mock", resolution=(800, 600))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    return g


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


# ==================================================================
# 1. Lifecycle: starts nonzero, decays to zero, offset properties
# ==================================================================

class TestCameraShakeLifecycle:

    def test_shake_starts_with_nonzero_offset_in_update(self) -> None:
        """shake(intensity, duration, decay) produces nonzero offset after update()."""
        cam = Camera((800, 600))
        cam.shake(intensity=20.0, duration=1.0, decay=1.0)

        cam.update(0.016)

        assert cam.shake_offset_x != 0.0 or cam.shake_offset_y != 0.0

    def test_shake_decays_to_zero_after_duration(self) -> None:
        """shake(intensity, 1.0, 1.0) ends with zero offsets after duration."""
        cam = Camera((800, 600))
        cam.shake(intensity=20.0, duration=1.0, decay=1.0)

        cam.update(0.5)  # elapsed = 0.5, still shaking
        assert cam._shake_elapsed == 0.5

        cam.update(0.6)  # elapsed = 1.1 >= 1.0, shake ends

        assert cam.shake_offset_x == 0.0
        assert cam.shake_offset_y == 0.0
        assert cam._shake_duration == 0.0

    def test_shake_offset_properties_return_current_offset(self) -> None:
        """shake_offset_x and shake_offset_y return the current offset."""
        cam = Camera((800, 600))
        cam.shake(intensity=10.0, duration=1.0, decay=1.0)
        cam.update(0.016)

        assert cam.shake_offset_x == cam._shake_offset_x
        assert cam.shake_offset_y == cam._shake_offset_y


# ==================================================================
# 2. Composition with center_on
# ==================================================================

class TestCameraShakeComposition:

    def test_shake_composes_with_center_on(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Shake offsets are added to _x/_y during sprite sync (draw phase)."""
        sprite = Sprite(
            "sprites/knight", position=(400, 300),
            anchor=SpriteAnchor.TOP_LEFT,
        )
        draw_positions = {}

        class WorldScene(Scene):
            def on_enter(self) -> None:
                self.camera = Camera((800, 600))
                self.camera.center_on(400, 300)  # _x=0, _y=0
                self.camera.shake(intensity=50.0, duration=1.0, decay=1.0)

            def draw(self) -> None:
                rec = backend.sprites[sprite.sprite_id]
                draw_positions["x"] = rec["x"]
                draw_positions["y"] = rec["y"]
                draw_positions["shake_x"] = self.camera.shake_offset_x
                draw_positions["shake_y"] = self.camera.shake_offset_y

        game.push(WorldScene())
        game.tick(dt=0.016)

        # Without shake: sprite at (400, 300), camera at (0, 0) → screen (400, 300).
        # With shake: screen = int(world - (camera._x + shake_x, camera._y + shake_y))
        #            = int((400, 300) - (shake_x, shake_y))  — truncate after subtract
        expected_x = int(400 - draw_positions["shake_x"])
        expected_y = int(300 - draw_positions["shake_y"])
        assert draw_positions["x"] == expected_x
        assert draw_positions["y"] == expected_y


# ==================================================================
# 3. No-op for duration <= 0
# ==================================================================

class TestCameraShakeNoOp:

    def test_shake_duration_zero_resets(self) -> None:
        """shake with duration 0 resets any active shake."""
        cam = Camera((800, 600))
        cam.shake(intensity=20.0, duration=1.0, decay=1.0)
        cam.update(0.016)
        assert cam.shake_offset_x != 0.0 or cam.shake_offset_y != 0.0

        cam.shake(intensity=99.0, duration=0.0, decay=1.0)

        assert cam.shake_offset_x == 0.0
        assert cam.shake_offset_y == 0.0
        assert cam._shake_duration == 0.0
        assert cam._shake_intensity == 0.0

    def test_shake_negative_duration_resets(self) -> None:
        """shake with negative duration resets any active shake."""
        cam = Camera((800, 600))
        cam.shake(intensity=20.0, duration=1.0, decay=1.0)
        cam.update(0.016)

        cam.shake(intensity=99.0, duration=-0.1, decay=1.0)

        assert cam.shake_offset_x == 0.0
        assert cam.shake_offset_y == 0.0
        assert cam._shake_duration == 0.0


# ==================================================================
# 4. Multiple shake() calls replace previous
# ==================================================================

class TestCameraShakeReplacement:

    def test_multiple_shake_calls_replace_previous(self) -> None:
        """A new shake() call replaces the previous shake (new params, reset elapsed)."""
        cam = Camera((800, 600))
        cam.shake(intensity=10.0, duration=2.0, decay=1.0)
        cam.update(0.5)  # First shake at 0.5s elapsed

        cam.shake(intensity=5.0, duration=0.5, decay=2.0)  # Replace

        assert cam._shake_intensity == 5.0
        assert cam._shake_duration == 0.5
        assert cam._shake_decay == 2.0
        assert cam._shake_elapsed == 0.0

        # Second shake should end after 0.5s total
        cam.update(0.3)
        cam.update(0.3)  # elapsed = 0.6 >= 0.5
        assert cam.shake_offset_x == 0.0
        assert cam.shake_offset_y == 0.0


# ==================================================================
# 5. Randomness
# ==================================================================

class TestCameraShakeRandomness:

    def test_shake_offsets_change_across_updates(self) -> None:
        """Shake offsets are random — multiple updates produce different values."""
        cam = Camera((800, 600))
        cam.shake(intensity=20.0, duration=1.0, decay=1.0)

        offsets: list[tuple[float, float]] = []
        for _ in range(8):
            cam.update(0.01)
            offsets.append((cam.shake_offset_x, cam.shake_offset_y))

        # At least two distinct offset pairs (allowing for rare collision).
        unique = set(offsets)
        assert len(unique) >= 2, "Shake offsets should vary across updates"
