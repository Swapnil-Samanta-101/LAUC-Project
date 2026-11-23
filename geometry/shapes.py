"""NASA FoilSim-style Analytical Geometry Generators.

Provides closed 2D polygon generators for:
- Flat Plate (slender rectangle with rounded edges)
- Ellipse (elliptical cylinder with thickness ratio)
- Cylinder (circular cylinder)
"""

from typing import Tuple
import numpy as np


def rotate_points(
    x_arr: np.ndarray,
    y_arr: np.ndarray,
    x_pivot: float,
    y_pivot: float,
    alpha_deg: float
) -> Tuple[np.ndarray, np.ndarray]:
    """Rotate 2D coordinates around pivot point (x_pivot, y_pivot) by alpha_deg (positive pitches nose UP)."""
    alpha_rad = np.radians(alpha_deg)
    cos_a = np.cos(alpha_rad)
    sin_a = np.sin(alpha_rad)

    dx = x_arr - x_pivot
    dy = y_arr - y_pivot

    # In aerodynamic convention: positive alpha rotates nose up (+y)
    x_rot = x_pivot + (dx * cos_a + dy * sin_a)
    y_rot = y_pivot + (-dx * sin_a + dy * cos_a)
    return x_rot, y_rot


def generate_flat_plate(
    chord: float = 1.0,
    x_le: float = 1.5,
    y_le: float = 1.5,
    alpha_deg: float = 0.0,
    thickness: float = 0.02,
    n_points: int = 100
) -> np.ndarray:
    """Generate a slender flat plate polygon with rounded leading and trailing edges.

    Args:
        chord: chord length c
        x_le: leading edge x
        y_le: leading edge y
        alpha_deg: angle of attack in degrees
        thickness: plate thickness as fraction of chord
        n_points: number of points in polygon

    Returns:
        (N, 2) closed polygon array
    """
    t_half = 0.5 * thickness * chord
    r_cap = t_half
    x_te = x_le + chord

    # Leading edge semi-circle arc (pi/2 to 3*pi/2)
    n_cap = max(10, n_points // 8)
    theta_le = np.linspace(np.pi / 2.0, 3.0 * np.pi / 2.0, n_cap)
    x_le_cap = (x_le + r_cap) + r_cap * np.cos(theta_le)
    y_le_cap = y_le + r_cap * np.sin(theta_le)

    # Lower straight surface (from LE to TE)
    n_side = max(20, (n_points - 2 * n_cap) // 2)
    x_lower = np.linspace(x_le + r_cap, x_te - r_cap, n_side)
    y_lower = np.full_like(x_lower, y_le - t_half)

    # Trailing edge semi-circle arc (-pi/2 to pi/2)
    theta_te = np.linspace(-np.pi / 2.0, np.pi / 2.0, n_cap)
    x_te_cap = (x_te - r_cap) + r_cap * np.cos(theta_te)
    y_te_cap = y_le + r_cap * np.sin(theta_te)

    # Upper straight surface (from TE to LE)
    x_upper = np.linspace(x_te - r_cap, x_le + r_cap, n_side)
    y_upper = np.full_like(x_upper, y_le + t_half)

    # Assemble perimeter
    x_raw = np.concatenate([x_le_cap, x_lower, x_te_cap, x_upper])
    y_raw = np.concatenate([y_le_cap, y_lower, y_te_cap, y_upper])

    # Rotate around quarter-chord
    x_qc = x_le + 0.25 * chord
    y_qc = y_le
    x_rot, y_rot = rotate_points(x_raw, y_raw, x_qc, y_qc, alpha_deg)

    return np.column_stack((x_rot, y_rot))


def generate_ellipse(
    chord: float = 1.0,
    x_le: float = 1.5,
    y_le: float = 1.5,
    alpha_deg: float = 0.0,
    thickness_ratio: float = 0.15,
    n_points: int = 120
) -> np.ndarray:
    """Generate an elliptical cylinder polygon.

    Args:
        chord: major axis length 2*a = chord
        x_le: leading edge x
        y_le: leading edge y
        alpha_deg: angle of attack in degrees
        thickness_ratio: minor axis / major axis (thickness b / a)
        n_points: number of perimeter vertices

    Returns:
        (N, 2) closed polygon array
    """
    a = 0.5 * chord
    b = 0.5 * chord * thickness_ratio
    cx = x_le + a
    cy = y_le

    theta = np.linspace(0.0, 2.0 * np.pi, n_points, endpoint=False)
    x_raw = cx + a * np.cos(theta)
    y_raw = cy + b * np.sin(theta)

    # Rotate around quarter-chord
    x_qc = x_le + 0.25 * chord
    y_qc = y_le
    x_rot, y_rot = rotate_points(x_raw, y_raw, x_qc, y_qc, alpha_deg)

    return np.column_stack((x_rot, y_rot))


def generate_cylinder(
    radius: float = 0.3,
    center_x: float = 2.0,
    center_y: float = 1.5,
    n_points: int = 64
) -> np.ndarray:
    """Generate a circular cylinder polygon.

    Args:
        radius: cylinder radius R
        center_x: cylinder center x
        center_y: cylinder center y
        n_points: number of perimeter points

    Returns:
        (N, 2) closed polygon array
    """
    theta = np.linspace(0.0, 2.0 * np.pi, n_points, endpoint=False)
    x = center_x + radius * np.cos(theta)
    y = center_y + radius * np.sin(theta)
    return np.column_stack((x, y))
