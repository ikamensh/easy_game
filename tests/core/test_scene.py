"""Tests for Scene and SceneStack lifecycle, deferred operations, and edge cases."""

import pytest

from easygame import Game, Scene
from easygame.input import InputEvent
from easygame.scene import SceneStack


class TrackingScene(Scene):
    """Scene that records lifecycle calls."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.enters: list[str] = []
        self.exits: list[str] = []
        self.reveals: list[str] = []
        self.updates: list[float] = []
        self.draws: int = 0
        self.inputs: list[object] = []

    def on_enter(self) -> None:
        self.enters.append(self.name)

    def on_exit(self) -> None:
        self.exits.append(self.name)

    def on_reveal(self) -> None:
        self.reveals.append(self.name)

    def update(self, dt: float) -> None:
        self.updates.append(dt)

    def draw(self) -> None:
        self.draws += 1

    def handle_input(self, event: object) -> bool:
        self.inputs.append(event)
        return False


# ---------------------------------------------------------------------------
# Basic push / pop / replace / clear_and_push lifecycle
# ---------------------------------------------------------------------------


def test_push_calls_on_enter(mock_game: Game) -> None:
    """push(B) when empty: B.game set, B.on_enter() called."""
    stack = mock_game._scene_stack
    b = TrackingScene("B")

    mock_game.push(b)

    assert stack.top() is b
    assert b.game is mock_game
    assert b.enters == ["B"]
    assert b.exits == []


def test_push_calls_on_exit_on_previous_top(mock_game: Game) -> None:
    """push(B) when A is top: A.on_exit() then B.on_enter()."""
    stack = mock_game._scene_stack
    a = TrackingScene("A")
    b = TrackingScene("B")

    mock_game.push(a)
    mock_game.push(b)

    assert a.exits == ["A"]
    assert a.enters == ["A"]
    assert b.enters == ["B"]
    assert stack.top() is b


def test_pop_calls_on_exit_and_on_reveal(mock_game: Game) -> None:
    """pop() when B on top of A: B.on_exit(), remove B, A.on_reveal()."""
    stack = mock_game._scene_stack
    a = TrackingScene("A")
    b = TrackingScene("B")

    mock_game.push(a)
    mock_game.push(b)
    mock_game.pop()

    assert stack.top() is a
    assert b.exits == ["B"]
    assert a.reveals == ["A"]
    assert a.exits == ["A"]  # from when B was pushed over A


def test_replace_calls_on_exit_and_on_enter_no_reveal(mock_game: Game) -> None:
    """replace(B) when A is top: A.on_exit(), remove A, B.on_enter()."""
    stack = mock_game._scene_stack
    a = TrackingScene("A")
    b = TrackingScene("B")

    mock_game.push(a)
    mock_game.replace(b)

    assert stack.top() is b
    assert a.exits == ["A"]
    assert b.enters == ["B"]
    assert a.reveals == []  # replace does not call on_reveal


def test_clear_and_push_calls_on_exit_on_all(mock_game: Game) -> None:
    """clear_and_push(C) when A,B on stack: B.on_exit(), A.on_exit(), C.on_enter()."""
    stack = mock_game._scene_stack
    a = TrackingScene("A")
    b = TrackingScene("B")
    c = TrackingScene("C")

    mock_game.push(a)
    mock_game.push(b)
    mock_game.clear_and_push(c)

    assert stack.top() is c
    assert len(stack._stack) == 1
    # A got on_exit when covered by B, then again when cleared
    assert a.exits == ["A", "A"]
    assert b.exits == ["B"]
    assert c.enters == ["C"]


# ---------------------------------------------------------------------------
# Deferred operations (begin_tick / flush_pending_ops)
# ---------------------------------------------------------------------------


def test_deferred_push_during_tick(mock_game: Game) -> None:
    """push() during update is deferred until flush."""
    stack = mock_game._scene_stack
    a = TrackingScene("A")
    b = TrackingScene("B")

    mock_game.push(a)
    stack.begin_tick()
    stack.push(b)

    assert stack.top() is a  # b not applied yet
    assert len(stack._stack) == 1

    stack.flush_pending_ops()

    assert stack.top() is b
    assert a.exits == ["A"]
    assert b.enters == ["B"]


def test_deferred_pop_during_tick(mock_game: Game) -> None:
    """pop() during handle_input is deferred until flush."""
    stack = mock_game._scene_stack
    a = TrackingScene("A")
    b = TrackingScene("B")

    mock_game.push(a)
    mock_game.push(b)
    stack.begin_tick()
    stack.pop()

    assert stack.top() is b  # still b before flush

    stack.flush_pending_ops()

    assert stack.top() is a
    assert b.exits == ["B"]
    assert a.reveals == ["A"]


def test_push_outside_tick_executes_immediately(mock_game: Game) -> None:
    """push() when not in tick executes immediately."""
    stack = mock_game._scene_stack
    a = TrackingScene("A")

    mock_game.push(a)

    assert stack.top() is a
    assert a.enters == ["A"]
    assert not stack._pending_ops


# ---------------------------------------------------------------------------
# Empty stack safety
# ---------------------------------------------------------------------------


def test_empty_stack_top_returns_none(mock_game: Game) -> None:
    """top() on empty stack returns None."""
    stack = mock_game._scene_stack
    assert stack.top() is None


def test_pop_empty_stack_no_crash(mock_game: Game) -> None:
    """pop() on empty stack does not crash."""
    mock_game.pop()
    assert mock_game._scene_stack.top() is None


def test_update_and_draw_empty_stack_no_crash(mock_game: Game) -> None:
    """update() and draw() on empty stack do not crash."""
    stack = mock_game._scene_stack
    stack.update(0.016)
    stack.draw()


# ---------------------------------------------------------------------------
# update / draw dispatching
# ---------------------------------------------------------------------------


def test_update_calls_top_scene(mock_game: Game) -> None:
    """update(dt) calls top scene's update with dt."""
    a = TrackingScene("A")

    mock_game.push(a)
    mock_game._scene_stack.update(0.032)

    assert a.updates == [0.032]


def test_draw_only_top_opaque_scene(mock_game: Game) -> None:
    """draw() with two opaque scenes only draws the top one."""
    stack = mock_game._scene_stack
    a = TrackingScene("A")
    b = TrackingScene("B")

    mock_game.push(a)
    mock_game.push(b)
    stack.draw()

    # B is opaque (transparent=False), so A is fully covered.
    assert a.draws == 0
    assert b.draws == 1


def test_pause_below_false_updates_scenes_below(mock_game: Game) -> None:
    """When top has pause_below=False, scene below also gets update."""
    stack = mock_game._scene_stack
    a = TrackingScene("A")
    b = TrackingScene("B")
    b.pause_below = False

    mock_game.push(a)
    mock_game.push(b)
    stack.update(0.016)

    assert a.updates == [0.016]
    assert b.updates == [0.016]


# ---------------------------------------------------------------------------
# Transparency / draw ordering
# ---------------------------------------------------------------------------


def test_draw_transparent_scene_shows_scene_below(mock_game: Game) -> None:
    """draw() with transparent top scene draws both scenes."""
    stack = mock_game._scene_stack
    a = TrackingScene("A")
    b = TrackingScene("B")
    b.transparent = True

    mock_game.push(a)
    mock_game.push(b)
    stack.draw()

    # B is transparent, so A (opaque) and B are both drawn.
    assert a.draws == 1
    assert b.draws == 1


def test_draw_three_scenes_transparency_chain(mock_game: Game) -> None:
    """draw() walks through transparent scenes until an opaque one."""
    stack = mock_game._scene_stack
    a = TrackingScene("A")
    b = TrackingScene("B")
    c = TrackingScene("C")
    # A: opaque, B: opaque, C: transparent
    c.transparent = True

    mock_game.push(a)
    mock_game.push(b)
    mock_game.push(c)
    stack.draw()

    # C is transparent -> look below. B is opaque -> stop.
    # Draw B, then C. A is not drawn.
    assert a.draws == 0
    assert b.draws == 1
    assert c.draws == 1


def test_draw_all_transparent_draws_entire_stack(mock_game: Game) -> None:
    """draw() draws all scenes when every scene is transparent."""
    stack = mock_game._scene_stack
    a = TrackingScene("A")
    b = TrackingScene("B")
    c = TrackingScene("C")
    a.transparent = True
    b.transparent = True
    c.transparent = True

    mock_game.push(a)
    mock_game.push(b)
    mock_game.push(c)
    stack.draw()

    # All transparent -> draw from index 0 (bottom) up.
    assert a.draws == 1
    assert b.draws == 1
    assert c.draws == 1


def test_draw_single_scene(mock_game: Game) -> None:
    """draw() with a single scene always draws it."""
    stack = mock_game._scene_stack
    a = TrackingScene("A")

    mock_game.push(a)
    stack.draw()

    assert a.draws == 1


# ---------------------------------------------------------------------------
# handle_input
# ---------------------------------------------------------------------------


def test_scene_handle_input_default_returns_false() -> None:
    """Default handle_input returns False (not consumed)."""
    s = Scene()
    event = InputEvent(type="key_press", key="space")
    assert s.handle_input(event) is False


# ---------------------------------------------------------------------------
# background_color -- framework clears screen before drawing
# ---------------------------------------------------------------------------


def test_background_color_none_passes_no_clear_color(mock_game: Game, mock_backend) -> None:
    """Scene without background_color: begin_frame receives clear_color=None."""
    class PlainScene(Scene):
        pass

    mock_game.push(PlainScene())
    mock_game.tick(dt=0.016)

    assert mock_backend.clear_color is None


def test_background_color_rgb_passes_clear_color(mock_game: Game, mock_backend) -> None:
    """Scene with background_color=(R,G,B): begin_frame receives it (alpha=255 implied)."""
    class GreenScene(Scene):
        background_color = (34, 139, 34)

    mock_game.push(GreenScene())
    mock_game.tick(dt=0.016)

    assert mock_backend.clear_color == (34, 139, 34)


def test_background_color_rgba_passes_clear_color(mock_game: Game, mock_backend) -> None:
    """Scene with background_color=(R,G,B,A): begin_frame receives full tuple."""
    class SemiTransparentScene(Scene):
        background_color = (25, 30, 40, 200)

    mock_game.push(SemiTransparentScene())
    mock_game.tick(dt=0.016)

    assert mock_backend.clear_color == (25, 30, 40, 200)


def test_background_color_uses_base_scene_when_transparent_overlay(
    mock_game: Game, mock_backend
) -> None:
    """When top scene is transparent, base (opaque) scene's background_color is used."""
    class BaseScene(Scene):
        background_color = (100, 50, 25, 255)

    class OverlayScene(Scene):
        transparent = True
        background_color = (0, 0, 0, 255)  # ignored -- we use base's

    mock_game.push(BaseScene())
    mock_game.push(OverlayScene())
    mock_game.tick(dt=0.016)

    # Base scene is the opaque one; its background_color wins.
    assert mock_backend.clear_color == (100, 50, 25, 255)


def test_get_base_scene_empty_returns_none(mock_game: Game) -> None:
    """get_base_scene() on empty stack returns None."""
    stack = mock_game._scene_stack
    assert stack.get_base_scene() is None


def test_get_base_scene_single_returns_it(mock_game: Game) -> None:
    """get_base_scene() with one scene returns that scene."""
    stack = mock_game._scene_stack
    s = TrackingScene("S")
    mock_game.push(s)
    assert stack.get_base_scene() is s


# ---------------------------------------------------------------------------
# Edge cases: re-entrant mutations (push/pop during on_enter / on_exit)
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
# Edge cases: replace on empty stack
# ---------------------------------------------------------------------------


def test_replace_on_empty_stack_acts_as_push(mock_game: Game) -> None:
    """replace(scene) when stack is empty pushes the scene (no on_exit to call)."""
    a = TrackingScene("A")
    mock_game.replace(a)

    assert mock_game._scene_stack.top() is a
    assert a.enters == ["A"]
    assert a.exits == []


# ---------------------------------------------------------------------------
# Edge cases: push(None) / replace(None) / clear_and_push(None)
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
# Edge cases: double push of same scene instance
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
# Edge cases: push scene that raises in on_enter (rollback behavior)
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
