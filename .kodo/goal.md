# Goal: Make games built with saga2d look beautiful

## The Problem

Saga2d is a feature-complete 2D game framework with 1400+ unit tests and screenshot regression testing. But nobody has ever critically evaluated whether the visual output actually looks good. The AI agents that built it tested code correctness — they never stepped back and asked "would a player enjoy looking at this?"

I rendered the main menu scene (Panel with Label + 3 Buttons, centered at 480x360) and here's what I saw:
- **Title "Main Menu" is CLIPPED** — the top of the text is cut off by the panel boundary. The label doesn't have enough vertical space.
- **Gray on gray on gray** — panel is medium gray (#6a6a7a), buttons are slightly darker gray (#3e3e4b), text is light gray/white. Zero visual hierarchy. It looks like a Windows 3.1 dialog.
- **No visual depth** — everything is flat rectangles. No borders, no shadows, no rounded corners. It's technically functional but visually dead.
- **White background** outside the panel — a real game would never have a plain white bg behind its menu.
- **Buttons are oversized** relative to their text — they stretch to fill the panel width with enormous padding.
- All sprite assets are tiny pixel art blobs (warrior is a 64x64 blue stick figure, skeleton is a red diamond with legs). These are adequate as placeholder programmer art but set a very low quality bar for example games.
- The screenshot test framework auto-generates golden images on first run, so "tests pass" just means "it renders the same as last time" — not "it looks good"

## What Success Looks Like

A new user clones saga2d, runs an example game, and thinks "this looks polished for a 2D framework." Specifically:

1. **The battle vignette example looks like a real game** — characters are readable, the background isn't blank, the selection ring is visible, attack animations feel impactful
2. **The tower defense example looks playable** — grass tiles tile seamlessly, towers look distinct, UI panels have visual depth, the HUD bar is readable
3. **UI widgets have visual polish** — buttons have hover/press feedback that looks good, panels have subtle borders or shadows, progress bars have rounded ends, labels have readable contrast
4. **The default theme is attractive** — good color palette, readable fonts, sufficient padding/spacing

## Mandatory: Visual Verification Protocol

**This is the critical constraint.** Every visual change MUST be verified by actually rendering it and examining the result. The verification process is:

1. Use `tests/screenshot/harness.py` — `render_scene()` to render to a PIL Image
2. Save the image to disk as PNG
3. **Open the PNG file and LOOK at it** — use your vision capabilities to examine the rendered output
4. Ask yourself: "Would a game developer be happy with this?" If no, iterate.
5. Only after visual inspection confirms quality, update the golden screenshot

DO NOT rely on "tests pass" as proof of visual quality. A screenshot test passing only means pixels match the golden — it says nothing about whether the golden itself looks good.

### How to actually look at rendered output

```python
# In any test or script:
from tests.screenshot.harness import render_scene
from saga2d import Game, Scene, Label, Sprite

def setup(game):
    # ... create your scene ...
    pass

image = render_scene(setup, tick_count=2, resolution=(800, 600))
image.save("/tmp/my_test_render.png")
# NOW OPEN /tmp/my_test_render.png AND LOOK AT IT
```

## Scope

### Must do:
- Improve the default `Theme` colors and styling so widgets look polished out of the box
- Fix any tile seam/gap rendering issues in the tile/background system
- Ensure text is readable (right size, good contrast, no overlap)
- Update the battle vignette example to look like a presentable demo (add background, improve sprite scale, ensure UI is readable)
- Update the tower defense example's visual quality (tile seams, HUD readability, tower/enemy visual distinction)
- Render a "visual gallery" showing every UI widget type with the improved theme, save as PNGs, and verify they all look good

### May do:
- Add a simple gradient or pattern to button backgrounds (via the backend's draw capabilities)
- Improve particle effects visibility
- Add subtle visual feedback for interactive elements (hover glow, press darken)

### Must NOT do:
- Don't change the framework's public API
- Don't break existing tests
- Don't add new dependencies (work within pyglet + pillow)
- Don't rewrite the rendering pipeline — improve within the existing architecture
