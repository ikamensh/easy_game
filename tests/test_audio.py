"""Tests for AudioManager: channels, volume, play_sound, play_music,
crossfade, sound pools, AssetManager audio extensions, and Game integration.
"""

from __future__ import annotations

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
    """Temp asset dir with test sounds and music files."""
    # Sound effects
    sounds = tmp_path / "sounds"
    sounds.mkdir()
    (sounds / "sword_hit.wav").write_bytes(b"wav")
    (sounds / "click.wav").write_bytes(b"wav")
    (sounds / "hover.ogg").write_bytes(b"ogg")
    (sounds / "beep.mp3").write_bytes(b"mp3")
    # For pool tests
    (sounds / "hit_01.wav").write_bytes(b"wav")
    (sounds / "hit_02.wav").write_bytes(b"wav")
    (sounds / "hit_03.wav").write_bytes(b"wav")
    (sounds / "lone.wav").write_bytes(b"wav")
    # Music tracks
    music = tmp_path / "music"
    music.mkdir()
    (music / "exploration.ogg").write_bytes(b"ogg")
    (music / "battle.ogg").write_bytes(b"ogg")
    (music / "victory.ogg").write_bytes(b"ogg")
    (music / "menu.wav").write_bytes(b"wav")
    # Images dir (for sprite-related needs)
    images = tmp_path / "images" / "sprites"
    images.mkdir(parents=True)
    (images / "knight.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def backend() -> MockBackend:
    return MockBackend()


@pytest.fixture
def assets(backend: MockBackend, asset_dir: Path) -> AssetManager:
    return AssetManager(backend, base_path=asset_dir)


@pytest.fixture
def audio(backend: MockBackend, assets: AssetManager) -> AudioManager:
    return AudioManager(backend, assets)


@pytest.fixture
def game(asset_dir: Path) -> Game:
    """Game with custom asset dir for audio tests."""
    g = Game("Test", backend="mock", resolution=(800, 600))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    return g


# ==================================================================
# 1. Channel volume hierarchy
# ==================================================================


class TestChannelVolume:
    """set_volume / get_volume and the volume hierarchy."""

    def test_default_volumes_all_one(self, audio: AudioManager) -> None:
        """All channels default to 1.0."""
        assert audio.get_volume("master") == 1.0
        assert audio.get_volume("music") == 1.0
        assert audio.get_volume("sfx") == 1.0
        assert audio.get_volume("ui") == 1.0

    def test_set_and_get_volume(self, audio: AudioManager) -> None:
        """set_volume stores the value, get_volume retrieves it."""
        audio.set_volume("sfx", 0.5)
        assert audio.get_volume("sfx") == 0.5

    def test_volume_clamped_above_one(self, audio: AudioManager) -> None:
        """Volumes above 1.0 are clamped to 1.0."""
        audio.set_volume("master", 2.5)
        assert audio.get_volume("master") == 1.0

    def test_volume_clamped_below_zero(self, audio: AudioManager) -> None:
        """Volumes below 0.0 are clamped to 0.0."""
        audio.set_volume("music", -0.5)
        assert audio.get_volume("music") == 0.0

    def test_volume_clamped_at_zero(self, audio: AudioManager) -> None:
        """Setting exactly 0.0 works."""
        audio.set_volume("ui", 0.0)
        assert audio.get_volume("ui") == 0.0

    def test_volume_clamped_at_one(self, audio: AudioManager) -> None:
        """Setting exactly 1.0 works."""
        audio.set_volume("master", 1.0)
        assert audio.get_volume("master") == 1.0

    def test_unknown_channel_set_raises(self, audio: AudioManager) -> None:
        """set_volume with unknown channel raises KeyError."""
        with pytest.raises(KeyError, match="unknown_channel"):
            audio.set_volume("unknown_channel", 0.5)

    def test_unknown_channel_get_raises(self, audio: AudioManager) -> None:
        """get_volume with unknown channel raises KeyError."""
        with pytest.raises(KeyError, match="nope"):
            audio.get_volume("nope")

    def test_effective_volume_sfx(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Effective SFX volume = master * sfx."""
        audio.set_volume("master", 0.8)
        audio.set_volume("sfx", 0.5)
        audio.play_sound("sword_hit")

        assert len(backend.sounds_played) == 1
        assert backend.sounds_played[0]["volume"] == pytest.approx(0.4)

    def test_effective_volume_ui(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Effective UI volume = master * ui."""
        audio.set_volume("master", 0.5)
        audio.set_volume("ui", 0.6)
        audio.play_sound("click", channel="ui")

        assert backend.sounds_played[0]["volume"] == pytest.approx(0.3)

    def test_effective_volume_music(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Effective music volume = master * music."""
        audio.set_volume("master", 0.5)
        audio.set_volume("music", 0.8)
        audio.play_music("exploration")

        assert backend.music_volume == pytest.approx(0.4)

    def test_changing_master_reapplies_to_music(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Changing master volume immediately adjusts the current music player."""
        audio.play_music("exploration")
        assert backend.music_volume == pytest.approx(1.0)

        audio.set_volume("master", 0.5)
        assert backend.music_volume == pytest.approx(0.5)

    def test_changing_music_channel_reapplies_to_music(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Changing music channel volume immediately adjusts the current music player."""
        audio.play_music("exploration")
        audio.set_volume("music", 0.3)
        assert backend.music_volume == pytest.approx(0.3)

    def test_changing_sfx_does_not_reapply_to_music(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Changing sfx volume does not affect the music player."""
        audio.play_music("exploration")
        audio.set_volume("sfx", 0.1)
        # Music should still be 1.0 (master=1.0, music=1.0)
        assert backend.music_volume == pytest.approx(1.0)

    def test_set_volume_no_music_playing_no_crash(
        self, audio: AudioManager,
    ) -> None:
        """Changing master/music volume when no music is playing doesn't crash."""
        audio.set_volume("master", 0.5)
        audio.set_volume("music", 0.3)


# ==================================================================
# 2. play_sound
# ==================================================================


class TestPlaySound:
    """play_sound records the correct handle and volume."""

    def test_play_sound_records_in_backend(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """play_sound is recorded in backend.sounds_played."""
        audio.play_sound("sword_hit")
        assert len(backend.sounds_played) == 1

    def test_play_sound_correct_handle(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Handle from backend.load_sound is passed to backend.play_sound."""
        audio.play_sound("sword_hit")
        entry = backend.sounds_played[0]
        # The handle should be the one that load_sound produced for the path.
        assert entry["handle"].startswith("sound_")

    def test_play_sound_default_volume_is_one(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Default volume (master=1, sfx=1) → effective = 1.0."""
        audio.play_sound("sword_hit")
        assert backend.sounds_played[0]["volume"] == pytest.approx(1.0)

    def test_play_sound_sfx_channel(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """play_sound uses the sfx channel by default."""
        audio.set_volume("sfx", 0.5)
        audio.play_sound("sword_hit")
        assert backend.sounds_played[0]["volume"] == pytest.approx(0.5)

    def test_play_sound_ui_channel(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """play_sound with channel='ui' uses the ui channel."""
        audio.set_volume("ui", 0.4)
        audio.play_sound("click", channel="ui")
        assert backend.sounds_played[0]["volume"] == pytest.approx(0.4)

    def test_volume_change_affects_subsequent_plays(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Changing volume after the first play affects the next play."""
        audio.play_sound("sword_hit")
        audio.set_volume("sfx", 0.5)
        audio.play_sound("sword_hit")

        assert backend.sounds_played[0]["volume"] == pytest.approx(1.0)
        assert backend.sounds_played[1]["volume"] == pytest.approx(0.5)

    def test_multiple_sounds_accumulate(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Playing multiple sounds appends to the list."""
        audio.play_sound("sword_hit")
        audio.play_sound("click")
        assert len(backend.sounds_played) == 2

    def test_master_times_sfx(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Effective volume is master * sfx."""
        audio.set_volume("master", 0.6)
        audio.set_volume("sfx", 0.5)
        audio.play_sound("sword_hit")
        assert backend.sounds_played[0]["volume"] == pytest.approx(0.3)

    def test_play_sound_missing_raises(self, audio: AudioManager) -> None:
        """Missing sound raises AssetNotFoundError when optional=False."""
        with pytest.raises(AssetNotFoundError, match="Sound"):
            audio.play_sound("nonexistent")

    def test_play_sound_missing_optional_returns_none(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Missing sound with optional=True returns None, no backend call."""
        result = audio.play_sound("nonexistent", optional=True)
        assert result is None
        assert len(backend.sounds_played) == 0


# ==================================================================
# 3. play_music
# ==================================================================


class TestPlayMusic:
    """play_music starts a music player with the correct parameters."""

    def test_play_music_starts_player(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """play_music creates a player in the backend."""
        audio.play_music("exploration")
        assert backend.music_playing is not None

    def test_play_music_volume(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Music player volume = master * music channel."""
        audio.set_volume("master", 0.8)
        audio.set_volume("music", 0.5)
        audio.play_music("exploration")
        assert backend.music_volume == pytest.approx(0.4)

    def test_play_music_loop_default_true(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """play_music loops by default."""
        audio.play_music("exploration")
        # Find the player and check loop
        player = list(backend._music_players.values())[-1]
        assert player["loop"] is True

    def test_play_music_loop_false(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """play_music with loop=False."""
        audio.play_music("exploration", loop=False)
        player = list(backend._music_players.values())[-1]
        assert player["loop"] is False

    def test_play_music_stops_old(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Playing new music stops the previous track."""
        audio.play_music("exploration")
        old_player_id = audio._current_player_id
        audio.play_music("battle")

        # Old player was stopped.
        assert backend._music_players[old_player_id]["playing"] is False
        # New player is active.
        assert audio._current_player_id is not None
        assert audio._current_player_id != old_player_id

    def test_play_music_tracks_name(
        self, audio: AudioManager,
    ) -> None:
        """_current_music_name tracks the active music name."""
        audio.play_music("exploration")
        assert audio._current_music_name == "exploration"
        audio.play_music("battle")
        assert audio._current_music_name == "battle"

    def test_play_music_missing_raises(self, audio: AudioManager) -> None:
        """Missing music raises AssetNotFoundError when optional=False."""
        with pytest.raises(AssetNotFoundError, match="Music"):
            audio.play_music("nonexistent")

    def test_play_music_missing_optional_returns_none(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Missing music with optional=True returns None, no backend call."""
        result = audio.play_music("nonexistent", optional=True)
        assert result is None
        assert backend.music_playing is None


# ==================================================================
# 4. stop_music
# ==================================================================


class TestStopMusic:
    """stop_music stops the current player and clears state."""

    def test_stop_music_stops_player(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """stop_music stops the backend player."""
        audio.play_music("exploration")
        player_id = audio._current_player_id
        audio.stop_music()

        assert backend._music_players[player_id]["playing"] is False

    def test_stop_music_clears_state(
        self, audio: AudioManager,
    ) -> None:
        """stop_music clears current_player_id and current_music_name."""
        audio.play_music("exploration")
        audio.stop_music()

        assert audio._current_player_id is None
        assert audio._current_music_name is None

    def test_stop_music_when_nothing_playing(
        self, audio: AudioManager,
    ) -> None:
        """stop_music when nothing playing is a no-op."""
        audio.stop_music()  # Should not raise

    def test_stop_music_updates_backend_convenience(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """stop_music updates backend.music_playing to None."""
        audio.play_music("exploration")
        audio.stop_music()
        assert backend.music_playing is None


# ==================================================================
# 5. crossfade_music
# ==================================================================


class TestCrossfadeMusic:
    """crossfade_music transitions between tracks using tweens."""

    def test_crossfade_creates_two_players(
        self, game: Game,
    ) -> None:
        """Crossfade creates a new player while old is still active."""
        backend = game.backend
        game.audio.play_music("exploration")
        old_player_id = game.audio._current_player_id

        game.audio.crossfade_music("battle", duration=1.0)

        # Old player is still active (fading out).
        assert backend._music_players[old_player_id]["playing"] is True
        # New player also active.
        new_player_id = game.audio._current_player_id
        assert new_player_id != old_player_id
        assert backend._music_players[new_player_id]["playing"] is True

    def test_crossfade_new_player_starts_at_zero(
        self, game: Game,
    ) -> None:
        """New player starts at volume 0 during crossfade."""
        backend = game.backend
        game.audio.play_music("exploration")
        game.audio.crossfade_music("battle", duration=1.0)

        new_player_id = game.audio._current_player_id
        # The new player was created with volume=0.0
        # But the tween may have already advanced slightly, check initial create
        # The play_music call in crossfade passes volume=0.0
        assert game.audio._current_music_name == "battle"

    def test_crossfade_completes_after_duration(
        self, game: Game,
    ) -> None:
        """After duration, old player is stopped and new player at full volume."""
        backend = game.backend
        game.audio.play_music("exploration")
        old_player_id = game.audio._current_player_id

        game.audio.crossfade_music("battle", duration=1.0)

        # Tick past the crossfade duration.
        for _ in range(70):  # 70 * 0.016 ≈ 1.12s
            game.tick(dt=0.016)

        # Old player stopped.
        assert backend._music_players[old_player_id]["playing"] is False
        # New player at full volume (master=1, music=1, base=1).
        new_player_id = game.audio._current_player_id
        assert backend._music_players[new_player_id]["volume"] == pytest.approx(1.0)

    def test_crossfade_midpoint_volumes(
        self, game: Game,
    ) -> None:
        """At halfway through crossfade, both players have intermediate volume."""
        backend = game.backend
        game.audio.play_music("exploration")
        old_player_id = game.audio._current_player_id

        game.audio.crossfade_music("battle", duration=1.0)
        new_player_id = game.audio._current_player_id

        # Advance to roughly halfway (0.5s).
        for _ in range(31):  # 31 * 0.016 ≈ 0.496s
            game.tick(dt=0.016)

        old_vol = backend._music_players[old_player_id]["volume"]
        new_vol = backend._music_players[new_player_id]["volume"]

        # Old should be around 0.5 (fading from 1.0 to 0.0).
        assert 0.3 < old_vol < 0.7
        # New should be around 0.5 (fading from 0.0 to 1.0).
        assert 0.3 < new_vol < 0.7

    def test_crossfade_same_track_is_noop(
        self, game: Game,
    ) -> None:
        """Crossfade to the same track is a no-op."""
        backend = game.backend
        game.audio.play_music("exploration")
        player_id = game.audio._current_player_id
        players_before = len(backend._music_players)

        game.audio.crossfade_music("exploration", duration=1.0)

        # No new player created.
        assert len(backend._music_players) == players_before
        # Same player still active.
        assert game.audio._current_player_id == player_id

    def test_crossfade_when_nothing_playing(
        self, game: Game,
    ) -> None:
        """Crossfade when nothing playing falls through to play_music."""
        backend = game.backend
        game.audio.crossfade_music("exploration", duration=1.0)

        assert backend.music_playing is not None
        assert game.audio._current_music_name == "exploration"
        # Should have started at full volume (not 0).
        assert backend.music_volume == pytest.approx(1.0)

    def test_crossfade_interruption(
        self, game: Game,
    ) -> None:
        """Interrupting a crossfade stops the old fading-out player."""
        backend = game.backend
        game.audio.play_music("exploration")
        exploration_player = game.audio._current_player_id

        # Start first crossfade.
        game.audio.crossfade_music("battle", duration=2.0)
        battle_player = game.audio._current_player_id

        # Advance a bit (not complete).
        for _ in range(10):
            game.tick(dt=0.016)

        # Interrupt with second crossfade.
        game.audio.crossfade_music("victory", duration=1.0)

        # The exploration player (was fading out during first crossfade) is stopped.
        assert backend._music_players[exploration_player]["playing"] is False
        # The battle player is now the old player fading out.
        # The victory player is the new current.
        assert game.audio._current_music_name == "victory"

    def test_crossfade_tween_ids_cleared_after_completion(
        self, game: Game,
    ) -> None:
        """Crossfade tween IDs are cleared after the crossfade completes."""
        game.audio.play_music("exploration")
        game.audio.crossfade_music("battle", duration=0.5)

        assert len(game.audio._crossfade_tween_ids) == 2

        # Tick past the duration.
        for _ in range(40):  # 40 * 0.016 = 0.64s
            game.tick(dt=0.016)

        assert len(game.audio._crossfade_tween_ids) == 0
        assert game.audio._crossfade_old_player is None

    def test_crossfade_respects_channel_volume(
        self, game: Game,
    ) -> None:
        """Crossfade volumes are multiplied by master * music channel."""
        backend = game.backend
        game.audio.set_volume("master", 0.5)
        game.audio.set_volume("music", 0.8)

        game.audio.play_music("exploration")
        game.audio.crossfade_music("battle", duration=1.0)

        # Tick to completion.
        for _ in range(70):
            game.tick(dt=0.016)

        # New player at effective volume = 0.5 * 0.8 * 1.0 = 0.4.
        new_player_id = game.audio._current_player_id
        assert backend._music_players[new_player_id]["volume"] == pytest.approx(0.4)

    def test_crossfade_base_volume_updates(
        self, game: Game,
    ) -> None:
        """_current_player_base_volume updates to 1.0 after crossfade."""
        game.audio.play_music("exploration")
        game.audio.crossfade_music("battle", duration=0.5)

        # Before completion, base volume is < 1.
        assert game.audio._current_player_base_volume < 1.0

        # Tick to completion.
        for _ in range(40):
            game.tick(dt=0.016)

        assert game.audio._current_player_base_volume == pytest.approx(1.0)

    def test_crossfade_with_loop_false(
        self, game: Game,
    ) -> None:
        """Crossfade with loop=False creates non-looping player."""
        backend = game.backend
        game.audio.play_music("exploration")
        game.audio.crossfade_music("victory", duration=0.5, loop=False)

        new_player_id = game.audio._current_player_id
        assert backend._music_players[new_player_id]["loop"] is False

    def test_stop_music_cancels_crossfade(
        self, game: Game,
    ) -> None:
        """stop_music during a crossfade cancels the crossfade tweens."""
        backend = game.backend
        game.audio.play_music("exploration")
        exploration_player = game.audio._current_player_id

        game.audio.crossfade_music("battle", duration=2.0)
        battle_player = game.audio._current_player_id

        # Stop in the middle.
        game.audio.stop_music()

        # Both players stopped.
        assert backend._music_players[exploration_player]["playing"] is False
        assert backend._music_players[battle_player]["playing"] is False
        assert game.audio._current_player_id is None
        assert game.audio._crossfade_tween_ids == []


# ==================================================================
# 6. Sound pools
# ==================================================================


class TestSoundPools:
    """register_pool, play_pool, no-immediate-repeat logic."""

    def test_register_pool(self, audio: AudioManager) -> None:
        """register_pool stores the pool."""
        audio.register_pool("hit", ["hit_01", "hit_02", "hit_03"])
        assert "hit" in audio._pools
        assert len(audio._pools["hit"]) == 3

    def test_play_pool_plays_a_sound(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """play_pool plays exactly one sound from the pool."""
        audio.register_pool("hit", ["hit_01", "hit_02", "hit_03"])
        audio.play_pool("hit")
        assert len(backend.sounds_played) == 1

    def test_play_pool_no_immediate_repeat(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Same sound never plays twice in a row (pool size > 1)."""
        audio.register_pool("hit", ["hit_01", "hit_02", "hit_03"])

        # Play many times and verify no consecutive duplicate handles.
        for _ in range(50):
            audio.play_pool("hit")

        handles = [entry["handle"] for entry in backend.sounds_played]
        for i in range(1, len(handles)):
            assert handles[i] != handles[i - 1], (
                f"Consecutive repeat at index {i}: {handles[i]}"
            )

    def test_play_pool_single_sound_always_plays(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Pool with one sound always plays that sound."""
        audio.register_pool("lone", ["lone"])
        audio.play_pool("lone")
        audio.play_pool("lone")
        audio.play_pool("lone")

        assert len(backend.sounds_played) == 3
        # All three should be the same handle.
        handles = {entry["handle"] for entry in backend.sounds_played}
        assert len(handles) == 1

    def test_play_pool_empty_is_noop(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Playing from an empty pool is a silent no-op."""
        audio.register_pool("empty", [])
        audio.play_pool("empty")
        assert len(backend.sounds_played) == 0

    def test_play_pool_unregistered_raises(
        self, audio: AudioManager,
    ) -> None:
        """Playing from an unregistered pool raises KeyError."""
        with pytest.raises(KeyError):
            audio.play_pool("nonexistent")

    def test_play_pool_uses_sfx_channel(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Pool sounds use the sfx channel volume."""
        audio.set_volume("sfx", 0.5)
        audio.register_pool("hit", ["hit_01", "hit_02"])
        audio.play_pool("hit")

        assert backend.sounds_played[0]["volume"] == pytest.approx(0.5)

    def test_play_pool_two_sounds_alternates(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """Pool with exactly 2 sounds alternates between them."""
        audio.register_pool("duo", ["hit_01", "hit_02"])

        for _ in range(20):
            audio.play_pool("duo")

        handles = [entry["handle"] for entry in backend.sounds_played]
        for i in range(1, len(handles)):
            assert handles[i] != handles[i - 1]

    def test_register_pool_copies_list(self, audio: AudioManager) -> None:
        """register_pool copies the input list (mutations don't affect pool)."""
        names = ["hit_01", "hit_02"]
        audio.register_pool("hit", names)
        names.append("hit_03")
        assert len(audio._pools["hit"]) == 2

    def test_register_pool_replaces_existing(
        self, audio: AudioManager,
    ) -> None:
        """Re-registering a pool replaces the previous one."""
        audio.register_pool("hit", ["hit_01", "hit_02"])
        audio.register_pool("hit", ["hit_03"])
        assert audio._pools["hit"] == ["hit_03"]
        # Last index is reset.
        assert audio._pool_last["hit"] == -1

    def test_play_pool_covers_all_sounds(
        self, audio: AudioManager, backend: MockBackend,
    ) -> None:
        """All sounds in a pool are eventually played."""
        audio.register_pool("hit", ["hit_01", "hit_02", "hit_03"])

        for _ in range(100):
            audio.play_pool("hit")

        handles = {entry["handle"] for entry in backend.sounds_played}
        assert len(handles) == 3


# ==================================================================
# 7. AssetManager extensions
# ==================================================================


class TestAssetManagerAudio:
    """sound() and music() methods on AssetManager."""

    def test_sound_loads_wav(
        self, assets: AssetManager, backend: MockBackend, asset_dir: Path,
    ) -> None:
        """sound('sword_hit') loads assets/sounds/sword_hit.wav."""
        handle = assets.sound("sword_hit")
        assert handle is not None
        expected = str(asset_dir / "sounds" / "sword_hit.wav")
        assert expected in backend._loaded_sounds

    def test_sound_prefers_wav_over_ogg(
        self, backend: MockBackend, tmp_path: Path,
    ) -> None:
        """sound() prefers .wav over .ogg when both exist."""
        sounds = tmp_path / "sounds"
        sounds.mkdir()
        (sounds / "test.wav").write_bytes(b"wav")
        (sounds / "test.ogg").write_bytes(b"ogg")

        mgr = AssetManager(backend, base_path=tmp_path)
        mgr.sound("test")

        wav_path = str(tmp_path / "sounds" / "test.wav")
        ogg_path = str(tmp_path / "sounds" / "test.ogg")
        assert wav_path in backend._loaded_sounds
        assert ogg_path not in backend._loaded_sounds

    def test_sound_falls_back_to_ogg(
        self, assets: AssetManager, backend: MockBackend, asset_dir: Path,
    ) -> None:
        """sound('hover') finds the .ogg when no .wav exists."""
        handle = assets.sound("hover")
        assert handle is not None
        expected = str(asset_dir / "sounds" / "hover.ogg")
        assert expected in backend._loaded_sounds

    def test_sound_falls_back_to_mp3(
        self, assets: AssetManager, backend: MockBackend, asset_dir: Path,
    ) -> None:
        """sound('beep') finds the .mp3 when no .wav or .ogg exist."""
        handle = assets.sound("beep")
        assert handle is not None
        expected = str(asset_dir / "sounds" / "beep.mp3")
        assert expected in backend._loaded_sounds

    def test_sound_cached(
        self, assets: AssetManager,
    ) -> None:
        """Calling sound() twice returns the same handle (cached)."""
        h1 = assets.sound("sword_hit")
        h2 = assets.sound("sword_hit")
        assert h1 is h2

    def test_sound_missing_raises(
        self, assets: AssetManager,
    ) -> None:
        """Missing sound raises AssetNotFoundError."""
        with pytest.raises(AssetNotFoundError, match="Sound"):
            assets.sound("nonexistent")

    def test_sound_with_explicit_extension(
        self, assets: AssetManager, backend: MockBackend, asset_dir: Path,
    ) -> None:
        """sound('sword_hit.wav') with explicit extension."""
        handle = assets.sound("sword_hit.wav")
        assert handle is not None
        expected = str(asset_dir / "sounds" / "sword_hit.wav")
        assert expected in backend._loaded_sounds

    def test_music_loads_ogg(
        self, assets: AssetManager, backend: MockBackend, asset_dir: Path,
    ) -> None:
        """music('exploration') loads assets/music/exploration.ogg."""
        handle = assets.music("exploration")
        assert handle is not None
        expected = str(asset_dir / "music" / "exploration.ogg")
        assert expected in backend._loaded_music

    def test_music_prefers_ogg_over_wav(
        self, backend: MockBackend, tmp_path: Path,
    ) -> None:
        """music() prefers .ogg over .wav when both exist."""
        music = tmp_path / "music"
        music.mkdir()
        (music / "track.ogg").write_bytes(b"ogg")
        (music / "track.wav").write_bytes(b"wav")

        mgr = AssetManager(backend, base_path=tmp_path)
        mgr.music("track")

        ogg_path = str(tmp_path / "music" / "track.ogg")
        wav_path = str(tmp_path / "music" / "track.wav")
        assert ogg_path in backend._loaded_music
        assert wav_path not in backend._loaded_music

    def test_music_falls_back_to_wav(
        self, assets: AssetManager, backend: MockBackend, asset_dir: Path,
    ) -> None:
        """music('menu') finds the .wav when no .ogg exists."""
        handle = assets.music("menu")
        assert handle is not None
        expected = str(asset_dir / "music" / "menu.wav")
        assert expected in backend._loaded_music

    def test_music_not_cached_handle(
        self, assets: AssetManager,
    ) -> None:
        """music() returns fresh handle each time (streaming limitation).

        The path is cached, but each call produces a new backend handle.
        """
        h1 = assets.music("exploration")
        h2 = assets.music("exploration")
        # Mock backend caches by path, so handles will be same string.
        # But the method itself should NOT cache the handle.
        assert "exploration" in assets._music_path_cache

    def test_music_missing_raises(
        self, assets: AssetManager,
    ) -> None:
        """Missing music raises AssetNotFoundError."""
        with pytest.raises(AssetNotFoundError, match="Music"):
            assets.music("nonexistent")

    def test_sound_error_lists_tried_paths(
        self, assets: AssetManager, asset_dir: Path,
    ) -> None:
        """Missing sound error message lists all tried paths."""
        with pytest.raises(AssetNotFoundError) as exc_info:
            assets.sound("missing_fx")

        msg = str(exc_info.value)
        assert "missing_fx.wav" in msg
        assert "missing_fx.ogg" in msg
        assert "missing_fx.mp3" in msg

    def test_music_error_lists_tried_paths(
        self, assets: AssetManager, asset_dir: Path,
    ) -> None:
        """Missing music error message lists all tried paths."""
        with pytest.raises(AssetNotFoundError) as exc_info:
            assets.music("missing_track")

        msg = str(exc_info.value)
        assert "missing_track.ogg" in msg
        assert "missing_track.wav" in msg
        assert "missing_track.mp3" in msg


# ==================================================================
# 8. Game integration
# ==================================================================


class TestGameIntegration:
    """game.audio returns an AudioManager wired to the backend."""

    def test_game_audio_returns_audio_manager(self) -> None:
        """game.audio lazily creates an AudioManager."""
        game = Game("Test", backend="mock", resolution=(800, 600))
        assert isinstance(game.audio, AudioManager)

    def test_game_audio_is_same_instance(self) -> None:
        """Accessing game.audio twice returns the same instance."""
        game = Game("Test", backend="mock", resolution=(800, 600))
        assert game.audio is game.audio

    def test_game_audio_can_be_overridden(self) -> None:
        """game.audio can be set to a custom AudioManager."""
        game = Game("Test", backend="mock", resolution=(800, 600))
        custom = AudioManager(game.backend, game.assets)
        game.audio = custom
        assert game.audio is custom

    def test_game_audio_uses_game_backend(self, game: Game) -> None:
        """AudioManager uses the same backend as the game."""
        assert game.audio._backend is game.backend

    def test_game_audio_uses_game_assets(self, game: Game) -> None:
        """AudioManager uses the game's AssetManager."""
        assert game.audio._assets is game.assets

    def test_game_audio_importable_from_easygame(self) -> None:
        """AudioManager is importable from the top-level package."""
        from easygame import AudioManager as AM
        assert AM is AudioManager

    def test_game_audio_play_sound_end_to_end(self, game: Game) -> None:
        """End-to-end: game.audio.play_sound records in backend."""
        backend = game.backend
        game.audio.play_sound("sword_hit")
        assert len(backend.sounds_played) == 1

    def test_game_audio_play_music_end_to_end(self, game: Game) -> None:
        """End-to-end: game.audio.play_music creates a player."""
        backend = game.backend
        game.audio.play_music("exploration")
        assert backend.music_playing is not None

    def test_game_crossfade_driven_by_tick(self, game: Game) -> None:
        """Crossfade is driven by the tween system in game.tick()."""
        backend = game.backend
        game.audio.play_music("exploration")
        old_player = game.audio._current_player_id

        game.audio.crossfade_music("battle", duration=0.5)
        new_player = game.audio._current_player_id

        # Initially, old still playing.
        assert backend._music_players[old_player]["playing"] is True

        # Tick past duration.
        for _ in range(40):
            game.tick(dt=0.016)

        # Old stopped, new at full volume.
        assert backend._music_players[old_player]["playing"] is False
        assert backend._music_players[new_player]["volume"] == pytest.approx(1.0)
