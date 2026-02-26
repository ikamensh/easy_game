"""Edge-case tests for InputManager."""

import pytest

from easygame.backends.base import KeyEvent, MouseEvent, WindowEvent
from easygame.input import InputManager


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mgr() -> InputManager:
    """Fresh InputManager with default bindings."""
    return InputManager()


# ------------------------------------------------------------------
# 1. bind with empty strings
# ------------------------------------------------------------------


def test_bind_empty_action(mgr: InputManager) -> None:
    """bind with empty action string is accepted."""
    mgr.bind("", "space")
    assert mgr.get_bindings().get("") == "space"


def test_bind_empty_key(mgr: InputManager) -> None:
    """bind with empty key string is accepted."""
    mgr.bind("custom", "")
    assert mgr.get_bindings().get("custom") == ""


# ------------------------------------------------------------------
# 2. bind with None for action/key (None is hashable; accepted)
# ------------------------------------------------------------------


def test_bind_none_action_accepted(mgr: InputManager) -> None:
    """bind with action=None is accepted (None is hashable as dict key)."""
    mgr.bind(None, "space")  # type: ignore[arg-type]
    assert mgr.get_bindings().get(None) == "space"


def test_bind_none_key_accepted(mgr: InputManager) -> None:
    """bind with key=None is accepted (None is hashable as dict key)."""
    mgr.bind("custom_none", None)  # type: ignore[arg-type]
    assert mgr.get_bindings().get("custom_none") is None


# ------------------------------------------------------------------
# 3. unbind with non-existent action
# ------------------------------------------------------------------


def test_unbind_nonexistent_noop(mgr: InputManager) -> None:
    """unbind with non-existent action is no-op; bindings unchanged."""
    before = mgr.get_bindings()
    mgr.unbind("nonexistent_action")
    assert mgr.get_bindings() == before


# ------------------------------------------------------------------
# 4. Key stealing: key was bound to another action
# ------------------------------------------------------------------


def test_bind_steals_key_from_other_action(mgr: InputManager) -> None:
    """bind("a", "k1") then bind("b", "k1") — "a" is unbound, "b" gets k1."""
    mgr.bind("a", "k1")
    mgr.bind("b", "k1")

    assert mgr.get_bindings().get("a") is None
    assert mgr.get_bindings().get("b") == "k1"


# ------------------------------------------------------------------
# 5. Key stealing: action was bound to another key
# ------------------------------------------------------------------


def test_bind_replaces_key_for_old_action(mgr: InputManager) -> None:
    """bind("a", "k1") then bind("a", "k2") — k1 is unbound, a gets k2."""
    mgr.bind("a", "k1")
    mgr.bind("a", "k2")

    assert mgr.get_bindings().get("a") == "k2"
    # k1 should not be bound to any action
    bindings = mgr.get_bindings()
    assert "k1" not in bindings.values()


# ------------------------------------------------------------------
# 6. translate with empty list
# ------------------------------------------------------------------


def test_translate_empty_list_returns_empty(mgr: InputManager) -> None:
    """translate([]) returns []."""
    result = mgr.translate([])
    assert result == []


# ------------------------------------------------------------------
# 7. translate with None
# ------------------------------------------------------------------


def test_translate_none_returns_empty(mgr: InputManager) -> None:
    """translate(None) returns []."""
    result = mgr.translate(None)  # type: ignore[arg-type]
    assert result == []


# ------------------------------------------------------------------
# 8. translate with WindowEvent (skipped)
# ------------------------------------------------------------------


def test_translate_window_event_skipped(mgr: InputManager) -> None:
    """translate with WindowEvent returns empty; WindowEvent is not translated."""
    raw = [WindowEvent(type="close")]
    result = mgr.translate(raw)
    assert result == []
