# EasyGame Architecture Reference

> Condensed from implementation journals (stages 6–13), updated for stage 3 API
> improvements. All API signatures verified against source.

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
  → screen draw corner → backend.update_sprite → [Pyglet] y-flip + scale → GPU
```

Without camera: sprites render at world pos (world == screen). Mouse `InputEvent`s
have `world_x`/`world_y` auto-populated by the framework before dispatch (via
camera when present, else equal to screen coords). Non-mouse events: `None`.

---

## Cross-Cutting Patterns

**Sync/Restore:** Camera applies per-frame offsets for rendering, then restores
original world positions after `end_frame()`. Prevents double-offsetting since
sprites eagerly push positions on every property change.

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
    def after(self, delay: float, callback) -> int
    def every(self, interval: float, callback) -> int
    def cancel(self, timer_id: int) -> None
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
`_particle_emitters` — sprites/emitters self-register on construction.

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
```

**`background_color`:** Base scene's color is passed to `backend.begin_frame(clear_color)`
in `Game.tick()`. Per-frame clear — no sprite creation/cleanup. Transparent overlay
scenes inherit the base scene's background.

**Sprite ownership:** `add_sprite()` registers a sprite; `_cleanup_owned_sprites()` runs
after `on_exit()` in all SceneStack transitions (push, pop, replace, clear_and_push).
Sprites individually removed via `sprite.remove()` auto-deregister from the scene.
Direct `Sprite()` creation without `add_sprite()` still works (unowned, manual cleanup).

---

## Sprite

```python
class Sprite:
    def __init__(self, image: str, *, position=(0,0),
                 anchor=SpriteAnchor.BOTTOM_CENTER,
                 layer=RenderLayer.UNITS, opacity=255, visible=True,
                 color_swap: ColorSwap | None = None,
                 team_palette: str | None = None)

    # Position (world coordinates)
    position: tuple[float, float]   # property, settable
    x: float                        # property, settable
    y: float                        # property, settable
    opacity: int                    # property, settable (0-255)
    visible: bool                   # property, settable
    image: str                      # property, settable (swaps texture)
    layer: RenderLayer              # read-only
    anchor: SpriteAnchor            # read-only

    # Movement
    def move_to(self, target_pos, speed, *, ease=None, on_arrive=None) -> None

    # Animation
    def play(self, anim: AnimationDef, *, on_complete=None) -> None
    def queue(self, anim: AnimationDef, *, on_complete=None) -> None
    def stop_animation(self) -> None

    # Composable actions
    def do(self, action: Action) -> None      # cancels current action
    def stop_actions(self) -> None

    # Lifecycle
    def remove(self) -> None         # stops actions + animations, deregisters
    @property is_removed -> bool
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

**Key scroll:** `enable_key_scroll(speed)` tracks held arrow keys via `handle_input()`.
`Game.tick()` calls `camera.handle_input(event)` after HUD and Scene UI, before
`scene.handle_input()`. `update()` applies key scroll alongside edge scroll.

Frustum culling uses sprite image dimensions as margin.

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

---

## Audio

```python
class AudioManager:
    def __init__(self, backend, assets: AssetManager)

    def play_sound(self, name: str, *, channel="sfx") -> None
    def play_music(self, name: str, *, loop=True) -> None
    def stop_music(self) -> None
    def crossfade_music(self, name: str, duration=1.0, *, loop=True) -> None
    def set_volume(self, channel: str, level: float) -> None   # 0.0–1.0
    def get_volume(self, channel: str) -> float
    def register_pool(self, name: str, sound_names: list[str]) -> None
    def play_pool(self, name: str) -> None  # random, no immediate repeat
```

**Channels:** `master`, `music`, `sfx`, `ui`. Effective = master × channel.
No `update(dt)` — crossfade driven by tween system. Music NOT cached (pyglet streaming
sources can't be reused). SFX are fire-and-forget.

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

**World coords:** `_with_world_coords(event, camera)` in `Game.tick()` creates a new
frozen InputEvent via `dataclasses.replace()` before any handler sees it. Mouse events
get camera-transformed coords (or screen coords if no camera). Non-mouse events: `None`.

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
class TimerManager:
    def after(self, delay, callback) -> int; def every(self, interval, callback) -> int
    def cancel(self, timer_id); def cancel_all(); def update(self, dt)

class TweenManager:
    def create(self, target, prop, from_val, to_val, duration,
               *, ease=Ease.LINEAR, on_complete=None) -> int
    def cancel(self, tween_id); def update(self, dt)

def tween(target, prop, from_val, to_val, duration, *,
          ease=Ease.LINEAR, on_complete=None) -> int  # module-level convenience

class Ease(Enum): LINEAR, EASE_IN, EASE_OUT, EASE_IN_OUT
```

Game exposes: `game.after()`, `game.every()`, `game.cancel()`, `game.cancel_tween()`.

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
class ColorSwap:
    def __init__(self, source_colors, target_colors)  # list[tuple[int,int,int]]
    def apply(self, image_path) -> PIL.Image.Image; def cache_key(self) -> tuple
def register_palette(name, swap); def get_palette(name) -> ColorSwap

class CursorManager:
    def register(self, name, image_name, hotspot=(0,0))
    def set(self, name)          # "default" restores system cursor
    def set_visible(self, visible: bool); @property current -> str

class SaveManager:
    def __init__(self, save_dir: Path)
    def save(self, slot, state: dict, scene_class_name: str)
    def load(self, slot) -> dict | None
    def list_slots(self, count=10) -> list[dict | None]; def delete(self, slot)
```

**ColorSwap:** Load-time Pillow pixel replacement, cached as GPU texture. Sprite
accepts `color_swap=` or `team_palette=` (registry lookup). `color_swap` wins.

**Save format:** `{"version": 1, "timestamp": "ISO-8601", "scene_class": "...", "state": {...}}`
File: `save_{slot}.json`, default dir: `~/.{slug}/saves/`. `game.save(slot)` calls
top scene's `get_save_state()`. `game.load(slot)` calls `load_save_state()` + returns dict.

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

    def add(self, child: Component) -> None
    def remove(self, child: Component) -> None
    @property parent -> Component | None
    @property children -> list[Component]

    def get_preferred_size(self) -> tuple[int, int]
    def hit_test(self, x, y) -> bool
    def handle_event(self, event) -> bool   # tree dispatch
    def on_event(self, event) -> bool       # subclass override point
    def draw(self) -> None                  # tree draw
    def on_draw(self) -> None               # subclass override point
    def update(self, dt) -> None            # per-frame (no-op default)
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
class ImageBox(Component):    __init__(self, image_name, *, width=64, height=64, **kw)
                              image_name: str  # settable
class ProgressBar(Component): __init__(self, value=0, max_value=100, *, width=200, height=24,
                                       bar_color=None, bg_color=None, **kw)
                              value: float; fraction: float  # settable / read-only
class TextBox(Component):     __init__(self, text, *, width=None, height=None,
                                       typewriter_speed=0.05, **kw)
                              text: str; is_typewriter_done: bool; skip_typewriter()
class List(Component):        __init__(self, items, *, width=300, item_height=40,
                                       on_select=None, **kw)
                              selected_index: int|None; set_items(); set_selected()
class Grid(Component):        __init__(self, columns, rows, *, cell_width=80, cell_height=80,
                                       spacing=4, on_select=None, **kw)
                              set_cell(col, row, comp); get_cell(col, row)
                              selected_cell: tuple[int,int]|None
class Tooltip(Component):     __init__(self, target, text, *, delay=0.5, **kw)
                              # Dual visibility: Component.visible=True; draw gated by _visible_now
class TabGroup(Component):    __init__(self, tabs: list[tuple[str, Component]], *,
                                       on_change=None, **kw)
                              active_tab_index: int; set_active_tab(index)
class DataTable(Component):   __init__(self, columns, rows, *, col_widths=None,
                                       row_height=32, on_select=None, **kw)
                              set_data(columns, rows); selected_row: int|None
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
    def __init__(self, *, font="serif", font_size=24, text_color=...,
                 panel_*=..., button_*=..., label_*=..., progressbar_*=...,
                 button_disabled_color=(40,42,55,200),
                 button_disabled_text_color=(100,100,110,200),
                 selected_color=..., tooltip_*=..., tab_*=..., datatable_*=...,
                 drop_accept_color=..., drop_reject_color=..., ghost_opacity=0.5)
    # resolve_{label,button,panel,...}_style()
    # resolve_button_style(explicit, state) — state: "normal"|"hovered"|"pressed"|"disabled"
```

Widget-specific colors not in `ResolvedStyle` are Theme properties (e.g.,
`theme.progressbar_color`, `theme.selected_color`, `theme.tab_active_color`).

**Disabled buttons:** `Button.on_draw()` resolves `"disabled"` state when `enabled=False`.
Theme provides `button_disabled_color` and `button_disabled_text_color` for muted visuals.

---

## Drag-and-Drop, HUD, Convenience Screens

```python
class DragManager:                         # lazy on _UIRoot
    @property is_dragging -> bool; @property drag_data -> Any | None
    def handle_event(self, event) -> bool
# Any Component: draggable=True, drag_data=..., drop_accept=fn, on_drop=fn
# Drag-start checked BEFORE on_event (beats Button.on_click). Escape cancels.

class HUD:                                 # lazy on game.hud
    visible: bool = True
    def add(self, component); def remove(self, component); def clear(self)
# Wraps _UIRoot. Visible when hud.visible AND top_scene.show_hud.
# Draws above base scene, below transparent overlays.

# Convenience screens — all Scene subclasses, transparent=True, show_hud=False, modal
class MessageScreen(Scene):   __init__(self, text, *, on_dismiss=None)
class ChoiceScreen(Scene):    __init__(self, prompt, choices, *, on_choice=None)
class ConfirmDialog(Scene):   __init__(self, question, *, on_confirm=None, on_cancel=None)
class SaveLoadScreen(Scene):  __init__(self, mode, *, on_save=None, on_load=None, on_cancel=None)
```

`game.show_sequence(screens, on_complete=...)` chains via `on_reveal()` lifecycle.

---

## Backend Protocol

```python
class Backend(Protocol):
    # Window lifecycle
    create_window(width, height, title, fullscreen, visible=True)
    begin_frame(clear_color=None); end_frame(); poll_events() -> list[Event]; get_dt() -> float; quit()

    # Images & sprites
    load_image(path) -> ImageHandle; load_image_from_pil(pil_image) -> ImageHandle
    get_image_size(image_handle) -> tuple[int, int]
    create_sprite(image_handle, order) -> SpriteId; remove_sprite(sprite_id)
    update_sprite(sprite_id, x, y, *, image=None, opacity=255, visible=True)
    set_sprite_order(sprite_id, order)

    # Per-frame drawing (cleared each begin_frame; uses _ui_overlay_group order=100)
    draw_rect(x, y, w, h, color, *, opacity=1.0)
    draw_text(text, x, y, font_size, color, *, font=None, anchor_x="left", anchor_y="baseline")
    draw_image(image_handle, x, y, w, h, *, opacity=1.0)
    load_font(name, path=None) -> FontHandle

    # Cursor
    set_cursor(image_handle, hotspot_x=0, hotspot_y=0); set_cursor_visible(visible)

    # Audio
    load_sound(path) -> SoundHandle; play_sound(sound_handle, volume=1.0)
    load_music(path) -> SoundHandle
    play_music(music_handle, loop=True, volume=1.0) -> PlayerHandle
    set_player_volume(player_id, volume); stop_player(player_id)
```

**Persistent sprites** (`create_sprite`/`update_sprite`) participate in camera sync.
**Per-frame draws** (`draw_rect`/`draw_text`/`draw_image`) are screen-space UI only.

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

**Asset generation:** All placeholder art is Pillow-generated via `assetgen/` primitives
(`solid_rect`, `labeled_rect`, `circle`, `triangle`, `ring`, `filled_ellipse`,
`vertical_gradient`, `crosshatch`, wireframe 3D). Each example/tutorial adds a
generator module in `assetgen/` and a corresponding call in `generate_assets.py`.
Assets go to both `assets/images/sprites/` (tests) and the local example dir.

**Import style:** Flat from `easygame` — never from subpackages:
```python
from easygame import Game, Scene, Sprite, Camera, Panel, Label, Button, ...
```

**Scene cleanup:** Sprites registered via `scene.add_sprite()` are auto-removed after
`on_exit()`. Unowned sprites, tweens, and timers still need manual cleanup in `on_exit()`.

---

## Stage 3: API Improvements — Completed

Seven friction points from TD tutorial (chapters 1–3) resolved. All changes are
additive (backward-compatible). Signatures integrated into subsystem sections above.

| Change | Files touched |
|--------|---------------|
| `Scene.background_color` | `scene.py` (attr + SceneStack), `game.py` (begin_frame) |
| `Scene.add_sprite()` / `remove_sprite()` | `scene.py` (ownership + lifecycle), `sprite.py` (deregister) |
| `Game(asset_path=...)` | `game.py` (__init__ + assets property) |
| `Button` disabled visual | `components.py` (on_draw), `theme.py` (disabled fields + resolve) |
| `Label(font_size=, text_color=)` | `components.py` (Label.__init__ + _merge_label_style) |
| `Camera.enable_key_scroll()` | `camera.py` (handle_input + update), `game.py` (dispatch) |
| `InputEvent.world_x/y` | `input.py` (fields + _with_world_coords), `game.py` (dispatch) |

**Key design decisions:**
- `InputEvent` stays `frozen=True`; world coords populated via `dataclasses.replace()`
- `add_sprite()` takes an already-created Sprite (not construction args) for flexibility
- `_cleanup_owned_sprites()` runs *after* user's `on_exit()` so custom cleanup can run first
- `Camera.handle_input()` consumes directional keys; scene can still override by consuming first
- `Label` gets `font_size`/`text_color`/`font` convenience kwargs; `Button` uses `style=` only
