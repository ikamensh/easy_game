# EasyGame — Project Instructions

## Visual Verification is Mandatory

Mock backend tests prove logic (scene stack, navigation, text content) but say
**nothing** about actual rendering.  Every UI or rendering change MUST be
visually verified with the pyglet backend before it's considered done.

### How to take screenshots

Pyglet double-buffers.  You must capture **after** `batch.draw()` but
**before** `window.flip()`, otherwise you get stale buffer contents.

The pattern that works — monkey-patch `end_frame`:

```python
import pyglet
from easygame import Game

game = Game("Test", resolution=(800, 600), backend="pyglet")
_orig = game.backend.end_frame
_capture = None

def _patched():
    if game.backend.window is None or game.backend.batch is None:
        return
    game.backend.batch.draw()
    if _capture:
        pyglet.image.get_buffer_manager().get_color_buffer().save(_capture)
    game.backend.window.flip()

game.backend.end_frame = _patched
```

Set `_capture = "/tmp/shot.png"` on the frame you want to capture, then set
it back to `None`.  Drive the game with `pyglet.clock.schedule_interval` +
`game.tick(dt=0.016)`.

### What to verify visually

- Overlay panels occlude content below them (text bleed-through = z-order bug)
- Layout centering and spacing look correct
- Background colors apply per-scene
- Buttons have visible backgrounds with readable text
- Transparent overlays show the scene below

### Bug we found this way (2026-02)

All `draw_text` and `draw_rect` calls used a single pyglet Group (`order=100`).
Transparent overlay panels couldn't occlude text from the scene below — text
from both scenes rendered at the same z-level and overlapped.  Mock tests
couldn't catch this because they don't test GPU draw ordering.

## Testing

- `uv run python -m pytest tests/ -v` — full suite (1400+ tests)
- Mock backend: `backend="mock"` — headless, records all operations
- Use `game.tick(dt=0.016)` to step frames in tests
- `game.backend.inject_key("escape")` / `inject_click(x, y)` for input
- `game.backend.texts` — list of `{"text": ...}` dicts rendered this frame
- `game._scene_stack._stack` — current scene stack for assertions

### Mock tests cannot catch pyglet event dispatch bugs

`inject_key()` adds events directly to the queue, bypassing pyglet's
`EventDispatcher`.  Pyglet's dispatch checks the instance handler first —
if it returns a falsy value, **it falls through to the class-level default**.
For example, `Window.on_key_press` closes the window on ESC by default.

**All pyglet event handlers MUST return `True`** to prevent fallthrough.
A handler returning `None` (Python's implicit return) lets pyglet's default
fire.  This caused ESC to close the window instead of being handled by the
game's scene stack.  Mock tests never caught it because `inject_key` doesn't
go through pyglet's `dispatch_event`.

## Project Structure

- `easygame/` — framework source
- `easygame/backends/` — backend implementations (base protocol, mock, pyglet)
- `tests/` — pytest suite
- `tutorials/` — runnable tutorial demos with companion tests
- `examples/` — example games
- `DESIGN.md` — backend-agnostic design document
- `BACKEND.md` — pyglet implementation specifics
- `PLAN.md` — 13-stage implementation plan (all stages complete)
