"""Unified asset generator for Saga2D.

Single entry point that generates all sprite PNGs for both tests and examples.

Run from project root::

    python generate_assets.py

Generates:
    - 12 test sprites   → assets/images/sprites/
    - 20 battle sprites → assets/images/sprites/
                        → examples/battle_vignette/assets/images/sprites/
"""

from __future__ import annotations

from pathlib import Path

from assetgen import test_sprites, battle_sprites

PROJECT_ROOT = Path(__file__).resolve().parent

# Output directories
MAIN_SPRITES = PROJECT_ROOT / "assets" / "images" / "sprites"
BATTLE_VIGNETTE_SPRITES = (
    PROJECT_ROOT / "examples" / "battle_vignette" / "assets" / "images" / "sprites"
)


def main() -> None:
    all_files: list[Path] = []

    # --- Test sprites → assets/images/sprites/ ---
    print("=== Test sprites ===")
    test_files = test_sprites.generate(MAIN_SPRITES)
    all_files.extend(test_files)

    # --- Battle sprites → assets/images/sprites/ ---
    print("\n=== Battle sprites (main) ===")
    battle_files_main = battle_sprites.generate(MAIN_SPRITES)
    all_files.extend(battle_files_main)

    # --- Battle sprites → examples/battle_vignette/assets/images/sprites/ ---
    print("\n=== Battle sprites (battle_vignette example) ===")
    battle_files_example = battle_sprites.generate(BATTLE_VIGNETTE_SPRITES)
    all_files.extend(battle_files_example)

    # --- Summary ---
    print(f"\n{'=' * 50}")
    print(f"Generated {len(all_files)} files total:")
    print(f"  {len(test_files)} test sprites      → {MAIN_SPRITES}")
    print(f"  {len(battle_files_main)} battle sprites    → {MAIN_SPRITES}")
    print(f"  {len(battle_files_example)} battle sprites    → {BATTLE_VIGNETTE_SPRITES}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
