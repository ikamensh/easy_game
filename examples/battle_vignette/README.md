# Battle Vignette Demo

A stress-test of the Saga2D framework's animation, tween, timer, and input systems.

## Generate Assets

From the project root:

```bash
python generate_assets.py
```

## Run

From the project root:

```bash
python examples/battle_vignette/battle_demo.py
```

## Controls

- **Click** friendly (blue) unit to select
- **Click** enemy (red) unit to attack
- **ESC** to quit

## What to Observe

- Full attack sequence: walk → attack → hit → damage number → walk back
- Multiple rounds work
- Dead enemies are removed

## Note

This demo intentionally uses callback-based choreography to surface where it gets awkward, motivating the future Actions system.
