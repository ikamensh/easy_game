"""Tests for Scene sprite ownership: add_sprite, remove_sprite, auto-cleanup."""

from pathlib import Path

import pytest

from easygame import Game, Scene, Sprite
from easygame.assets import AssetManager
from easygame.backends.mock_backend import MockBackend


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    """Create a temporary asset directory with test images."""
    images = tmp_path / "images"
    images.mkdir()
    sprites = images / "sprites"
    sprites.mkdir()
    (sprites / "knight.png").write_bytes(b"png")
    (sprites / "tree.png").write_bytes(b"png")
    (sprites / "arrow.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def game(asset_dir: Path) -> Game:
    """Return a Game with mock backend and assets."""
    g = Game("Test", backend="mock", resolution=(1920, 1080))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    return g


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


# ------------------------------------------------------------------
# add_sprite registers ownership
# ------------------------------------------------------------------

def test_add_sprite_returns_the_sprite(game: Game) -> None:
    """add_sprite returns the same sprite for chaining."""
    scene = Scene()
    game.push(scene)
    sprite = Sprite("sprites/knight", position=(100, 100))

    result = scene.add_sprite(sprite)

    assert result is sprite


def test_add_sprite_tracks_in_owned_set(game: Game) -> None:
    """add_sprite registers the sprite in the scene's owned set."""
    scene = Scene()
    game.push(scene)
    sprite = Sprite("sprites/knight", position=(100, 100))

    scene.add_sprite(sprite)

    assert sprite in scene._get_owned_sprites()


def test_add_sprite_sets_owning_scene_on_sprite(game: Game) -> None:
    """add_sprite sets _owning_scene back-reference on the sprite."""
    scene = Scene()
    game.push(scene)
    sprite = Sprite("sprites/knight", position=(100, 100))

    scene.add_sprite(sprite)

    assert sprite._owning_scene is scene


def test_add_sprite_ignores_removed_sprite(game: Game) -> None:
    """add_sprite on an already-removed sprite is a no-op."""
    scene = Scene()
    game.push(scene)
    sprite = Sprite("sprites/knight", position=(100, 100))
    sprite.remove()

    scene.add_sprite(sprite)

    assert sprite not in scene._get_owned_sprites()


# ------------------------------------------------------------------
# remove_sprite explicit removal
# ------------------------------------------------------------------

def test_remove_sprite_removes_from_backend(game: Game, backend: MockBackend) -> None:
    """remove_sprite destroys the sprite in the backend."""
    scene = Scene()
    game.push(scene)
    sprite = Sprite("sprites/knight", position=(100, 100))
    sid = sprite.sprite_id
    scene.add_sprite(sprite)

    scene.remove_sprite(sprite)

    assert sid not in backend.sprites
    assert sprite.is_removed


def test_remove_sprite_deregisters_from_owned_set(game: Game) -> None:
    """remove_sprite removes the sprite from the scene's owned set."""
    scene = Scene()
    game.push(scene)
    sprite = Sprite("sprites/knight", position=(100, 100))
    scene.add_sprite(sprite)

    scene.remove_sprite(sprite)

    assert sprite not in scene._get_owned_sprites()


def test_remove_sprite_safe_on_already_removed(game: Game) -> None:
    """remove_sprite on an already-removed sprite does not raise."""
    scene = Scene()
    game.push(scene)
    sprite = Sprite("sprites/knight", position=(100, 100))
    scene.add_sprite(sprite)
    sprite.remove()

    scene.remove_sprite(sprite)  # should not raise


def test_remove_sprite_safe_on_unowned(game: Game) -> None:
    """remove_sprite on a sprite not owned by this scene does not raise."""
    scene = Scene()
    game.push(scene)
    sprite = Sprite("sprites/knight", position=(100, 100))

    scene.remove_sprite(sprite)  # never added — should not raise

    assert sprite.is_removed


# ------------------------------------------------------------------
# Auto-cleanup on scene exit (pop)
# ------------------------------------------------------------------

def test_pop_removes_owned_sprites(game: Game, backend: MockBackend) -> None:
    """Popping a scene auto-removes all owned sprites."""
    class GameScene(Scene):
        def on_enter(self) -> None:
            self.s1 = self.add_sprite(
                Sprite("sprites/knight", position=(100, 100))
            )
            self.s2 = self.add_sprite(
                Sprite("sprites/tree", position=(200, 200))
            )

    scene = GameScene()
    game.push(scene)
    sid1 = scene.s1.sprite_id
    sid2 = scene.s2.sprite_id
    assert sid1 in backend.sprites
    assert sid2 in backend.sprites

    game.pop()

    assert sid1 not in backend.sprites
    assert sid2 not in backend.sprites
    assert scene.s1.is_removed
    assert scene.s2.is_removed


def test_pop_calls_on_exit_before_cleanup(game: Game) -> None:
    """User's on_exit runs before owned sprites are removed."""
    sprites_alive_in_on_exit = []

    class GameScene(Scene):
        def on_enter(self) -> None:
            self.s = self.add_sprite(
                Sprite("sprites/knight", position=(100, 100))
            )

        def on_exit(self) -> None:
            # Sprite should still be alive during on_exit
            sprites_alive_in_on_exit.append(not self.s.is_removed)

    game.push(GameScene())
    game.pop()

    assert sprites_alive_in_on_exit == [True]


def test_unowned_sprites_survive_scene_exit(game: Game, backend: MockBackend) -> None:
    """Sprites NOT added via add_sprite are NOT cleaned up on scene exit."""
    unowned_sprite = None

    class GameScene(Scene):
        def on_enter(self) -> None:
            nonlocal unowned_sprite
            self.owned = self.add_sprite(
                Sprite("sprites/knight", position=(100, 100))
            )
            unowned_sprite = Sprite("sprites/tree", position=(200, 200))

    scene = GameScene()
    game.push(scene)
    owned_sid = scene.owned.sprite_id
    unowned_sid = unowned_sprite.sprite_id

    game.pop()

    # Owned sprite is cleaned up.
    assert owned_sid not in backend.sprites
    # Unowned sprite survives.
    assert unowned_sid in backend.sprites
    assert not unowned_sprite.is_removed


# ------------------------------------------------------------------
# Auto-cleanup on push (old scene exits)
# ------------------------------------------------------------------

def test_push_cleans_up_old_scene_sprites(game: Game, backend: MockBackend) -> None:
    """Pushing a new scene cleans up the old scene's owned sprites."""
    class SceneA(Scene):
        def on_enter(self) -> None:
            self.s = self.add_sprite(
                Sprite("sprites/knight", position=(100, 100))
            )

    scene_a = SceneA()
    game.push(scene_a)
    sid = scene_a.s.sprite_id
    assert sid in backend.sprites

    game.push(Scene())  # pushes over SceneA → SceneA.on_exit + cleanup

    assert sid not in backend.sprites
    assert scene_a.s.is_removed


# ------------------------------------------------------------------
# Auto-cleanup on replace
# ------------------------------------------------------------------

def test_replace_cleans_up_old_scene_sprites(game: Game, backend: MockBackend) -> None:
    """Replacing a scene cleans up the old scene's owned sprites."""
    class SceneA(Scene):
        def on_enter(self) -> None:
            self.s = self.add_sprite(
                Sprite("sprites/knight", position=(100, 100))
            )

    scene_a = SceneA()
    game.push(scene_a)
    sid = scene_a.s.sprite_id

    game.replace(Scene())

    assert sid not in backend.sprites
    assert scene_a.s.is_removed


# ------------------------------------------------------------------
# Auto-cleanup on clear_and_push
# ------------------------------------------------------------------

def test_clear_and_push_cleans_up_all_scene_sprites(
    game: Game, backend: MockBackend,
) -> None:
    """clear_and_push cleans up sprites from ALL cleared scenes."""
    class SceneA(Scene):
        def on_enter(self) -> None:
            self.s = self.add_sprite(
                Sprite("sprites/knight", position=(100, 100))
            )

    class SceneB(Scene):
        def on_enter(self) -> None:
            self.s = self.add_sprite(
                Sprite("sprites/tree", position=(200, 200))
            )

    scene_a = SceneA()
    scene_b = SceneB()
    game.push(scene_a)
    game.push(scene_b)
    sid_a = scene_a.s.sprite_id
    sid_b = scene_b.s.sprite_id

    game.clear_and_push(Scene())

    assert sid_a not in backend.sprites
    assert sid_b not in backend.sprites


# ------------------------------------------------------------------
# Early removal via sprite.remove() deregisters from scene
# ------------------------------------------------------------------

def test_sprite_remove_deregisters_from_scene(game: Game) -> None:
    """Calling sprite.remove() directly deregisters from owning scene."""
    scene = Scene()
    game.push(scene)
    sprite = Sprite("sprites/knight", position=(100, 100))
    scene.add_sprite(sprite)

    sprite.remove()

    assert sprite not in scene._get_owned_sprites()
    assert sprite._owning_scene is None


def test_early_remove_then_scene_exit_no_double_remove(
    game: Game, backend: MockBackend,
) -> None:
    """Sprite removed early is not double-removed when scene exits."""

    class GameScene(Scene):
        def on_enter(self) -> None:
            self.s = self.add_sprite(
                Sprite("sprites/knight", position=(100, 100))
            )

    scene = GameScene()
    game.push(scene)
    # Remove early
    scene.s.remove()
    assert scene.s.is_removed

    # Scene exit should not try to remove it again (it's already gone).
    game.pop()  # should not raise


# ------------------------------------------------------------------
# Multiple sprites: partial early removal
# ------------------------------------------------------------------

def test_partial_early_removal(game: Game, backend: MockBackend) -> None:
    """Some sprites removed early, rest cleaned up on scene exit."""
    class GameScene(Scene):
        def on_enter(self) -> None:
            self.s1 = self.add_sprite(
                Sprite("sprites/knight", position=(100, 100))
            )
            self.s2 = self.add_sprite(
                Sprite("sprites/tree", position=(200, 200))
            )
            self.s3 = self.add_sprite(
                Sprite("sprites/arrow", position=(300, 300))
            )

    scene = GameScene()
    game.push(scene)
    sid1 = scene.s1.sprite_id
    sid2 = scene.s2.sprite_id
    sid3 = scene.s3.sprite_id

    # Remove s2 early
    scene.s2.remove()
    assert sid2 not in backend.sprites

    # Exit scene — s1 and s3 should be cleaned up
    game.pop()

    assert sid1 not in backend.sprites
    assert sid3 not in backend.sprites
    assert scene.s1.is_removed
    assert scene.s3.is_removed


# ------------------------------------------------------------------
# Scene with no owned sprites: cleanup is harmless
# ------------------------------------------------------------------

def test_scene_without_owned_sprites_exits_cleanly(game: Game) -> None:
    """A scene that never calls add_sprite exits without error."""
    game.push(Scene())
    game.pop()  # should not raise


# ------------------------------------------------------------------
# Deferred operations preserve cleanup semantics
# ------------------------------------------------------------------

def test_deferred_pop_cleans_up_sprites(game: Game, backend: MockBackend) -> None:
    """Deferred pop (during tick) still cleans up owned sprites."""
    class GameScene(Scene):
        def on_enter(self) -> None:
            self.s = self.add_sprite(
                Sprite("sprites/knight", position=(100, 100))
            )

        def update(self, dt: float) -> None:
            self.game.pop()

    scene = GameScene()
    game.push(scene)
    sid = scene.s.sprite_id

    game.tick(dt=0.016)

    assert sid not in backend.sprites
    assert scene.s.is_removed
