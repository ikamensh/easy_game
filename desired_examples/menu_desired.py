"""
Main menu with 4 buttons, background image, custom font, hover effects.
This is what we want it to look like with Saga2D.
"""
from saga2d import Game, Scene
from saga2d.ui import Panel, Label, Button, Anchor, Layout, Style, Theme


class SaveLoadScreen(Scene):
    """Placeholder for save/load screen."""

    def on_enter(self):
        panel = Panel(anchor=Anchor.CENTER, layout=Layout.VERTICAL, spacing=20)
        panel.add(Label("Save / Load", style=Style(font_size=48)))
        panel.add(Button("Back", on_click=lambda: self.game.pop()))
        self.ui.add(panel)


class SettingsScene(Scene):
    """Placeholder for settings screen."""

    def on_enter(self):
        panel = Panel(anchor=Anchor.CENTER, layout=Layout.VERTICAL, spacing=20)
        panel.add(Label("Settings", style=Style(font_size=48)))
        panel.add(Button("Back", on_click=lambda: self.game.pop()))
        self.ui.add(panel)


class WorldMapScene(Scene):
    """Placeholder for world map."""

    def on_enter(self):
        panel = Panel(anchor=Anchor.CENTER, layout=Layout.VERTICAL, spacing=20)
        panel.add(Label("World Map", style=Style(font_size=48)))
        panel.add(Button("Back to Menu", on_click=lambda: self.game.clear_and_push(MainMenu())))
        self.ui.add(panel)


class MainMenu(Scene):
    show_hud = False

    def on_enter(self):
        panel = Panel(anchor=Anchor.CENTER, layout=Layout.VERTICAL, spacing=20)
        panel.add(Label("Chronicles of the Realm", style=Style(font_size=64)))
        panel.add(Button("New Game", on_click=self.new_game))
        panel.add(Button("Load Game", on_click=lambda: self.game.push(SaveLoadScreen())))
        panel.add(Button("Settings", on_click=lambda: self.game.push(SettingsScene())))
        panel.add(Button("Quit", on_click=self.game.quit))
        self.ui.add(panel)

        # self.game.audio.play_music("menu_theme")  # requires assets/music/menu_theme.*

    def new_game(self):
        self.game.replace(WorldMapScene())


game = Game("Chronicles of the Realm", resolution=(800, 600), fullscreen=False)
game.theme = Theme(font="serif")
game.run(MainMenu())

# Lines of code: ~25
# What's handled automatically:
# - Fullscreen with proper scaling and retina support
# - Font loading, caching, fallback
# - Button hover/press visual states from theme
# - Hover sound (theme default)
# - Centered layout math
# - Scene stack (push settings, push save/load, replace with game)
# - Music playback with looping
# - ESC to quit (default binding)
# - Window close handling
# - Game loop, frame timing, event dispatch
