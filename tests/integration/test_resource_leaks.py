"""Tests for architectural and resource leak fixes.

Covers:
1. Game.__init__ singleton guard
2. Game._particle_emitters is WeakSet
3. SceneStack._cleanup_exiting_scene clears scene._ui
4. DragManager.cancel_active cancels active drag sessions
5. MockBackend.stop_player removes entry from _music_players
6. SceneStack sets scene.game = None on pop/replace
7. Game.tick wraps draw in try/finally for end_frame/_restore_sprites
8. TimerManager/TweenManager wrap callbacks in try/except
"""

from __future__ import annotations

import weakref
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from easygame import Game, Scene
from easygame.backends.mock_backend import MockBackend
from easygame.util.timer import TimerManager
from easygame.util.tween import TweenManager, Ease


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def game() -> Game:
    g = Game("Test", backend="mock", resolution=(800, 600))
    yield g
    g._teardown()


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


# ==================================================================
# 1. Game.__init__ singleton guard
# ==================================================================


class TestGameSingletonGuard:
    """Game.__init__ raises RuntimeError if another Game already exists."""

    def test_second_game_raises_runtime_error(self, game: Game) -> None:
        """Creating a second Game while one exists raises RuntimeError."""
        with pytest.raises(RuntimeError, match="Game instance already exists"):
            Game("Second", backend="mock", resolution=(800, 600))

    def test_can_create_after_teardown(self) -> None:
        """After _teardown(), a new Game can be created."""
        g1 = Game("First", backend="mock", resolution=(800, 600))
        g1._teardown()
        # Should not raise
        g2 = Game("Second", backend="mock", resolution=(800, 600))
        g2._teardown()


# ==================================================================
# 2. _particle_emitters is WeakSet
# ==================================================================


class TestParticleEmittersWeakSet:
    """Game._particle_emitters uses WeakSet so emitters can be GC'd."""

    def test_particle_emitters_is_weakset(self, game: Game) -> None:
        """_particle_emitters is a weakref.WeakSet."""
        assert isinstance(game._particle_emitters, weakref.WeakSet)

    def test_emitter_gc_removes_from_set(self, game: Game) -> None:
        """When an emitter is garbage collected, it disappears from the set."""

        class FakeEmitter:
            is_active = True

            def update(self, dt: float) -> None:
                pass

        emitter = FakeEmitter()
        game._particle_emitters.add(emitter)
        assert len(game._particle_emitters) == 1

        # Drop the only strong reference — WeakSet should lose it.
        del emitter
        assert len(game._particle_emitters) == 0


# ==================================================================
# 3. _cleanup_exiting_scene clears scene._ui
# ==================================================================


class TestCleanupClearsUI:
    """SceneStack._cleanup_exiting_scene clears scene._ui."""

    def test_ui_cleared_on_pop(self, game: Game) -> None:
        """Popping a scene clears its _ui attribute."""

        class UIScene(Scene):
            def on_enter(self) -> None:
                # Access .ui to force lazy creation.
                self.ui.add(MagicMock())

        scene = UIScene()
        game.push(scene)
        game.tick(dt=0.016)  # let it enter
        assert scene._ui is not None

        game.pop()
        game.tick(dt=0.016)  # flush deferred pop
        assert scene._ui is None

    def test_ui_cleared_on_replace(self, game: Game) -> None:
        """Replacing a scene clears its _ui attribute."""

        class UIScene(Scene):
            def on_enter(self) -> None:
                self.ui.add(MagicMock())

        old_scene = UIScene()
        game.push(old_scene)
        game.tick(dt=0.016)
        assert old_scene._ui is not None

        game.replace(Scene())
        game.tick(dt=0.016)
        assert old_scene._ui is None


# ==================================================================
# 4. DragManager.cancel_active
# ==================================================================


class TestDragManagerCancelActive:
    """DragManager.cancel_active cancels active drag sessions."""

    def test_cancel_active_clears_drag(self, game: Game) -> None:
        """cancel_active() ends an active drag session."""
        from easygame.ui.drag_drop import DragManager

        scene = Scene()
        game.push(scene)
        game.tick(dt=0.016)

        # Get the drag manager via the UI root.
        dm = scene.ui.drag_manager
        assert not dm.is_dragging

        # Simulate a drag session.
        source = MagicMock()
        source._computed_x = 10
        source._computed_y = 20
        dm._start_drag(source, data="test", x=15, y=25)
        assert dm.is_dragging

        dm.cancel_active()
        assert not dm.is_dragging

    def test_drag_cancelled_on_scene_exit(self, game: Game) -> None:
        """Active drag is cancelled when the scene is popped."""

        scene = Scene()
        game.push(scene)
        game.tick(dt=0.016)

        dm = scene.ui.drag_manager
        source = MagicMock()
        source._computed_x = 10
        source._computed_y = 20
        dm._start_drag(source, data="test", x=15, y=25)
        assert dm.is_dragging

        game.pop()
        game.tick(dt=0.016)
        # Drag should have been cancelled during cleanup.
        assert not dm.is_dragging


# ==================================================================
# 5. MockBackend.stop_player removes from _music_players
# ==================================================================


class TestStopPlayerRemovesEntry:
    """MockBackend.stop_player removes the entry from _music_players."""

    def test_stop_removes_player_entry(self, backend: MockBackend) -> None:
        """stop_player removes the player_id from _music_players dict."""
        handle = backend.load_music("battle.ogg")
        pid = backend.play_music(handle, volume=0.8)
        assert pid in backend._music_players

        backend.stop_player(pid)
        assert pid not in backend._music_players

    def test_stop_updates_convenience_fields(self, backend: MockBackend) -> None:
        """After stopping all players, music_playing is None."""
        h1 = backend.load_music("a.ogg")
        pid1 = backend.play_music(h1)
        backend.stop_player(pid1)

        assert backend.music_playing is None
        assert backend._music_players == {}

    def test_stop_with_multiple_players(self, backend: MockBackend) -> None:
        """Stopping one player when others exist updates correctly."""
        h1 = backend.load_music("a.ogg")
        h2 = backend.load_music("b.ogg")
        pid1 = backend.play_music(h1)
        pid2 = backend.play_music(h2)

        backend.stop_player(pid1)
        assert pid1 not in backend._music_players
        assert pid2 in backend._music_players
        assert backend.music_playing == h2


# ==================================================================
# 6. scene.game = None on pop/replace
# ==================================================================


class TestSceneGameNulledOnExit:
    """SceneStack sets scene.game = None when a scene leaves the stack."""

    def test_game_none_after_pop(self, game: Game) -> None:
        """Popped scene has game set to None."""
        scene = Scene()
        game.push(scene)
        game.tick(dt=0.016)
        assert scene.game is game

        game.pop()
        game.tick(dt=0.016)
        assert scene.game is None

    def test_game_none_after_replace(self, game: Game) -> None:
        """Replaced scene has game set to None."""
        old = Scene()
        game.push(old)
        game.tick(dt=0.016)
        assert old.game is game

        game.replace(Scene())
        game.tick(dt=0.016)
        assert old.game is None

    def test_game_none_after_clear_and_push(self, game: Game) -> None:
        """All cleared scenes have game set to None."""
        s1 = Scene()
        s2 = Scene()
        game.push(s1)
        game.tick(dt=0.016)
        game.push(s2)
        game.tick(dt=0.016)

        game.clear_and_push(Scene())
        game.tick(dt=0.016)
        assert s1.game is None
        assert s2.game is None

    def test_pushed_over_scene_keeps_game(self, game: Game) -> None:
        """Scene that is pushed OVER (not popped) retains game reference.

        Push causes on_exit for the old scene but it stays on the stack,
        so game should remain set.
        """
        bottom = Scene()
        game.push(bottom)
        game.tick(dt=0.016)

        game.push(Scene())
        game.tick(dt=0.016)
        # bottom is still on the stack (pushed over), game stays set.
        # Note: _cleanup_exiting_scene runs but game is NOT nulled for
        # push — only for pop/replace/clear.
        assert bottom.game is game


# ==================================================================
# 7. Game.tick draw phase try/finally
# ==================================================================


class TestDrawPhaseTryFinally:
    """Game.tick wraps draw in try/finally to ensure end_frame and
    _restore_sprites run even when draw raises."""

    def test_end_frame_called_on_draw_error(self, game: Game) -> None:
        """end_frame runs even when scene.draw() raises."""

        class ExplodingScene(Scene):
            def draw(self) -> None:
                raise RuntimeError("draw exploded")

        game.push(ExplodingScene())
        backend = game.backend

        initial_frames = backend.frame_count
        with pytest.raises(RuntimeError, match="draw exploded"):
            game.tick(dt=0.016)

        # end_frame should have run despite the exception.
        assert backend.frame_count == initial_frames + 1

    def test_sprite_positions_restored_on_draw_error(self, game: Game) -> None:
        """_restore_sprites runs even when scene.draw() raises.

        We verify by checking that the sprite's backend position is
        restored to the pre-camera value after a draw exception.
        """
        from easygame.rendering.camera import Camera
        from easygame.rendering.layers import SpriteAnchor
        from easygame import Sprite
        from easygame.assets import AssetManager

        backend = game.backend

        class CameraScene(Scene):
            first_draw = True

            def on_enter(self) -> None:
                self.camera = Camera(
                    viewport_size=(800, 600),
                    world_bounds=(0, 0, 1600, 1200),
                )
                self.sprite = self.add_sprite(
                    Sprite(
                        "sprites/knight",
                        position=(100, 100),
                        anchor=SpriteAnchor.TOP_LEFT,
                    )
                )

            def draw(self) -> None:
                if not self.first_draw:
                    raise RuntimeError("boom")
                self.first_draw = False

        scene = CameraScene()
        game.push(scene)
        # First tick: no error, establishes positions.
        game.tick(dt=0.016)

        # Record the sprite's backend position after first frame.
        sid = scene.sprite.sprite_id
        orig_x = backend.sprites[sid]["x"]
        orig_y = backend.sprites[sid]["y"]

        # Second tick: draw raises, but sprite positions should be restored.
        with pytest.raises(RuntimeError, match="boom"):
            game.tick(dt=0.016)

        assert backend.sprites[sid]["x"] == orig_x
        assert backend.sprites[sid]["y"] == orig_y


# ==================================================================
# 8. TimerManager/TweenManager callback try/except
# ==================================================================


class TestTimerCallbackSafety:
    """TimerManager wraps callbacks in try/except so failures don't
    prevent removal or cause double-fire."""

    def test_failing_timer_removed(self) -> None:
        """A timer whose callback raises is removed, not re-fired."""
        tm = TimerManager()
        call_count = 0

        def bad_callback() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("boom")

        tm.after(0.1, bad_callback)
        tm.update(0.2)  # fires and fails
        assert call_count == 1
        assert len(tm._timers) == 0  # removed despite error

    def test_failing_timer_does_not_block_others(self) -> None:
        """A failing timer doesn't prevent other timers from firing."""
        tm = TimerManager()
        results = []

        def bad() -> None:
            raise ValueError("boom")

        def good() -> None:
            results.append("ok")

        tm.after(0.1, bad)
        tm.after(0.1, good)
        tm.update(0.2)

        assert "ok" in results

    def test_failing_repeating_timer_removed(self) -> None:
        """A repeating timer whose callback raises is removed."""
        tm = TimerManager()
        call_count = 0

        def bad() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("boom")

        tm.every(0.1, bad)
        tm.update(0.2)  # fires and fails
        assert call_count == 1

        tm.update(0.2)  # should NOT fire again
        assert call_count == 1
        assert len(tm._timers) == 0


class TestTweenCallbackSafety:
    """TweenManager wraps on_complete in try/except so failures don't
    prevent tween removal or cause double-fire."""

    def test_failing_on_complete_tween_removed(self) -> None:
        """A tween whose on_complete raises is still removed."""
        tm = TweenManager()
        obj = type("Obj", (), {"val": 0.0})()
        call_count = 0

        def bad_complete() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("boom")

        tm.create(obj, "val", 0.0, 100.0, 0.5, on_complete=bad_complete)
        tm.update(1.0)  # completes and calls bad on_complete

        assert call_count == 1
        assert obj.val == 100.0  # final value still set
        assert len(tm._tweens) == 0  # removed despite error

    def test_failing_on_complete_does_not_block_others(self) -> None:
        """A failing on_complete doesn't prevent other tweens from completing."""
        tm = TweenManager()
        obj1 = type("Obj", (), {"val": 0.0})()
        obj2 = type("Obj", (), {"val": 0.0})()
        results = []

        def bad() -> None:
            raise ValueError("boom")

        def good() -> None:
            results.append("ok")

        tm.create(obj1, "val", 0.0, 10.0, 0.5, on_complete=bad)
        tm.create(obj2, "val", 0.0, 20.0, 0.5, on_complete=good)
        tm.update(1.0)

        assert obj1.val == 10.0
        assert obj2.val == 20.0
        assert "ok" in results
        assert len(tm._tweens) == 0
