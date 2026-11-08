"""Validation Test: 2D Lid-Driven Cavity at Re=100 compared with Ghia et al. (1982) data."""

import pytest
import numpy as np
from solver.grid import MACGrid
from solver.boundary import BoundaryConditions
from solver.ns_solver import NavierStokesSolver


def test_lid_driven_cavity_ghia_re100():
    """Verify velocity profile against benchmark centerline data of Ghia, Ghia & Shin (1982)."""
    grid = MACGrid(nx=64, ny=64, lx=1.0, ly=1.0)
    bc = BoundaryConditions(inlet_type="no_slip", outlet_type="no_slip", top_bottom_type="lid", u_lid=1.0)
    solver = NavierStokesSolver(grid=grid, re=100.0, boundary_conditions=bc)
    solver.reset_flow(0.0, 0.0)

    # Advance until steady circulation develops
    while solver.time < 7.0:
        solver.step()

    uc, vc = grid.to_cell_centers(solver.u, solver.v)
    mid_i = grid.nx // 2

    # Benchmark Ghia et al. (1982) vertical centerline u(y) at x=0.5
    ghia_y = np.array([
        1.0000, 0.9766, 0.9688, 0.9609, 0.9531, 0.8516, 0.7344, 0.6172,
        0.5000, 0.4531, 0.2813, 0.1719, 0.1016, 0.0703, 0.0625, 0.0547, 0.0000
    ])
    ghia_u = np.array([
        1.0000, 0.84123, 0.78871, 0.73722, 0.68717, 0.23151, 0.00332, -0.13641,
        -0.20581, -0.21090, -0.15662, -0.10150, -0.06434, -0.04775, -0.04192, -0.03717, 0.0000
    ])

    # Interpolate simulation profile onto Ghia measurement stations
    u_sim_interp = np.interp(ghia_y, grid.yc, uc[:, mid_i])
    u_sim_interp[0] = 1.0  # moving lid boundary
    u_sim_interp[-1] = 0.0  # stationary bottom wall

    l2_error = float(np.linalg.norm(u_sim_interp - ghia_u) / np.linalg.norm(ghia_u))
    pearson_corr = float(np.corrcoef(u_sim_interp, ghia_u)[0, 1])

    print(f"\n[Cavity Re=100] L2 Relative Error: {l2_error * 100:.2f}%, Pearson Correlation: {pearson_corr:.5f}")

    # Check that error is below 5% and correlation exceeds 0.99
    assert l2_error < 0.05, f"L2 error {l2_error:.4f} exceeded 5% benchmark tolerance"
    assert pearson_corr > 0.99, f"Correlation {pearson_corr:.4f} is below 0.99"
