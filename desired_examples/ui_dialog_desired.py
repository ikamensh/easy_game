"""
A styled dialog box with a character portrait, text, and choice buttons.
Think: Baldur's Gate dialogue, or Heroes 2 event popup.
This is what we want it to look like with Saga2D.
"""
from saga2d import Game, Scene
from saga2d.ui import Panel, Label, ImageBox, TextBox, Button, Anchor, Layout, Style


class DialogScene(Scene):
    """Push this over the game world — transparent=True keeps the world visible."""
    transparent = True
    pause_below = True

    def __init__(self, speaker, portrait, text, choices, on_choice):
        self.speaker_name = speaker
        self.portrait_img = portrait
        self.dialog_text = text
        self.choices = choices
        self.on_choice = on_choice

    def on_enter(self):
        dialog = Panel(anchor=Anchor.CENTER, width=600, height=300, layout=Layout.HORIZONTAL)

        # Left: portrait
        dialog.add(ImageBox(self.portrait_img, width=96, height=96))

        # Right: text + choices
        right = Panel(layout=Layout.VERTICAL, spacing=8)
        right.add(Label(self.speaker_name, style=Style(font_size=28)))
        right.add(TextBox(self.dialog_text, typewriter_speed=30))  # auto word-wrap, typewriter

        for i, choice in enumerate(self.choices):
            right.add(Button(choice, on_click=lambda idx=i: self._choose(idx)))

        dialog.add(right)
        self.ui.add(dialog)

    def _choose(self, index):
        self.on_choice(index)
        self.game.pop()


# Usage from game code:
# self.game.push(DialogScene(
#     speaker="Elder Sage",
#     portrait="sprites/sage_portrait",
#     text="The ancient prophecy speaks of a hero who will rise from the ashes. "
#          "The three kingdoms have fallen to darkness. Only you can restore the light. "
#          "But first, you must choose your path wisely.",
#     choices=["I will fight for honor.", "Tell me more.", "I'm not interested."],
#     on_choice=self.handle_dialog_choice,
# ))

# ~35 lines for the same dialog. Reusable for any conversation.
#
# What's handled:
# - Word wrapping (TextBox does it)
# - Typewriter text reveal (TextBox property)
# - Layout (horizontal split for portrait + text, vertical for text + choices)
# - Theming (panel background, button styles, font — all from game theme)
# - Keyboard navigation of choices (Button handles focus/selection)
# - Scene overlay with transparency
# - Pop back to game world when choice is made
# - No pixel arithmetic
# - No manual drawing code
