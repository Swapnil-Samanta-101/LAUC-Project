"""Verification test: Velocity field divergence (mass conservation) stays below tolerance."""

import pytest
import numpy as np
from solver.grid import MACGrid
from solver.boundary import BoundaryConditions
from solver.ns_solver import NavierStokesSolver
from geometry.naca import NACA4Airfoil
from geometry.penalization import compute_polygon_mask


def test_pure_fluid_divergence():
    """Verify that pure fluid flow preserves machine-precision incompressibility."""
    grid = MACGrid(nx=64, ny=32, lx=4.0, ly=2.0)
    bc = BoundaryConditions(inlet_type="uniform_inlet", outlet_type="convective", top_bottom_type="free_slip")
    solver = NavierStokesSolver(grid=grid, re=200.0, boundary_conditions=bc)
    solver.reset_flow(1.0, 0.0)

    for _ in range(15):
        solver.step()

    div = grid.compute_divergence(solver.u, solver.v)
    assert np.max(np.abs(div)) < 1e-10, f"Expected machine-precision divergence, got max {np.max(np.abs(div))}"
    assert np.sqrt(np.mean(div ** 2)) < 1e-10


def test_immersed_boundary_divergence_tolerance():
    """Verify that flow with immersed boundary maintains divergence below 1e-4 tolerance."""
    grid = MACGrid(nx=64, ny=32, lx=4.0, ly=2.0)
    bc = BoundaryConditions(inlet_type="uniform_inlet", outlet_type="convective", top_bottom_type="free_slip")
    solver = NavierStokesSolver(grid=grid, re=100.0, boundary_conditions=bc)

    airfoil = NACA4Airfoil(code="0012", chord=1.0, x_origin=1.0, y_origin=1.0, alpha_deg=5.0)
    mask = compute_polygon_mask(airfoil.polygon, grid.X_c, grid.Y_c)
    solver.set_solid_mask(mask)

    # Advance flow past initial transient (40 steps to let impulsive start settle)
    for _ in range(40):
        solver.step(0.01)

    div = grid.compute_divergence(solver.u, solver.v)
    rms_div = float(np.sqrt(np.mean(div ** 2)))
    max_div = float(np.max(np.abs(div)))

    print(f"\n[Airfoil Flow Divergence] RMS: {rms_div:.3e}, Max: {max_div:.3e}")
    assert rms_div < 1e-4, f"RMS divergence {rms_div:.3e} exceeds tolerance 1e-4"
    assert max_div < 2e-3, f"Max divergence {max_div:.3e} exceeds tolerance 2e-3"
