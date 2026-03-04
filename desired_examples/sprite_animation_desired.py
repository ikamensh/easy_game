"""
Animated unit: walks to a target, plays attack animation, then idles.
This is what we want it to look like with Saga2D.
"""
from saga2d import Game, Scene, Sprite, AnimationDef


# Define animations — reusable templates, not tied to any sprite instance
idle = AnimationDef(frames="sprites/knight_idle", frame_duration=0.15, loop=True)
walk = AnimationDef(frames="sprites/knight_walk", frame_duration=0.15, loop=True)
attack = AnimationDef(frames="sprites/knight_attack", frame_duration=0.1, loop=False)
death = AnimationDef(frames="sprites/knight_death", frame_duration=0.2, loop=False)


class BattleScene(Scene):
    def on_enter(self):
        self.knight = Sprite("sprites/knight_idle", position=(100, 400))

        # Walk to target, attack on arrival, then idle
        self.knight.play(walk)
        self.knight.move_to((500, 400), speed=200, on_arrive=self.do_attack)

    def do_attack(self):
        self.knight.play(attack, on_complete=lambda: self.knight.play(idle))


# That's it. 15 lines.
#
# What's handled:
# - Sprite sheet loading and slicing (by naming convention or companion .json)
# - Animation frame timing, looping, completion callbacks
# - Movement with smooth interpolation (tween system)
# - Bottom-center anchoring (default for game sprites)
# - Composing movement + frame animation simultaneously
# - No manual distance/direction math
# - No manual frame timer logic
# - No sprite sheet cutting code
# - Callback chaining just works (play on_complete → next animation)
#
# For a death sequence:
#   self.knight.play(death, on_complete=lambda: self.knight.remove())
#
# For a projectile:
#   arrow = Sprite("sprites/arrow", position=archer.position)
#   arrow.move_to(target.position, speed=500, on_arrive=lambda: [
#       arrow.remove(),
#       target.play(hit_reaction),
#   ])
#
# For complex multi-step sequences, use composable Actions instead of callbacks:
#
#   from saga2d.actions import Sequence, Parallel, PlayAnim, MoveTo, Delay, Do, Remove
#
#   self.knight.do(Sequence(
#       Parallel(PlayAnim(walk), MoveTo((500, 400), speed=200)),
#       PlayAnim(attack),
#       Delay(0.3),
#       Do(lambda: target.do(Sequence(PlayAnim(hit), PlayAnim(death), Remove()))),
#       Parallel(PlayAnim(walk), MoveTo((100, 400), speed=200)),
#       PlayAnim(idle),
#   ))
#
# See actions_desired.py for full examples.
