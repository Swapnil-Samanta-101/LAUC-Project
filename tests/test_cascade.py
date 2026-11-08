"""Validation Test: Turbofan / Compressor Blade Cascade with Pitchwise Periodic Boundaries."""

import pytest
import numpy as np
from solver.grid import MACGrid
from solver.boundary import BoundaryConditions
from solver.ns_solver import NavierStokesSolver
from geometry.cascade import TurbofanCascade
from geometry.penalization import compute_polygon_mask
from geometry.diagnostics import AerodynamicDiagnostics


def test_cascade_pitchwise_periodicity_and_turning():
    """Verify that cascade enforces exact pitchwise periodic boundary conditions and flow turning."""
    pitch = 1.5
    grid = MACGrid(nx=96, ny=48, lx=6.0, ly=3.0)
    inlet_angle = 20.0
    u_in = float(np.cos(np.radians(inlet_angle)))
    v_in = float(np.sin(np.radians(inlet_angle)))

    bc = BoundaryConditions(
        inlet_type="uniform_inlet",
        outlet_type="convective",
        top_bottom_type="periodic",
        u_inlet=u_in,
        v_inlet=v_in
    )
    solver = NavierStokesSolver(grid=grid, re=300.0, boundary_conditions=bc)
    cascade = TurbofanCascade(
        chord=1.0,
        pitch=pitch,
        stagger_deg=20.0,
        camber_code="6412",
        domain_ly=3.0,
        x_axial_pos=1.5
    )
    mask = compute_polygon_mask(cascade.polygons, grid.X_c, grid.Y_c)
    solver.set_solid_mask(mask)

    while solver.time < 8.0:
        solver.step()

    # 1. Pitchwise periodic boundary verification:
    # Transverse velocity v at y=0 (index 0) must exactly match v at y=Ly (index ny)
    v_bottom = solver.v[0, :]
    v_top = solver.v[grid.ny, :]
    max_periodic_diff = float(np.max(np.abs(v_top - v_bottom)))
    print(f"\n[Cascade Periodicity] Max boundary disparity: {max_periodic_diff:.3e}")
    assert max_periodic_diff < 1e-12, f"Periodic boundary disparity {max_periodic_diff} exceeds tolerance"

    # 2. Blade-to-blade flow turning & loss verification:
    metrics = AerodynamicDiagnostics.compute_cascade_metrics(solver)
    print(f"[Cascade Aerodynamics] Turning Angle: {metrics['turning_angle_deg']:.3f} deg, Yp Loss: {metrics['total_pressure_loss_yp']:.4f}")
    assert metrics["turning_angle_deg"] > 0.0, "Cambered blade must turn flow toward axial direction"
    assert metrics["total_pressure_loss_yp"] > 0.0, "Viscous profile losses through cascade must be non-zero positive"
