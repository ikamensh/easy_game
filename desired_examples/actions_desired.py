"""
Multi-step game sequence: Heroes 2-style battle attack turn.
Attacker walks forward, attacks, defender reacts, attacker walks back.
This is what we want it to look like with EasyGame's composable Actions.
"""
from easygame import Sprite, RenderLayer, ParticleEmitter
from easygame.actions import (
    Sequence, Parallel, Delay, Do, PlayAnim, MoveTo, FadeOut, FadeIn, Remove, Repeat,
)


def execute_attack_turn(attacker, defender, damage, on_complete):
    """Full battle attack sequence — flat, readable, reorderable."""

    target_pos = (defender.position[0] - 60, defender.position[1])
    original_pos = attacker.position

    attacker.do(Sequence(
        # Walk to defender
        Parallel(PlayAnim(walk), MoveTo(target_pos, speed=200)),

        # Attack
        PlayAnim(attack),
        Delay(0.3),

        # Defender reacts (runs on the defender sprite, in parallel with us waiting)
        Do(lambda: defender.do(PlayAnim(hit))),
        Do(lambda: show_floating_damage(defender.position, damage)),
        Delay(0.5),

        # Walk back
        Parallel(PlayAnim(walk), MoveTo(original_pos, speed=200)),

        # Done
        PlayAnim(idle),
        Do(on_complete),
    ))


# 20 lines. Same sequence. Flat, no nesting, no state machine.
#
# Want to add a screen shake on hit? Insert one line:
#   Do(lambda: game.camera.shake(intensity=5, duration=0.2, decay=1.0)),
#
# Want the defender to also play a death animation if killed?
#   Do(lambda: defender.do(Sequence(PlayAnim(death), FadeOut(0.5), Remove())) if hp <= 0 else None),
#
# Want to skip the walk-back for a ranged attack?
#   Just delete those two lines.
#
# === More examples ===

# Spell effect: fireball travels, explodes on impact
def cast_fireball(caster, target_pos):
    fireball = Sprite("sprites/fireball", position=caster.position, layer=RenderLayer.EFFECTS)
    fireball.do(Sequence(
        MoveTo(target_pos, speed=400),
        Do(lambda: ParticleEmitter("sprites/flame", position=target_pos, count=30).burst()),
        Do(lambda: game.audio.play_sound("explosion")),
        Do(lambda: game.camera.shake(intensity=8, duration=0.3, decay=1.0)),
        FadeOut(0.2),
        Remove(),
    ))


# Cutscene: camera pans, characters talk, fade to black.
# Uses timer chaining — no game.do() needed.
def intro_cutscene():
    game.after(0, lambda: game.camera.pan_to(1000, 500, duration=2.0)).then(
        lambda: game.push(DialogScene("Elder", "The prophecy has begun...")), 1.0
    ).then(
        lambda: game.camera.pan_to(2000, 800, duration=2.0), 0.5
    ).then(
        lambda: game.push(DialogScene("Knight", "I am ready.")), 1.0
    ).then(
        lambda: game.replace(GameWorldScene()), 0.0
    )


# Looping ambient animation: torch flickers
torch = Sprite("sprites/torch", position=(300, 200))
torch.do(Repeat(Sequence(
    FadeOut(0.3),
    FadeIn(0.3),
    Delay(0.1),
)))
