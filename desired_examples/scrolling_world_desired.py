"""
Scrolling world: camera follows player, edge scrolling, 50 units with y-sorting.
This is what we want it to look like with Saga2D.
"""
from saga2d import Game, Scene, Sprite, Camera, RenderLayer
import random


class WorldScene(Scene):
    def on_enter(self):
        self.camera = Camera(viewport_size=(1920, 1080), world_bounds=(0, 0, 4096, 4096))
        self.camera.enable_edge_scroll(margin=50, speed=300)

        # Background — in a real game, use a pre-tiled background image.
        # The framework handles camera-relative scrolling.
        self.background = Sprite("backgrounds/grass", layer=RenderLayer.BACKGROUND)

        # Trees
        for _ in range(200):
            Sprite("sprites/tree",
                   position=(random.randint(0, 4096), random.randint(0, 4096)),
                   layer=RenderLayer.OBJECTS)

        # Units
        self.units = []
        for _ in range(50):
            unit = Sprite("sprites/knight",
                          position=(random.randint(100, 3900), random.randint(100, 3900)),
                          layer=RenderLayer.UNITS)
            self.units.append(unit)

        # Player
        self.player = Sprite("sprites/player", position=(2048, 2048),
                             layer=RenderLayer.UNITS)
        self.camera.follow(self.player)

    def handle_input(self, event):
        if event.type == "click":
            world_pos = self.camera.screen_to_world(event.x, event.y)
            self.player.move_to(world_pos, speed=200)
            return True


game = Game("World Demo", resolution=(1920, 1080))
game.run(WorldScene())

# ~35 lines. 200 trees, 50 units, camera, edge scroll, click-to-move.
#
# What's handled:
# - Camera scroll, clamping, coordinate conversion, edge scroll
# - Y-sorting within each layer (trees sort among trees, units among units,
#   and layers render in fixed order: BACKGROUND → OBJECTS → UNITS)
# - Frustum culling (only visible sprites sent to GPU)
# - Sprite batching (one GPU draw call for all sprites via pyglet Batch)
# - Click position → world position conversion
# - Smooth movement via tween system
# - Bottom-center anchoring by default
# - No manual sort call
# - No manual tile grid rendering
