# API Friction Log — Tower Defense Tutorial (Chapters 1–3)

This document records concrete friction points discovered while building
`ch1_title_screen.py`, `ch2_game_map.py`, and `ch3_tower_placement.py`
against the EasyGame framework.  Each entry includes the awkward code,
why it hurts, and the fix that was applied.

---

## 1. Scene background color requires raw backend calls — RESOLVED

### The awkward code

Every scene that wants a solid background color must drop down to the
backend's low-level API — `create_solid_color_image`, `create_sprite`,
`update_sprite` — then manually clean it up in `on_exit`:

```python
# ch1, ch2, ch3 — identical boilerplate in every TitleScene.on_enter()
backend = self.game.backend
bg_image = backend.create_solid_color_image(
    BG_COLOR[0], BG_COLOR[1], BG_COLOR[2], BG_COLOR[3],
    SCREEN_W, SCREEN_H,
)
self._bg_sprite_id = backend.create_sprite(
    bg_image,
    RenderLayer.BACKGROUND.value * 100_000,
)
backend.update_sprite(self._bg_sprite_id, 0, 0)
```

```python
# ... and the cleanup in on_exit()
def on_exit(self) -> None:
    if self._bg_sprite_id is not None:
        self.game.backend.remove_sprite(self._bg_sprite_id)
        self._bg_sprite_id = None
```

### Why it's friction

This is 10 lines of backend plumbing (plus cleanup) for the most common
thing a scene needs to do.  It also requires importing `RenderLayer` and
knowing the `layer.value * 100_000` ordering formula.  A first-time user
shouldn't need to understand render layer arithmetic just to set a
background color.

### Fix

Added `background_color` class attribute to `Scene`. The framework
clears the screen with this color in `begin_frame` before drawing.
No sprite creation or cleanup needed.

```python
class TitleScene(Scene):
    background_color = (25, 30, 40, 255)
```

---

## 2. Manual sprite cleanup is error-prone and tedious — RESOLVED

### The awkward code

Every scene that creates sprites must track them in lists/dicts and
explicitly `.remove()` each one in `on_exit()`:

```python
# ch3 GameScene.on_exit() — 15 lines of cleanup
def on_exit(self) -> None:
    for sprite in self._tile_sprites:
        sprite.remove()
    self._tile_sprites.clear()

    for sprite in self._slot_sprites.values():
        sprite.remove()
    self._slot_sprites.clear()

    for sprite in self._tower_sprites:
        sprite.remove()
    self._tower_sprites.clear()

    if self._range_indicator is not None:
        self._range_indicator.remove()
        self._range_indicator = None

    self._placed_towers.clear()
    self._scroll_dx = 0.0
    self._scroll_dy = 0.0
```

ch2's `on_exit` has the same pattern with `_tile_sprites` and
`_slot_sprites`.  Every new sprite collection adds another for-loop.

### Why it's friction

Forgetting to remove even one sprite causes visual ghosts.  As the
scene gains more sprite types (enemies, projectiles, effects), the
cleanup block grows linearly and each addition is a potential bug.
The framework knows which sprites exist in the backend batch — the
game code shouldn't have to mirror that bookkeeping.

### Fix

Added `Scene.add_sprite(sprite)` that registers ownership. The framework
calls `_cleanup_owned_sprites()` after `on_exit`, auto-removing all owned
sprites. Direct `Sprite()` creation still works; only sprites passed to
`add_sprite()` are tracked and cleaned up.

```python
sprite = self.add_sprite(Sprite("grass", position=(x, y)))
```

---

## 3. AssetManager must be constructed separately from Game — RESOLVED

### The awkward code

Every tutorial file repeats this same three-step setup:

```python
game = Game(
    "Tower Defense — Chapter 3",
    resolution=(SCREEN_W, SCREEN_H),
    fullscreen=False,
    backend="pyglet",
)

game.assets = AssetManager(
    game.backend,         # must pass game.backend manually
    base_path=_asset_dir, # must pass the path
)

game.theme = Theme(...)
```

The `AssetManager` constructor requires `game.backend` as its first
argument, which means the user must know about the backend object even
though they just told `Game` which backend to use.

### Why it's friction

The user already told `Game` which backend to use.  Having to fish out
`game.backend` and pass it to `AssetManager` is a leaky abstraction.
Most games only need to say "my assets are here".

### Fix

Added `asset_path` parameter to `Game` constructor. Lazy `game.assets`
uses this path when creating the `AssetManager`. Explicit
`game.assets = AssetManager(...)` still overrides for custom setups.

```python
game = Game(
    "Tower Defense — Chapter 3",
    resolution=(SCREEN_W, SCREEN_H),
    asset_path=_asset_dir,
    backend="pyglet",
)
```

---

## 4. No visual feedback for disabled buttons — RESOLVED

### The awkward code

In ch3, Buy buttons are disabled when the player can't afford a tower:

```python
def _refresh_buy_buttons(self) -> None:
    for i, tdef in enumerate(TOWER_DEFS):
        can_afford = self._gold >= tdef["cost"]
        self._buy_buttons[i].enabled = can_afford
```

Setting `enabled = False` blocks input correctly (the framework handles
that), but **the button looks identical to an enabled one**.  There is no
visual distinction — no greyed-out text, no dimmed background.

### Why it's friction

The `Component` docstring says disabled components "draw (greyed out) but
skip input", but the actual `Button.on_draw()` always resolves the
`"normal"` state style when not hovered/pressed — it never checks
`self.enabled`.  The user either gets confusingly invisible feedback or
must add their own style-swapping logic.

### Fix

`Button` resolves `"disabled"` state when `enabled=False`. Theme provides
`button_disabled_color` and `button_disabled_text_color` for muted
appearance. Disabled buttons draw greyed out and skip input.

---

## 5. Arrow-key scrolling requires manual key_press/key_release tracking — RESOLVED

### The awkward code

Both ch2 and ch3 duplicate this 20-line pattern to scroll the camera
with arrow keys:

```python
# In handle_input — track held directions
if event.type == "key_press":
    if event.action == "left":
        self._scroll_dx = -speed
        return True
    elif event.action == "right":
        self._scroll_dx = speed
        return True
    elif event.action == "up":
        self._scroll_dy = -speed
        return True
    elif event.action == "down":
        self._scroll_dy = speed
        return True

if event.type == "key_release":
    if event.action in ("left", "right"):
        self._scroll_dx = 0.0
        return True
    elif event.action in ("up", "down"):
        self._scroll_dy = 0.0
        return True
```

```python
# In update — apply scroll
def update(self, dt: float) -> None:
    if self._scroll_dx != 0.0 or self._scroll_dy != 0.0:
        self.camera.scroll(self._scroll_dx * dt, self._scroll_dy * dt)
```

Plus two instance variables (`_scroll_dx`, `_scroll_dy`) initialised in
`on_enter` and reset in `on_exit`.

### Why it's friction

Arrow-key camera scrolling is the most common camera interaction for any
2D game with a world larger than the screen.  Every scene that uses a
camera will copy-paste this pattern.  The camera already has
`enable_edge_scroll()` for mouse-based scrolling — keyboard scrolling
should be just as easy to enable.

### Fix

Added `Camera.enable_key_scroll(speed)`. The camera listens for
directional actions and applies scrolling in its update step. No
`_scroll_dx`/`_scroll_dy` state or `handle_input`/`update` overrides
needed in the scene.

```python
self.camera.enable_key_scroll(speed=CAMERA_SCROLL_SPEED)
```

---

## 6. Label styling requires a Style object even for just a color change — RESOLVED

### The awkward code

Almost every label in the tutorials wraps a `Style(...)` just to set
one or two fields:

```python
Label(
    "Wave: 1",
    style=Style(font_size=20, text_color=HUD_TEXT_COLOR),
)

Label(
    "Arrow keys: scroll | ESC: menu",
    style=Style(font_size=14, text_color=(140, 140, 150, 255)),
)

Label(
    "Tower Defense",
    style=Style(font_size=48, text_color=TITLE_COLOR),
)
```

ch3's `_build_menu` alone creates 7 labels, each with
`style=Style(font_size=..., text_color=...)`.  The `Style` wrapper adds
noise for what is logically "display this text in this color at this
size".

### Why it's friction

Labels are the most commonly created UI component.  Requiring a `Style`
object for the two most common overrides (font_size, text_color) makes
label-heavy UIs verbose.  `Style` is valuable for complex customization,
but the 90% case is just size and color.

### Fix

`Label` and `Button` accept `font_size` and `text_color` as direct
kwargs, merged with any explicit `style=Style(...)`. Explicit style
wins for overlapping fields.

```python
Label("Wave: 1", font_size=20, text_color=HUD_TEXT_COLOR)
```

---

## 7. screen_to_world conversion is always needed but never automatic for mouse events — RESOLVED

### The awkward code

In ch3, every mouse event handler must manually convert screen
coordinates to world coordinates:

```python
# Left-click placement
if event.type == "click" and event.button == "left":
    if self._placing_tower_def is not None:
        wx, wy = self.camera.screen_to_world(event.x, event.y)
        self._try_place_tower(wx, wy)

# Mouse movement
if event.type in ("move", "drag"):
    if self._placing_tower_def is not None:
        wx, wy = self.camera.screen_to_world(event.x, event.y)
        snap = self._snap_to_nearest_slot(wx, wy)
```

Every mouse handler that interacts with the game world (not UI) needs
this same `camera.screen_to_world(event.x, event.y)` call.

### Why it's friction

`InputEvent` arrives in screen space, but game logic (hit testing,
placement, selection, movement commands) almost always needs world space.
The conversion is trivial but forgetting it produces subtle bugs — the
game works until the camera scrolls, then clicks land in wrong positions.
This is a classic "works in testing, breaks in production" mistake.

### Fix

`InputEvent` has `world_x` and `world_y` fields. The framework populates
them via `_with_world_coords()` before dispatching to `handle_input`.
For mouse events with a camera: camera-transformed coords. For non-mouse
events: `None`.

```python
if event.type == "click" and event.world_x is not None and event.world_y is not None:
    self._try_place_tower(event.world_x, event.world_y)
```

---

## Summary

| # | Friction | Status |
|---|----------|--------|
| 1 | Background color requires backend calls | RESOLVED — `Scene.background_color` |
| 2 | Manual sprite cleanup in on_exit | RESOLVED — `Scene.add_sprite()` + auto-cleanup |
| 3 | AssetManager constructed separately | RESOLVED — `Game(asset_path=...)` |
| 4 | No visual feedback for disabled buttons | RESOLVED — disabled style state |
| 5 | Arrow-key scrolling boilerplate | RESOLVED — `Camera.enable_key_scroll()` |
| 6 | Label styling verbosity | RESOLVED — `font_size`/`text_color` kwargs |
| 7 | Manual screen-to-world conversion | RESOLVED — `event.world_x`/`event.world_y` |
