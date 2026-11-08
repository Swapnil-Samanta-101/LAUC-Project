"""Validation Test: Laminar flow past circular cylinder at Re=100 (Karman vortex shedding)."""

import pytest
import numpy as np
from solver.grid import MACGrid
from solver.boundary import BoundaryConditions
from solver.ns_solver import NavierStokesSolver
from geometry.penalization import compute_circle_mask


def test_cylinder_vortex_shedding_strouhal():
    """Verify Strouhal number St = f * D / U_inf is approximately 0.16 - 0.17 at Re=100."""
    D = 0.6
    grid = MACGrid(nx=128, ny=64, lx=10.0, ly=6.0)
    bc = BoundaryConditions(inlet_type="uniform_inlet", outlet_type="convective", top_bottom_type="free_slip")

    # Re_D = U_inf * D / nu = 100 => nu = 0.6 / 100 = 0.006 => Solver Re = 1 / nu = 166.67
    solver = NavierStokesSolver(grid=grid, re=166.67, boundary_conditions=bc)
    mask = compute_circle_mask(center_x=2.5, center_y=3.0, radius=D / 2.0, X=grid.X_c, Y=grid.Y_c)
    solver.set_solid_mask(mask)

    # Trigger asymmetric vortex shedding in wake
    solver.v += 0.2 * np.exp(-((grid.X_v - 3.0) ** 2 + (grid.Y_v - 3.2) ** 2) / 0.2)

    cl_list = []
    t_list = []

    # Advance until steady periodic shedding regime
    while solver.time < 42.0:
        solver.step()
        if solver.step_count % 5 == 0:
            _, _, cl, _ = solver.compute_aerodynamic_forces()
            cl_list.append(cl)
            t_list.append(solver.time)

    t_arr = np.array(t_list)
    cl_arr = np.array(cl_list)

    # Extract limit cycle shedding (post-transient t > 15)
    post_transient = (t_arr > 15.0)
    cl_post = cl_arr[post_transient]
    t_post = t_arr[post_transient]

    zero_crossings = np.where(np.diff(np.sign(cl_post)))[0]
    assert len(zero_crossings) >= 6, f"Expected periodic vortex shedding, found only {len(zero_crossings)} zero crossings"

    # Full period is time between every second zero-crossing
    periods = np.diff(t_post[zero_crossings[::2]])
    mean_period = float(np.mean(periods))
    shedding_freq = 1.0 / mean_period
    strouhal = float(shedding_freq * D / 1.0)

    print(f"\n[Cylinder Re=100] Shedding Period: {mean_period:.3f} s, Frequency: {shedding_freq:.3f} Hz, Strouhal: {strouhal:.4f}")

    # Published benchmark St = 0.164 +/- 0.015
    assert 0.150 <= strouhal <= 0.180, f"Strouhal number {strouhal:.4f} outside expected range [0.15, 0.18]"
