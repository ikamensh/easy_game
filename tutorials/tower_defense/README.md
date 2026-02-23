# Building a Tower Defense Game with EasyGame

A step-by-step tutorial that takes you from an empty file to a fully playable Tower Defense game. Along the way, you'll learn how EasyGame's scene stack, camera, sprites, UI widgets, timers, state machines, composable actions, particles, and audio system work together to let you focus on gameplay instead of engine plumbing.

**What you'll build:** A 960x540 tower defense game with a scrollable tile map, three tower types (Basic, Sniper, Splash), three enemy types (Soldier, Scout, Tank), five escalating waves, a build menu with gold economy, health bars, particle explosions, background music, sound effects, and win/lose screens with retry.

**Time:** ~60 minutes to read and understand; each chapter is a standalone, runnable `.py` file.

**Prerequisites:** Python 3.11+, `pip install pyglet pillow`.

## Running the Tutorial

Each chapter is self-contained. Run any chapter from the project root:

```bash
python tutorials/tower_defense/ch1_title_screen.py
python tutorials/tower_defense/ch2_game_map.py
python tutorials/tower_defense/ch3_tower_placement.py
python tutorials/tower_defense/ch4_enemies.py
python tutorials/tower_defense/ch5_combat.py
python tutorials/tower_defense/ch6_game_loop.py
```

Assets are auto-generated the first time you run any chapter. The placeholder art uses Pillow to create simple but recognizable sprites, so you don't need to download anything.

---

## Chapter 1: Title Screen

**File:** `ch1_title_screen.py` | **Subsystems:** Game, Scene, Panel, Label, Button, Theme, InputEvent

Every EasyGame program starts the same way: create a `Game`, define a `Scene`, and call `game.run()`.

### The Minimal Setup

```python
from easygame import Game, Scene, Theme

game = Game(
    "Tower Defense",
    resolution=(960, 540),
    backend="pyglet",
    asset_path=_asset_dir,
)
game.theme = Theme(
    font="serif",
    button_background_color=(50, 55, 80, 255),
    button_hover_color=(70, 80, 120, 255),
    button_text_color=(220, 220, 230, 255),
    button_min_width=220,
)
game.run(TitleScene())
```

Three lines of setup. The `Game` object owns the window, the main loop, the scene stack, and the audio manager. The `Theme` sets global defaults for all UI widgets -- individual components inherit these unless they provide an explicit `Style` override.

### Building a Scene

A `Scene` is a self-contained game state. It has lifecycle hooks that you override:

```python
class TitleScene(Scene):
    background_color = (25, 30, 40, 255)  # auto-cleared each frame

    def on_enter(self) -> None:
        """Called when this scene becomes active."""
        title_label = Label("Tower Defense", font_size=48, text_color=(255, 220, 80, 255))
        play_button = Button("Play", on_click=self._on_play_clicked)
        quit_button = Button("Quit", on_click=self._on_quit_clicked)

        menu_panel = Panel(
            layout=Layout.VERTICAL,
            spacing=20,
            anchor=Anchor.CENTER,
            style=Style(background_color=(30, 35, 50, 220), padding=40),
            children=[title_label, play_button, quit_button],
        )
        self.ui.add(menu_panel)

    def _on_play_clicked(self) -> None:
        self.game.push(GameScene())

    def _on_quit_clicked(self) -> None:
        self.game.quit()
```

The UI system is declarative: you describe a tree of components (panels contain labels and buttons), attach them to `self.ui`, and the framework handles layout, drawing, hover states, and click dispatch. `Anchor.CENTER` pins the panel to the middle of the screen. `Layout.VERTICAL` stacks children top-to-bottom with the specified `spacing`.

### Keyboard Input

EasyGame translates raw key presses into semantic actions. You handle them in `handle_input`:

```python
def handle_input(self, event: InputEvent) -> bool:
    if event.action == "confirm":     # Enter key
        self._on_play_clicked()
        return True                   # consumed -- don't pass to other handlers
    if event.action == "cancel":      # Escape key
        self._on_quit_clicked()
        return True
    return False                      # not consumed
```

Return `True` to consume an event, `False` to let it propagate down the scene stack. The UI system handles mouse clicks on buttons automatically, so `handle_input` only needs to add keyboard shortcuts.

> **Without EasyGame** -- In raw pyglet, there is no scene stack. You'd track `current_scene = "title"` as a string and branch everywhere:
>
> ```python
> # Raw pyglet: manual scene management
> current_scene = "title"
>
> @window.event
> def on_draw():
>     if current_scene == "title":
>         draw_title_screen()
>     elif current_scene == "game":
>         draw_game()
>     elif current_scene == "pause":
>         draw_game()          # must redraw game underneath!
>         draw_pause_overlay()
>
> @window.event
> def on_key_press(symbol, modifiers):
>     global current_scene
>     if current_scene == "title":
>         if symbol == key.RETURN:
>             current_scene = "game"
>             init_game()      # manual initialization
>     elif current_scene == "game":
>         if symbol == key.ESCAPE:
>             current_scene = "title"
>             cleanup_game()   # manual cleanup
> ```
>
> Adding a pause menu, settings screen, or confirmation dialog means adding branches to every `on_draw` and `on_key_press` handler. EasyGame's scene stack handles layering, lifecycle hooks, and input dispatch automatically.

> **Without EasyGame** -- Buttons in raw pyglet are hand-coded rectangles with manual hit-testing:
>
> ```python
> # Raw pyglet: manual button implementation
> BUTTON_W, BUTTON_H = 300, 50
> buttons = [("Play", start_game), ("Quit", quit_game)]
>
> # Calculate positions manually
> total_h = len(buttons) * BUTTON_H + (len(buttons) - 1) * 20
> start_y = (540 - total_h) // 2
> button_rects = []
> for i, (text, _) in enumerate(buttons):
>     x = (960 - BUTTON_W) // 2
>     y = start_y + i * (BUTTON_H + 20)
>     button_rects.append((x, y, BUTTON_W, BUTTON_H))
>
> @window.event
> def on_mouse_press(x, y, button, modifiers):
>     for i, rect in enumerate(button_rects):
>         rx, ry, rw, rh = rect
>         if rx <= x <= rx + rw and ry <= y <= ry + rh:
>             buttons[i][1]()  # call action
>
> @window.event
> def on_draw():
>     for i, ((text, _), rect) in enumerate(zip(buttons, button_rects)):
>         rx, ry, rw, rh = rect
>         is_hovered = (rx <= mouse_x <= rx + rw and ry <= mouse_y <= ry + rh)
>         color = HOVER_COLOR if is_hovered else NORMAL_COLOR
>         draw_rect(rx, ry, rw, rh, color)
>         draw_text(text, rx + rw // 2, ry + rh // 2)
> ```
>
> No hover states, no disabled state, no theming, no auto-layout. Add a button? Recalculate all positions. EasyGame's `Button`, `Panel`, and `Layout` handle all of this declaratively.

---

## Chapter 2: Game Map

**File:** `ch2_game_map.py` | **New subsystems:** Camera, Sprite, SpriteAnchor, RenderLayer

This chapter adds the actual play area: a 40x22 tile map (1280x704 pixels) viewed through a 960x540 camera, with arrow-key scrolling and a top-bar HUD.

### Tile Map Rendering

The map is a 2D list of integers. We iterate it and create one `Sprite` per tile:

```python
GRASS = 0
PATH = 1

def _create_tile_map(self) -> None:
    tile_images = {GRASS: "grass", PATH: "path_straight"}
    for row in range(MAP_ROWS):
        for col in range(MAP_COLS):
            tile_type = MAP_DATA[row][col]
            sprite = Sprite(
                tile_images[tile_type],
                position=(col * TILE_SIZE, row * TILE_SIZE),
                anchor=SpriteAnchor.TOP_LEFT,
                layer=RenderLayer.BACKGROUND,
            )
            self.add_sprite(sprite)
```

Key concepts:

- **`SpriteAnchor.TOP_LEFT`** -- the sprite's position is its top-left corner, perfect for tile grids.
- **`RenderLayer.BACKGROUND`** -- tiles draw behind everything else. The framework sorts by layer automatically.
- **`self.add_sprite(sprite)`** -- registers the sprite as owned by this scene. When the scene exits, all owned sprites are automatically removed. No manual cleanup needed.

### Camera Setup

The map is larger than the screen, so we need a camera:

```python
self.camera = Camera(
    (SCREEN_W, SCREEN_H),
    world_bounds=(0, 0, MAP_WIDTH_PX, MAP_HEIGHT_PX),
)
self.camera.center_on(MAP_WIDTH_PX / 2, MAP_HEIGHT_PX / 2)
self.camera.enable_key_scroll(speed=200.0)
```

Setting `self.camera` on the scene tells the framework to offset all sprites by the camera position during rendering. `world_bounds` clamps the camera so it can't scroll past the map edges. `enable_key_scroll` adds arrow-key scrolling with no additional code needed -- the camera reads held keys each frame and adjusts its position.

### Scene Transitions

The Play button now pushes a `GameScene` on top of the `TitleScene`:

```python
def _on_play_clicked(self) -> None:
    self.game.push(GameScene())  # title stays underneath
```

`push()` leaves the TitleScene on the stack. When the player presses Escape in GameScene, we `pop()` back -- the title screen is revealed without rebuilding it. This stack-based navigation is how strategy games handle title -> gameplay -> pause -> settings hierarchies.

> **Without EasyGame** -- Camera scrolling in raw pyglet means writing the offset math yourself, including bounds clamping and key-held tracking:
>
> ```python
> # Raw pyglet: manual camera
> cam_x, cam_y = 0, 0
> keys_held = set()
>
> @window.event
> def on_key_press(symbol, mods):
>     keys_held.add(symbol)
>
> @window.event
> def on_key_release(symbol, mods):
>     keys_held.discard(symbol)
>
> def update(dt):
>     global cam_x, cam_y
>     if key.LEFT in keys_held:
>         cam_x -= 200 * dt
>     if key.RIGHT in keys_held:
>         cam_x += 200 * dt
>     # Don't forget bounds clamping!
>     cam_x = max(0, min(cam_x, MAP_W - SCREEN_W))
>     cam_y = max(0, min(cam_y, MAP_H - SCREEN_H))
>
> @window.event
> def on_draw():
>     for tile in tiles:
>         screen_x = tile.world_x - cam_x
>         screen_y = tile.world_y - cam_y
>         # Manual frustum culling -- easy to forget
>         if -32 < screen_x < SCREEN_W + 32 and -32 < screen_y < SCREEN_H + 32:
>             tile.image.blit(screen_x, screen_y)
> ```
>
> Every sprite's position must be manually offset. Forget the bounds clamping and you get black edges. Forget the culling and you're drawing 880 sprites even when only 300 are visible. EasyGame's `Camera` does offset, clamping, culling, and key-scroll in three lines.

---

## Chapter 3: Tower Placement

**File:** `ch3_tower_placement.py` | **New concepts:** mouse input, coordinate systems, dynamic UI

This chapter adds interactive tower placement: a build menu on the right, click-to-place with a range indicator that snaps to valid slots, and gold tracking.

### Coordinate Systems

EasyGame input events carry both screen and world coordinates:

```python
def handle_input(self, event: InputEvent) -> bool:
    if event.type == "click" and event.button == "left":
        if self._placing_tower_def is not None:
            # event.world_x / event.world_y are auto-transformed
            # through the camera -- no manual math needed.
            self._try_place_tower(event.world_x, event.world_y)
            return True
    return False
```

`event.world_x` and `event.world_y` are the click position in world space, automatically transformed through the camera's inverse. You never need to call `camera.screen_to_world()` manually on input events -- the framework does it for you.

### Placement Logic

Converting world coordinates to tile coordinates is simple division:

```python
def _try_place_tower(self, world_x: float, world_y: float) -> bool:
    col = int(world_x) // TILE_SIZE
    row = int(world_y) // TILE_SIZE

    if (col, row) not in self._slot_sprites:
        return False  # not a valid slot
    if self._gold < tower_def["cost"]:
        return False  # can't afford

    self._gold -= tower_def["cost"]

    # Remove the slot marker, create the tower sprite.
    slot_sprite = self._slot_sprites.pop((col, row))
    slot_sprite.remove()

    tower_sprite = Sprite(
        tower_def["image"],
        position=(col * TILE_SIZE, row * TILE_SIZE),
        anchor=SpriteAnchor.TOP_LEFT,
        layer=RenderLayer.OBJECTS,
    )
    self.add_sprite(tower_sprite)
```

### Dynamic UI

Buy buttons are disabled when the player can't afford a tower:

```python
def _refresh_buy_buttons(self) -> None:
    for i, tdef in enumerate(TOWER_DEFS):
        self._buy_buttons[i].enabled = self._gold >= tdef["cost"]
```

Setting `button.enabled = False` blocks all input on that component automatically. The button draws in a dimmed state with no additional code.

### Range Indicator

A translucent circle follows the cursor during placement mode, snapping to nearby tower slots:

```python
if event.type in ("move", "drag"):
    snap = self._snap_to_nearest_slot(event.world_x, event.world_y)
    if snap is not None:
        self._range_indicator.position = snap
    else:
        self._range_indicator.position = (event.world_x, event.world_y)
```

The range indicator is a normal `Sprite` with `visible=False` initially, shown when entering placement mode. No special rendering code -- just move and show/hide.

---

## Chapter 4: Enemy Waves

**File:** `ch4_enemies.py` | **New subsystems:** StateMachine, Scene timers (`self.after`), Sprite.move_to, Actions (Sequence, FadeOut, Do, Remove)

This is where the game comes alive. Enemies spawn in waves, follow the path, and cost lives when they escape.

### Enemy State Machine

Each enemy gets a `StateMachine` with three states:

```python
fsm = StateMachine(
    states=["walking", "dying", "dead"],
    initial="walking",
    transitions={
        "walking": {"die": "dying"},
        "dying": {"finish": "dead"},
    },
)
```

`StateMachine` is a lightweight utility for tracking game entity states with validated transitions. `fsm.trigger("die")` moves from `walking` to `dying`; calling it from `dead` raises an error. This catches bugs early -- an enemy can't die twice.

### Path Following

Enemies follow waypoints using `sprite.move_to()` with chained callbacks:

```python
def _walk_to_next(self, enemy: dict) -> None:
    if enemy["fsm"].state != "walking":
        return

    idx = enemy["path_index"] + 1
    if idx >= len(ENEMY_PATH_PX):
        self._enemy_reached_end(enemy)
        return

    enemy["path_index"] = idx
    target = ENEMY_PATH_PX[idx]
    enemy["sprite"].move_to(
        target,
        speed=enemy["speed"],
        on_arrive=lambda e=enemy: self._walk_to_next(e),
    )
```

`move_to()` interpolates the sprite's position toward the target at the given speed. The `on_arrive` callback fires when the sprite reaches the target -- we advance to the next waypoint. This gives smooth, speed-based movement with no per-frame position polling.

### Scene-Owned Timers

Waves are scheduled using `self.after()`:

```python
# In on_enter():
self.after(2.0, self._start_next_wave)

# After each wave clears:
wave_delay = WAVE_DEFS[self._current_wave]["delay"]
self.after(wave_delay, self._start_next_wave)

# Inside the wave, each spawn schedules the next:
def _schedule_next_spawn(self) -> None:
    interval = WAVE_DEFS[self._current_wave]["spawn_interval"]
    self.after(interval, self._spawn_enemy)
```

`self.after(delay, callback)` schedules a one-shot timer. The critical feature: **scene-owned timers are automatically cancelled when the scene exits.** If the player presses Escape mid-wave, popping the GameScene cancels all pending spawn timers with no cleanup code needed. No `on_exit` method required for timer management.

### Death Animation with Composable Actions

When an enemy's HP reaches 0:

```python
def _kill_enemy(self, enemy: dict) -> None:
    enemy["fsm"].trigger("die")
    self._gold += enemy["gold_reward"]

    enemy["sprite"].do(
        Sequence(
            FadeOut(0.4),
            Do(lambda e=enemy: self._finish_dying(e)),
            Remove(),
        )
    )
```

`Sequence` executes actions one after another. `FadeOut(0.4)` fades opacity to 0 over 0.4 seconds. `Do(callback)` runs a function. `Remove()` destroys the sprite. This declarative approach replaces nested callback chains.

> **Without EasyGame** -- Timer management in raw pyglet requires tracking IDs and manual cancellation:
>
> ```python
> # Raw pyglet: manual timer management
> class GameScene:
>     def __init__(self):
>         self.timer_ids = []
>
>     def schedule_wave(self, delay):
>         tid = pyglet.clock.schedule_once(self._start_wave, delay)
>         self.timer_ids.append(tid)
>
>     def on_exit(self):
>         # Forget this and timers fire into a dead scene
>         for tid in self.timer_ids:
>             pyglet.clock.unschedule(tid)
>         self.timer_ids.clear()
> ```
>
> EasyGame's `self.after()` handles this automatically. No timer ID tracking, no `on_exit` cleanup.

> **Without EasyGame** -- Death animations require callback chains or coroutines:
>
> ```python
> # Raw pyglet: callback chain for death animation
> def kill_enemy(enemy):
>     enemy.state = "dying"
>     start_fade_out(enemy, duration=0.4, on_complete=lambda: remove_enemy(enemy))
>
> def start_fade_out(enemy, duration, on_complete):
>     enemy.fade_timer = 0
>     enemy.fade_duration = duration
>     enemy.fade_callback = on_complete
>     # Must be called every frame in update():
>     # enemy.opacity = 255 * (1 - enemy.fade_timer / enemy.fade_duration)
>     # if enemy.fade_timer >= enemy.fade_duration: enemy.fade_callback()
> ```
>
> EasyGame's composable actions (`Sequence`, `FadeOut`, `Do`, `Remove`) let you describe the sequence declaratively. The framework handles the per-frame interpolation.

---

## Chapter 5: Combat

**File:** `ch5_combat.py` | **New subsystems:** ParticleEmitter, `draw_world_rect()`

Towers now target enemies and fire projectiles. When projectiles arrive, they deal damage, spawn particle explosions, and remove themselves.

### Tower Targeting

Each frame, towers scan for the closest walking enemy in range:

```python
def _update_towers(self, dt: float) -> None:
    for (col, row), tower in self._placed_towers.items():
        tower["cooldown"] -= dt
        if tower["cooldown"] > 0:
            continue

        tdef = tower["def"]
        tx, ty = self._tower_center(col, row)

        best_enemy = None
        best_dist = float("inf")
        for enemy in self._enemies:
            if enemy["fsm"].state != "walking":
                continue
            esp = enemy["sprite"]
            ex, ey = esp._x, esp._y
            dist = math.sqrt((tx - ex)**2 + (ty - ey)**2)
            if dist <= tdef["range_px"] and dist < best_dist:
                best_dist = dist
                best_enemy = enemy

        if best_enemy is not None:
            self._fire_projectile(tower, col, row, best_enemy)
            tower["cooldown"] = 1.0 / tdef["fire_rate"]
```

This runs in the scene's `update(dt)` method. Note how the FSM check (`enemy["fsm"].state != "walking"`) cleanly excludes dying and dead enemies from targeting.

### Projectiles and Particles

Projectiles are sprites that fly from tower to target:

```python
def _fire_projectile(self, tower, col, row, target_enemy) -> None:
    tdef = tower["def"]
    tx, ty = self._tower_center(col, row)
    target_pos = (target_enemy["sprite"]._x, target_enemy["sprite"]._y)

    proj_sprite = self.add_sprite(
        Sprite(tdef["projectile"], position=(tx, ty),
               anchor=SpriteAnchor.CENTER, layer=RenderLayer.EFFECTS)
    )
    proj_sprite.move_to(
        target_pos, speed=300.0,
        on_arrive=lambda p=proj: self._projectile_arrived(p),
    )
```

On arrival, the projectile deals damage and spawns particles:

```python
def _projectile_arrived(self, proj: dict) -> None:
    impact_x, impact_y = proj["target_pos"]

    if proj["splash_radius"] > 0:
        self._apply_splash_damage(impact_x, impact_y, proj["splash_radius"], proj["damage"])
    else:
        self._deal_damage(proj["target_enemy"], proj["damage"])

    # Particle burst at impact point
    ParticleEmitter(
        "explosion",
        position=(impact_x, impact_y),
        count=8,
        speed=(30, 80),
        lifetime=(0.15, 0.35),
        fade_out=True,
    ).burst()

    proj["sprite"].remove()
```

`ParticleEmitter` creates a burst of small sprites (using the `"explosion"` image) that fly outward and fade. The framework handles their lifecycle -- no particle tracking or cleanup needed in your code.

### Health Bars with `draw_world_rect()`

Health bars are drawn each frame in the scene's `draw()` method:

```python
def draw(self) -> None:
    for enemy in self._enemies:
        if enemy["fsm"].state != "walking" or enemy["hp"] >= enemy["max_hp"]:
            continue

        esp = enemy["sprite"]
        bar_x = esp._x - HEALTH_BAR_WIDTH / 2
        bar_y = esp._y + HEALTH_BAR_Y_OFFSET

        # Background bar (dark red)
        self.draw_world_rect(bar_x, bar_y, HEALTH_BAR_WIDTH, HEALTH_BAR_HEIGHT,
                             (80, 20, 20, 200))

        # Foreground bar (green, proportional to HP)
        hp_ratio = max(0.0, enemy["hp"] / enemy["max_hp"])
        fill_width = max(1, int(HEALTH_BAR_WIDTH * hp_ratio))
        self.draw_world_rect(bar_x, bar_y, fill_width, HEALTH_BAR_HEIGHT,
                             (40, 200, 40, 220))
```

`draw_world_rect()` takes **world-space** coordinates and automatically applies the camera transform. The health bar follows the enemy as the camera scrolls. No manual `camera.world_to_screen()` calls needed.

> **Without EasyGame** -- Drawing world-space UI elements in raw pyglet requires manual camera transforms:
>
> ```python
> # Raw pyglet: manual camera transform for health bars
> def draw_health_bar(enemy, camera):
>     # Manual world-to-screen conversion
>     screen_x = int(enemy.world_x - camera.x)
>     screen_y = int(enemy.world_y - camera.y)
>     bar_x = screen_x - BAR_WIDTH // 2
>     bar_y = screen_y - 14
>
>     # Raw OpenGL or shape drawing
>     pyglet.shapes.Rectangle(bar_x, bar_y, BAR_WIDTH, BAR_HEIGHT,
>                             color=(80, 20, 20)).draw()
>     fill_w = int(BAR_WIDTH * enemy.hp / enemy.max_hp)
>     pyglet.shapes.Rectangle(bar_x, bar_y, fill_w, BAR_HEIGHT,
>                             color=(40, 200, 40)).draw()
> ```
>
> Every world-space overlay needs the same boilerplate. EasyGame's `draw_world_rect()` encapsulates the camera transform.

---

## Chapter 6: Complete Game

**File:** `ch6_game_loop.py` | **New subsystems:** AudioManager (`play_sound`, `play_music`, `optional=True`), ChoiceScreen, MessageScreen

The final chapter adds audio, win/lose conditions, a score system, 5 waves with a Tank enemy type, a 2x speed toggle, and polished game-over flow.

### Audio with `optional=True`

Sound effects and music are played through the `AudioManager`:

```python
def _play_sfx(game: Game, name: str) -> None:
    game.audio.play_sound(name, optional=True)

def _play_music(game: Game, name: str) -> None:
    game.audio.play_music(name, optional=True)
```

The `optional=True` parameter silently skips missing audio files instead of raising an error. This is essential for tutorials and prototyping -- you can add audio incrementally without breaking the game. Sound effects fire on tower shots (`sfx_shoot`), impacts (`sfx_hit`), enemy deaths (`sfx_death`), wave starts (`sfx_wave`), and life loss (`sfx_lose_life`).

### Win/Lose Conditions

**Lose:** When lives reach 0, we push a `ChoiceScreen` overlay:

```python
def _trigger_game_over(self) -> None:
    self._game_over = True
    _stop_music(self.game)

    self.game.push(ChoiceScreen(
        f"Game Over!  Score: {self._score}",
        ["Retry", "Quit to Title"],
        on_choice=self._on_game_over_choice,
    ))
```

`ChoiceScreen` is a built-in overlay scene that displays a message and buttons. It pushes itself onto the scene stack -- the game scene stays underneath, frozen by `self._game_over = True`.

The choice callback schedules the follow-up action:

```python
def _on_game_over_choice(self, index: int) -> None:
    if index == 0:  # Retry
        self.game.after(0, lambda: self.game.replace(GameScene()))
    else:           # Quit to Title
        self.game.after(0, lambda: self.game.pop())
```

Note: we use `self.game.after(0, ...)` here, **not** `self.after()`. The callback fires before `ChoiceScreen` pops itself. `self.after()` would auto-cancel the timer when the scene exits. `game.after()` survives scene transitions -- it's the right tool when you need a callback to fire after the current scene is gone.

**Win:** When all waves are cleared and no enemies remain:

```python
def _check_victory(self) -> None:
    if self._game_over or self._game_won:
        return
    alive = [e for e in self._enemies if e["fsm"].state in ("walking", "dying")]
    if alive:
        return
    self._game_won = True
    _stop_music(self.game)
    self.game.push(MessageScreen(
        f"Victory!  Score: {self._score}",
        on_dismiss=lambda: self.game.pop(),
    ))
```

`MessageScreen` is a simpler overlay -- one message, one "OK" button.

### Speed Toggle

A single key press toggles 2x game speed:

```python
if event.type == "key_press" and getattr(event, "key", None) == "space":
    if self._speed_multiplier == 1.0:
        self._speed_multiplier = 2.0
        self._speed_label.text = "[2\u00d7 SPEED]"
    else:
        self._speed_multiplier = 1.0
        self._speed_label.text = ""
```

The multiplier is applied in `update()`:

```python
def update(self, dt: float) -> None:
    effective_dt = dt * self._speed_multiplier
    self._update_towers(effective_dt)
```

This speeds up tower cooldowns. Enemy movement speeds are already baked into `sprite.move_to()`, so they move at their natural speed -- the tower fire rate is what changes. This is a design choice that's easy to customize.

> **Without EasyGame** -- Audio in raw pyglet requires manual volume management and error handling:
>
> ```python
> # Raw pyglet: manual audio management
> try:
>     shoot_sound = pyglet.media.load("assets/sounds/sfx_shoot.wav", streaming=False)
> except Exception:
>     shoot_sound = None
>
> def play_sfx(sound):
>     if sound is not None:
>         try:
>             sound.play()
>         except Exception:
>             pass  # swallow errors for missing audio
>
> # No channel system -- can't independently control SFX vs music volume
> # No crossfade -- music transitions are jarring
> # No sound pools -- playing the same sound 10x loads it 10x
> ```
>
> EasyGame's `AudioManager` provides channels (sfx, music, ambient), volume control per channel, sound pools, crossfade, and `optional=True` for graceful degradation.

---

## EasyGame Subsystems Used

Here's every subsystem exercised across the six chapters:

| Subsystem | Chapter | Purpose |
|-----------|---------|---------|
| **Game** | 1 | Window, main loop, scene stack |
| **Scene** | 1 | Lifecycle hooks, scene stack navigation |
| **Theme** | 1 | Global UI styling |
| **Panel, Label, Button** | 1 | Declarative UI with auto-layout |
| **Style, Anchor, Layout** | 1 | Per-component overrides, positioning |
| **InputEvent** | 1 | Unified keyboard + mouse input |
| **Camera** | 2 | Scrollable viewport with bounds clamping |
| **Sprite** | 2 | GPU-accelerated image rendering |
| **SpriteAnchor** | 2 | TOP_LEFT for tiles, CENTER for units |
| **RenderLayer** | 2 | BACKGROUND, OBJECTS, EFFECTS draw order |
| **Scene.add_sprite** | 2 | Automatic sprite lifecycle management |
| **StateMachine** | 4 | Enemy state tracking with validated transitions |
| **Scene.after** | 4 | Scene-owned timers with auto-cancel |
| **Sprite.move_to** | 4 | Speed-based movement with arrival callbacks |
| **Sequence, FadeOut, Do, Remove** | 4 | Composable death animations |
| **ParticleEmitter** | 5 | Impact burst effects |
| **draw_world_rect** | 5 | Camera-aware health bar rendering |
| **AudioManager** | 6 | SFX and music with `optional=True` |
| **ChoiceScreen, MessageScreen** | 6 | Built-in dialog overlays |

---

## What's Next

### Extend the Game

The tutorial game is a solid foundation. Here are ideas for extending it:

- **Tower upgrades** -- add a right-click menu on placed towers with damage/range/speed upgrades
- **Selling towers** -- refund a portion of the cost
- **More enemy types** -- flying enemies that skip the path, boss enemies with special abilities
- **Tower animations** -- use `Sprite.do(PlayAnim("fire"))` to animate the barrel
- **Save/Load** -- use `Scene.get_save_state()` / `load_save_state()` to persist between sessions
- **Fog of war** -- only reveal the map within tower range (game code, not framework)

### Explore Other Subsystems

EasyGame has subsystems not used in this tutorial:

- **HUD** -- a persistent overlay that draws between the base scene and modal overlays
- **DragManager** -- built-in drag-and-drop with snap targets
- **CursorManager** -- custom cursor images per scene
- **ColorSwap** -- palette swaps for sprite recoloring (team colors, damage flash)
- **SaveManager** -- JSON-based save/load with slot management
- **tween / Ease** -- property interpolation with easing curves

### The Complete Example

The `examples/tower_defense/` directory contains the entire game consolidated into a single `main.py` file. It's the same game as Chapter 6, cleaned up and documented as a standalone example:

```bash
python examples/tower_defense/main.py
```

### API Reference

For detailed API documentation on every class and method used in this tutorial:

- `easygame.Game` -- window, main loop, scene stack management
- `easygame.Scene` -- lifecycle hooks, `add_sprite()`, `after()`, `every()`, `draw_rect()`, `draw_world_rect()`
- `easygame.Sprite` -- position, opacity, `move_to()`, `do()`, `remove()`
- `easygame.Camera` -- viewport, scrolling, `world_to_screen()`, `enable_key_scroll()`
- `easygame.StateMachine` -- states, transitions, `trigger()`
- `easygame.ParticleEmitter` -- `burst()`, lifetime, speed, fade
- `easygame.AudioManager` -- `play_sound()`, `play_music()`, `stop_music()`, channels
- `easygame.ui` -- `Panel`, `Label`, `Button`, `Layout`, `Anchor`, `Style`, `Theme`
- `easygame.actions` -- `Sequence`, `Parallel`, `Delay`, `Do`, `FadeIn`, `FadeOut`, `MoveTo`, `PlayAnim`, `Remove`, `Repeat`
