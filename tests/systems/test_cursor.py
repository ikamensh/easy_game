"""Comprehensive tests for Stage 11 CursorManager.

Tests register, set, current state, set_cursor_visible, unregistered name error,
and backend receives correct calls.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from easygame import CursorManager, Game
from easygame.assets import AssetManager
from easygame.backends.mock_backend import MockBackend


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def asset_dir(tmp_path: Path) -> Path:
    """Temp asset dir with a cursor image."""
    images = tmp_path / "images" / "ui"
    images.mkdir(parents=True)
    (images / "cursor_attack.png").write_bytes(b"png")
    (images / "cursor_move.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def game(asset_dir: Path) -> Game:
    g = Game("Test", backend="mock", resolution=(800, 600))
    g.assets = AssetManager(g.backend, base_path=asset_dir)
    return g


@pytest.fixture
def backend(game: Game) -> MockBackend:
    return game.backend


@pytest.fixture
def cursor(game: Game) -> CursorManager:
    return game.cursor


# ------------------------------------------------------------------
# Register
# ------------------------------------------------------------------


class TestCursorRegister:
    def test_register_cursor(self, cursor: CursorManager, backend: MockBackend) -> None:
        """Register loads image and stores handle."""
        cursor.register("attack", "ui/cursor_attack")
        cursor.set("attack")
        assert backend.cursor_image is not None
        assert backend.cursor_hotspot == (0, 0)

    def test_register_with_hotspot(
        self, cursor: CursorManager, backend: MockBackend,
    ) -> None:
        cursor.register("attack", "ui/cursor_attack", hotspot=(8, 8))
        cursor.set("attack")
        assert backend.cursor_image is not None
        assert backend.cursor_hotspot == (8, 8)

    def test_register_overwrites(
        self, cursor: CursorManager, backend: MockBackend,
    ) -> None:
        """Re-registering same name overwrites."""
        cursor.register("attack", "ui/cursor_attack", hotspot=(0, 0))
        cursor.register("attack", "ui/cursor_move", hotspot=(16, 16))
        cursor.set("attack")
        assert backend.cursor_hotspot == (16, 16)


# ------------------------------------------------------------------
# Set
# ------------------------------------------------------------------


class TestCursorSet:
    def test_set_default_restores_system(
        self, cursor: CursorManager, backend: MockBackend,
    ) -> None:
        cursor.register("attack", "ui/cursor_attack")
        cursor.set("attack")
        assert backend.cursor_image is not None

        cursor.set("default")
        assert backend.cursor_image is None
        assert cursor.current == "default"

    def test_set_custom_cursor(
        self, cursor: CursorManager, backend: MockBackend,
    ) -> None:
        cursor.register("attack", "ui/cursor_attack", hotspot=(4, 4))
        cursor.set("attack")
        assert backend.cursor_image is not None
        assert backend.cursor_hotspot == (4, 4)
        assert cursor.current == "attack"

    def test_set_unregistered_raises(self, cursor: CursorManager) -> None:
        with pytest.raises(KeyError, match="not registered"):
            cursor.set("nonexistent")

    def test_set_default_does_not_require_register(
        self, cursor: CursorManager, backend: MockBackend,
    ) -> None:
        cursor.set("default")
        assert backend.cursor_image is None
        assert cursor.current == "default"


# ------------------------------------------------------------------
# Current state
# ------------------------------------------------------------------


class TestCursorCurrent:
    def test_current_default_initially(self, cursor: CursorManager) -> None:
        assert cursor.current == "default"

    def test_current_after_set(self, cursor: CursorManager) -> None:
        cursor.register("attack", "ui/cursor_attack")
        cursor.set("attack")
        assert cursor.current == "attack"

    def test_current_after_set_default(self, cursor: CursorManager) -> None:
        cursor.register("attack", "ui/cursor_attack")
        cursor.set("attack")
        cursor.set("default")
        assert cursor.current == "default"


# ------------------------------------------------------------------
# set_cursor_visible
# ------------------------------------------------------------------


class TestCursorVisible:
    def test_set_cursor_visible_true(self, cursor: CursorManager, backend: MockBackend) -> None:
        cursor.set_visible(True)
        assert backend.cursor_visible is True

    def test_set_cursor_visible_false(self, cursor: CursorManager, backend: MockBackend) -> None:
        cursor.set_visible(False)
        assert backend.cursor_visible is False

    def test_set_cursor_visible_toggle(
        self, cursor: CursorManager, backend: MockBackend,
    ) -> None:
        assert backend.cursor_visible is True
        cursor.set_visible(False)
        assert backend.cursor_visible is False
        cursor.set_visible(True)
        assert backend.cursor_visible is True


# ------------------------------------------------------------------
# Backend receives correct calls
# ------------------------------------------------------------------


class TestCursorBackendCalls:
    def test_backend_receives_correct_handle(
        self, cursor: CursorManager, backend: MockBackend, game: Game,
    ) -> None:
        cursor.register("attack", "ui/cursor_attack")
        cursor.set("attack")
        expected_handle = game.assets.image("ui/cursor_attack")
        assert backend.cursor_image == expected_handle

    def test_backend_receives_correct_hotspot(
        self, cursor: CursorManager, backend: MockBackend,
    ) -> None:
        cursor.register("move", "ui/cursor_move", hotspot=(12, 12))
        cursor.set("move")
        assert backend.cursor_hotspot == (12, 12)

    def test_backend_receives_none_for_default(
        self, cursor: CursorManager, backend: MockBackend,
    ) -> None:
        cursor.register("attack", "ui/cursor_attack")
        cursor.set("attack")
        cursor.set("default")
        assert backend.cursor_image is None


# ------------------------------------------------------------------
# Game integration
# ------------------------------------------------------------------


class TestCursorGameIntegration:
    def test_game_cursor_lazy_property(self, game: Game) -> None:
        """game.cursor creates CursorManager on first access."""
        assert game._cursor is None
        cm = game.cursor
        assert cm is not None
        assert game._cursor is cm
        assert game.cursor is cm

    def test_cursor_mock_backend_tracking(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Backend cursor_image updated when set."""
        game.cursor.register("attack", "ui/cursor_attack")
        assert backend.cursor_image is None

        game.cursor.set("attack")
        assert backend.cursor_image is not None

        game.cursor.set("default")
        assert backend.cursor_image is None
