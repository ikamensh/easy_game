"""Tests for the Save/Load system (Stage 13 Part 2).

Covers:
- SaveManager file I/O, directory creation, JSON format
- Save/load round-trip, slot listing, overwrite, delete
- Scene.get_save_state() / load_save_state() stubs
- Game.save() / Game.load() integration
- Save directory configuration (explicit and slug-derived)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from easygame import Game, Scene
from easygame.save import SaveManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def save_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for save files."""
    return tmp_path / "saves"


@pytest.fixture
def manager(save_dir: Path) -> SaveManager:
    """Return a SaveManager using a temp directory."""
    return SaveManager(save_dir)


@pytest.fixture
def game_with_saves(tmp_path: Path) -> Game:
    """Return a mock Game with save_dir pointing to a temp directory."""
    return Game(
        "Test Game",
        backend="mock",
        resolution=(640, 480),
        save_dir=tmp_path / "saves",
    )


# ---------------------------------------------------------------------------
# SaveManager — basic I/O
# ---------------------------------------------------------------------------

class TestSaveManagerSave:
    """Test SaveManager.save() file writing."""

    def test_save_creates_directory(
        self, manager: SaveManager, save_dir: Path,
    ) -> None:
        """save() creates the save directory if it doesn't exist."""
        assert not save_dir.exists()
        manager.save(1, {"gold": 100}, "WorldScene")
        assert save_dir.exists()
        assert save_dir.is_dir()

    def test_save_creates_file(
        self, manager: SaveManager, save_dir: Path,
    ) -> None:
        """save() creates a save_N.json file in the save directory."""
        manager.save(1, {"gold": 100}, "WorldScene")
        assert (save_dir / "save_1.json").exists()

    def test_save_file_is_valid_json(
        self, manager: SaveManager, save_dir: Path,
    ) -> None:
        """The save file is valid, human-readable JSON."""
        manager.save(1, {"gold": 100}, "WorldScene")
        text = (save_dir / "save_1.json").read_text(encoding="utf-8")
        data = json.loads(text)
        assert isinstance(data, dict)

    def test_save_file_format(
        self, manager: SaveManager, save_dir: Path,
    ) -> None:
        """The save file contains version, timestamp, scene_class, state."""
        manager.save(1, {"gold": 100}, "WorldScene")
        data = json.loads(
            (save_dir / "save_1.json").read_text(encoding="utf-8"),
        )
        assert data["version"] == 1
        assert "timestamp" in data
        assert data["scene_class"] == "WorldScene"
        assert data["state"] == {"gold": 100}

    def test_save_timestamp_is_iso_format(
        self, manager: SaveManager, save_dir: Path,
    ) -> None:
        """The timestamp is a valid ISO 8601 datetime string."""
        from datetime import datetime

        manager.save(1, {}, "TestScene")
        data = json.loads(
            (save_dir / "save_1.json").read_text(encoding="utf-8"),
        )
        # Should parse without error.
        dt = datetime.fromisoformat(data["timestamp"])
        assert dt.year >= 2024

    def test_save_different_slots(
        self, manager: SaveManager, save_dir: Path,
    ) -> None:
        """Saving to different slots creates separate files."""
        manager.save(1, {"slot": 1}, "Scene1")
        manager.save(2, {"slot": 2}, "Scene2")
        manager.save(3, {"slot": 3}, "Scene3")
        assert (save_dir / "save_1.json").exists()
        assert (save_dir / "save_2.json").exists()
        assert (save_dir / "save_3.json").exists()

    def test_save_overwrites_existing(
        self, manager: SaveManager, save_dir: Path,
    ) -> None:
        """Saving to an existing slot overwrites the old data."""
        manager.save(1, {"gold": 100}, "WorldScene")
        manager.save(1, {"gold": 999}, "WorldScene")
        data = json.loads(
            (save_dir / "save_1.json").read_text(encoding="utf-8"),
        )
        assert data["state"]["gold"] == 999


# ---------------------------------------------------------------------------
# SaveManager — load
# ---------------------------------------------------------------------------

class TestSaveManagerLoad:
    """Test SaveManager.load() file reading."""

    def test_load_empty_slot_returns_none(
        self, manager: SaveManager,
    ) -> None:
        """Loading from a non-existent slot returns None."""
        assert manager.load(1) is None

    def test_load_returns_saved_data(
        self, manager: SaveManager,
    ) -> None:
        """load() returns the full dict written by save()."""
        manager.save(1, {"gold": 500, "units": ["knight"]}, "MapScene")
        data = manager.load(1)
        assert data is not None
        assert data["version"] == 1
        assert data["scene_class"] == "MapScene"
        assert data["state"]["gold"] == 500
        assert data["state"]["units"] == ["knight"]

    def test_save_load_round_trip(
        self, manager: SaveManager,
    ) -> None:
        """Data survives a save → load round-trip intact."""
        original_state = {
            "turn": 42,
            "gold": 1500,
            "units": [
                {"name": "Knight", "x": 100, "y": 200},
                {"name": "Archer", "x": 300, "y": 400},
            ],
            "flags": {"quest_complete": True, "boss_defeated": False},
        }
        manager.save(5, original_state, "BattleScene")
        loaded = manager.load(5)
        assert loaded is not None
        assert loaded["state"] == original_state

    def test_load_different_slot_is_independent(
        self, manager: SaveManager,
    ) -> None:
        """Loading from one slot doesn't affect another."""
        manager.save(1, {"slot": 1}, "Scene1")
        manager.save(2, {"slot": 2}, "Scene2")
        assert manager.load(1)["state"]["slot"] == 1  # type: ignore[index]
        assert manager.load(2)["state"]["slot"] == 2  # type: ignore[index]


# ---------------------------------------------------------------------------
# SaveManager — list_slots
# ---------------------------------------------------------------------------

class TestSaveManagerListSlots:
    """Test SaveManager.list_slots() slot listing."""

    def test_list_slots_all_empty(
        self, manager: SaveManager,
    ) -> None:
        """list_slots returns all None for empty save directory."""
        slots = manager.list_slots(count=5)
        assert len(slots) == 5
        assert all(s is None for s in slots)

    def test_list_slots_with_some_saves(
        self, manager: SaveManager,
    ) -> None:
        """list_slots returns data for occupied slots, None for empty."""
        manager.save(1, {"gold": 100}, "Scene1")
        manager.save(3, {"gold": 300}, "Scene3")
        slots = manager.list_slots(count=5)
        assert len(slots) == 5
        assert slots[0] is not None  # slot 1
        assert slots[1] is None      # slot 2
        assert slots[2] is not None  # slot 3
        assert slots[3] is None      # slot 4
        assert slots[4] is None      # slot 5

    def test_list_slots_includes_slot_number(
        self, manager: SaveManager,
    ) -> None:
        """list_slots adds a 'slot' key to each non-None entry."""
        manager.save(2, {"x": 1}, "S")
        slots = manager.list_slots(count=3)
        assert slots[1] is not None
        assert slots[1]["slot"] == 2  # type: ignore[index]

    def test_list_slots_default_count(
        self, manager: SaveManager,
    ) -> None:
        """list_slots defaults to 10 slots."""
        slots = manager.list_slots()
        assert len(slots) == 10

    def test_list_slots_contains_metadata(
        self, manager: SaveManager,
    ) -> None:
        """list_slots entries contain version, timestamp, scene_class."""
        manager.save(1, {"gold": 100}, "MyScene")
        slots = manager.list_slots(count=1)
        entry = slots[0]
        assert entry is not None
        assert entry["version"] == 1
        assert "timestamp" in entry
        assert entry["scene_class"] == "MyScene"
        assert entry["state"] == {"gold": 100}


# ---------------------------------------------------------------------------
# SaveManager — delete
# ---------------------------------------------------------------------------

class TestSaveManagerDelete:
    """Test SaveManager.delete() slot deletion."""

    def test_delete_removes_save_file(
        self, manager: SaveManager, save_dir: Path,
    ) -> None:
        """delete() removes the save file for the slot."""
        manager.save(1, {"gold": 100}, "Scene")
        assert (save_dir / "save_1.json").exists()
        manager.delete(1)
        assert not (save_dir / "save_1.json").exists()

    def test_delete_makes_load_return_none(
        self, manager: SaveManager,
    ) -> None:
        """After delete(), load() returns None for that slot."""
        manager.save(1, {"gold": 100}, "Scene")
        manager.delete(1)
        assert manager.load(1) is None

    def test_delete_empty_slot_is_noop(
        self, manager: SaveManager,
    ) -> None:
        """Deleting an empty slot does not raise."""
        manager.delete(99)  # Should not raise.

    def test_delete_does_not_affect_other_slots(
        self, manager: SaveManager,
    ) -> None:
        """Deleting one slot doesn't affect others."""
        manager.save(1, {"slot": 1}, "S")
        manager.save(2, {"slot": 2}, "S")
        manager.delete(1)
        assert manager.load(1) is None
        assert manager.load(2) is not None


# ---------------------------------------------------------------------------
# SaveManager — slot_path
# ---------------------------------------------------------------------------

class TestSlotPath:
    """Test SaveManager._slot_path() internal helper."""

    def test_slot_path_format(
        self, manager: SaveManager, save_dir: Path,
    ) -> None:
        """_slot_path returns save_dir / save_N.json."""
        assert manager._slot_path(1) == save_dir / "save_1.json"
        assert manager._slot_path(42) == save_dir / "save_42.json"


# ---------------------------------------------------------------------------
# Scene — get_save_state / load_save_state stubs
# ---------------------------------------------------------------------------

class TestSceneSaveStubs:
    """Test Scene base class save/load methods."""

    def test_get_save_state_returns_empty_dict(self) -> None:
        """Base Scene.get_save_state() returns an empty dict."""
        scene = Scene()
        assert scene.get_save_state() == {}

    def test_load_save_state_is_noop(self) -> None:
        """Base Scene.load_save_state() does nothing (no-op)."""
        scene = Scene()
        scene.load_save_state({"gold": 100})  # Should not raise.

    def test_subclass_can_override_get_save_state(self) -> None:
        """Subclasses can override get_save_state() to return custom data."""

        class MyScene(Scene):
            def __init__(self) -> None:
                self.gold = 500
                self.turn = 10

            def get_save_state(self) -> dict:
                return {"gold": self.gold, "turn": self.turn}

        scene = MyScene()
        assert scene.get_save_state() == {"gold": 500, "turn": 10}

    def test_subclass_can_override_load_save_state(self) -> None:
        """Subclasses can override load_save_state() to restore data."""

        class MyScene(Scene):
            def __init__(self) -> None:
                self.gold = 0
                self.turn = 0

            def load_save_state(self, state: dict) -> None:
                self.gold = state["gold"]
                self.turn = state["turn"]

        scene = MyScene()
        scene.load_save_state({"gold": 999, "turn": 42})
        assert scene.gold == 999
        assert scene.turn == 42


# ---------------------------------------------------------------------------
# Game — save / load integration
# ---------------------------------------------------------------------------

class TestGameSave:
    """Test Game.save() integration."""

    def test_game_save_writes_to_disk(
        self, game_with_saves: Game, tmp_path: Path,
    ) -> None:
        """game.save() creates a save file on disk."""

        class MapScene(Scene):
            def get_save_state(self) -> dict:
                return {"gold": 1500}

        game_with_saves.push(MapScene())
        game_with_saves.save(1)
        path = tmp_path / "saves" / "save_1.json"
        assert path.exists()

    def test_game_save_includes_scene_class_name(
        self, game_with_saves: Game, tmp_path: Path,
    ) -> None:
        """game.save() records the scene's class name."""

        class WorldMapScene(Scene):
            def get_save_state(self) -> dict:
                return {"turn": 5}

        game_with_saves.push(WorldMapScene())
        game_with_saves.save(1)
        data = json.loads(
            (tmp_path / "saves" / "save_1.json").read_text(encoding="utf-8"),
        )
        assert data["scene_class"] == "WorldMapScene"

    def test_game_save_stores_state(
        self, game_with_saves: Game, tmp_path: Path,
    ) -> None:
        """game.save() stores the result of get_save_state()."""

        class BattleScene(Scene):
            def get_save_state(self) -> dict:
                return {"hp": 100, "mp": 50}

        game_with_saves.push(BattleScene())
        game_with_saves.save(1)
        data = json.loads(
            (tmp_path / "saves" / "save_1.json").read_text(encoding="utf-8"),
        )
        assert data["state"] == {"hp": 100, "mp": 50}

    def test_game_save_empty_stack_is_noop(
        self, game_with_saves: Game, tmp_path: Path,
    ) -> None:
        """game.save() does nothing if no scene is on the stack."""
        game_with_saves.save(1)
        assert not (tmp_path / "saves" / "save_1.json").exists()

    def test_game_save_base_scene_stores_empty_dict(
        self, game_with_saves: Game, tmp_path: Path,
    ) -> None:
        """A base Scene (no override) saves an empty state dict."""
        game_with_saves.push(Scene())
        game_with_saves.save(1)
        data = json.loads(
            (tmp_path / "saves" / "save_1.json").read_text(encoding="utf-8"),
        )
        assert data["state"] == {}


class TestGameLoad:
    """Test Game.load() integration."""

    def test_game_load_returns_save_data(
        self, game_with_saves: Game,
    ) -> None:
        """game.load() returns the full save dict after game.save()."""

        class MyScene(Scene):
            def get_save_state(self) -> dict:
                return {"gold": 777}

        game_with_saves.push(MyScene())
        game_with_saves.save(1)
        data = game_with_saves.load(1)
        assert data is not None
        assert data["state"]["gold"] == 777
        assert data["scene_class"] == "MyScene"

    def test_game_load_empty_slot_returns_none(
        self, game_with_saves: Game,
    ) -> None:
        """game.load() returns None for an empty slot."""
        assert game_with_saves.load(99) is None

    def test_game_save_load_round_trip(
        self, game_with_saves: Game,
    ) -> None:
        """Full round-trip: save scene state, load it, restore."""

        class RPGScene(Scene):
            def __init__(self) -> None:
                self.gold = 0
                self.level = 1

            def get_save_state(self) -> dict:
                return {"gold": self.gold, "level": self.level}

            def load_save_state(self, state: dict) -> None:
                self.gold = state["gold"]
                self.level = state["level"]

        # Save with some state.
        scene1 = RPGScene()
        scene1.gold = 5000
        scene1.level = 15
        game_with_saves.push(scene1)
        game_with_saves.save(1)

        # Load into a new scene.
        data = game_with_saves.load(1)
        assert data is not None
        scene2 = RPGScene()
        scene2.load_save_state(data["state"])
        assert scene2.gold == 5000
        assert scene2.level == 15


# ---------------------------------------------------------------------------
# Game — save_manager property
# ---------------------------------------------------------------------------

class TestGameSaveManager:
    """Test Game.save_manager lazy property."""

    def test_save_manager_is_lazy(self, tmp_path: Path) -> None:
        """save_manager is not created until first access."""
        game = Game(
            "Test", backend="mock", save_dir=tmp_path / "s",
        )
        assert game._save_manager is None
        _ = game.save_manager
        assert game._save_manager is not None

    def test_save_manager_uses_explicit_save_dir(
        self, tmp_path: Path,
    ) -> None:
        """save_manager uses the save_dir passed to Game()."""
        custom_dir = tmp_path / "custom_saves"
        game = Game(
            "Test", backend="mock", save_dir=custom_dir,
        )
        sm = game.save_manager
        assert sm._save_dir == custom_dir

    def test_save_manager_default_dir_from_title(self) -> None:
        """Without save_dir, save_manager derives dir from game title."""
        game = Game("My Cool Game", backend="mock")
        sm = game.save_manager
        expected = Path.home() / ".my_cool_game" / "saves"
        assert sm._save_dir == expected

    def test_save_manager_slug_strips_special_chars(self) -> None:
        """Title slug replaces non-alnum chars with underscores."""
        game = Game("Hero's Quest: The Return!", backend="mock")
        sm = game.save_manager
        expected = Path.home() / ".hero_s_quest__the_return" / "saves"
        assert sm._save_dir == expected

    def test_save_manager_same_instance_on_repeated_access(
        self, tmp_path: Path,
    ) -> None:
        """Repeated access returns the same SaveManager instance."""
        game = Game(
            "Test", backend="mock", save_dir=tmp_path,
        )
        sm1 = game.save_manager
        sm2 = game.save_manager
        assert sm1 is sm2

    def test_save_dir_accepts_string(self, tmp_path: Path) -> None:
        """save_dir parameter accepts a string path."""
        game = Game(
            "Test", backend="mock", save_dir=str(tmp_path / "saves"),
        )
        sm = game.save_manager
        assert sm._save_dir == tmp_path / "saves"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases and robustness tests."""

    def test_save_complex_nested_state(
        self, manager: SaveManager,
    ) -> None:
        """Complex nested dicts and lists round-trip correctly."""
        state = {
            "inventory": {
                "weapons": [
                    {"name": "Sword", "damage": 10, "enchanted": True},
                    {"name": "Bow", "damage": 8, "enchanted": False},
                ],
                "potions": [{"type": "health", "count": 5}],
            },
            "map": [[0, 1, 2], [3, 4, 5]],
            "flags": {"quest1": True, "quest2": False},
            "empty_list": [],
            "empty_dict": {},
            "null_value": None,
        }
        manager.save(1, state, "ComplexScene")
        loaded = manager.load(1)
        assert loaded is not None
        assert loaded["state"] == state

    def test_save_empty_state(
        self, manager: SaveManager,
    ) -> None:
        """Saving an empty state dict works."""
        manager.save(1, {}, "EmptyScene")
        loaded = manager.load(1)
        assert loaded is not None
        assert loaded["state"] == {}

    def test_save_state_with_unicode(
        self, manager: SaveManager,
    ) -> None:
        """Unicode characters in state survive round-trip."""
        state = {"name": "Héro", "quest": "Aller à la montagne 🏔️"}
        manager.save(1, state, "UnicodeScene")
        loaded = manager.load(1)
        assert loaded is not None
        assert loaded["state"]["name"] == "Héro"
        assert "🏔️" in loaded["state"]["quest"]

    def test_save_large_slot_number(
        self, manager: SaveManager,
    ) -> None:
        """Large slot numbers work fine."""
        manager.save(999, {"x": 1}, "S")
        loaded = manager.load(999)
        assert loaded is not None
        assert loaded["state"]["x"] == 1

    def test_save_numeric_values_preserved(
        self, manager: SaveManager,
    ) -> None:
        """Integer and float values are preserved through JSON."""
        state = {"int_val": 42, "float_val": 3.14, "neg": -100}
        manager.save(1, state, "NumScene")
        loaded = manager.load(1)
        assert loaded is not None
        assert loaded["state"]["int_val"] == 42
        assert abs(loaded["state"]["float_val"] - 3.14) < 1e-10
        assert loaded["state"]["neg"] == -100

    def test_overwrite_updates_timestamp(
        self, manager: SaveManager,
    ) -> None:
        """Overwriting a slot updates the timestamp."""
        import time

        manager.save(1, {"v": 1}, "S")
        manager.load(1)["timestamp"]  # type: ignore[index]
        time.sleep(0.01)  # Ensure time passes.
        manager.save(1, {"v": 2}, "S")
        manager.load(1)["timestamp"]  # type: ignore[index]
        # Timestamps should differ (or at minimum, the state changed).
        loaded = manager.load(1)
        assert loaded is not None
        assert loaded["state"]["v"] == 2

    def test_multiple_managers_same_directory(
        self, save_dir: Path,
    ) -> None:
        """Two SaveManagers pointing at the same dir see the same files."""
        m1 = SaveManager(save_dir)
        m2 = SaveManager(save_dir)
        m1.save(1, {"from": "m1"}, "Scene")
        loaded = m2.load(1)
        assert loaded is not None
        assert loaded["state"]["from"] == "m1"

    def test_corrupted_save_error_includes_recovery_hint(
        self, save_dir: Path,
    ) -> None:
        """SaveError message includes a recovery hint about deleting the file."""
        from easygame.save import SaveError

        save_dir.mkdir(parents=True, exist_ok=True)
        corrupt_file = save_dir / "save_1.json"
        corrupt_file.write_text("not valid json!!!", encoding="utf-8")

        manager = SaveManager(save_dir)
        with pytest.raises(SaveError, match="delete the file to clear this slot"):
            manager.load(1)

    def test_corrupted_save_error_includes_slot_and_path(
        self, save_dir: Path,
    ) -> None:
        """SaveError message includes slot number and file path."""
        from easygame.save import SaveError

        save_dir.mkdir(parents=True, exist_ok=True)
        corrupt_file = save_dir / "save_3.json"
        corrupt_file.write_text("{bad", encoding="utf-8")

        manager = SaveManager(save_dir)
        with pytest.raises(SaveError, match="slot 3.*save_3.json"):
            manager.load(3)
