"""Verify UI API pattern from acceptance criteria."""
from saga2d import Panel, Label, Button, Anchor, Layout, Style, Theme, Component
from saga2d.ui import Panel as UIPanel, Label as UILabel, Button as UIButton, Anchor as UIAnchor, Layout as UILayout

# Verify all imports work
assert Panel is not None
assert Label is not None
assert Button is not None
assert Anchor.CENTER is not None
assert Layout.VERTICAL is not None
assert Style is not None
assert Theme is not None
assert Component is not None

# Verify saga2d.ui re-exports match
assert Panel is UIPanel
assert Label is UILabel
assert Button is UIButton
assert Anchor is UIAnchor
assert Layout is UILayout

# Verify Anchor has all 9 values
for name in ['CENTER', 'TOP', 'BOTTOM', 'LEFT', 'RIGHT', 'TOP_LEFT', 'TOP_RIGHT', 'BOTTOM_LEFT', 'BOTTOM_RIGHT']:
    assert hasattr(Anchor, name), f"Anchor missing {name}"

# Verify Layout has 3 values
for name in ['NONE', 'VERTICAL', 'HORIZONTAL']:
    assert hasattr(Layout, name), f"Layout missing {name}"

print("All API checks passed!")
