"""Validation Test: NACA 0012 Airfoil Aerodynamics at Low Reynolds Number."""

import pytest
import numpy as np
from solver.grid import MACGrid
from solver.boundary import BoundaryConditions
from solver.ns_solver import NavierStokesSolver
from geometry.naca import NACA4Airfoil
from geometry.penalization import compute_polygon_mask
from geometry.diagnostics import AerodynamicDiagnostics


def simulate_airfoil(alpha_deg: float, re: float = 200.0, sim_time: float = 6.0):
    """Helper to simulate flow over NACA 0012 at a given angle of attack."""
    grid = MACGrid(nx=96, ny=48, lx=6.0, ly=3.0)
    bc = BoundaryConditions(inlet_type="uniform_inlet", outlet_type="convective", top_bottom_type="free_slip")
    solver = NavierStokesSolver(grid=grid, re=re, boundary_conditions=bc)

    airfoil = NACA4Airfoil(code="0012", chord=1.0, x_origin=1.5, y_origin=1.5, alpha_deg=alpha_deg)
    mask = compute_polygon_mask(airfoil.polygon, grid.X_c, grid.Y_c)
    solver.set_solid_mask(mask)

    while solver.time < sim_time:
        solver.step()

    fx, fy, cl, cd = solver.compute_aerodynamic_forces()
    cp_data = AerodynamicDiagnostics.extract_surface_cp(solver, x_le=1.5, chord=1.0)
    return cl, cd, cp_data


def test_naca_0012_zero_lift_at_zero_alpha():
    """Verify that symmetric NACA 0012 at alpha = 0 deg produces approximately zero lift."""
    cl, cd, cp_data = simulate_airfoil(alpha_deg=0.0)
    print(f"\n[NACA 0012 alpha=0 deg] Cl: {cl:.5f}, Cd: {cd:.4f}")
    assert abs(cl) < 0.05, f"Expected Cl near zero for symmetric airfoil at 0 deg, got {cl}"
    assert cd > 0.0, "Drag coefficient must be strictly positive"


def test_naca_0012_positive_lift_slope():
    """Verify that lift increases with angle of attack prior to stall."""
    cl_0, cd_0, _ = simulate_airfoil(alpha_deg=0.0)
    cl_4, cd_4, _ = simulate_airfoil(alpha_deg=4.0)
    cl_8, cd_8, _ = simulate_airfoil(alpha_deg=8.0)

    print(f"\n[NACA 0012 Polars] Cl(0 deg) = {cl_0:.4f}, Cl(4 deg) = {cl_4:.4f}, Cl(8 deg) = {cl_8:.4f}")
    assert cl_4 > cl_0, "Lift at alpha=4 deg must exceed lift at alpha=0 deg"
    assert cl_8 > cl_4, "Lift at alpha=8 deg must exceed lift at alpha=4 deg"

    # Verify Cp upper surface suction: Cp_upper should be more negative than Cp_lower at alpha=4
    _, _, cp_4 = simulate_airfoil(alpha_deg=4.0)
    mean_cp_upper = np.mean(cp_4["cp_upper"])
    mean_cp_lower = np.mean(cp_4["cp_lower"])
    print(f"[NACA 0012 Cp] Mean upper Cp: {mean_cp_upper:.3f}, Mean lower Cp: {mean_cp_lower:.3f}")
    assert mean_cp_upper < mean_cp_lower, "Upper surface must exhibit suction (lower pressure) relative to lower surface"
