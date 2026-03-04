"""Screenshot regression tests for StateMachine (saga2d.util.fsm).

Run from the project root::

    pytest tests/screenshot/test_fsm_screenshots.py -v

Requires pyglet (GPU context).  Excluded from the normal ``pytest tests/``
run by ``collect_ignore`` in ``tests/conftest.py``.

Each test creates a Scene that uses a StateMachine to drive which UI panel
is visible.  Different states show different colored panels with labels.
Transitions are triggered during setup; the harness ticks and captures.
"""

from __future__ import annotations

import pytest

from saga2d import Scene, StateMachine
from saga2d.ui import Anchor, Label, Layout, Panel, Style

from tests.screenshot.harness import assert_screenshot, render_scene

_RESOLUTION = (480, 360)

# Distinct colors per state for visual differentiation
_IDLE_COLOR = (60, 180, 80, 240)      # green
_WALKING_COLOR = (60, 100, 200, 240)  # blue
_ATTACKING_COLOR = (200, 80, 60, 240)  # red
_DEAD_COLOR = (80, 80, 80, 240)       # dark grey


class FsmStateScene(Scene):
    """Scene that displays the current FSM state as a colored panel + label."""

    def on_enter(self) -> None:
        self.fsm = StateMachine(
            states=["idle", "walking", "attacking", "dead"],
            initial="idle",
            transitions={
                "idle": {"move": "walking", "attack": "attacking", "die": "dead"},
                "walking": {"arrive": "idle", "attack": "attacking", "die": "dead"},
                "attacking": {"done": "idle", "die": "dead"},
            },
        )
        self._panels: dict[str, Panel] = {}
        for state, color in [
            ("idle", _IDLE_COLOR),
            ("walking", _WALKING_COLOR),
            ("attacking", _ATTACKING_COLOR),
            ("dead", _DEAD_COLOR),
        ]:
            panel = Panel(
                anchor=Anchor.CENTER,
                layout=Layout.VERTICAL,
                spacing=4,
                style=Style(
                    background_color=color,
                    padding=16,
                    font_size=24,
                    text_color=(255, 255, 255, 255),
                ),
            )
            panel.add(Label(state.upper()))
            self._panels[state] = panel
            self.ui.add(panel)
        self._sync_visibility()

    def update(self, dt: float) -> None:
        self._sync_visibility()

    def _sync_visibility(self) -> None:
        for state, panel in self._panels.items():
            panel.visible = self.fsm.state == state


# ---------------------------------------------------------------------------
# 1. Initial state — idle (green panel)
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_fsm_initial_state() -> None:
    """FSM starts in initial state; green IDLE panel displayed.

    No transitions triggered.  The on_enter callback for initial state
    has run; the UI shows the idle state.
    """

    def setup(game):
        game.push(FsmStateScene())

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "fsm_initial_state")


# ---------------------------------------------------------------------------
# 2. After transition: idle → walking (blue panel)
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_fsm_idle_to_walking() -> None:
    """Trigger 'move' from idle; blue WALKING panel displayed."""

    def setup(game):
        game.push(FsmStateScene())
        scene = game._scene_stack.top()
        scene.fsm.trigger("move")

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "fsm_idle_to_walking")


# ---------------------------------------------------------------------------
# 3. After transition: walking → attacking (red panel)
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_fsm_walking_to_attacking() -> None:
    """Trigger 'move' then 'attack'; red ATTACKING panel displayed."""

    def setup(game):
        game.push(FsmStateScene())
        scene = game._scene_stack.top()
        scene.fsm.trigger("move")
        scene.fsm.trigger("attack")

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "fsm_walking_to_attacking")


# ---------------------------------------------------------------------------
# 4. Absorbing state: dead (grey panel, no way out)
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_fsm_absorbing_dead() -> None:
    """Trigger 'die' from idle; grey DEAD panel displayed.

    Dead is an absorbing state — no transitions out.  The FSM stays
    in dead forever.
    """

    def setup(game):
        game.push(FsmStateScene())
        scene = game._scene_stack.top()
        scene.fsm.trigger("die")

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "fsm_absorbing_dead")


# ---------------------------------------------------------------------------
# 5. Self-transition: idle → idle (green panel, callbacks fired)
# ---------------------------------------------------------------------------

@pytest.mark.screenshot
def test_fsm_self_transition_idle() -> None:
    """Self-transition idle→idle via 'reset' event.

    Both on_exit and on_enter fire for self-transitions.  Visually
    still shows green IDLE panel.
    """

    class FsmSelfTransitionScene(Scene):
        def on_enter(self) -> None:
            self.fsm = StateMachine(
                states=["idle", "walking"],
                initial="idle",
                transitions={
                    "idle": {"move": "walking", "reset": "idle"},
                    "walking": {"arrive": "idle"},
                },
            )
            self._panels = {}
            for state, color in [("idle", _IDLE_COLOR), ("walking", _WALKING_COLOR)]:
                panel = Panel(
                    anchor=Anchor.CENTER,
                    layout=Layout.VERTICAL,
                    spacing=4,
                    style=Style(
                        background_color=color,
                        padding=16,
                        font_size=24,
                        text_color=(255, 255, 255, 255),
                    ),
                )
                panel.add(Label(state.upper()))
                self._panels[state] = panel
                self.ui.add(panel)
            self._sync_visibility()

        def update(self, dt: float) -> None:
            self._sync_visibility()

        def _sync_visibility(self) -> None:
            for state, panel in self._panels.items():
                panel.visible = self.fsm.state == state

    def setup(game):
        game.push(FsmSelfTransitionScene())
        scene = game._scene_stack.top()
        scene.fsm.trigger("reset")  # idle → idle

    image = render_scene(setup, tick_count=1, resolution=_RESOLUTION)
    assert_screenshot(image, "fsm_self_transition_idle")
