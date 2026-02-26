"""EasyGame — a Python framework for 2D sprite-based games.

Public API re-exports.  Game code imports from here::

    from easygame import Game, Scene, RenderLayer, SpriteAnchor, AssetManager
    from easygame import Panel, Label, Button, Anchor, Layout, Style, Theme

Internal modules (backends, rendering internals) are **not** re-exported.
"""

from easygame.actions import (
    Action,
    Delay,
    Do,
    FadeIn,
    FadeOut,
    MoveTo,
    Parallel,
    PlayAnim,
    Remove,
    Repeat,
    Sequence,
)
from easygame.animation import AnimationDef
from easygame.assets import AssetManager, AssetNotFoundError
from easygame.audio import AudioManager
from easygame.backends.base import (
    Event,
    KeyEvent,
    MouseEvent,
    WindowEvent,
)
from easygame.cursor import CursorManager
from easygame.game import Game
from easygame.input import InputEvent, InputManager
from easygame.rendering import Camera, ColorSwap, get_palette, register_palette
from easygame.rendering.layers import RenderLayer, SpriteAnchor
from easygame.rendering.particles import ParticleEmitter
from easygame.rendering.sprite import Sprite
from easygame.save import SaveError, SaveManager
from easygame.scene import Scene
from easygame.ui import (
    HUD,
    Anchor,
    Button,
    ChoiceScreen,
    Component,
    ConfirmDialog,
    DataTable,
    DragManager,
    Grid,
    ImageBox,
    Label,
    Layout,
    List,
    MessageScreen,
    Panel,
    ProgressBar,
    SaveLoadScreen,
    Style,
    TabGroup,
    TextBox,
    Theme,
    Tooltip,
)
from easygame.util.fsm import StateMachine
from easygame.util.timer import TimerHandle
from easygame.util.tween import Ease, tween

__all__ = [
    "Action",
    "Anchor",
    "AnimationDef",
    "AssetManager",
    "AssetNotFoundError",
    "AudioManager",
    "Button",
    "Camera",
    "ChoiceScreen",
    "ColorSwap",
    "Component",
    "ConfirmDialog",
    "CursorManager",
    "DataTable",
    "Delay",
    "Do",
    "DragManager",
    "Ease",
    "Event",
    "FadeIn",
    "FadeOut",
    "Game",
    "get_palette",
    "Grid",
    "HUD",
    "ImageBox",
    "InputManager",
    "InputEvent",
    "KeyEvent",
    "Label",
    "Layout",
    "List",
    "MessageScreen",
    "MouseEvent",
    "MoveTo",
    "Panel",
    "Parallel",
    "ParticleEmitter",
    "PlayAnim",
    "ProgressBar",
    "register_palette",
    "Remove",
    "RenderLayer",
    "Repeat",
    "SaveError",
    "SaveLoadScreen",
    "SaveManager",
    "Scene",
    "Sequence",
    "StateMachine",
    "Sprite",
    "SpriteAnchor",
    "Style",
    "TabGroup",
    "TextBox",
    "TimerHandle",
    "Theme",
    "Tooltip",
    "WindowEvent",
    "tween",
]
