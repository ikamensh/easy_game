# Agent Guidelines — Saga2D

Instructions for AI agents working on this codebase.

## The #1 Rule: Visually Verify Rendering Changes

Mock backend tests are necessary but insufficient.  They test logic (scene
stack, text content, input handling) but cannot test:

- Z-ordering between draw calls (rects vs text vs sprites)
- Alpha blending and transparency compositing
- Layout positioning on actual GPU-rendered frames
- Font rendering and sizing

**After any change to UI components, the draw pipeline, or the pyglet
backend, you MUST take pyglet screenshots and inspect them.**

### How we found the overlay z-order bug

1. Wrote mock backend tests for a menu tutorial — 34 tests, all passed.
2. Asked "how confident are you it works in graphics?" — answer: not enough.
3. Took pyglet screenshots of each screen — revealed that text from the base
   scene bled through overlay panel backgrounds.
4. Root cause: all `draw_text` and `draw_rect` used the same pyglet Group
   (`order=100`), so GPU draw order between scenes was undefined.
5. Mock tests could never catch this — they just record call lists, not
   actual pixel output.

### Screenshot capture technique

See `CLAUDE.md` for the monkey-patch pattern.  Key gotcha: pyglet
double-buffers, so you must capture **between** `batch.draw()` and
`window.flip()`.  Capturing after `end_frame()` reads a stale buffer and
every screenshot looks identical.

## Architecture Quick Reference

### Draw Pipeline (scene stack → GPU)

```
begin_frame()  — clear screen with base scene's background_color
│
├─ Base scene (lowest opaque)
│  ├─ scene.draw()     — sprites, custom draw calls
│  └─ scene.ui.draw()  — UI component tree (Panel → Label, Button)
│
├─ HUD (if visible)
│
├─ Overlay 1 (transparent=True)
│  ├─ scene.draw()
│  └─ scene.ui.draw()
│
├─ Overlay 2 ...
│
end_frame()  — batch.draw() then window.flip()
```

Each scene's UI elements MUST render above the previous scene's elements.
This requires the backend to assign increasing z-order groups per scene layer.

### Backend Protocol

- `saga2d/backends/base.py` — abstract protocol (what backends must implement)
- `saga2d/backends/mock_backend.py` — headless testing (records operations)
- `saga2d/backends/pyglet_backend.py` — GPU rendering (single file, ~700 lines)

The protocol uses `begin_frame/end_frame` for GPU batch compatibility.
Per-frame calls (`draw_text`, `draw_rect`, `draw_image`) are cleared each
`begin_frame` and rendered during `end_frame`.

### Key Files for UI/Rendering

| File | What it does |
|------|--------------|
| `saga2d/game.py` | Game loop, scene stack tick/draw orchestration |
| `saga2d/scene.py` | Scene class + SceneStack (push/pop/replace/clear_and_push) |
| `saga2d/ui/component.py` | Component base, _UIRoot, tree draw/input dispatch |
| `saga2d/ui/components.py` | Panel, Label, Button — `on_draw` calls `draw_rect`/`draw_text` |
| `saga2d/rendering/layers.py` | RenderLayer enum (GROUND..OVERLAY), sprite z-ordering |

### Testing Patterns

- Mock backend: `Game("test", resolution=(800,600), backend="mock")`
- Step frames: `game.tick(dt=0.016)`
- Inject input: `game.backend.inject_key("escape")`, `inject_click(x, y)`
- Assert text: `[t["text"] for t in game.backend.texts]`
- Assert stack: `[s.__class__.__name__ for s in game._scene_stack._stack]`

### Common Pitfalls

1. **Don't trust mock tests alone for visual correctness** — they prove logic, not rendering.
2. **Pyglet Groups determine draw order** — items in the same Group have no guaranteed ordering.  Different scene layers need different Group orders.
3. **Double buffering** — screenshot capture must happen between `batch.draw()` and `window.flip()`.
4. **Y-axis flip** — pyglet uses OpenGL bottom-left origin; the framework uses top-left.  The backend handles conversion in `_to_physical`.
5. **Pyglet event handlers MUST return True** — pyglet's `dispatch_event` checks the instance handler first; if it returns `None` (falsy), it falls through to the class-level default.  `Window.on_key_press` closes the window on ESC by default.  Every `@window.event` handler must `return True` to prevent this.  Mock tests can't catch this because `inject_key()` bypasses pyglet's `EventDispatcher` entirely.

### Why mock tests have a blind spot

`inject_key("escape")` adds a `KeyEvent` directly to `_event_queue`.  The
game's `tick()` picks it up via `poll_events()` and routes it through
`handle_input` / `bind_key` — all framework code.

But in a real pyglet window, the key press goes through pyglet's
`EventDispatcher.dispatch_event("on_key_press", ...)` FIRST.  If the handler
returns falsy, pyglet's default fires BEFORE our framework ever sees the
event.  This means:

- **Mock test:** ESC → `_event_queue` → `bind_key("cancel")` → push PauseMenu ✓
- **Real pyglet:** ESC → `dispatch_event` → handler returns None → fallthrough → `Window.on_key_press` → `on_close` → app exits ✗

The lesson: for input handling, also test with `window.dispatch_event()` to
exercise the real pyglet path, not just `inject_key()`.
