"""Tests for StateMachine (saga2d.util.fsm)."""

from __future__ import annotations

import pytest

from saga2d.util.fsm import StateMachine


def test_construction_valid() -> None:
    fsm = StateMachine(
        states=["idle", "walking"],
        initial="idle",
        transitions={"idle": {"move": "walking"}, "walking": {"arrive": "idle"}},
    )
    assert fsm.state == "idle"


def test_initial_state_not_in_states_raises() -> None:
    with pytest.raises(ValueError, match="Initial state 'bogus' not in states"):
        StateMachine(
            states=["idle", "walking"],
            initial="bogus",
        )


def test_transition_source_not_in_states_raises() -> None:
    with pytest.raises(ValueError, match="Transition source 'bogus' not in states"):
        StateMachine(
            states=["idle", "walking"],
            initial="idle",
            transitions={"bogus": {"move": "walking"}},
        )


def test_transition_target_not_in_states_raises() -> None:
    with pytest.raises(
        ValueError,
        match="Transition target 'bogus' \\(from 'idle' on 'move'\\) not in states",
    ):
        StateMachine(
            states=["idle", "walking"],
            initial="idle",
            transitions={"idle": {"move": "bogus"}},
        )


def test_trigger_valid_transition_fires_callbacks() -> None:
    entered: list[str] = []
    exited: list[str] = []

    fsm = StateMachine(
        states=["idle", "walking"],
        initial="idle",
        transitions={"idle": {"move": "walking"}, "walking": {"arrive": "idle"}},
        on_enter={"idle": lambda: entered.append("idle"), "walking": lambda: entered.append("walking")},
        on_exit={"idle": lambda: exited.append("idle"), "walking": lambda: exited.append("walking")},
    )
    assert entered == ["idle"]  # on_enter fires for initial state
    assert exited == []

    got = fsm.trigger("move")
    assert got is True
    assert fsm.state == "walking"
    assert entered == ["idle", "walking"]
    assert exited == ["idle"]

    got = fsm.trigger("arrive")
    assert got is True
    assert fsm.state == "idle"
    assert entered == ["idle", "walking", "idle"]
    assert exited == ["idle", "walking"]


def test_trigger_invalid_event_returns_false() -> None:
    fsm = StateMachine(
        states=["idle", "walking"],
        initial="idle",
        transitions={"idle": {"move": "walking"}},
    )
    got = fsm.trigger("attack")
    assert got is False
    assert fsm.state == "idle"


def test_self_transition_fires_both_callbacks() -> None:
    entered: list[str] = []
    exited: list[str] = []

    fsm = StateMachine(
        states=["idle"],
        initial="idle",
        transitions={"idle": {"reset": "idle"}},
        on_enter={"idle": lambda: entered.append("idle")},
        on_exit={"idle": lambda: exited.append("idle")},
    )
    assert entered == ["idle"]
    assert exited == []

    got = fsm.trigger("reset")
    assert got is True
    assert fsm.state == "idle"
    assert entered == ["idle", "idle"]
    assert exited == ["idle"]


def test_absorbing_state_no_transitions() -> None:
    fsm = StateMachine(
        states=["idle", "dead"],
        initial="idle",
        transitions={"idle": {"die": "dead"}},
    )
    fsm.trigger("die")
    assert fsm.state == "dead"

    got = fsm.trigger("revive")
    assert got is False
    assert fsm.state == "dead"


def test_valid_events() -> None:
    fsm = StateMachine(
        states=["idle", "walking", "attacking"],
        initial="idle",
        transitions={
            "idle": {"move": "walking", "attack": "attacking"},
            "walking": {"arrive": "idle"},
            "attacking": {"done": "idle"},
        },
    )
    assert fsm.valid_events == ["move", "attack"]

    fsm.trigger("move")
    assert fsm.valid_events == ["arrive"]

    fsm.trigger("arrive")
    assert fsm.valid_events == ["move", "attack"]


def test_on_enter_fires_for_initial_state() -> None:
    called = False

    def on_idle() -> None:
        nonlocal called
        called = True

    StateMachine(
        states=["idle"],
        initial="idle",
        on_enter={"idle": on_idle},
    )
    assert called is True


def test_empty_transitions() -> None:
    fsm = StateMachine(
        states=["idle"],
        initial="idle",
        transitions=None,
    )
    assert fsm.state == "idle"
    assert fsm.trigger("anything") is False
    assert fsm.valid_events == []


def test_on_enter_on_exit_extra_keys_ignored() -> None:
    """Extra keys in on_enter/on_exit are silently ignored (no validation)."""
    fsm = StateMachine(
        states=["idle"],
        initial="idle",
        on_enter={"idle": lambda: None, "bogus": lambda: None},
        on_exit={"bogus": lambda: None},
    )
    assert fsm.state == "idle"


def test_callbacks_modify_external_state() -> None:
    counter = 0

    def inc() -> None:
        nonlocal counter
        counter += 1

    fsm = StateMachine(
        states=["a", "b"],
        initial="a",
        transitions={"a": {"go": "b"}, "b": {"back": "a"}},
        on_enter={"a": inc, "b": inc},
    )
    assert counter == 1  # initial on_enter

    fsm.trigger("go")
    assert counter == 2
    fsm.trigger("back")
    assert counter == 3
