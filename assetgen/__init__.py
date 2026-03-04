"""
assetgen - Procedural asset generation toolkit for Saga2D.

Provides Pillow-based drawing primitives and 3D wireframe math
used by sprite generators to create placeholder and final art assets.

Submodules:
    primitives  - Filled/outlined polygons, gradients, hatching, ellipses.
    wireframe   - 3D shapes, rotation, projection, edge rendering.
"""

from assetgen.primitives import (
    filled_polygon,
    outlined_polygon,
    vertical_gradient,
    horizontal_gradient,
    crosshatch,
    filled_ellipse,
    outlined_ellipse,
    solid_rect,
    labeled_rect,
    triangle,
    circle,
    ring,
)

from assetgen.wireframe import (
    tetrahedron,
    octahedron,
    cube,
    rotate_x,
    rotate_y,
    rotate_z,
    project_perspective,
    project_orthographic,
    render_wireframe,
)

__all__ = [
    # primitives
    "filled_polygon",
    "outlined_polygon",
    "vertical_gradient",
    "horizontal_gradient",
    "crosshatch",
    "filled_ellipse",
    "outlined_ellipse",
    "solid_rect",
    "labeled_rect",
    "triangle",
    "circle",
    "ring",
    # wireframe
    "tetrahedron",
    "octahedron",
    "cube",
    "rotate_x",
    "rotate_y",
    "rotate_z",
    "project_perspective",
    "project_orthographic",
    "render_wireframe",
]
