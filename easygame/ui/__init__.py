"""UI components, layout, and theming."""

from easygame.ui.component import Component
from easygame.ui.components import Button, Label, Panel
from easygame.ui.drag_drop import DragManager
from easygame.ui.hud import HUD
from easygame.ui.layout import (
    Anchor,
    Layout,
    compute_anchor_position,
    compute_content_size,
    compute_flow_layout,
)
from easygame.ui.screens import (
    ChoiceScreen,
    ConfirmDialog,
    MessageScreen,
    SaveLoadScreen,
)
from easygame.ui.theme import Style, Theme
from easygame.ui.widgets import (
    DataTable,
    Grid,
    ImageBox,
    ListWidget,
    ProgressBar,
    TabGroup,
    TextBox,
    Tooltip,
)

# Backward-compatible alias — avoids shadowing builtins.list in new code.
List = ListWidget

__all__ = [
    "Anchor",
    "Button",
    "ChoiceScreen",
    "Component",
    "ConfirmDialog",
    "compute_anchor_position",
    "compute_content_size",
    "compute_flow_layout",
    "DataTable",
    "DragManager",
    "Grid",
    "HUD",
    "ImageBox",
    "Label",
    "Layout",
    "List",
    "ListWidget",
    "MessageScreen",
    "Panel",
    "ProgressBar",
    "SaveLoadScreen",
    "Style",
    "TabGroup",
    "TextBox",
    "Theme",
    "Tooltip",
]
