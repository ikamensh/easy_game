# Desired Examples

Before/after comparisons: how each subsystem works today (pygame) vs how Saga2D
should make it work. Each pair has `_current.py` (what you write now) and
`_desired.py` (what we want).

| Subsystem | Current | Desired | Pain eliminated |
|---|---|---|---|
| `menu` | ~110 lines | ~25 lines | Manual button system, hover tracking, no scene transitions |
| `sprite_animation` | ~90 lines | ~15 lines | Manual sheet loading, frame timers, lerp math |
| `scene_stack` | ~150 lines | ~60 lines | Global state flags, no push/pop, manual overlays |
| `scrolling_world` | ~130 lines | ~35 lines | Manual camera, y-sort, no frustum culling |
| `ui_dialog` | ~130 lines | ~35 lines | Manual word wrap, layout math, typewriter state |
| `audio` | ~120 lines | ~15 lines | Manual crossfade manager, no channels, no sound pools |
| `actions` | ~90 lines | ~20 lines | Callback chains or state machine boilerplate |
