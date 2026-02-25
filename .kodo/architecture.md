# EasyGame Architecture Reference

> Condensed from implementation journals (stages 6–13), updated through stage 5 API
> improvements. All API signatures verified against source. **1144 tests passing.**

---

## Game Loop Order (`Game.tick(dt)`)

```
1. poll_events → InputManager.translate → handle_input → flush_pending_ops
2. scene_stack.update(dt) → UI._update_tree(dt) → HUD._update(dt) → flush
3. _update_actions(dt)       — composable actions on sprites
4. _update_particles(dt)     — particle emitter lifecycle
5. _timer_manager.update(dt) — one-shot / repeating timers
6. _tween_manager.update(dt) — property interpolation
7. _update_animations(dt)    — sprite frame animation
8. camera sync → begin_frame → draw → end_frame → camera restore
```

**Input dispatch order:** HUD → Scene UI → Camera key scroll → `scene.handle_input(event)`

**Draw order (SceneStack):**
1. Base scene (lowest opaque) + its UI
2. HUD (if `hud.visible AND top_scene.show_hud`)
3. Transparent overlay scenes + their UIs (bottom-up)

---

## Coordinate Flow

```
Sprite world pos → anchor_offset → world draw corner → subtract camera offset
  → screen draw corner → backend.update_sprite(pos, opacity, visible, tint)
  → [Pyglet] y-flip + scale + tint color multiply → GPU
```

Without camera: sprites render at world pos (world == screen). Mouse `InputEvent`s
have `world_x`/`world_y` auto-populated by the framework before dispatch (via
camera when present, else equal to screen coords). Non-mouse events: `None`.

---

## Cross-Cutting Patterns

**Sync/Restore:** Camera applies per-frame offsets for rendering, then restores
original world positions after `end_frame()`. Prevents double-offsetting since
sprites eagerly push positions on every property change. Both `_sync_sprites_to_camera`
and `_restore_sprites` must pass `tint=sprite._tint` to `update_sprite` to preserve
the sprite's tint through the camera sync/restore cycle.

**Lazy Subsystems:** `game.audio`, `game.theme`, `game.cursor`, `game.hud`,
`game.save_manager`, `scene.ui` — all created on first access via `@property`.

**Modal Overlays:** Convenience screens use `transparent=True`, `show_hud=False`,
`handle_input` returns `True` for all events → HUD hidden, input captured, scene
below visible.

---

## Game

```python
class Game:
    def __init__(self, title: str, *, resolution=(1920, 1080), fullscreen=True,
                 backend="pyglet", visible=True, save_dir: Path | str | None = None,
                 asset_path: Path | str | None = None)
    # asset_path: when provided, lazy game.assets uses this as base_path

    # Scene stack
    def push(self, scene: Scene) -> None
    def pop(self) -> None
    def replace(self, scene: Scene) -> None
    def clear_and_push(self, scene: Scene) -> None

    # Timers
    def after(self, delay: float, callback) -> TimerHandle
    def every(self, interval: float, callback) -> TimerHandle
    def cancel(self, timer_id: int | TimerHandle) -> None  # TimerHandle cancels whole chain
    def cancel_tween(self, tween_id: int) -> None

    # Save/load
    def save(self, slot: int) -> None          # top scene's get_save_state() → file
    def load(self, slot: int) -> dict | None   # loads + calls top.load_save_state()

    # Convenience
    def show_sequence(self, screens: list, *, on_complete=None) -> None
    def push_settings(self) -> None

    # Main loop
    def run(self, start_scene: Scene) -> None
    def tick(self, dt: float | None = None) -> None
    def quit(self) -> None

    # Lazy properties
    @property assets -> AssetManager       # settable
    @property audio -> AudioManager        # settable
    @property theme -> Theme               # settable
    @property cursor -> CursorManager
    @property input -> InputManager
    @property hud -> HUD
    @property save_manager -> SaveManager  # default dir: ~/.{slug}/saves/
```

**Internal registries:** `_all_sprites`, `_animated_sprites`, `_action_sprites`,
`_particle_emitters` — self-register on construction.

## Scene

```python
class Scene:
    transparent: bool = False     # if True, scene below is visible
    pause_below: bool = True      # if True, scene below doesn't update
    show_hud: bool = True         # if False, HUD hidden when this is on top
    background_color: tuple[int, ...] | None = None  # (R,G,B[,A]) 0-255, clear color
    game: Game                    # set by SceneStack on push
    camera: Camera | None = None  # set by subclass in on_enter()
    @property ui -> _UIRoot       # lazy

    def on_enter(self) -> None
    def on_exit(self) -> None     # after this, framework calls _cleanup_owned_sprites()
    def on_reveal(self) -> None           # called when scene above is popped
    def update(self, dt: float) -> None
    def draw(self) -> None
    def handle_input(self, event) -> bool # True = consumed
    def get_save_state(self) -> dict      # default: {}
    def load_save_state(self, state: dict) -> None

    # Sprite ownership — auto-removed after on_exit()
    def add_sprite(self, sprite: Sprite) -> Sprite    # register; returns sprite for chaining
    def remove_sprite(self, sprite: Sprite) -> None   # deregister + sprite.remove()

    # Timer ownership — auto-cancelled after on_exit()
    def after(self, delay: float, callback) -> TimerHandle    # scene-scoped game.after()
    def every(self, interval: float, callback) -> TimerHandle # scene-scoped game.every()
    def cancel_timer(self, timer_id: int | TimerHandle) -> None  # deregister + game.cancel()

    # Draw helpers — call in draw(), cleared each frame
    def draw_rect(self, x, y, w, h, color) -> None          # screen-space
    def draw_world_rect(self, x, y, w, h, color) -> None    # auto camera transform
```

**`background_color`:** Per-frame clear via `begin_frame()`. Transparent overlays inherit base.

**Ownership (sprites + timers):** Cleanup runs after `on_exit()` in all SceneStack transitions.
`sprite.remove()` auto-deregisters. `game.after()` only for cross-scene timers.

**Draw helpers:** `draw_world_rect()` auto-applies camera transform; both delegate to backend
and are per-frame (cleared each `begin_frame()`). Eliminates `game._backend` access.

---

## Sprite

```python
class Sprite:
    def __init__(self, image: str, *, position=(0,0),
                 anchor=SpriteAnchor.BOTTOM_CENTER,
                 layer=RenderLayer.UNITS, opacity=255, visible=True,
                 tint: tuple[float, float, float] = (1.0, 1.0, 1.0),
                 color_swap: ColorSwap | None = None,
                 team_palette: str | None = None)

    # Properties (all settable): position, x, y, opacity (0-255), visible, image,
    #   tint ((r, g, b) floats 0.0–1.0, default (1.0, 1.0, 1.0) = no tint)
    # Read-only: layer (RenderLayer), anchor (SpriteAnchor)
    def move_to(self, target_pos, speed, *, ease=None, on_arrive=None) -> None
    def play(self, anim: AnimationDef, *, on_complete=None) -> None
    def queue(self, anim: AnimationDef, *, on_complete=None) -> None
    def stop_animation(self) -> None
    def do(self, action: Action) -> None      # cancels current action
    def stop_actions(self) -> None
    def remove(self) -> None; @property is_removed -> bool
```

```python
class RenderLayer(IntEnum):
    BACKGROUND = 0; OBJECTS = 1; UNITS = 2; EFFECTS = 3; UI_WORLD = 4

class SpriteAnchor(Enum):
    TOP_LEFT, TOP_CENTER, TOP_RIGHT, CENTER_LEFT, CENTER, CENTER_RIGHT,
    BOTTOM_LEFT, BOTTOM_CENTER, BOTTOM_RIGHT
```

---

## Camera

Pure math, no backend dependency. Set `scene.camera = Camera(...)` in `on_enter()`.

```python
class Camera:
    def __init__(self, viewport_size, *, world_bounds=None)
    # world_bounds = (left, top, right, bottom) — not (width, height)
    x, y: float          # read-only, top-left of viewport in world space
    viewport_width, viewport_height: int  # read-only
    world_bounds          # read-write, re-clamps on set

    def center_on(self, x, y)           # cancels pan + follow
    def follow(self, sprite)            # cancels pan
    def scroll(self, dx, dy)            # cancels pan + follow
    def pan_to(self, x, y, duration, easing=None)  # smooth tween
    def enable_edge_scroll(self, margin, speed)
    def disable_edge_scroll(self)
    def enable_key_scroll(self, speed: float = 300)   # arrow-key scrolling
    def disable_key_scroll(self)
    def handle_input(self, event) -> bool  # process directional keys; True = consumed
    def screen_to_world(self, sx, sy) -> tuple[float, float]
    def world_to_screen(self, wx, wy) -> tuple[float, float]
    def update(self, dt, mouse_x=None, mouse_y=None)  # per-frame (edge + key scroll)
```

**Key scroll:** dispatched after HUD/UI, before `scene.handle_input()`. Frustum culling
uses sprite image dimensions as margin.

**Screen Shake:**
```python
Camera.shake(intensity: float, duration: float, decay: float = 1.0)
```
- **State:** `_shake_intensity`, `_shake_duration`, `_shake_elapsed`, `_shake_decay`,
  `_shake_offset_x`, `_shake_offset_y` — all zeroed when inactive.
- **Behavior:** Each frame in `update(dt)`, a random offset is computed:
  `remaining = (1 - elapsed/duration) ** decay`, offset = `random(-remaining, remaining) * intensity`.
  When `elapsed >= duration`, shake ends and offsets reset to zero.
- **Composition:** Shake offset is **additive** to camera position during the sync pass.
  Does NOT mutate `_x`/`_y` — camera's logical position stays clean for follow/pan/scroll.
- **Public read-only:** `shake_offset_x`, `shake_offset_y` — consumed by the game sync
  pass to shift all sprites without polluting camera position state.

## Animation

```python
class AnimationDef:
    def __init__(self, frames: list[str] | str, frame_duration=0.15, loop=True)
class AnimationPlayer:
    current_frame, is_playing, is_finished  # properties
    def update(self, dt) -> Any | None      # returns new frame handle or None
```

---

## Composable Actions

11 classes. Actions are run via `sprite.do(action)`. One action per sprite at a time.

```python
class Action:                             # base class
    def start(self, sprite) -> None
    def update(self, dt) -> bool          # True = done
    def stop(self) -> None                # safe on unstarted
    @property is_finite -> bool           # True by default

class Sequence(*actions: Action)          # chains in order; instant actions chain same frame
class Parallel(*actions: Action)          # done when all finite children done; stops infinite
class Delay(seconds: float)               # wait
class Do(fn: Callable)                    # call function, instant
class PlayAnim(anim_def: AnimationDef)    # delegates to sprite.play(); is_finite = not loop
class MoveTo(position, speed: float)      # direct lerp (NOT tween system)
class FadeOut(duration: float)            # opacity 255→0
class FadeIn(duration: float)             # opacity 0→255
class Remove()                            # sprite.remove(), instant
class Repeat(action, times=None)          # None = infinite; uses deepcopy per iteration
```

**Key decisions:**
- `MoveTo`/`FadeOut`/`FadeIn` use direct per-frame lerp, NOT the tween system
- `Parallel` finishes when all **finite** children done (`is_finite` property)
- `Sequence` chains instant actions in one frame (no 1-frame-per-step delay)
- Action phase runs before timers/tweens so `PlayAnim.start()` → animation phase
  processes the first frame in the same tick
- **Re-entrancy trap:** `sprite.do()` inside a `Sequence`'s `Do()` callback gets
  silently overwritten by the continuing Sequence. Workaround: use
  `sprite.move_to(on_arrive=callback)` for movement chains. Documented in LIMITATIONS.md

---

## Audio

```python
class AudioManager:
    def __init__(self, backend, assets: AssetManager)

    def play_sound(self, name: str, *, channel="sfx", optional=False) -> None
    def play_music(self, name: str, *, loop=True, optional=False) -> None
    def stop_music(self) -> None
    def crossfade_music(self, name: str, duration=1.0, *, loop=True) -> None
    def set_volume(self, channel: str, level: float) -> None   # 0.0–1.0
    def get_volume(self, channel: str) -> float
    def register_pool(self, name: str, sound_names: list[str]) -> None
    def play_pool(self, name: str) -> None  # random, no immediate repeat
```

**Channels:** `master`, `music`, `sfx`, `ui`. Effective = master × channel.
No `update(dt)` — crossfade driven by tween system. Music NOT cached (pyglet streaming
sources can't be reused). SFX are fire-and-forget. **`optional=True`:** catches
`AssetNotFoundError` and logs warning instead of raising — useful during development
when assets may be missing.

## Input

```python
@dataclass(frozen=True)
class InputEvent:
    type: str           # "key_press"|"key_release"|"click"|"release"|"move"|"drag"|"scroll"
    key: str | None; action: str | None   # action = mapped name
    x: int; y: int; button: str | None; dx: int; dy: int
    world_x: float | None = None  # camera-transformed x (mouse events only)
    world_y: float | None = None  # camera-transformed y (mouse events only)

class InputManager:
    def bind(self, action, key); def unbind(self, action)
    def get_bindings(self) -> dict[str, str]
    def translate(self, raw_events) -> list[InputEvent]
```

**World coords:** Populated via `dataclasses.replace()` before dispatch. Mouse events get
camera-transformed coords; non-mouse events: `None`.

## Assets

```python
class AssetManager:
    def __init__(self, backend, base_path=Path("assets"), *, scale_factor=1.0)
    def image(self, name) -> ImageHandle            # cached
    def image_swapped(self, name, color_swap) -> ImageHandle  # cached by (name, key)
    def frames(self, prefix) -> list[str]           # sorted frame names
    def sound(self, name) -> SoundHandle            # cached; tries .wav/.ogg/.mp3
    def music(self, name) -> SoundHandle            # NOT cached (streaming)
class AssetNotFoundError(FileNotFoundError): ...
```

---

## Timers & Tweens

```python
class TimerManager:  # after(delay, cb)->TimerHandle, every(interval, cb)->TimerHandle, cancel(id), cancel_all()
class TweenManager:  # create(target, prop, from, to, duration, ease, on_complete)->int, cancel(id)
def tween(target, prop, from_val, to_val, duration, *, ease=Ease.LINEAR, on_complete=None) -> int
class Ease(Enum): LINEAR, EASE_IN, EASE_OUT, EASE_IN_OUT
```

Game exposes: `game.after()`, `game.every()`, `game.cancel()`, `game.cancel_tween()`.
**Prefer `Scene.after()`/`Scene.every()`** for auto-cleanup (see Scene section).

### Timer Chaining (TimerHandle)

**Problem:** Sequencing delayed callbacks requires nested lambdas:
```python
self.after(1.0, lambda: self.after(0.5, lambda: self.after(0.2, final_cb)))
```

**Solution:** `after()` and `every()` return a `TimerHandle` instead of a bare `int`.
`TimerHandle.then(callback, delay)` chains a follow-up timer that starts when the
parent fires. The handle is backward-compatible: `int(handle)` and scene ownership
(`set[int]`) work via `__eq__`/`__hash__` delegation to `timer_id`.

#### Public API

```python
class TimerHandle:
    """Lightweight wrapper around a timer ID that supports .then() chaining."""

    timer_id: int               # ID of the *first* timer in this handle's chain
    _manager: TimerManager      # back-reference (not exposed to users)
    _chain_ids: list[int]       # all timer IDs owned by this chain (for cancellation)

    def then(self, callback: Callable[[], Any], delay: float = 0.0) -> TimerHandle:
        """Chain a callback to run *delay* seconds after the parent fires.

        Returns the SAME handle (``self``) for fluent chaining.  The
        callback/delay pair is appended to the root _Timer's then_chain
        list and threaded forward step-by-step when each link fires.
        """

    # Backward compat with bare int
    def __eq__(self, other): ...   # compare as timer_id
    def __hash__(self): ...        # hash as timer_id
    def __int__(self): ...         # int(handle) → timer_id
```

#### Signature changes

```python
# TimerManager (internal)
def after(self, delay, callback) -> TimerHandle   # was -> int
def every(self, interval, callback) -> TimerHandle # was -> int
def cancel(self, timer_id: int | TimerHandle) -> None  # accepts both

# Game (public) — same change
def after(self, delay, callback) -> TimerHandle
def every(self, interval, callback) -> TimerHandle
def cancel(self, timer_id: int | TimerHandle) -> None

# Scene — returns TimerHandle, owned set still uses int IDs internally
def after(self, delay, callback) -> TimerHandle
def every(self, interval, callback) -> TimerHandle
```

#### How .then() works internally

`handle.then(cb, delay)` does NOT immediately create a timer. It appends `(cb, delay)`
to the root `_Timer`'s `then_chain` list and returns `self` (the same handle) for
fluent chaining. No callback wrapping occurs.

**TimerHandle.then():**
```python
def then(self, callback, delay=0.0):
    root = self._manager._timers.get(self.timer_id)
    if root is not None:
        root.then_chain.append((callback, delay))
    return self  # fluent — same handle, same timer_id
```

**TimerManager.update() — chain propagation:** After a one-shot timer fires, if it has
a non-empty `then_chain`, `_schedule_chain_step(chain, chain_ids)` pops the first entry,
schedules it via `after()`, threads the remaining chain onto the child's `then_chain`,
and shares the `chain_ids` list so cancellation reaches all children. For repeating
timers the chain is cloned (via `list()`) per repetition so each cycle gets its own
independent chain sequence.

**`handle.timer_id` always refers to the root timer.** Cancelling via
`game.cancel(handle)` iterates `_chain_ids` and cancels the root + all
already-scheduled children. Children not yet created are never scheduled because
the root (or parent link) is gone.

#### Behavior by use case

**1. `game.after(1, cb1).then(cb2, 0.5).then(cb3, 0.2)`**
- t=0: root timer created (ID=0, delay=1s). cb1 is wrapped twice (by each `.then()`).
- t=1.0: cb1 fires → wrapper schedules after(0.5, cb2_wrapped). chain_ids=[0, 1].
- t=1.5: cb2 fires → wrapper schedules after(0.2, cb3). chain_ids=[0, 1, 2].
- t=1.7: cb3 fires. One-shot, removed.

**2. `game.every(1, cb1).then(cb2, 0.5)`**
- t=0: repeating timer created (ID=0, interval=1s). cb1 wrapped.
- t=1.0: cb1 fires → after(0.5, cb2) created (ID=1). chain_ids=[0, 1].
- t=1.5: cb2 fires. One-shot, removed.
- t=2.0: cb1 fires again → after(0.5, cb2) created (ID=2). chain_ids=[0, 1, 2].
- t=2.5: cb2 fires again. Pattern repeats.
- On cancel: root repeating timer cancelled. Any pending child one-shots in
  chain_ids also cancelled.

**3. Cancellation: `game.cancel(handle)` or `game.cancel(handle.timer_id)`**
- `cancel()` checks if the argument is a `TimerHandle`. If so, iterates `_chain_ids`
  and cancels ALL timer IDs in the list (both already-scheduled and future-proof).
- If argument is a bare `int`, behaves as before (cancels that single timer only).
- Cancelled root = wrapper never fires = children never created. Safe.

#### Scene ownership integration

`_owned_timers` is `set[TimerHandle]`. `_cleanup_owned_timers()` iterates the set and
calls `game.cancel(handle)` — since `cancel()` receives a `TimerHandle`, it iterates
`_chain_ids` and cancels the root + all already-scheduled children.

**Critical invariant (scene.py `_wrapper`):** `Scene.after()`'s internal `_wrapper`
must NOT discard the handle from `_owned_timers` when the root fires if a `then_chain`
is pending. Otherwise the handle is orphaned and scene-exit cleanup never cancels the
in-flight chain children. The wrapper checks `root.then_chain` before discarding.
For plain (non-chained) one-shot timers the handle is still discarded on fire,
preserving the original cleanup semantics.

#### Backward compatibility

- `TimerHandle.__eq__` and `__hash__` delegate to `timer_id`, so `handle == 5`,
  `handle in {5}`, `{handle} == {5}` all work. Existing code that stores timer IDs
  as ints and compares them continues to work.
- `game.cancel(int_id)` still works for bare ints (single timer cancellation).
- `game.cancel(handle)` cancels the whole chain (new behavior, but only triggers
  when users pass a handle — which they got from the new API).
- `Scene.after()` returns `TimerHandle` instead of `int`. Since `TimerHandle`
  compares as int, existing `if tid: ...` and `cancel_timer(tid)` patterns work.

#### Key decisions

- **`timer_id` = root timer** on all handles in a chain. Predictable, cancellation is
  always "cancel the whole sequence".
- **Shared mutable `_chain_ids` list** across all handles in a chain. One cancel
  cleans up everything.
- **Lazy child creation** (children scheduled only when parent fires). No pre-allocated
  IDs. Simpler, no wasted timer slots.
- **`every().then()` creates a new one-shot child per repetition.** Each child is
  appended to `_chain_ids` so cancellation catches them.
- **`TimerHandle` lives in `easygame/util/timer.py`** (same module as `TimerManager`).
  Re-exported from `easygame/__init__.py` for `from easygame import TimerHandle`.
- **No `.cancel()` on TimerHandle itself.** Users call `game.cancel(handle)` or
  `scene.cancel_timer(handle)`. Keeps TimerHandle lightweight (no game back-ref needed
  in the public API — `_manager` is internal).

---

## State Machine

```python
class StateMachine:
    def __init__(self, states, initial, transitions=None, on_enter=None, on_exit=None)
    @property state -> str; @property valid_events -> list[str]
    def trigger(self, event) -> bool   # False = no such transition (silent)
```

`on_enter[initial]` fires on construction. Self-transitions fire both exit/enter.
No transitions entry = absorbing state. Purely event-driven (no `update(dt)`).

## Particles

```python
class ParticleEmitter:
    def __init__(self, image: str | list[str], position, count=10,
                 speed=(50, 200), direction=(0, 360), lifetime=(0.3, 0.8),
                 fade_out=True, layer=RenderLayer.EFFECTS)
    position: tuple[float, float]  # settable
    @property is_active -> bool
    def burst(self, count=None); def continuous(self, rate: float)
    def stop(self); def remove(self)  # stop = let die; remove = kill all
```

Particles are real `Sprite` instances (camera + y-sort). Auto-registers/deregisters
with `Game._particle_emitters`.

## ColorSwap, Cursor, Save/Load

```python
class ColorSwap:      # source_colors, target_colors → Pillow pixel replacement, cached as GPU texture
    def apply(self, image_path) -> PIL.Image.Image; def cache_key(self) -> tuple
def register_palette(name, swap); def get_palette(name) -> ColorSwap

class CursorManager:  # register(name, image_name, hotspot), set(name), set_visible(bool)
class SaveManager:    # save(slot, state, scene_class_name), load(slot), list_slots(), delete(slot)
```

**ColorSwap:** Sprite accepts `color_swap=` or `team_palette=` (registry lookup). `color_swap` wins.
**Save format:** `save_{slot}.json` in `~/.{slug}/saves/`. `game.save()` → `get_save_state()`;
`game.load()` → `load_save_state()` + returns dict.

---

## UI Foundation

UI renders with per-frame `draw_text()` + `draw_rect()` + `draw_image()`, NOT
persistent sprites. This avoids camera sync/restore interference. All per-frame
draw calls are cleared in `begin_frame()`.

### Component (base class)

```python
class Component:
    def __init__(self, *, width=None, height=None, anchor=None, margin=0,
                 visible=True, enabled=True, style=None,
                 draggable=False, drag_data=None, drop_accept=None, on_drop=None)
    # Tree: add(child), remove(child), parent, children
    # Overrides: on_event(event)->bool, on_draw(), update(dt)
    # Framework: handle_event(event)->bool (tree dispatch), draw() (tree draw),
    #            get_preferred_size(), hit_test(x, y)
```

Layout computed lazily (dirty flag). `_ensure_layout()` called before draw/input.

### Widgets

```python
# Foundation (easygame/ui/components.py)
class Label(Component):    __init__(self, text, *, font_size=None, text_color=None,
                                    font=None, style=None, **kw)
                           text: str  # settable
                           # font_size/text_color convenience kwargs merged into Style
class Button(Component):   __init__(self, text, *, on_click=None, style=None, **kw)
                           text: str; is_hovered: bool; is_pressed: bool
                           # on_draw resolves "disabled" state when enabled=False
class Panel(Component):    __init__(self, *, layout=Layout.NONE, spacing=0, padding=0, **kw)

# Extended (easygame/ui/widgets.py)
class ImageBox(Component):    # image_name (settable), width, height
class ProgressBar(Component): # value (settable), max_value, fraction (read-only), bar_color, bg_color
class TextBox(Component):     # text, typewriter_speed; is_typewriter_done, skip_typewriter()
class List(Component):        # items, on_select; selected_index, set_items(), set_selected()
class Grid(Component):        # columns, rows, cell_width, cell_height; set_cell(), get_cell()
class Tooltip(Component):     # target, text, delay; dual visibility (Component.visible + _visible_now)
class TabGroup(Component):    # tabs: list[(str, Component)]; active_tab_index, set_active_tab()
class DataTable(Component):   # columns, rows, col_widths; set_data(), selected_row
```

### Layout, Theme & Style

```python
class Anchor(Enum): CENTER, TOP, BOTTOM, LEFT, RIGHT, TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT
class Layout(Enum): NONE, VERTICAL, HORIZONTAL
# Pure math helpers: compute_anchor_position(), compute_flow_layout(), compute_content_size()

@dataclass
class Style:         # all optional — merged with theme defaults
class ResolvedStyle: # all concrete — result of theme resolution
# Both have: font, font_size, text_color, background_color, padding,
#            border_color, border_width, hover_color, press_color

class Theme:
    # font, font_size, text_color + per-widget color groups (panel_*, button_*, label_*,
    # progressbar_*, tooltip_*, tab_*, datatable_*, drop_*, ghost_opacity)
    # resolve_{label,button,panel,...}_style(); button state: "normal"|"hovered"|"pressed"|"disabled"
```

Widget-specific colors are Theme properties (`progressbar_color`, `selected_color`, etc.).
**Disabled buttons:** `Button.on_draw()` resolves `"disabled"` state when `enabled=False`.

---

## Drag-and-Drop, HUD, Convenience Screens

```python
class DragManager:   # lazy on _UIRoot; is_dragging, drag_data, handle_event()
# Component kwargs: draggable, drag_data, drop_accept, on_drop. Escape cancels.

class HUD:           # lazy on game.hud; add(comp), remove(comp), clear()
# Visible when hud.visible AND top_scene.show_hud. Above base scene, below overlays.

# Convenience screens — transparent=True, show_hud=False, modal
class MessageScreen(Scene):   # text, on_dismiss
class ChoiceScreen(Scene):    # prompt, choices, on_choice
class ConfirmDialog(Scene):   # question, on_confirm, on_cancel
class SaveLoadScreen(Scene):  # mode, on_save, on_load, on_cancel
```

`game.show_sequence(screens, on_complete=...)` chains via `on_reveal()` lifecycle.

---

## Backend Protocol

Game code should NOT access `game._backend` directly — use `Scene.draw_rect()` /
`Scene.draw_world_rect()` instead. Backend is an internal abstraction.

**Key groups:** window lifecycle (`create_window`, `begin_frame`/`end_frame`, `poll_events`,
`get_dt`, `quit`), image/sprite management (`load_image`, `create_sprite`, `update_sprite`,
`remove_sprite`), per-frame drawing (`draw_rect`, `draw_text`, `draw_image`, `load_font`),
cursor (`set_cursor`, `set_cursor_visible`), audio (`load_sound`/`play_sound`,
`load_music`/`play_music`, `set_player_volume`, `stop_player`).

**`update_sprite` signature:** `update_sprite(sprite_id, x, y, *, image=None, opacity=255,
visible=True, tint=(1.0, 1.0, 1.0))`. The `tint` parameter is an `(r, g, b)` tuple of
floats (0.0–1.0) that multiplies the sprite's color channels. Default `(1.0, 1.0, 1.0)`
means no tint. Backends must accept and apply this parameter.

**Persistent sprites** participate in camera sync. **Per-frame draws** are screen-space only.

---

## Example & Tutorial Conventions

**Directory layout:**
```
examples/<name>/          # standalone demos (battle_vignette)
tutorials/<name>/         # multi-chapter tutorials (tower_defense)
  ├── assets/images/...   # local generated assets
  ├── chapter_NN_topic.py # one runnable file per chapter
  └── README.md           # setup + run instructions
```

**Entry point pattern** (every runnable .py):
```python
_project_root = Path(__file__).resolve().parents[N]   # N = depth to repo root
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

game = Game("Title", resolution=(1920, 1080), fullscreen=False, backend="pyglet",
            asset_path=Path(__file__).resolve().parent / "assets")
game.run(StartScene())
```

**Asset generation:** Pillow-generated via `assetgen/` primitives. Each example/tutorial
adds a generator module called from `generate_assets.py`. Assets go to both
`assets/images/sprites/` (tests) and the local example/tutorial dir.

**Import style:** Flat from `easygame` — never from subpackages:
```python
from easygame import Game, Scene, Sprite, Camera, Panel, Label, Button, ...
```

**Scene cleanup:** Sprites registered via `scene.add_sprite()` are auto-removed after
`on_exit()`. Unowned sprites, tweens, and timers still need manual cleanup in `on_exit()`.

---

## Stage 3: API Improvements — Completed

Seven friction points from TD tutorial (chapters 1–3) resolved. All additive/backward-compatible.
Signatures integrated into subsystem sections above.

**Changes:** `Scene.background_color`, `Scene.add_sprite()`/`remove_sprite()`,
`Game(asset_path=...)`, `Button` disabled visual, `Label(font_size=, text_color=)`,
`Camera.enable_key_scroll()`, `InputEvent.world_x/y`.

**Key decisions:** `InputEvent` stays `frozen=True` (world coords via `dataclasses.replace()`).
`add_sprite()` takes existing Sprite, not construction args. `_cleanup_owned_sprites()` runs
after `on_exit()`. `Camera.handle_input()` consumes directional keys before scene.

---

## TD Tutorial: Chapters 4–6 (as implemented)

### Chapter 4 — Enemies & Waves

**Data:** `ENEMY_DEFS` (name, image, hp, speed, gold_reward) + `WAVE_DEFS` (enemy_def
index, count, spawn_interval, delay).

**Enemy record:** `self._enemies: list[dict]` — sprite, fsm, hp, max_hp, speed,
gold_reward, path_index, def. `SpriteAnchor.CENTER` on `RenderLayer.OBJECTS`.

**Movement:** `sprite.move_to(target, speed, on_arrive=callback)` with chained callbacks.
Does NOT use `Sequence(MoveTo, Do)` — avoids action re-entrancy trap.

**FSM:** 3-state: `walking → dying → dead`. Death triggers `FadeOut(0.4) + Do + Remove()`.

**Wave spawning:** Chained `self.after(interval, _spawn_enemy)` calls — scene-scoped,
auto-cancelled on exit. No manual `_timer_ids` tracking needed.

### Chapter 5 — Combat

**Targeting:** Per-frame cooldown decrement. When ≤ 0, closest walking enemy in range →
fire projectile via `sprite.move_to()`. On arrival: damage + `ParticleEmitter.burst()`.

**Health bars:** `self.draw_world_rect()` in `draw()` — uses public `sprite.x`/`sprite.y`.
Camera transform handled automatically by the framework helper.

### Chapter 6 — Complete Game

**Game over:** Lives ≤ 0 → `ChoiceScreen`. Retry deferred via `self.after(0, ...)`.

**Win condition:** All waves + enemies done → `MessageScreen` with double-pop back to title.

**Audio:** `game.audio.play_sound(name, optional=True)` / `play_music(name, optional=True)`.
No try/except wrappers needed. SFX: shoot, hit, death, wave, lose_life. Music: bgm_game.

**Speed toggle:** Space toggles `_speed_multiplier` (1.0/2.0), tower cooldown only.
Does NOT affect enemy movement or timers (framework-level time scaling not supported).

---

## Stage 5: API Friction Fixes — Completed

Four friction points from TD tutorial round 2 (#8–#11) resolved. All changes are
additive (backward-compatible). Signatures integrated into subsystem sections above.

| # | Issue | Resolution |
|---|-------|------------|
| 8 | Timer cleanup is manual (~30 occurrences) | `Scene.after()` / `Scene.every()` / `Scene.cancel_timer()` with auto-cleanup |
| 9 | Action re-entrancy: `Do` + `sprite.do()` | Documented in LIMITATIONS.md; workaround: `sprite.move_to(on_arrive=...)` |
| 10 | Health bars require `game._backend.draw_rect()` | `Scene.draw_rect()` / `Scene.draw_world_rect()` |
| 11 | Audio crashes on missing assets | `play_sound(optional=True)` / `play_music(optional=True)` |

**Additional deliverables:**
- `examples/tower_defense/` — complete standalone game
- `tutorials/tower_defense/README.md` — tutorial walkthrough
- `LIMITATIONS.md` — 6 items (4 from stage 3 + action re-entrancy + speed toggle)
- Tutorials ch4–ch6 updated to use new APIs (no `_timer_ids`, no `_backend` access,
  no try/except audio wrappers)

### Subsystem Coverage

**Exercised (15):** Game, Scene (push/pop/replace + timers + draw helpers), Sprite,
Camera (center_on, key_scroll, world_to_screen, world_bounds), Actions (Sequence, Do,
FadeOut, Remove), StateMachine, ParticleEmitter, Timers (Scene.after), Audio
(play_sound, play_music, stop_music, optional=True), UI (Panel, Label, Button),
HUD, InputEvent (world_x/y), ChoiceScreen, MessageScreen, AssetManager

**Not exercised:** Save/Load, Cursor, ColorSwap, DragManager, AnimationDef, Tweens,
ProgressBar, ImageBox, TextBox, List, Grid, Tooltip, TabGroup, DataTable,
show_sequence, Parallel/FadeIn/Repeat/Delay/PlayAnim, camera.follow/pan_to/edge_scroll

Coverage gap is acceptable for a TD game. Future tutorials would cover remaining subsystems.

---

## Edge Case Decisions (Stage 2)

Findings from adversarial testing (`tests/test_edge_cases.py`, 48 tests).
Seven issues where the framework lacks input validation or clamping.

### Desired Behaviors (to be implemented as fixes)

| # | Module | Issue | Desired Behavior |
|---|--------|-------|------------------|
| 1 | `rendering/sprite.py:215-218` | `opacity` setter stores raw value | Clamp to `max(0, min(255, int(value)))` |
| 2 | `rendering/sprite.py:235-238` | `tint` setter stores raw components | Clamp each component to `max(0.0, min(1.0, float(c)))` |
| 3 | `scene.py:340-345` | `push(None)` raises `AttributeError` | Guard with `if scene is None: raise ValueError("scene must not be None")` |
| 4 | `util/timer.py:138-153` | `every()` accepts interval <= 0 | Validate `if interval <= 0: raise ValueError("interval must be > 0")` |
| 5 | `actions.py:390-393` | `Repeat(times=0)` runs child once | Treat `times=0` as no-op: skip `start()` on child, `update()` returns `True` immediately |
| 6 | `rendering/camera.py:125-134` | `center_on()` accepts NaN/Inf | Validate `if not math.isfinite(x) or not math.isfinite(y): raise ValueError` |
| 7 | `save.py:92-93` | `load()` leaks `json.JSONDecodeError` | Add `SaveError(Exception)`, wrap `json.loads` in try/except, raise `SaveError("Corrupted save file")` |

### Edge Cases That Already Work (no findings)

- `Sprite.remove()` twice — safe (early return on `_removed`)
- `Sprite.do()` on removed sprite — silently ignored
- `Sequence()` with no children — finishes immediately
- `Parallel()` with no children — finishes immediately
- `MoveTo` to current position (distance=0) — finishes immediately
- `FadeOut(duration=0)` and `FadeIn(duration=0)` — set final value, finish
- `Do()` callback exception — propagates correctly
- Nested `Sequence(Sequence(Sequence(...)))` — works
- `Timer.after(delay=0)` — fires next tick
- Cancel timer inside own callback — safe
- Cancel same timer twice — no-op
- `Camera.shake(intensity=5, duration=0)` — resets shake state
- World bounds smaller than viewport — clamp handles it
- `AudioManager.set_volume` — already clamps to [0.0, 1.0]
- `AudioManager.set_volume` unknown channel — raises `KeyError`
- `InputManager.translate([])` — returns `[]`
- `KeyEvent(key="")` — translates without error
- `MouseEvent` with negative coords — translates without error
- `SaveManager.load()` non-existent slot — returns `None`
- `SaveManager.delete()` non-existent slot — no-op
