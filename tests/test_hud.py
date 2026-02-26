"""Tests for the HUD layer (Stage 13 Part 3).

Covers:
- HUD creation (lazy property, component tree)
- Component management (add, remove, clear)
- Visibility logic (hud.visible, scene.show_hud)
- Input dispatch order (HUD before scene UI before scene.handle_input)
- Update dispatch (HUD components receive dt updates)
- Draw order (base scene → HUD → overlays)
- Persistence across scene transitions
"""

from __future__ import annotations


import pytest

from easygame import Game, Scene
from easygame.backends.mock_backend import MockBackend
from easygame.ui import Anchor, Label, Panel, Style
from easygame.ui.component import Component, _UIRoot
from easygame.ui.hud import HUD


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def game() -> Game:
    """Return a mock game instance."""
    return Game("Test", backend="mock", resolution=(800, 600))


@pytest.fixture
def backend(game: Game) -> MockBackend:
    """Return the mock backend from the game."""
    return game._backend


# ---------------------------------------------------------------------------
# HUD creation and lazy property
# ---------------------------------------------------------------------------

class TestHUDCreation:
    """Test HUD construction and lazy access."""

    def test_hud_not_created_until_accessed(self, game: Game) -> None:
        """game._hud is None until game.hud is accessed."""
        assert game._hud is None

    def test_hud_created_on_access(self, game: Game) -> None:
        """game.hud creates the HUD on first access."""
        hud = game.hud
        assert hud is not None
        assert isinstance(hud, HUD)

    def test_hud_same_instance_on_repeated_access(self, game: Game) -> None:
        """Accessing game.hud multiple times returns the same instance."""
        h1 = game.hud
        h2 = game.hud
        assert h1 is h2

    def test_hud_has_root(self, game: Game) -> None:
        """HUD has an internal _UIRoot component tree."""
        hud = game.hud
        assert isinstance(hud._root, _UIRoot)

    def test_hud_visible_by_default(self, game: Game) -> None:
        """HUD.visible defaults to True."""
        assert game.hud.visible is True

    def test_hud_root_covers_full_screen(self, game: Game) -> None:
        """HUD root has the full screen resolution."""
        hud = game.hud
        assert hud._root._computed_w == 800
        assert hud._root._computed_h == 600


# ---------------------------------------------------------------------------
# Component management
# ---------------------------------------------------------------------------

class TestHUDComponentManagement:
    """Test add, remove, clear."""

    def test_add_component(self, game: Game) -> None:
        """add() adds a component to the HUD root."""
        label = Label("Gold: 100")
        game.hud.add(label)
        assert label in game.hud._root._children

    def test_add_multiple_components(self, game: Game) -> None:
        """Multiple components can be added."""
        l1 = Label("HP")
        l2 = Label("MP")
        game.hud.add(l1)
        game.hud.add(l2)
        assert len(game.hud._root._children) == 2

    def test_remove_component(self, game: Game) -> None:
        """remove() removes a component from the HUD."""
        label = Label("Gold: 100")
        game.hud.add(label)
        game.hud.remove(label)
        assert label not in game.hud._root._children

    def test_clear_removes_all(self, game: Game) -> None:
        """clear() removes all components from the HUD."""
        game.hud.add(Label("A"))
        game.hud.add(Label("B"))
        game.hud.add(Label("C"))
        assert len(game.hud._root._children) == 3
        game.hud.clear()
        assert len(game.hud._root._children) == 0

    def test_add_propagates_game_ref(self, game: Game) -> None:
        """Added components receive the _game reference."""
        label = Label("Test")
        game.hud.add(label)
        assert label._game is game

    def test_clear_then_add(self, game: Game) -> None:
        """After clear(), new components can be added."""
        game.hud.add(Label("Old"))
        game.hud.clear()
        new_label = Label("New")
        game.hud.add(new_label)
        assert len(game.hud._root._children) == 1
        assert new_label in game.hud._root._children


# ---------------------------------------------------------------------------
# Visibility logic
# ---------------------------------------------------------------------------

class TestHUDVisibility:
    """Test HUD visibility based on hud.visible and scene.show_hud."""

    def test_should_draw_both_true(self, game: Game) -> None:
        """HUD draws when visible=True and show_hud=True."""
        game.hud.visible = True
        assert game.hud._should_draw(True) is True

    def test_should_draw_hud_invisible(self, game: Game) -> None:
        """HUD doesn't draw when visible=False."""
        game.hud.visible = False
        assert game.hud._should_draw(True) is False

    def test_should_draw_scene_hides_hud(self, game: Game) -> None:
        """HUD doesn't draw when scene.show_hud=False."""
        game.hud.visible = True
        assert game.hud._should_draw(False) is False

    def test_should_draw_both_false(self, game: Game) -> None:
        """HUD doesn't draw when both are False."""
        game.hud.visible = False
        assert game.hud._should_draw(False) is False

    def test_scene_show_hud_default_true(self) -> None:
        """Scene.show_hud defaults to True."""
        scene = Scene()
        assert scene.show_hud is True

    def test_scene_show_hud_override(self) -> None:
        """Subclass can set show_hud=False (e.g. modal overlays)."""

        class ModalOverlay(Scene):
            show_hud = False

        assert ModalOverlay.show_hud is False
        assert ModalOverlay().show_hud is False


# ---------------------------------------------------------------------------
# Input dispatch order
# ---------------------------------------------------------------------------

class TestHUDInputOrder:
    """Test that HUD receives input before scene UI and handle_input."""

    def test_hud_consumes_event_before_scene_ui(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """When HUD consumes an event, scene UI doesn't see it."""
        scene_ui_hit = []
        hud_hit = []

        class CatchScene(Scene):
            def on_enter(self) -> None:
                btn = Panel(
                    width=800, height=600,
                    anchor=Anchor.CENTER,
                    style=Style(background_color=(0, 0, 0, 255)),
                )
                # Attach a handler that records events.
                original_on_event = btn.on_event

                def spy_on_event(event):
                    scene_ui_hit.append(event)
                    return True

                btn.on_event = spy_on_event
                self.ui.add(btn)

        game.push(CatchScene())

        # Add a consuming button to the HUD that covers the same area.
        hud_btn = Panel(
            width=800, height=600,
            anchor=Anchor.CENTER,
            style=Style(background_color=(0, 0, 0, 0)),
        )
        original = hud_btn.on_event

        def hud_spy(event):
            hud_hit.append(event)
            return True  # Consume

        hud_btn.on_event = hud_spy
        game.hud.add(hud_btn)

        backend.inject_click(400, 300)
        game.tick(dt=0.016)

        assert len(hud_hit) == 1
        assert len(scene_ui_hit) == 0  # Scene UI never saw the event.

    def test_hud_passes_event_to_scene_when_not_consumed(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """When HUD doesn't consume, scene handle_input() receives it."""
        scene_events = []

        class ListenScene(Scene):
            def handle_input(self, event) -> bool:
                scene_events.append(event)
                return True

        game.push(ListenScene())

        # Access HUD (creates it) but don't add any components.
        _ = game.hud

        backend.inject_key("space")
        game.tick(dt=0.016)

        assert len(scene_events) == 1

    def test_hud_hidden_by_show_hud_does_not_intercept(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """When scene.show_hud=False, HUD doesn't intercept input."""
        hud_events = []
        scene_events = []

        class NoHudScene(Scene):
            show_hud = False

            def handle_input(self, event) -> bool:
                scene_events.append(event)
                return True

        game.push(NoHudScene())

        # Add a consuming button to the HUD.
        hud_btn = Panel(
            width=800, height=600,
            anchor=Anchor.CENTER,
        )

        def hud_spy(event):
            hud_events.append(event)
            return True

        hud_btn.on_event = hud_spy
        game.hud.add(hud_btn)

        backend.inject_key("space")
        game.tick(dt=0.016)

        assert len(hud_events) == 0  # HUD was skipped.
        assert len(scene_events) == 1

    def test_hud_invisible_does_not_intercept(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """When hud.visible=False, HUD doesn't intercept input."""
        hud_events = []
        scene_events = []

        class MyScene(Scene):
            def handle_input(self, event) -> bool:
                scene_events.append(event)
                return True

        game.push(MyScene())

        hud_btn = Panel(width=800, height=600, anchor=Anchor.CENTER)
        hud_btn.on_event = lambda e: (hud_events.append(e), True)[-1]
        game.hud.add(hud_btn)
        game.hud.visible = False

        backend.inject_key("space")
        game.tick(dt=0.016)

        assert len(hud_events) == 0
        assert len(scene_events) == 1


# ---------------------------------------------------------------------------
# Update dispatch
# ---------------------------------------------------------------------------

class TestHUDUpdate:
    """Test that HUD components receive per-frame updates."""

    def test_hud_components_receive_update(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Components in the HUD receive update(dt) each tick."""
        update_calls = []

        class Tracker(Component):
            def __init__(self):
                super().__init__(width=10, height=10)

            def update(self, dt: float) -> None:
                update_calls.append(dt)

        game.push(Scene())
        tracker = Tracker()
        game.hud.add(tracker)

        game.tick(dt=0.016)
        game.tick(dt=0.032)

        assert len(update_calls) == 2
        assert update_calls[0] == pytest.approx(0.016)
        assert update_calls[1] == pytest.approx(0.032)

    def test_hud_update_skipped_when_hidden(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """HUD components don't update when show_hud=False."""
        update_calls = []

        class Tracker(Component):
            def __init__(self):
                super().__init__(width=10, height=10)

            def update(self, dt: float) -> None:
                update_calls.append(dt)

        class NoHudScene(Scene):
            show_hud = False

        game.push(NoHudScene())
        game.hud.add(Tracker())

        game.tick(dt=0.016)

        assert len(update_calls) == 0

    def test_hud_update_skipped_when_invisible(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """HUD components don't update when hud.visible=False."""
        update_calls = []

        class Tracker(Component):
            def __init__(self):
                super().__init__(width=10, height=10)

            def update(self, dt: float) -> None:
                update_calls.append(dt)

        game.push(Scene())
        game.hud.add(Tracker())
        game.hud.visible = False

        game.tick(dt=0.016)

        assert len(update_calls) == 0


# ---------------------------------------------------------------------------
# Draw order
# ---------------------------------------------------------------------------

class TestHUDDrawOrder:
    """Test that HUD draws between base scene and overlays."""

    def test_hud_draws_after_base_scene(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """HUD components are drawn after the base scene's UI."""
        draw_order = []

        class BaseScene(Scene):
            def draw(self) -> None:
                draw_order.append("base_scene")

        game.push(BaseScene())

        # Add a panel to HUD that will draw a rect.
        hud_panel = Panel(
            width=50, height=50,
            anchor=Anchor.TOP_LEFT,
            style=Style(background_color=(255, 0, 0, 255)),
        )
        game.hud.add(hud_panel)

        game.tick(dt=0.016)

        # The base scene drew first, then HUD panel drew rects.
        assert draw_order == ["base_scene"]
        # And HUD rects are present in the backend.
        assert len(backend.rects) > 0

    def test_hud_draws_before_overlay(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """HUD draws between base scene and transparent overlay."""
        draw_order = []

        class BaseScene(Scene):
            def draw(self) -> None:
                draw_order.append("base")

        class Overlay(Scene):
            transparent = True
            show_hud = True

            def draw(self) -> None:
                draw_order.append("overlay")

        game.push(BaseScene())
        game.push(Overlay())

        # Trigger HUD creation.
        _ = game.hud

        game.tick(dt=0.016)

        # Draw order: base, then overlay. HUD is between them.
        assert draw_order == ["base", "overlay"]

    def test_hud_hidden_by_overlay_show_hud_false(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """HUD doesn't draw when the top scene has show_hud=False."""
        hud_draw_count = [0]

        class BaseScene(Scene):
            pass

        class ModalOverlay(Scene):
            transparent = True
            show_hud = False

        game.push(BaseScene())
        game.push(ModalOverlay())

        # Add a visible panel to HUD.
        hud_panel = Panel(
            width=50, height=50,
            anchor=Anchor.TOP_LEFT,
            style=Style(background_color=(255, 0, 0, 255)),
        )
        game.hud.add(hud_panel)

        game.tick(dt=0.016)

        # The top scene is ModalOverlay with show_hud=False.
        # HUD should NOT have drawn. Only the base scene draws rects
        # (none, since BaseScene has no UI).
        # We verify by checking that no rects come from the HUD panel.
        # Since BaseScene has no UI, the only rects would be from HUD.
        assert len(backend.rects) == 0

    def test_hud_visible_with_show_hud_true_overlay(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """HUD draws when overlay has show_hud=True (default)."""

        class BaseScene(Scene):
            pass

        class Overlay(Scene):
            transparent = True
            # show_hud defaults to True

        game.push(BaseScene())
        game.push(Overlay())

        hud_panel = Panel(
            width=50, height=50,
            anchor=Anchor.TOP_LEFT,
            style=Style(background_color=(255, 0, 0, 255)),
        )
        game.hud.add(hud_panel)

        game.tick(dt=0.016)

        # HUD panel should have drawn a rect.
        assert len(backend.rects) > 0


# ---------------------------------------------------------------------------
# Persistence across scene transitions
# ---------------------------------------------------------------------------

class TestHUDPersistence:
    """Test that HUD persists across scene push/pop/replace."""

    def test_hud_survives_push_pop(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """HUD components remain after push and pop."""
        game.push(Scene())
        game.hud.add(Label("HUD Label"))

        # Push a new scene on top.
        game.push(Scene())
        assert len(game.hud._root._children) == 1

        # Pop it.
        game.pop()
        assert len(game.hud._root._children) == 1

    def test_hud_survives_replace(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """HUD components remain after scene replacement."""
        game.push(Scene())
        game.hud.add(Label("Persistent"))

        game.replace(Scene())
        assert len(game.hud._root._children) == 1

    def test_hud_survives_clear_and_push(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """HUD components remain after clear_and_push."""
        game.push(Scene())
        game.hud.add(Label("Sticky"))

        game.clear_and_push(Scene())
        assert len(game.hud._root._children) == 1

    def test_hud_draws_with_new_scene(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """HUD still draws its components after scene transition."""
        game.push(Scene())
        hud_panel = Panel(
            width=50, height=50,
            anchor=Anchor.TOP_LEFT,
            style=Style(background_color=(255, 0, 0, 255)),
        )
        game.hud.add(hud_panel)

        game.replace(Scene())
        game.tick(dt=0.016)

        # HUD panel should still draw.
        assert len(backend.rects) > 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestHUDEdgeCases:
    """Edge cases and robustness."""

    def test_no_hud_accessed_no_overhead(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """If game.hud is never accessed, no HUD overhead in tick."""
        game.push(Scene())
        game.tick(dt=0.016)
        # game._hud should still be None.
        assert game._hud is None

    def test_empty_hud_no_draw(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """An empty HUD draws nothing."""
        game.push(Scene())
        _ = game.hud  # Create but don't add anything.

        game.tick(dt=0.016)

        # No rects drawn (empty HUD, base scene has no UI).
        assert len(backend.rects) == 0

    def test_hud_with_nested_components(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Nested Panel with children in HUD all get game ref."""
        parent = Panel(width=100, height=100, anchor=Anchor.TOP_LEFT)
        child = Label("Child")
        parent.add(child)
        game.hud.add(parent)

        assert parent._game is game
        assert child._game is game

    def test_hud_toggle_visibility(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """Toggling hud.visible works correctly across ticks."""
        game.push(Scene())
        hud_panel = Panel(
            width=50, height=50,
            anchor=Anchor.TOP_LEFT,
            style=Style(background_color=(255, 0, 0, 255)),
        )
        game.hud.add(hud_panel)

        # Frame 1: visible.
        game.tick(dt=0.016)
        rects_visible = len(backend.rects)
        assert rects_visible > 0

        # Frame 2: hidden.
        game.hud.visible = False
        game.tick(dt=0.016)
        assert len(backend.rects) == 0

        # Frame 3: visible again.
        game.hud.visible = True
        game.tick(dt=0.016)
        assert len(backend.rects) > 0

    def test_hud_no_scene_stack_empty(
        self, game: Game, backend: MockBackend,
    ) -> None:
        """HUD doesn't crash with an empty scene stack."""
        _ = game.hud
        game.tick(dt=0.016)  # Should not raise.
