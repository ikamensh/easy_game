"""
Audio: background music with crossfade, sound effects with channels, sound pools.
This is what we want it to look like with Saga2D.
"""
from saga2d import Game

game = Game("Audio Demo")

# --- Music ---
game.audio.play_music("exploration")                    # loops by default
game.audio.crossfade_music("battle_theme", duration=1.0)  # non-blocking crossfade

# --- Sound effects ---
game.audio.play_sound("sword_hit")     # plays on sfx channel
game.audio.play_sound("ui_click")      # plays on ui channel (auto-detected by asset path? or explicit)

# --- Volume hierarchy ---
# master: 1.0, music: 0.5, sfx: 0.8, ui: 0.6
# Effective music volume = 1.0 * 0.5 = 0.5
game.audio.set_volume(channel="master", level=1.0)
game.audio.set_volume(channel="music", level=0.5)
game.audio.set_volume(channel="sfx", level=0.8)
game.audio.set_volume(channel="ui", level=0.6)

# Changes apply to currently playing sounds immediately.
# Settings screen uses these same calls — no wiring needed.

# --- Sound pools ---
game.audio.register_pool("knight_ack", ["knight_ack_01", "knight_ack_02", "knight_ack_03"])
game.audio.play_pool("knight_ack")  # random from pool, no immediate repeat

# That's it. ~15 lines for everything.
#
# What's handled:
# - Non-blocking crossfade (two audio players with tweened volumes)
# - Channel system with volume hierarchy (master * channel)
# - Volume changes apply retroactively to playing sounds
# - Sound pools with no-repeat logic
# - Asset loading by name (no paths, no try/except)
# - Integration with Settings screen (volume sliders wired automatically)
# - All state management internal (no global variables, no manual tracking)
