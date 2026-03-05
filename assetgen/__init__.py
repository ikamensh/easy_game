"""
assetgen - Procedural asset generation toolkit for Saga2D.

Provides Pillow-based drawing primitives and 3D wireframe math
used by sprite generators to create placeholder and final art assets.

Submodules:
    primitives  - Filled/outlined polygons, gradients, hatching, ellipses,
                  effects, colour utilities, and supersampling.
    wireframe   - 3D shapes, rotation, projection, edge rendering.
"""

from assetgen.primitives import (
    # colour utilities
    lighten,
    darken,
    adjust_alpha,
    # supersampling
    supersample,
    supersample_draw,
    # polygons
    filled_polygon,
    outlined_polygon,
    # gradients
    vertical_gradient,
    horizontal_gradient,
    linear_gradient,
    radial_gradient,
    # hatching
    crosshatch,
    # ellipses
    filled_ellipse,
    outlined_ellipse,
    # effects
    apply_blur,
    apply_drop_shadow,
    apply_glow,
    # texture
    apply_noise,
    # high-level shape factories
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
    # colour utilities
    "lighten",
    "darken",
    "adjust_alpha",
    # supersampling
    "supersample",
    "supersample_draw",
    # primitives — polygons
    "filled_polygon",
    "outlined_polygon",
    # primitives — gradients
    "vertical_gradient",
    "horizontal_gradient",
    "linear_gradient",
    "radial_gradient",
    # primitives — hatching
    "crosshatch",
    # primitives — ellipses
    "filled_ellipse",
    "outlined_ellipse",
    # effects
    "apply_blur",
    "apply_drop_shadow",
    "apply_glow",
    # texture
    "apply_noise",
    # high-level shape factories
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
