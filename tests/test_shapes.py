"""Validation Tests for NASA FoilSim Shape Generators."""

import pytest
import numpy as np
from geometry.shapes import generate_flat_plate, generate_ellipse, generate_cylinder
from geometry.naca import NACA4Airfoil


def test_flat_plate_geometry():
    """Verify flat plate creates closed polygon with correct chord and thickness."""
    poly = generate_flat_plate(chord=1.0, x_le=1.5, y_le=1.5, alpha_deg=0.0, thickness=0.02)
    assert poly.ndim == 2
    assert poly.shape[1] == 2
    assert poly.shape[0] >= 30
    x_min, x_max = np.min(poly[:, 0]), np.max(poly[:, 0])
    y_min, y_max = np.min(poly[:, 1]), np.max(poly[:, 1])
    # Chord should span approximately 1.5 to 2.5
    assert abs((x_max - x_min) - 1.0) < 0.05
    # Thickness should be approx 0.02
    assert abs((y_max - y_min) - 0.02) < 0.01


def test_ellipse_geometry():
    """Verify ellipse creates closed polygon with minor/major axis."""
    poly = generate_ellipse(chord=1.0, x_le=1.5, y_le=1.5, alpha_deg=0.0, thickness_ratio=0.20)
    assert poly.ndim == 2
    x_min, x_max = np.min(poly[:, 0]), np.max(poly[:, 0])
    y_min, y_max = np.min(poly[:, 1]), np.max(poly[:, 1])
    assert abs((x_max - x_min) - 1.0) < 0.05
    assert abs((y_max - y_min) - 0.20) < 0.02


def test_cylinder_geometry():
    """Verify cylinder polygon vertices form a circle of radius R."""
    r = 0.3
    cx, cy = 2.0, 1.5
    poly = generate_cylinder(radius=r, center_x=cx, center_y=cy, n_points=64)
    assert poly.shape[0] == 64
    distances = np.sqrt((poly[:, 0] - cx) ** 2 + (poly[:, 1] - cy) ** 2)
    assert np.allclose(distances, r, atol=1e-5)


def test_naca_custom_camber_thickness():
    """Verify NACA generator supports direct camber and thickness sliders."""
    airfoil = NACA4Airfoil(code="0012", camber=0.04, thickness=0.15)
    assert abs(airfoil.m - 0.04) < 1e-5
    assert abs(airfoil.t - 0.15) < 1e-5
    assert airfoil.polygon.shape[0] > 50
    assert hasattr(airfoil, "upper_normals")
    assert hasattr(airfoil, "lower_normals")
