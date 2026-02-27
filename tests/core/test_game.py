"""Tests for Game, mock backend, tick/quit/run behavior."""

from easygame import Game, Scene
from easygame.backends.mock_backend import MockBackend


class InputTrackingScene(Scene):
    """Scene that records received input events."""

    def __init__(self) -> None:
        self.events: list = []

    def handle_input(self, event) -> bool:
        self.events.append(event)
        return False


def test_inject_key_reaches_handle_input(mock_game: Game, mock_backend: MockBackend) -> None:
    """inject_key → poll_events → handle_input receives the event."""
    scene = InputTrackingScene()
    mock_game.push(scene)

    mock_backend.inject_key("space")
    mock_game.tick(dt=0.016)

    assert len(scene.events) == 1
    assert scene.events[0].key == "space"
    assert scene.events[0].type == "key_press"


def test_quit_sets_running_false(mock_game: Game) -> None:
    """game.quit() sets running=False."""
    assert mock_game.running is True
    mock_game.quit()
    assert mock_game.running is False


def test_tick_runs_exactly_one_frame(mock_game: Game, mock_backend: MockBackend) -> None:
    """game.tick(dt) runs exactly one frame (begin_frame, draw, end_frame)."""
    scene = Scene()
    mock_game.push(scene)

    assert mock_backend.frame_count == 0
    mock_game.tick(dt=0.016)
    assert mock_backend.frame_count == 1
    mock_game.tick(dt=0.016)
    assert mock_backend.frame_count == 2


def test_mock_backend_records_sprite_text_sound(mock_game: Game, mock_backend: MockBackend) -> None:
    """Mock backend records sprite, text, and sound operations from a scene."""

    class RecordingScene(Scene):
        def __init__(self) -> None:
            self._sprite_id: str | None = None

        def on_enter(self) -> None:
            img = self.game.backend.load_image("hero.png")
            self._sprite_id = self.game.backend.create_sprite(img, layer_order=0)
            self.game.backend.update_sprite(self._sprite_id, x=100, y=200)

        def draw(self) -> None:
            self.game.backend.draw_rect(10, 10, 100, 50, (255, 0, 0, 128))
            self.game.backend.draw_text("Hello", 50, 50, 24, (255, 255, 255, 255))

        def update(self, dt: float) -> None:
            snd = self.game.backend.load_sound("beep.wav")
            self.game.backend.play_sound(snd)

    mock_game.push(RecordingScene())
    mock_game.tick(dt=0.016)

    assert len(mock_backend.sprites) >= 1
    assert any(s["x"] == 100 and s["y"] == 200 for s in mock_backend.sprites.values())
    assert len(mock_backend.rects) >= 1
    assert any(r["x"] == 10 and r["width"] == 100 for r in mock_backend.rects)
    assert len(mock_backend.texts) >= 1
    assert any(t["text"] == "Hello" for t in mock_backend.texts)
    assert len(mock_backend.sounds_played) >= 1


def test_run_pushes_start_scene_and_loops() -> None:
    """run() pushes the start scene, loops, and exits when quit is called."""
    game = Game("Test", backend="mock", resolution=(1920, 1080))

    class QuitAfterThreeFrames(Scene):
        def __init__(self) -> None:
            self.frame = 0

        def update(self, dt: float) -> None:
            self.frame += 1
            if self.frame >= 3:
                self.game.quit()

    scene = QuitAfterThreeFrames()
    game.run(scene)

    # Exactly 3 frames ran (update increments before quit, tick still draws).
    assert scene.frame == 3
    assert game.running is False


def test_run_calls_backend_quit_after_loop() -> None:
    """run() calls backend.quit() after the loop exits."""
    game = Game("Test", backend="mock", resolution=(1920, 1080))
    backend = game.backend

    class QuitImmediately(Scene):
        def update(self, dt: float) -> None:
            self.game.quit()

    game.run(QuitImmediately())

    assert backend.is_running is False


def test_window_close_stops_run_loop() -> None:
    """Window close event causes run() to exit cleanly."""
    game = Game("Test", backend="mock", resolution=(1920, 1080))
    backend = game.backend

    class InjectCloseOnFirstFrame(Scene):
        def __init__(self) -> None:
            self.frame = 0

        def update(self, dt: float) -> None:
            self.frame += 1
            if self.frame == 1:
                # Next tick will see the close event
                backend.inject_window_event("close")

    scene = InjectCloseOnFirstFrame()
    game.run(scene)

    assert game.running is False
    assert backend.is_running is False
