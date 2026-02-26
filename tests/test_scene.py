"""Tests for Scene and SceneStack lifecycle and deferred operations."""


from easygame.input import InputEvent
from easygame.scene import Scene, SceneStack


class FakeGame:
    """Minimal game object for SceneStack tests."""

    _hud = None


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


def test_push_calls_on_enter():
    """push(B) when empty: B.game set, B.on_enter() called."""
    game = FakeGame()
    stack = SceneStack(game)
    b = TrackingScene("B")

    stack.push(b)

    assert stack.top() is b
    assert b.game is game
    assert b.enters == ["B"]
    assert b.exits == []


def test_push_calls_on_exit_on_previous_top():
    """push(B) when A is top: A.on_exit() then B.on_enter()."""
    game = FakeGame()
    stack = SceneStack(game)
    a = TrackingScene("A")
    b = TrackingScene("B")

    stack.push(a)
    stack.push(b)

    assert a.exits == ["A"]
    assert a.enters == ["A"]
    assert b.enters == ["B"]
    assert stack.top() is b


def test_pop_calls_on_exit_and_on_reveal():
    """pop() when B on top of A: B.on_exit(), remove B, A.on_reveal()."""
    game = FakeGame()
    stack = SceneStack(game)
    a = TrackingScene("A")
    b = TrackingScene("B")

    stack.push(a)
    stack.push(b)
    stack.pop()

    assert stack.top() is a
    assert b.exits == ["B"]
    assert a.reveals == ["A"]
    assert a.exits == ["A"]  # from when B was pushed over A


def test_replace_calls_on_exit_and_on_enter_no_reveal():
    """replace(B) when A is top: A.on_exit(), remove A, B.on_enter()."""
    game = FakeGame()
    stack = SceneStack(game)
    a = TrackingScene("A")
    b = TrackingScene("B")

    stack.push(a)
    stack.replace(b)

    assert stack.top() is b
    assert a.exits == ["A"]
    assert b.enters == ["B"]
    assert a.reveals == []  # replace does not call on_reveal


def test_clear_and_push_calls_on_exit_on_all():
    """clear_and_push(C) when A,B on stack: B.on_exit(), A.on_exit(), C.on_enter()."""
    game = FakeGame()
    stack = SceneStack(game)
    a = TrackingScene("A")
    b = TrackingScene("B")
    c = TrackingScene("C")

    stack.push(a)
    stack.push(b)
    stack.clear_and_push(c)

    assert stack.top() is c
    assert len(stack._stack) == 1
    # A got on_exit when covered by B, then again when cleared
    assert a.exits == ["A", "A"]
    assert b.exits == ["B"]
    assert c.enters == ["C"]


def test_deferred_push_during_tick():
    """push() during update is deferred until flush."""
    game = FakeGame()
    stack = SceneStack(game)
    a = TrackingScene("A")
    b = TrackingScene("B")

    stack.push(a)
    stack.begin_tick()
    stack.push(b)

    assert stack.top() is a  # b not applied yet
    assert len(stack._stack) == 1

    stack.flush_pending_ops()

    assert stack.top() is b
    assert a.exits == ["A"]
    assert b.enters == ["B"]


def test_deferred_pop_during_tick():
    """pop() during handle_input is deferred until flush."""
    game = FakeGame()
    stack = SceneStack(game)
    a = TrackingScene("A")
    b = TrackingScene("B")

    stack.push(a)
    stack.push(b)
    stack.begin_tick()
    stack.pop()

    assert stack.top() is b  # still b before flush

    stack.flush_pending_ops()

    assert stack.top() is a
    assert b.exits == ["B"]
    assert a.reveals == ["A"]


def test_push_outside_tick_executes_immediately():
    """push() when not in tick executes immediately."""
    game = FakeGame()
    stack = SceneStack(game)
    a = TrackingScene("A")

    stack.push(a)

    assert stack.top() is a
    assert a.enters == ["A"]
    assert not stack._pending_ops


def test_empty_stack_top_returns_none():
    """top() on empty stack returns None."""
    game = FakeGame()
    stack = SceneStack(game)

    assert stack.top() is None


def test_pop_empty_stack_no_crash():
    """pop() on empty stack does not crash."""
    game = FakeGame()
    stack = SceneStack(game)

    stack.pop()
    assert stack.top() is None


def test_update_and_draw_empty_stack_no_crash():
    """update() and draw() on empty stack do not crash."""
    game = FakeGame()
    stack = SceneStack(game)

    stack.update(0.016)
    stack.draw()


def test_update_calls_top_scene():
    """update(dt) calls top scene's update with dt."""
    game = FakeGame()
    stack = SceneStack(game)
    a = TrackingScene("A")

    stack.push(a)
    stack.update(0.032)

    assert a.updates == [0.032]


def test_draw_only_top_opaque_scene():
    """draw() with two opaque scenes only draws the top one."""
    game = FakeGame()
    stack = SceneStack(game)
    a = TrackingScene("A")
    b = TrackingScene("B")

    stack.push(a)
    stack.push(b)
    stack.draw()

    # B is opaque (transparent=False), so A is fully covered.
    assert a.draws == 0
    assert b.draws == 1


def test_pause_below_false_updates_scenes_below():
    """When top has pause_below=False, scene below also gets update."""
    game = FakeGame()
    stack = SceneStack(game)
    a = TrackingScene("A")
    b = TrackingScene("B")
    b.pause_below = False

    stack.push(a)
    stack.push(b)
    stack.update(0.016)

    assert a.updates == [0.016]
    assert b.updates == [0.016]


def test_draw_transparent_scene_shows_scene_below():
    """draw() with transparent top scene draws both scenes."""
    game = FakeGame()
    stack = SceneStack(game)
    a = TrackingScene("A")
    b = TrackingScene("B")
    b.transparent = True

    stack.push(a)
    stack.push(b)
    stack.draw()

    # B is transparent, so A (opaque) and B are both drawn.
    assert a.draws == 1
    assert b.draws == 1


def test_draw_three_scenes_transparency_chain():
    """draw() walks through transparent scenes until an opaque one."""
    game = FakeGame()
    stack = SceneStack(game)
    a = TrackingScene("A")
    b = TrackingScene("B")
    c = TrackingScene("C")
    # A: opaque, B: opaque, C: transparent
    c.transparent = True

    stack.push(a)
    stack.push(b)
    stack.push(c)
    stack.draw()

    # C is transparent → look below. B is opaque → stop.
    # Draw B, then C. A is not drawn.
    assert a.draws == 0
    assert b.draws == 1
    assert c.draws == 1


def test_draw_all_transparent_draws_entire_stack():
    """draw() draws all scenes when every scene is transparent."""
    game = FakeGame()
    stack = SceneStack(game)
    a = TrackingScene("A")
    b = TrackingScene("B")
    c = TrackingScene("C")
    a.transparent = True
    b.transparent = True
    c.transparent = True

    stack.push(a)
    stack.push(b)
    stack.push(c)
    stack.draw()

    # All transparent → draw from index 0 (bottom) up.
    assert a.draws == 1
    assert b.draws == 1
    assert c.draws == 1


def test_draw_single_scene():
    """draw() with a single scene always draws it."""
    game = FakeGame()
    stack = SceneStack(game)
    a = TrackingScene("A")

    stack.push(a)
    stack.draw()

    assert a.draws == 1


def test_scene_handle_input_default_returns_false():
    """Default handle_input returns False (not consumed)."""
    s = Scene()
    event = InputEvent(type="key_press", key="space")
    assert s.handle_input(event) is False


# ---------------------------------------------------------------------------
# background_color — framework clears screen before drawing
# ---------------------------------------------------------------------------


def test_background_color_none_passes_no_clear_color(mock_game, mock_backend):
    """Scene without background_color: begin_frame receives clear_color=None."""
    class PlainScene(Scene):
        pass

    mock_game.push(PlainScene())
    mock_game.tick(dt=0.016)

    assert mock_backend.clear_color is None


def test_background_color_rgb_passes_clear_color(mock_game, mock_backend):
    """Scene with background_color=(R,G,B): begin_frame receives it (alpha=255 implied)."""
    class GreenScene(Scene):
        background_color = (34, 139, 34)

    mock_game.push(GreenScene())
    mock_game.tick(dt=0.016)

    assert mock_backend.clear_color == (34, 139, 34)


def test_background_color_rgba_passes_clear_color(mock_game, mock_backend):
    """Scene with background_color=(R,G,B,A): begin_frame receives full tuple."""
    class SemiTransparentScene(Scene):
        background_color = (25, 30, 40, 200)

    mock_game.push(SemiTransparentScene())
    mock_game.tick(dt=0.016)

    assert mock_backend.clear_color == (25, 30, 40, 200)


def test_background_color_uses_base_scene_when_transparent_overlay(mock_game, mock_backend):
    """When top scene is transparent, base (opaque) scene's background_color is used."""
    class BaseScene(Scene):
        background_color = (100, 50, 25, 255)

    class OverlayScene(Scene):
        transparent = True
        background_color = (0, 0, 0, 255)  # ignored — we use base's

    mock_game.push(BaseScene())
    mock_game.push(OverlayScene())
    mock_game.tick(dt=0.016)

    # Base scene is the opaque one; its background_color wins.
    assert mock_backend.clear_color == (100, 50, 25, 255)


def test_get_base_scene_empty_returns_none():
    """get_base_scene() on empty stack returns None."""
    from easygame.scene import SceneStack

    class FakeGame:
        _hud = None

    stack = SceneStack(FakeGame())
    assert stack.get_base_scene() is None


def test_get_base_scene_single_returns_it():
    """get_base_scene() with one scene returns that scene."""
    from easygame.scene import SceneStack

    class FakeGame:
        _hud = None

    stack = SceneStack(FakeGame())
    s = TrackingScene("S")
    stack.push(s)
    assert stack.get_base_scene() is s
