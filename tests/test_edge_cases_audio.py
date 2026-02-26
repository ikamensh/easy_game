"""Edge-case tests for AudioManager."""

from pathlib import Path

import pytest

from easygame import Game
from easygame.assets import AssetManager, AssetNotFoundError
from easygame.audio import AudioManager
from easygame.backends.mock_backend import MockBackend


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    """Temp asset dir with sounds and music."""
    sounds = tmp_path / "sounds"
    sounds.mkdir()
    (sounds / "sword_hit.wav").write_bytes(b"wav")
    music = tmp_path / "music"
    music.mkdir()
    (music / "exploration.ogg").write_bytes(b"ogg")
    (music / "battle.ogg").write_bytes(b"ogg")
    images = tmp_path / "images" / "sprites"
    images.mkdir(parents=True)
    (images / "knight.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def game(asset_dir: Path) -> Game:
    g = Game("Test", backend="mock", resolution=(800, 600))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    yield g
    g._teardown()


# ------------------------------------------------------------------
# 1. play_sound with nonexistent asset
# ------------------------------------------------------------------


def test_play_sound_nonexistent_raises(game: Game) -> None:
    """play_sound with nonexistent asset and optional=False raises AssetNotFoundError."""
    with pytest.raises(AssetNotFoundError):
        game.audio.play_sound("nonexistent")


def test_play_sound_nonexistent_optional_noop(game: Game) -> None:
    """play_sound with nonexistent asset and optional=True is no-op; no backend call."""
    result = game.audio.play_sound("nonexistent", optional=True)
    assert result is None
    assert len(game.backend.sounds_played) == 0


# ------------------------------------------------------------------
# 2. crossfade_music to the same track
# ------------------------------------------------------------------


def test_crossfade_same_track_no_new_play(game: Game) -> None:
    """crossfade_music to the same track creates no new player."""
    backend = game.backend
    game.audio.play_music("exploration")
    player_id = game.audio._current_player_id
    players_before = len(backend._music_players)

    game.audio.crossfade_music("exploration", duration=1.0)

    assert len(backend._music_players) == players_before
    assert game.audio._current_player_id == player_id


# ------------------------------------------------------------------
# 3. crossfade_music when no music is playing
# ------------------------------------------------------------------


def test_crossfade_no_music_just_plays(game: Game) -> None:
    """crossfade_music when nothing playing delegates to play_music."""
    backend = game.backend
    game.audio.crossfade_music("exploration", duration=1.0)

    assert backend.music_playing is not None
    assert game.audio._current_music_name == "exploration"
    assert backend.music_volume == pytest.approx(1.0)


# ------------------------------------------------------------------
# 4. set_volume and play_sound on unknown channel
# ------------------------------------------------------------------


def test_play_sound_unknown_channel_raises(game: Game) -> None:
    """play_sound with unknown channel raises KeyError (consistent with set_volume)."""
    with pytest.raises(KeyError, match="Unknown audio channel"):
        game.audio.play_sound("sword_hit", channel="unknown")


def test_set_volume_unknown_channel_raises(game: Game) -> None:
    """set_volume with unknown channel raises KeyError."""
    with pytest.raises(KeyError, match="unknown"):
        game.audio.set_volume("unknown", 0.5)


# ------------------------------------------------------------------
# 5. play_pool on empty pool
# ------------------------------------------------------------------


def test_play_pool_empty_noop(game: Game) -> None:
    """play_pool on empty pool is no-op; no sound played."""
    game.audio.register_pool("empty", [])
    game.audio.play_pool("empty")

    assert len(game.backend.sounds_played) == 0


# ------------------------------------------------------------------
# 6. play_pool with unknown pool name
# ------------------------------------------------------------------


def test_play_pool_unknown_raises(game: Game) -> None:
    """play_pool with unregistered pool name raises KeyError."""
    with pytest.raises(KeyError):
        game.audio.play_pool("nonexistent_pool")


# ------------------------------------------------------------------
# 7. crossfade_music with duration=0
# ------------------------------------------------------------------


def test_crossfade_duration_zero(game: Game) -> None:
    """crossfade_music with duration=0 completes in one tick."""
    backend = game.backend
    game.audio.play_music("exploration")
    old_player_id = game.audio._current_player_id

    game.audio.crossfade_music("battle", duration=0.0)

    game.tick(dt=0.016)

    assert game.audio._current_music_name == "battle"
    assert old_player_id not in backend._music_players
    assert game.audio._crossfade_tween_ids == []


# ------------------------------------------------------------------
# 8. set_volume with NaN/Inf level
# ------------------------------------------------------------------


def test_set_volume_nan_clamped(game: Game) -> None:
    """set_volume with NaN level is clamped (min/max behavior)."""
    game.audio.set_volume("master", float("nan"))
    val = game.audio.get_volume("master")
    assert 0.0 <= val <= 1.0


def test_set_volume_inf_clamped(game: Game) -> None:
    """set_volume with Inf level is clamped to 1.0."""
    game.audio.set_volume("sfx", float("inf"))
    assert game.audio.get_volume("sfx") == 1.0


def test_set_volume_neg_inf_clamped(game: Game) -> None:
    """set_volume with -Inf level is clamped to 0.0."""
    game.audio.set_volume("music", float("-inf"))
    assert game.audio.get_volume("music") == 0.0
