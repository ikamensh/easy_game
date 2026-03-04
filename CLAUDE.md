# Saga2D — Project Instructions

## Visual Verification is MANDATORY — Not Optional

Mock backend tests prove logic (scene stack, navigation, text content) but say
**nothing** about actual rendering. Screenshot tests that auto-generate golden
images prove consistency, not quality. **You must actually render and LOOK at
the output to verify visual quality.**

### The render-and-look protocol

**Every** visual change requires this loop:

1. Render to PNG using the screenshot harness
2. **Open the PNG and examine it with your vision** — read the file
3. Ask: "Would a game developer ship this?" If no → iterate
4. Only then update golden images or mark the task done

```python
from tests.screenshot.harness import render_scene

def setup(game):
    # set up your scene, sprites, UI...
    pass

image = render_scene(setup, tick_count=2, resolution=(800, 600))
image.save("/tmp/verify.png")
# NOW READ /tmp/verify.png AND LOOK AT IT
```

**Do NOT trust "tests pass" as visual verification.** A screenshot test passing
means pixels match the golden — it says nothing about whether the golden itself
looks good. The golden images are auto-generated on first run.

### What to verify visually

- Overlay panels occlude content below them (text bleed-through = z-order bug)
- Layout centering and spacing look correct
- Background colors apply per-scene
- Buttons have visible backgrounds with readable text
- Transparent overlays show the scene below
- **Text is readable** — right size, good contrast, no overlap with other elements
- **Tiles are seamless** — no visible gaps or seams between adjacent tiles
- **Colors are attractive** — not just "renders something"
- **Spacing feels right** — padding, margins, element separation

### Capturing screenshots (low-level alternative)

Pyglet double-buffers.  You must capture **after** `batch.draw()` but
**before** `window.flip()`, otherwise you get stale buffer contents.

```python
import pyglet
from saga2d import Game

game = Game("Test", resolution=(800, 600), backend="pyglet")
# Use game.backend.capture_frame() after tick — see harness.py
```

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

- `saga2d/` — framework source
- `saga2d/backends/` — backend implementations (base protocol, mock, pyglet)
- `tests/` — pytest suite
- `tutorials/` — runnable tutorial demos with companion tests
- `examples/` — example games
- `DESIGN.md` — backend-agnostic design document
- `BACKEND.md` — pyglet implementation specifics
- `PLAN.md` — 13-stage implementation plan (all stages complete)
