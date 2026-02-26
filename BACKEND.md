# Backend Implementation: Pyglet

This document covers the implementation-specific details of the first backend.
For the framework's requirements and abstractions, see `DESIGN.md`.

## Why Pyglet

### Decision context

The framework needs a backend that can: render sprites on a 2D canvas with layering,
play audio with channels, handle window/input events, and load images/fonts. The
backend is completely hidden from users — only the framework code touches it.

### Options considered

| Backend | Rendering | Language | Install |
|---|---|---|---|
| **pygame / pygame-ce** | CPU (SDL2 surfaces) | Python wrapper over C | `pip install pygame-ce` |
| **pyglet** | GPU (OpenGL) | Pure Python | `pip install pyglet` |
| **raylib** (Python CFFI) | GPU (OpenGL) | C library + CFFI | `pip install raylib` |
| **SDL2 direct** (pysdl2) | CPU or GPU | Python wrapper | `pip install pysdl2` + system lib |
| **moderngl** | GPU (OpenGL) | Python wrapper | `pip install moderngl` |

### Why pyglet wins

**GPU by default.** Pyglet uses OpenGL for all rendering. Sprites are textures on the
GPU. Drawing 1000 sprites costs roughly the same as drawing 10 when batched. This
removes the performance ceiling that CPU-based backends (pygame) hit at a few hundred
sprites.

**Pure Python.** No CFFI, no binary dependencies to install, no C crashes with opaque
error messages. Stack traces are readable Python. This matters enormously for debugging
during framework development.

**Built-in sprite batching.** `pyglet.graphics.Batch` collects all draw calls and
submits them to the GPU in one operation. This maps directly to our Backend protocol's
`begin_frame()` / `end_frame()` pattern.

**Rich text rendering.** Pyglet has `Label` with wrapping, alignment, multiline, and
HTML-like formatting. This gives us a head start on `TextBox` and `Label` components
instead of building text layout from scratch.

**Built-in audio.** OpenAL-based audio with multiple channels. Supports WAV and basic
formats out of the box. Sufficient for our channel model (master, music, sfx, ui).

**Mature and maintained.** Pyglet 2.x is actively developed, supports macOS well
(Cocoa windowing), and has been around for nearly 20 years.

### Why not pygame

Pygame is the default choice in Python game dev, but:
- CPU rendering (SDL2 surfaces) — performance ceiling with many sprites
- We'd start with the worst-performing backend, then "upgrade" later
- Since our abstraction layer hides the backend anyway, pygame's large community and
  tutorial ecosystem doesn't benefit our users
- Our abstractions might unconsciously shape around CPU blitting limitations

### Why not raylib

Raylib itself is excellent, but the Python bindings are CFFI wrappers around a C library:
- Two layers of translation (our protocol → CFFI → C) makes debugging harder
- C-level crashes are opaque — segfaults instead of Python exceptions
- Memory management for C structs requires care
- Raylib's clean imperative API is irrelevant since our Backend protocol hides it

Raylib's advantage (simpler draw API) doesn't matter behind an abstraction layer.
Pyglet's advantage (pure Python, rich text, sprite batching) directly reduces our work.

---

## How Pyglet Maps to the Backend Protocol

### Window and lifecycle

```python
import pyglet

class PygletBackend:
    def create_window(self, width, height, fullscreen):
        self.window = pyglet.window.Window(
            width=width, height=height,
            fullscreen=fullscreen,
            vsync=True,
        )

    def begin_frame(self):
        self.window.clear()
        self.batch = pyglet.graphics.Batch()

    def end_frame(self):
        self.batch.draw()      # one GPU call for all sprites
        self.window.flip()
```

### Image loading and drawing

```python
    def load_image(self, path):
        # Returns a pyglet.image.AbstractImage — this IS the ImageHandle
        return pyglet.image.load(str(path))

    def draw_image(self, handle, x, y, opacity=255, scale=1.0, rotation=0):
        # Create a sprite in the current batch
        sprite = pyglet.sprite.Sprite(handle, x=x, y=y, batch=self.batch)
        sprite.opacity = opacity
        sprite.scale = scale
        sprite.rotation = rotation
        # Sprite draws when batch.draw() is called in end_frame()
```

Note: creating a `pyglet.sprite.Sprite` per draw call is not ideal for performance.
The real implementation will maintain a pool of reusable pyglet sprites or use the
lower-level `pyglet.graphics` API directly. This pseudocode shows the mapping.

### Efficient sprite rendering (actual approach)

For production, we'll use pyglet's `Batch` and `Group` system:

```python
class PygletBackend:
    def __init__(self):
        self.batch = pyglet.graphics.Batch()
        # One group per render layer, ordered
        self.groups = {
            RenderLayer.BACKGROUND: pyglet.graphics.Group(order=0),
            RenderLayer.OBJECTS: pyglet.graphics.Group(order=1),
            RenderLayer.UNITS: pyglet.graphics.Group(order=2),
            RenderLayer.EFFECTS: pyglet.graphics.Group(order=3),
            RenderLayer.UI_WORLD: pyglet.graphics.Group(order=4),
        }
        self.sprites = {}  # our Sprite id -> pyglet.sprite.Sprite

    def register_sprite(self, sprite_id, image_handle, layer):
        """Create a persistent pyglet sprite in the batch."""
        group = self.groups[layer]
        pyg_sprite = pyglet.sprite.Sprite(image_handle, batch=self.batch, group=group)
        self.sprites[sprite_id] = pyg_sprite

    def update_sprite(self, sprite_id, x, y, image=None, opacity=255):
        """Update position/image each frame — no new object created."""
        pyg = self.sprites[sprite_id]
        pyg.x, pyg.y = x, y
        pyg.opacity = opacity
        if image:
            pyg.image = image

    def remove_sprite(self, sprite_id):
        self.sprites[sprite_id].delete()
        del self.sprites[sprite_id]

    def draw(self):
        self.batch.draw()  # single GPU call renders everything
```

This is the key performance advantage: sprites are persistent objects in a batch.
Each frame we update positions/images, then draw the entire batch in one call. No
per-sprite draw calls.

### Text rendering

```python
    def load_font(self, name, size):
        # Store logical size — physical size computed at draw time
        return (name, size)

    def draw_text(self, text, font_handle, x, y, color, width=None, align="left"):
        name, logical_size = font_handle
        physical_size = int(logical_size * self.scale_factor)
        physical_x = int(x * self.scale_factor) + self.offset_x
        physical_y = int(y * self.scale_factor) + self.offset_y
        physical_width = int(width * self.scale_factor) if width else None
        label = pyglet.text.Label(
            text, font_name=name, font_size=physical_size,
            x=physical_x, y=physical_y, color=color,
            width=physical_width, multiline=physical_width is not None,
            anchor_x=align,
            batch=self.batch,
        )
```

Text is always rasterized at the physical pixel density — sharp on any display.
Font size 16 in logical coordinates becomes 32pt on a 2x retina display.

Pyglet's `Label` supports:
- Multi-line with word wrapping (`width` + `multiline`)
- Alignment (left, center, right)
- Rich text via `HTMLLabel` (bold, italic, color spans)
- This covers our `Label` and `TextBox` component needs

### Audio

```python
    def load_sound(self, path):
        return pyglet.media.load(str(path), streaming=False)

    def play_sound(self, handle):
        handle.play()

    def load_music(self, path):
        # Streaming for long tracks
        return pyglet.media.load(str(path), streaming=True)

    def play_music(self, handle, loop=True):
        player = pyglet.media.Player()
        player.queue(handle)
        if loop:
            player.loop = True
        player.play()
        return player  # caller manages the player for stop/volume
```

Pyglet audio uses OpenAL. Supports:
- Multiple simultaneous sounds (our sfx/ui channels)
- Streaming for music (doesn't load entire file into memory)
- Volume control per player
- Crossfade can be implemented by running two players and tweening volumes

### Input events

```python
    def poll_events(self):
        # Pyglet uses an event-based model. We adapt to polling.
        events = []

        @self.window.event
        def on_key_press(symbol, modifiers):
            events.append(KeyEvent("press", symbol, modifiers))

        @self.window.event
        def on_key_release(symbol, modifiers):
            events.append(KeyEvent("release", symbol, modifiers))

        @self.window.event
        def on_mouse_press(x, y, button, modifiers):
            events.append(MouseEvent("click", x, y, button))

        @self.window.event
        def on_mouse_motion(x, y, dx, dy):
            events.append(MouseEvent("move", x, y))

        @self.window.event
        def on_mouse_drag(x, y, dx, dy, buttons, modifiers):
            events.append(MouseEvent("drag", x, y, buttons))

        self.window.dispatch_events()
        return events
```

Note: in the real implementation, event handlers are registered once at window creation,
not per poll. They append to a list that `poll_events()` drains. The above shows the
mapping concept.

### Game loop integration

Pyglet wants to own the main loop via `pyglet.app.run()`, but we own ours. The manual
approach:

```python
while running:
    # Pyglet's clock tracks dt
    dt = pyglet.clock.tick()

    # Poll window events (keyboard, mouse, close)
    self.window.dispatch_events()
    events = self.drain_event_queue()

    # Framework update phase
    # ... (scene update, tweens, animation, timers)

    # Framework draw phase
    self.window.clear()
    # ... (scene draw calls populate the batch via register/update sprite)
    self.batch.draw()

    self.window.flip()
```

This gives us full control over frame timing, update order, and draw order while
pyglet handles the windowing and GPU submission.

---

## Coordinate System

Two conversions happen in the backend:

**Y-axis flip:** Pyglet uses OpenGL coordinates — (0,0) at bottom-left, y up. Our
framework uses screen coordinates — (0,0) at top-left, y down.

**Scale + offset:** Logical coordinates are scaled to physical pixels and offset for
letterboxing/pillarboxing.

Combined conversion (logical framework → physical pyglet):
```python
def to_physical(self, logical_x, logical_y):
    physical_x = logical_x * self.scale_factor + self.offset_x
    physical_y = (self.logical_height - logical_y) * self.scale_factor + self.offset_y
    return physical_x, physical_y

def to_logical(self, physical_x, physical_y):
    logical_x = (physical_x - self.offset_x) / self.scale_factor
    logical_y = self.logical_height - (physical_y - self.offset_y) / self.scale_factor
    return logical_x, logical_y
```

`to_physical` is used in all draw calls. `to_logical` is used for input events (mouse
position). The framework and game code never see physical coordinates.

---

## Resolution: Logical Coordinates, Native Rendering

### The problem

The game uses a logical coordinate space (e.g. 1920x1080). The physical display may be
different: 2560x1440, 3840x2160 retina, 1366x768 laptop. A naive approach — render to
a 1920x1080 buffer and upscale — produces blurry text and blurry UI. This is wrong.

### The correct approach

**Logical coordinates are for positioning only. Rendering happens at native resolution.**

The `scale_factor` is the ratio of physical pixels to logical pixels:
```python
scale_factor = physical_width / logical_width  # e.g. 2.0 on retina
```

Different things scale differently:

**Text** — rasterized at physical pixel density. A "font size 16" in logical coords
becomes `16 * scale_factor` points when pyglet rasterizes the glyphs. Result: sharp
text at any display density.

```python
def draw_text(self, text, font_handle, x, y, ...):
    name, logical_size = font_handle
    physical_size = int(logical_size * self.scale_factor)
    label = pyglet.text.Label(
        text, font_name=name, font_size=physical_size,
        x=int(x * self.scale_factor),
        y=int(y * self.scale_factor),
        ...
    )
```

**UI elements** (panels, borders, filled rects) — drawn at physical coordinates using
the scale factor. Solid colors and gradients are resolution-independent. Background
images follow the sprite rules below.

**Sprites** — this depends on the source art:

| Art style | Source resolution | Scaling method | Result |
|---|---|---|---|
| Pixel art | 1x (e.g. 32x32) | Nearest-neighbor | Crispy chunky pixels, intentionally blocky |
| Painted / AI art | 1x | Linear filtering | Smooth but slightly soft on retina |
| Painted / AI art | 2x (`@2x` variant) | Linear, drawn at native size | Sharp at retina, perfect |

The asset manager handles variant selection:
```python
# Developer provides:
#   assets/images/sprites/knight.png       (base resolution)
#   assets/images/sprites/knight@2x.png    (retina variant, optional)
#
# game.assets.image("sprites/knight") returns:
#   - knight@2x.png on a 2x display (if available)
#   - knight.png otherwise (upscaled with configured filtering)
```

### Scaling mode configuration

```python
game = Game(
    resolution=(1920, 1080),
    scaling_mode="linear",       # default: smooth scaling for painted/AI art
    # scaling_mode="nearest",    # pixel art mode: crispy upscaling
)
```

Can also be set per-sprite for games that mix pixel art and high-res UI:
```python
sprite = Sprite(image="sprites/knight", scaling="nearest")   # pixel art unit
background = Sprite(image="backgrounds/forest", scaling="linear")  # painted bg
```

### Implementation with pyglet

Pyglet's `Sprite` supports setting texture filtering:
```python
from pyglet.gl import GL_NEAREST, GL_LINEAR

def set_sprite_filtering(pyglet_sprite, mode):
    texture = pyglet_sprite.image.get_texture()
    if mode == "nearest":
        glTexParameteri(texture.target, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(texture.target, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    else:
        glTexParameteri(texture.target, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(texture.target, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
```

All coordinate conversions (logical → physical for drawing, physical → logical for
input events) go through the scale factor. The framework and game code work entirely
in logical coordinates. The backend handles the rest.

### Aspect ratio handling

When the physical aspect ratio doesn't match the logical ratio:
- Compute the largest area that fits with correct aspect ratio
- Center it (letterbox/pillarbox with black bars)
- Mouse coordinates are adjusted to account for the offset

```python
def compute_viewport(self, logical_w, logical_h, physical_w, physical_h):
    physical_ratio = physical_w / physical_h
    logical_ratio = logical_w / logical_h

    if physical_ratio > logical_ratio:
        # Physical is wider — pillarbox (black bars on sides)
        self.scale_factor = physical_h / logical_h
        self.offset_x = (physical_w - logical_w * self.scale_factor) / 2
        self.offset_y = 0
    else:
        # Physical is taller — letterbox (black bars top/bottom)
        self.scale_factor = physical_w / logical_w
        self.offset_x = 0
        self.offset_y = (physical_h - logical_h * self.scale_factor) / 2
```

---

## Color Swap Implementation

Pyglet operates on textures (GPU). Color swapping at load time:

1. Load the image as a PIL/Pillow image (CPU-side pixel access)
2. Replace source colors with target colors in the pixel data
3. Upload the modified image as a pyglet texture

```python
from PIL import Image

def apply_color_swap(image_path, source_colors, target_colors):
    img = Image.open(image_path).convert("RGBA")
    pixels = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = pixels[x, y]
            for src, tgt in zip(source_colors, target_colors):
                if (r, g, b) == src:
                    pixels[x, y] = (*tgt, a)
                    break
    # Convert to pyglet image
    raw = img.tobytes()
    return pyglet.image.ImageData(img.width, img.height, "RGBA", raw)
```

Cache the result per (image_path, color_swap) pair. Each unique recoloring is a
separate texture on the GPU — but textures are cheap.

For high-performance color swaps (many factions, many unit types), a shader-based
approach could replace specific hue ranges on the GPU. This is a future optimization
that doesn't change the framework API.

---

## Dependencies

```
pyglet >= 2.0
Pillow >= 12.1.1   # for color swap pixel manipulation, sprite sheet processing (12.1.1+ fixes CVE-2026-25990)
```

Pillow is needed for:
- Color swap implementation (per-pixel color replacement at load time)
- Sprite sheet slicing (crop regions from a sheet)
- Image format support beyond what pyglet handles natively

Both install cleanly with pip on macOS, no system dependencies.

---

## What Pyglet Gives Us "For Free"

Things we don't need to build because pyglet handles them:
- Window creation and fullscreen (including macOS retina, multi-monitor)
- GPU sprite rendering with batching
- Text rasterization with wrapping, alignment, formatting (we scale, pyglet rasterizes)
- Audio playback with multiple simultaneous sources
- Keyboard/mouse event handling
- VSync support
- Image format loading (PNG, JPEG, BMP, etc.)
- System font loading
- Texture filtering modes (nearest-neighbor / linear)

## What We Build On Top

Things the framework must implement using pyglet primitives:
- Resolution scaling (logical→physical coords, scale factor, aspect ratio letterboxing)
- Asset manager (caching, naming convention, sprite sheets, @2x variant loading)
- Scene stack and lifecycle management
- UI component tree (layout, anchoring, theming, hit testing)
- Animation system (frame sequencing, callbacks, queuing)
- Tween system (property interpolation, easing)
- Input action mapping (key → action, rebinding, settings persistence)
- Audio channels with volume hierarchy (master → channel)
- Sound pools and crossfade logic
- Camera (viewport offset, clamping, edge scroll, coord conversion)
- Drag-and-drop (mouse tracking, ghost rendering, hit testing)
- Save/load (file I/O, versioning, slot UI)
- Particle emitter (spawn, update, remove lightweight sprites)
- Cursor management (custom cursor images, context switching)
- Color swap (Pillow-based pixel replacement, caching)
- HUD layer (render ordering between scene stack and modals)
