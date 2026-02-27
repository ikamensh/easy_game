"""
Scene management: title screen → game world → inventory overlay → back.
This is what we want it to look like with EasyGame.
"""
from easygame import Game, Scene, Sprite
from easygame.ui import Panel, Label, Button, List, Anchor, Layout, Style


class TitleScreen(Scene):
    show_hud = False

    def on_enter(self):
        panel = Panel(anchor=Anchor.CENTER, layout=Layout.VERTICAL, spacing=16)
        panel.add(Label("My Game", style=Style(font_size=48)))
        panel.add(Button("Start", on_click=lambda: self.game.replace(GameWorld())))
        panel.add(Button("Quit", on_click=self.game.quit))
        self.ui.add(panel)


class Item:
    def __init__(self, name):
        self.name = name
    def use(self):
        pass


class GameWorld(Scene):
    transparent = False

    def on_enter(self):
        self.inventory = [Item("Potion"), Item("Key")]
        self.player = Sprite("sprites/player", position=(400, 300))
        # HUD hint
        self.ui.add(Label("I=Inventory  ESC=Menu", anchor=Anchor.TOP_LEFT, margin=10))

    def handle_input(self, event):
        if event.action == "menu":
            self.game.push(PauseMenu())  # push overlay — game world stays underneath
            return True
        if event.key == "i":
            self.game.push(InventoryScreen(self.inventory))
            return True


class PauseMenu(Scene):
    transparent = True    # draw scene below (game world visible underneath)
    pause_below = True    # game world stops updating

    def on_enter(self):
        # Semi-transparent overlay + centered menu — that's it
        self.ui.add(Panel(
            anchor=Anchor.CENTER, layout=Layout.VERTICAL, spacing=16,
            style=Style(background_color=(0, 0, 0, 128)),
            children=[
                Label("PAUSED", style=Style(font_size=48)),
                Button("Resume", on_click=lambda: self.game.pop()),
                Button("Quit to Title", on_click=lambda: self.game.clear_and_push(TitleScreen())),
            ],
        ))

    def handle_input(self, event):
        if event.action == "menu":
            self.game.pop()  # ESC resumes
            return True


class InventoryScreen(Scene):
    transparent = True
    pause_below = True

    def __init__(self, inventory):
        self.inventory = inventory

    def on_enter(self):
        panel = Panel(anchor=Anchor.CENTER, width=500, height=500, layout=Layout.VERTICAL)
        panel.add(Label("Inventory"))
        panel.add(List(
            items=[item.name for item in self.inventory],
            on_select=self.select_item,
        ))
        self.ui.add(panel)

    def select_item(self, index):
        self.inventory[index].use()

    def handle_input(self, event):
        if event.action == "cancel" or event.key == "i":
            self.game.pop()
            return True


game = Game("My Game")
game.run(TitleScreen())

# ~60 lines for 4 screens with proper scene lifecycle.
#
# What's handled:
# - Scene stack with push/pop/replace/clear_and_push
# - on_enter/on_exit/on_reveal lifecycle hooks
# - transparent=True draws the scene below automatically
# - pause_below=True stops updating the scene below
# - ESC binding to "menu" action is default
# - No manual overlay rendering
# - No global state — each scene owns its state
# - No main loop dispatcher
