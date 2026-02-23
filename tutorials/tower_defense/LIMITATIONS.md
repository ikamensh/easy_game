# Tower Defense Tutorial — Known Limitations & Design Decisions

Concise notes on trade-offs and intentional constraints in the EasyGame
framework as used by the tower defense chapters.

---

## Sprite ownership

**`add_sprite` is opt-in.** Sprites created directly via `Sprite(...)` are
*not* auto-cleaned when a scene exits. Only sprites passed to
`scene.add_sprite(sprite)` are tracked and removed on `on_exit`. This
keeps existing code that creates sprites directly working unchanged;
scenes that want auto-cleanup opt in by calling `add_sprite`.

---

## Input events

**`world_x` / `world_y` are `None` for non-mouse events.** Keyboard
events (key_press, key_release) never carry coordinates; only mouse
events (click, release, move, drag, scroll) get `world_x`/`world_y`
populated. Game code must check for `None` before using them in world-space logic.

---

## Background color

**`background_color` is per-scene, not per-region.** The framework clears
the entire screen with the base scene’s `background_color` before drawing.
There is no support for different background colors in different screen
regions (e.g. split view). For transparent overlay scenes, the base
(opaque) scene’s color is used.

---

## Camera key scroll

**`enable_key_scroll` consumes directional input.** The camera handles
left/right/up/down before the scene’s `handle_input`. If a scene needs
those keys for something else (e.g. menu navigation), it won’t receive
them when the camera has key scroll enabled.
