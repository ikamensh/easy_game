"""Edge-case tests for Scene stack: re-entrant mutations, empty stack, invalid args."""

import pytest

from easygame import Game, Scene


class TrackingScene(Scene):
    """Records lifecycle calls for assertions."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.enters: list[str] = []
        self.exits: list[str] = []
        self.reveals: list[str] = []

    def on_enter(self) -> None:
        self.enters.append(self.name)

    def on_exit(self) -> None:
        self.exits.append(self.name)

    def on_reveal(self) -> None:
        self.reveals.append(self.name)


# ---------------------------------------------------------------------------
# 1. Re-entrant mutations: push/pop during on_enter / on_exit
# ---------------------------------------------------------------------------


def test_push_during_on_enter_executes_immediately(mock_game: Game) -> None:
    """Push during on_enter runs immediately; new scene ends up on top."""
    b = TrackingScene("B")

    class SceneA(Scene):
        def on_enter(self) -> None:
            self.game.push(b)

    mock_game.push(SceneA())

    assert mock_game._scene_stack.top() is b
    assert b.enters == ["B"]


def test_pop_during_on_exit_removes_newly_pushed_scene(mock_game: Game) -> None:
    """When top scene's on_exit calls pop (deferred), flush pops the newly pushed scene."""
    a = TrackingScene("A")
    c = TrackingScene("C")

    class SceneB(TrackingScene):
        def __init__(self) -> None:
            super().__init__("B")

        def update(self, dt: float) -> None:
            self.game.push(c)

        def on_exit(self) -> None:
            super().on_exit()
            self.game.pop()

    b = SceneB()
    mock_game.push(a)
    mock_game.push(b)
    mock_game.tick(dt=0.016)  # B.update pushes C (deferred); B.on_exit defers pop

    assert mock_game._scene_stack.top() is b
    assert b.exits == ["B"]
    assert b.reveals == ["B"]
    assert c.enters == ["C"]
    assert c.exits == ["C"]


def test_push_during_on_exit_is_deferred(mock_game: Game) -> None:
    """Push during on_exit is deferred; applied after current operation completes."""
    a = TrackingScene("A")
    c = TrackingScene("C")

    class SceneB(Scene):
        def update(self, dt: float) -> None:
            self.game.push(Scene())  # Push D (deferred)

        def on_exit(self) -> None:
            self.game.push(c)

    mock_game.push(a)
    mock_game.push(SceneB())
    mock_game.tick(dt=0.016)

    assert mock_game._scene_stack.top() is c
    assert c.enters == ["C"]


# ---------------------------------------------------------------------------
# 2. replace on empty stack
# ---------------------------------------------------------------------------


def test_replace_on_empty_stack_acts_as_push(mock_game: Game) -> None:
    """replace(scene) when stack is empty pushes the scene (no on_exit to call)."""
    a = TrackingScene("A")
    mock_game.replace(a)

    assert mock_game._scene_stack.top() is a
    assert a.enters == ["A"]
    assert a.exits == []


# ---------------------------------------------------------------------------
# 3. push(None) behavior
# ---------------------------------------------------------------------------


def test_push_none_raises(mock_game: Game) -> None:
    """push(None) raises TypeError (Game rejects non-Scene)."""
    with pytest.raises(TypeError, match="Scene instance"):
        mock_game.push(None)


def test_replace_none_raises(mock_game: Game) -> None:
    """replace(None) raises TypeError."""
    with pytest.raises(TypeError, match="Scene instance"):
        mock_game.replace(None)


def test_clear_and_push_none_raises(mock_game: Game) -> None:
    """clear_and_push(None) raises TypeError."""
    with pytest.raises(TypeError, match="Scene instance"):
        mock_game.clear_and_push(None)


# ---------------------------------------------------------------------------
# 4. Double push of same scene instance
# ---------------------------------------------------------------------------


def test_double_push_same_scene_instance(mock_game: Game) -> None:
    """Pushing the same scene instance twice: it appears twice, on_exit then on_enter."""
    a = TrackingScene("A")
    mock_game.push(a)
    mock_game.push(a)

    assert len(mock_game._scene_stack._stack) == 2
    assert mock_game._scene_stack._stack[0] is a
    assert mock_game._scene_stack._stack[1] is a
    assert mock_game._scene_stack.top() is a
    assert a.enters == ["A", "A"]
    assert a.exits == ["A"]


# ---------------------------------------------------------------------------
# 5. push scene that raises in on_enter (rollback behavior)
# ---------------------------------------------------------------------------


def test_push_scene_raising_in_on_enter_rolls_back(mock_game: Game) -> None:
    """When on_enter raises, the scene is popped from the stack and exception propagates."""
    a = TrackingScene("A")
    mock_game.push(a)

    class BadScene(Scene):
        def on_enter(self) -> None:
            raise RuntimeError("on_enter failed")

    with pytest.raises(RuntimeError, match="on_enter failed"):
        mock_game.push(BadScene())

    assert mock_game._scene_stack.top() is a
    assert len(mock_game._scene_stack._stack) == 1


def test_replace_scene_raising_in_on_enter_rolls_back(mock_game: Game) -> None:
    """When replace's new scene raises in on_enter, bad scene is popped; old was already removed."""
    a = TrackingScene("A")
    mock_game.push(a)

    class BadScene(Scene):
        def on_enter(self) -> None:
            raise ValueError("replace on_enter failed")

    with pytest.raises(ValueError, match="replace on_enter failed"):
        mock_game.replace(BadScene())

    # replace() removes old scene before pushing new one; rollback only pops the failed scene
    assert mock_game._scene_stack.top() is None
    assert len(mock_game._scene_stack._stack) == 0
    assert a.exits == ["A"]


def test_replace_on_empty_stack_raising_in_on_enter_rolls_back(mock_game: Game) -> None:
    """replace(scene) on empty stack when on_enter raises: stack stays empty."""
    class BadScene(Scene):
        def on_enter(self) -> None:
            raise RuntimeError("bad")

    with pytest.raises(RuntimeError, match="bad"):
        mock_game.replace(BadScene())

    assert mock_game._scene_stack.top() is None
    assert len(mock_game._scene_stack._stack) == 0
