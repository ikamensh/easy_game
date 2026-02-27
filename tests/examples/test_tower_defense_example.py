"""Headless verification of examples/tower_defense (complete TD game).

Uses the mock backend since pyglet requires a display. Verifies:
- TitleScene and GameScene load without error
- Play button transitions to GameScene
- HUD renders (Score, Wave, Lives, Gold)
- Tower placement and combat work
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from easygame import Game, Theme

_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_example_asset_dir = _project_root / "examples" / "tower_defense" / "assets"


@pytest.fixture
def example_td_game() -> Game:
    """Game with mock backend and example TD assets."""
    # Ensure assets exist (main.py generates on first run)
    if not _example_asset_dir.exists() or not (_example_asset_dir / "images").exists():
        from examples.tower_defense.generate_assets import generate
        generate(_example_asset_dir)

    game = Game(
        "TD Example Test",
        resolution=(960, 540),
        fullscreen=False,
        backend="mock",
        asset_path=_example_asset_dir,
    )
    game.theme = Theme(
        font="serif",
        font_size=24,
        text_color=(220, 220, 230, 255),
        panel_background_color=(30, 35, 50, 220),
        panel_padding=16,
        button_background_color=(50, 55, 80, 255),
        button_hover_color=(70, 80, 120, 255),
        button_press_color=(35, 40, 60, 255),
        button_text_color=(220, 220, 230, 255),
        button_padding=14,
        button_font_size=26,
        button_min_width=220,
    )
    return game


def test_example_title_screen_loads(example_td_game: Game) -> None:
    """Example: TitleScene builds UI and renders."""
    from examples.tower_defense.main import TitleScene

    example_td_game.push(TitleScene())

    for _ in range(5):
        example_td_game.tick(dt=0.016)

    texts = [t["text"] for t in example_td_game.backend.texts]
    assert "Tower Defense" in texts
    assert "Play" in texts or any("Play" in t for t in texts)
    assert "Quit" in texts or any("Quit" in t for t in texts)


def test_example_play_transitions_to_game(example_td_game: Game) -> None:
    """Example: Clicking Play pushes GameScene."""
    from examples.tower_defense.main import TitleScene

    example_td_game.push(TitleScene())
    example_td_game.tick(dt=0.016)
    example_td_game.backend.inject_click(480, 300)
    example_td_game.tick(dt=0.016)

    stack = example_td_game._scene_stack._stack
    assert len(stack) >= 1
    assert stack[-1].__class__.__name__ == "GameScene"


def test_example_game_scene_hud(example_td_game: Game) -> None:
    """Example: GameScene shows HUD (Score, Wave, Lives, Gold)."""
    from examples.tower_defense.main import GameScene

    example_td_game.push(GameScene())

    for _ in range(5):
        example_td_game.tick(dt=0.016)

    texts = [t["text"] for t in example_td_game.backend.texts]
    assert any("Score" in t for t in texts)
    assert any("Wave" in t for t in texts)
    assert any("Lives" in t for t in texts)
    assert any("Gold" in t for t in texts)


def test_example_tower_placement_and_combat(example_td_game: Game) -> None:
    """Example: Placing towers and running combat increases score."""
    from examples.tower_defense.main import GameScene, TOWER_DEFS, TILE_SIZE

    example_td_game.push(GameScene())
    example_td_game.tick(dt=0.016)

    gs = example_td_game._scene_stack._stack[-1]
    assert gs._score == 0

    gs._placing_tower_def = TOWER_DEFS[0]
    gs._try_place_tower(4 * TILE_SIZE + 16, 4 * TILE_SIZE + 16)
    gs._placing_tower_def = TOWER_DEFS[1]
    gs._try_place_tower(8 * TILE_SIZE + 16, 2 * TILE_SIZE + 16)

    for _ in range(800):
        example_td_game.tick(dt=0.016)

    assert gs._score > 0
