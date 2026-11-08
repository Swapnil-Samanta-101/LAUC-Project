"""Geometry package: NACA airfoil generator, cascade setup, Brinkman penalization masks, diagnostics."""

from .naca import NACA4Airfoil, parse_naca_4digit
from .cascade import TurbofanCascade
from .penalization import compute_polygon_mask, compute_circle_mask
from .diagnostics import AerodynamicDiagnostics

__all__ = [
    "NACA4Airfoil",
    "parse_naca_4digit",
    "TurbofanCascade",
    "compute_polygon_mask",
    "compute_circle_mask",
    "AerodynamicDiagnostics"
]
