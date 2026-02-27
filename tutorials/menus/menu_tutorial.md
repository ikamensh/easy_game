# EasyGame — Menus & Navigation

A complete guide to building multi-screen games with EasyGame: what the
abstractions are, why they're designed the way they are, and how to use them.

---

## The core idea: scenes are states

A game is a state machine.  At any moment you're in exactly one logical
state: the title screen, the main menu, the game world, the inventory, the
pause screen.  Each state has its own UI, its own input rules, its own
update logic.  When you leave a state you want it cleaned up.  When you come
back you want it restored.

EasyGame makes each state a **Scene**.  A Scene is a Python class.  You
subclass it, override the hooks you care about, and the framework handles
the rest.

```python
class TitleScreen(Scene):
    def on_enter(self): ...   # build UI, start music
    def on_exit(self):  ...   # framework auto-cleans sprites/timers
    def update(self, dt): ... # per-frame logic
    def handle_input(self, event): ...  # keyboard / mouse
```

Scenes live on a **stack**.  The top of the stack is the active scene.
Push a new one to overlay it.  Pop it to go back.  The stack is the
navigation model — it's a direct encoding of the "back button" concept
that every game's menu system needs.

---

## Building a title screen

```python
from easygame import Game, Scene, Panel, Label, Button, Anchor, Layout

class TitleScreen(Scene):
    background_color = (20, 24, 35, 255)   # dark blue-grey

    def on_enter(self):
        panel = Panel(anchor=Anchor.CENTER, layout=Layout.VERTICAL, spacing=20)
        panel.add(Label("My Game", font_size=52))
        panel.add(Button("Play",     on_click=lambda: self.game.replace(GameScreen())))
        panel.add(Button("Settings", on_click=lambda: self.game.push(SettingsOverlay())))
        panel.add(Button("Quit",     on_click=self.game.quit))
        self.ui.add(panel)

game = Game("My Game", resolution=(800, 600), fullscreen=False)
game.run(TitleScreen())
```

**Why it looks like this:**

`background_color` is a class attribute, not code.  You declare intent;
the framework clears the screen before every draw.  No sprite, no backend
call, no cleanup.

`self.ui` is a full-screen component tree that every Scene gets for free.
You add to it in `on_enter`.  When the scene exits the framework discards
it automatically.

`Panel` with `layout=Layout.VERTICAL` is the centering primitive.
`anchor=Anchor.CENTER` places the whole group in the middle of the screen.
`spacing=20` puts 20 pixels between each child.  You describe structure;
the framework computes coordinates.

`Label` and `Button` accept `font_size` and `text_color` directly — no
`Style(...)` wrapper for the common case.

`on_click` is a plain callable.  No event system, no observer pattern, no
signal/slot ceremony.  Just a function.

---

## Navigating between screens

Four methods on `game` cover every navigation case:

| Method | Stack effect | Use when |
|--------|-------------|----------|
| `game.push(scene)` | `[..., current, new]` | opening an overlay; current stays underneath |
| `game.pop()` | `[..., current]` | dismissing an overlay; return to what was below |
| `game.replace(scene)` | `[..., new]` | transitioning; current is gone for good |
| `game.clear_and_push(scene)` | `[new]` | hard reset; nuke everything and start fresh |

**The `push` vs `replace` distinction is load-bearing.**

When the player clicks "New Game", you want `replace` — the title screen
should not be sitting in the stack underneath the game world.  If you used
`push`, pressing ESC during gameplay would bring the menu back, which is
wrong.  `replace` makes the navigation graph explicit in the code.

When the player opens Settings from the title screen, you want `push` — the
title screen stays underneath; Settings is an overlay; ESC pops it and the
title screen reappears.

These aren't framework quirks.  They're the two distinct navigation
relationships that every menu system has.  EasyGame surfaces them as
first-class operations rather than hiding them behind a single "go to screen"
call.

---

## Overlay scenes: transparent + pause_below

A settings panel or pause menu sits *on top of* the scene below.  You want
the game world (or title screen) to remain visible underneath.

```python
class SettingsOverlay(Scene):
    transparent = True    # draw the scene below me first
    pause_below = True    # don't update the scene below
    pop_on_cancel = True  # ESC dismisses this overlay automatically

    def on_enter(self):
        panel = Panel(
            anchor=Anchor.CENTER, layout=Layout.VERTICAL, spacing=16,
            style=Style(background_color=(0, 0, 0, 180), padding=40),
        )
        panel.add(Label("Settings", font_size=40))
        panel.add(Label("(volume, keybindings, etc.)", font_size=18))
        panel.add(Button("Back", on_click=lambda: self.game.pop()))
        self.ui.add(panel)
```

**`transparent = True`** — the draw loop walks down the stack until it
finds an opaque scene, draws it, then draws overlays on top.  This one
attribute gives you composited overlays with no rendering code.

**`pause_below = True`** — the update loop stops at this scene.  The game
world freezes (enemies stop moving, timers pause) while the overlay is
active.  Set it to `False` if you want the world to keep running behind a
transparent overlay — for example a minimap or a non-modal HUD panel.

**`pop_on_cancel = True`** — ESC is automatically handled.  No
`handle_input` override needed.  Any scene with this flag pops itself when
the cancel action fires and nothing else has consumed the event first.

The three attributes together express the full contract of an overlay scene
in a single declarative block at the top of the class.

---

## Hotkeys with bind_key

Game screens need hotkeys: `I` for inventory, `C` for character, `M` for
map.  `bind_key` registers these in `on_enter` alongside the rest of your
scene setup:

```python
class GameScreen(Scene):
    background_color = (10, 60, 10, 255)

    def on_enter(self):
        # Hotkeys — registered alongside UI, live and die with this scene
        self.bind_key("cancel", lambda: self.game.push(PauseMenu()))
        self.bind_key("i",      lambda: self.game.push(InventoryScreen()))
        self.bind_key("c",      lambda: self.game.push(CharacterScreen()))
        self.bind_key("m",      lambda: self.game.push(MapScreen()))

        # UI hint
        hint = Label("I=Inventory  C=Character  M=Map  ESC=Pause",
                     font_size=16, anchor=Anchor.BOTTOM_LEFT, margin=12)
        self.ui.add(hint)
```

`bind_key` accepts either a raw key name (`"i"`, `"space"`) or a named
action (`"cancel"`, `"confirm"`).  Named actions go through the input
manager, so if the player rebinds ESC to a different key, `"cancel"` still
works.

Bindings fire on `key_press` only (not release) and consume the event,
so they don't accidentally trigger `handle_input` for the same key.

**Why `bind_key` belongs in `on_enter`:**  All of a scene's behaviour —
visual structure, hotkeys, timers, music — is wiring.  It belongs in one
place.  Separating hotkeys into a dedicated `handle_input` method that grows
silently as the game adds features creates a maintenance split.  `bind_key`
makes the full contract of a scene readable at a glance.

**When to still use `handle_input`:**  Mouse clicks, drag gestures, anything
that needs `event.x / event.y / event.world_x`, conditional logic based on
game state.  Simple key → callback lives in `bind_key`.  Everything else
lives in `handle_input`.  They compose cleanly — both can be present; the
game loop calls bindings first, then falls through to `handle_input` if not
consumed.

---

## Full working example

Five screens.  Full navigation.  ~70 lines.

```python
from easygame import Game, Scene, Panel, Label, Button, Anchor, Layout, Style


class TitleScreen(Scene):
    background_color = (20, 24, 35, 255)
    show_hud = False

    def on_enter(self):
        panel = Panel(anchor=Anchor.CENTER, layout=Layout.VERTICAL, spacing=20)
        panel.add(Label("My Game", font_size=52))
        panel.add(Button("Play",     on_click=lambda: self.game.replace(GameScreen())))
        panel.add(Button("Settings", on_click=lambda: self.game.push(SettingsOverlay())))
        panel.add(Button("Quit",     on_click=self.game.quit))
        self.ui.add(panel)


class SettingsOverlay(Scene):
    transparent = True
    pause_below = True
    pop_on_cancel = True

    def on_enter(self):
        panel = Panel(
            anchor=Anchor.CENTER, layout=Layout.VERTICAL, spacing=16,
            style=Style(background_color=(0, 0, 0, 180), padding=40),
        )
        panel.add(Label("Settings", font_size=40))
        panel.add(Label("(nothing here yet)", font_size=18))
        panel.add(Button("Back", on_click=lambda: self.game.pop()))
        self.ui.add(panel)


class GameScreen(Scene):
    background_color = (10, 60, 10, 255)

    def on_enter(self):
        self.bind_key("cancel", lambda: self.game.push(PauseMenu()))
        self.bind_key("i",      lambda: self.game.push(InventoryScreen()))

        self.ui.add(Label("I=Inventory  ESC=Pause",
                          font_size=16, anchor=Anchor.BOTTOM_LEFT, margin=12))


class PauseMenu(Scene):
    transparent = True
    pause_below = True
    pop_on_cancel = True

    def on_enter(self):
        menu = Panel(
            anchor=Anchor.CENTER, layout=Layout.VERTICAL, spacing=16,
            style=Style(background_color=(0, 0, 0, 160), padding=40),
        )
        menu.add(Label("PAUSED", font_size=48))
        menu.add(Button("Resume",        on_click=lambda: self.game.pop()))
        menu.add(Button("Quit to Title", on_click=lambda: self.game.clear_and_push(TitleScreen())))
        self.ui.add(menu)


class InventoryScreen(Scene):
    transparent = True
    pause_below = True
    pop_on_cancel = True

    def on_enter(self):
        panel = Panel(
            anchor=Anchor.CENTER, layout=Layout.VERTICAL, spacing=16,
            style=Style(background_color=(10, 10, 30, 200), padding=40),
        )
        panel.add(Label("Inventory", font_size=40))
        panel.add(Label("(empty)", font_size=18))
        panel.add(Button("Close", on_click=lambda: self.game.pop()))
        self.ui.add(panel)


game = Game("My Game", resolution=(800, 600), fullscreen=False)
game.run(TitleScreen())
```

---

## Why these abstractions work

Game frameworks tend to solve menu navigation in one of three ways:

**1. Global state machine** — a single `current_screen` variable, a
`switch_to(screen_id)` function, and manual save/restore of whatever was
happening before.  Works for linear flows.  Breaks the moment you need
overlays (where is the game world while Settings is open?) or nested stacks
(pause menu → options → keybinding → back, back, back).

**2. Screen manager with events** — screens register as event listeners,
a central dispatcher routes events, transitions are triggered by emitting
events.  Decoupled but verbose.  Every new screen type needs to know which
events to emit and subscribe to.  The navigation graph lives in the event
names, not in the code.

**3. Scene stack** — what EasyGame uses.  Navigation IS the call stack.
`push` is "open"; `pop` is "back"; `replace` is "transition".  The stack
implicitly tracks "what was I doing before this overlay".  There's no
registry, no event bus, no screen IDs.  The navigation graph is visible in
the code as a tree of class instantiations.

The scene stack is the right abstraction because game navigation *is* a
stack.  You open settings over the menu, keybindings over settings, a
confirmation dialog over keybindings.  Each level is independent.  Closing
any level returns to the level below.  A stack models this exactly.  A flat
state machine or event bus models it awkwardly.

`transparent` and `pause_below` are the two orthogonal axes of overlay
behaviour.  Draw-below and update-below are independent choices:

|  | `pause_below=True` | `pause_below=False` |
|--|-------------------|---------------------|
| **`transparent=True`** | pause menu (world visible, frozen) | live minimap overlay |
| **`transparent=False`** | loading screen (world hidden, frozen) | cutscene (world running, hidden) |

Expressing this as two booleans on the Scene class — readable at the top of
the class definition — is more honest than hiding it in a screen transition
API.

---

## What could be better / redesign from scratch

### 1. `transparent` should be called `opaque` (inverted default)

The most common overlay is transparent (draw below).  The flag should
default to the common case.  `opaque = False` reads: "this scene is not
opaque — draw what's below."  `transparent = True` reads: "this scene is
transparent" which sounds like alpha, not "draw the scene below me."

Flipping to `opaque: bool = True` with `False` for overlays would make the
meaning clearer and the default safer.  Discovering you need `transparent =
True` because your overlay has a black background is a sharp edge.

### 2. `pop_on_cancel` should probably default to `True` for pushed scenes

The distinction: scenes that enter via `push` are almost always overlays
that should dismiss on ESC.  Scenes that enter via `replace` or
`clear_and_push` are top-level states that should not.  The framework knows
which operation was used to push a scene — it could automatically set the
equivalent of `pop_on_cancel` based on how the scene was pushed, with an
opt-out for scenes that want to handle cancel themselves.

This would make the common overlay pattern require zero boilerplate:
`push(SettingsOverlay())` implies "ESC will pop this."

### 3. `bind_key` should support `on_hold` and `on_release`

Currently `bind_key` fires on `key_press` only.  Games need held keys
(camera scroll while held, sprint while held).  A richer API:

```python
self.bind_key("space", on_press=self.jump)
self.bind_key("shift", on_hold=self.sprint, on_release=self.stop_sprint)
```

The held-key pattern currently requires tracking state in `handle_input`
plus `update`, which is exactly the boilerplate `bind_key` was meant to
eliminate.  The framework already processes `key_press` and `key_release` —
it just doesn't expose hold tracking at the scene level.

### 4. Named action bindings need a `register` step

Currently `bind_key("cancel", cb)` works because `"cancel"` is a
pre-registered action.  But if a game defines `"attack"`, `"interact"`,
`"map"` as custom actions, `bind_key("map", cb)` silently falls back to
key-name matching.  There's no way to know if `"map"` is a registered
action or a raw key named `"map"`.  A small registration step would close
this:

```python
game.input.register_action("map", default_key="m")
game.input.register_action("inventory", default_key="i")
# Now bind_key("inventory", ...) is unambiguous and rebindable
```

### 5. Scene constructor arguments vs lifecycle

Passing data to a scene currently looks like:

```python
class InventoryScreen(Scene):
    def __init__(self, items):
        self.items = items

    def on_enter(self):
        # use self.items — self.game is available here, but not in __init__
```

This works but mixes two concepts: scene configuration (constructor) and
scene activation (on_enter).  `self.game` is None during `__init__`, which
bites new users.  A cleaner design would make scene arguments explicit:

```python
game.push(InventoryScreen, items=player.inventory)
# Framework calls InventoryScreen(game=self, items=player.inventory)
# on_enter receives the args, game is available from the start
```

This also opens the door to scene caching — the framework could re-use an
existing InventoryScreen instance if the args haven't changed, avoiding
rebuild cost on every open.

### 6. If redesigning from scratch: scenes as coroutines

The deepest redesign would use async/coroutines to express scene lifecycle:

```python
async def settings_overlay(game):
    async with game.scene(transparent=True, pause_below=True) as scene:
        scene.ui.add(Panel(...))
        await game.wait_for_cancel()   # suspends here until ESC
    # exiting the context manager pops the scene automatically
```

This makes the "open, wait, close" lifecycle linear and readable.  The
currently implicit lifecycle (on_enter → [user interacts] → on_exit) becomes
explicit control flow.  Stack management disappears into context managers.
Re-entrant overlays compose naturally with nested async calls.

The tradeoff is that it requires the game loop to be async-native, which
constrains embedding options and complicates testing.  The current
class-based approach is more familiar to Python game developers and easier
to reason about without async knowledge — which matters for the target
audience.  But for a framework designed today with async Python as a given,
the coroutine model would be architecturally superior.
