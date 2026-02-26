"""Edge-case tests for SaveManager."""

from pathlib import Path

import pytest

from easygame.save import SaveError, SaveManager


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def save_dir(tmp_path: Path) -> Path:
    """Temp directory for save files."""
    return tmp_path / "saves"


@pytest.fixture
def manager(save_dir: Path) -> SaveManager:
    """SaveManager using tmp_path."""
    return SaveManager(save_dir)


# ------------------------------------------------------------------
# 1. save with non-serializable state
# ------------------------------------------------------------------


def test_save_non_serializable_state_raises_save_error(
    manager: SaveManager,
) -> None:
    """save with non-JSON-serializable state (e.g. set) raises SaveError."""
    with pytest.raises(SaveError, match="Cannot write"):
        manager.save(1, {"a": {1, 2}}, "TestScene")


# ------------------------------------------------------------------
# 2. load corrupted JSON
# ------------------------------------------------------------------


def test_load_corrupted_json_raises_save_error(
    manager: SaveManager, save_dir: Path
) -> None:
    """load on corrupted JSON file raises SaveError."""
    save_dir.mkdir(parents=True, exist_ok=True)
    (save_dir / "save_1.json").write_text("{ invalid json }", encoding="utf-8")

    with pytest.raises(SaveError, match="Corrupted"):
        manager.load(1)


# ------------------------------------------------------------------
# 3. save with slot=0, slot=-1
# ------------------------------------------------------------------


def test_save_slot_zero_raises_value_error(manager: SaveManager) -> None:
    """save with slot=0 raises ValueError."""
    with pytest.raises(ValueError, match="slot must be >= 1"):
        manager.save(0, {"x": 1}, "TestScene")


def test_save_slot_negative_raises_value_error(manager: SaveManager) -> None:
    """save with slot=-1 raises ValueError."""
    with pytest.raises(ValueError, match="slot must be >= 1"):
        manager.save(-1, {"x": 1}, "TestScene")


# ------------------------------------------------------------------
# 4. save with slot=1.5 (non-int)
# ------------------------------------------------------------------


def test_save_slot_float_raises_type_error(manager: SaveManager) -> None:
    """save with slot=1.5 raises TypeError."""
    with pytest.raises(TypeError, match="int"):
        manager.save(1.5, {"x": 1}, "TestScene")


# ------------------------------------------------------------------
# 5. list_slots with count=0 and count=-1
# ------------------------------------------------------------------


def test_list_slots_count_zero_returns_empty(manager: SaveManager) -> None:
    """list_slots(count=0) returns []."""
    result = manager.list_slots(count=0)
    assert result == []


def test_list_slots_count_negative_returns_empty(manager: SaveManager) -> None:
    """list_slots(count=-1) returns []."""
    result = manager.list_slots(count=-1)
    assert result == []


# ------------------------------------------------------------------
# 6. load missing file returns None
# ------------------------------------------------------------------


def test_load_missing_file_returns_none(manager: SaveManager) -> None:
    """load on empty slot (no file) returns None."""
    result = manager.load(1)
    assert result is None


# ------------------------------------------------------------------
# 7. load empty file raises SaveError
# ------------------------------------------------------------------


def test_load_empty_file_raises_save_error(
    manager: SaveManager, save_dir: Path
) -> None:
    """load on empty file raises SaveError (invalid JSON)."""
    save_dir.mkdir(parents=True, exist_ok=True)
    (save_dir / "save_1.json").write_text("", encoding="utf-8")

    with pytest.raises(SaveError, match="Corrupted"):
        manager.load(1)
