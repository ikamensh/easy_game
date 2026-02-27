from easygame import Game, Scene, Button, Label, Panel, Layout, Anchor

class MenuScene(Scene):
    def on_enter(self) -> None:
        self.ui.add(Panel(
            layout=Layout.VERTICAL,
            spacing=20,
            anchor=Anchor.CENTER,
            children=[
                Label("My Game", font_size=48),
                Button("Play", on_click=lambda: self.game.pop()),
            ],
        ))

game = Game("My Game", resolution=(960, 540))
game.run(MenuScene())

