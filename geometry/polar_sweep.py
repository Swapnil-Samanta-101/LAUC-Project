"""Aerodynamic Polar Sweep Tool (Lift Curve & Drag Polar).

Runs automated Angle of Attack sweeps (alpha from -4 deg to +16 deg) using the
2D Navier-Stokes solver, warm-starting each angle from the previous solution
to rapidly compute Cl vs alpha and Cl vs Cd polar curves.
"""

from typing import List, Dict, Any, Optional
import numpy as np

from solver.grid import MACGrid
from solver.boundary import BoundaryConditions
from solver.ns_solver import NavierStokesSolver
from geometry.naca import NACA4Airfoil
from geometry.shapes import generate_flat_plate, generate_ellipse
from geometry.penalization import compute_polygon_mask


def run_alpha_sweep(
    shape_type: str = "naca",
    naca_code: str = "0012",
    camber: Optional[float] = None,
    thickness: Optional[float] = None,
    reynolds: float = 500.0,
    alpha_start: float = -4.0,
    alpha_end: float = 16.0,
    alpha_step: float = 2.0,
    steps_per_alpha: int = 80,
    nx: int = 96,
    ny: int = 48,
    lx: float = 6.0,
    ly: float = 3.0
) -> Dict[str, Any]:
    """Run an automated angle of attack sweep and return aerodynamic polars.

    Args:
        shape_type: "naca", "flat_plate", or "ellipse"
        naca_code: NACA 4-digit code if shape_type == "naca"
        camber: camber fraction (e.g. 0.04) if specified
        thickness: thickness fraction (e.g. 0.12) if specified
        reynolds: Reynolds number
        alpha_start: starting angle in degrees
        alpha_end: ending angle in degrees (inclusive)
        alpha_step: step size in degrees
        steps_per_alpha: time steps to settle flow at each alpha
        nx, ny, lx, ly: grid dimensions for sweep solver

    Returns:
        Dict with:
            - sweep_data: list of dicts with alpha, cl, cd, ld
            - cl_max: maximum lift coefficient
            - stall_alpha: angle of attack where Cl is maximized
            - zero_lift_alpha: angle where Cl ~ 0
    """
    alphas = np.arange(alpha_start, alpha_end + 0.5 * alpha_step, alpha_step)
    chord = 1.0
    x_le = 1.5
    y_le = ly / 2.0

    grid = MACGrid(nx=nx, ny=ny, lx=lx, ly=ly)
    bc = BoundaryConditions(inlet_type="uniform_inlet", outlet_type="convective", top_bottom_type="free_slip")
    solver = NavierStokesSolver(grid=grid, re=reynolds, boundary_conditions=bc)

    sweep_results: List[Dict[str, float]] = []

    for alpha in alphas:
        alpha_val = float(alpha)

        # Generate shape polygon for active alpha
        if shape_type == "flat_plate":
            t_ratio = thickness if thickness is not None else 0.03
            poly = generate_flat_plate(chord=chord, x_le=x_le, y_le=y_le, alpha_deg=alpha_val, thickness=t_ratio)
        elif shape_type == "ellipse":
            t_ratio = thickness if thickness is not None else 0.15
            poly = generate_ellipse(chord=chord, x_le=x_le, y_le=y_le, alpha_deg=alpha_val, thickness_ratio=t_ratio)
        else:  # naca
            airfoil = NACA4Airfoil(
                code=naca_code,
                chord=chord,
                x_origin=x_le,
                y_origin=y_le,
                alpha_deg=alpha_val,
                camber=camber,
                thickness=thickness,
                n_points=100
            )
            poly = airfoil.polygon

        mask = compute_polygon_mask([poly], grid.X_c, grid.Y_c)
        solver.set_solid_mask(mask)

        # Run relaxation steps at this angle of attack
        for _ in range(steps_per_alpha):
            solver.step()

        # Extract aerodynamic coefficients
        _, _, cl, cd = solver.compute_aerodynamic_forces()
        cd_clean = max(cd, 1e-4)
        ld = cl / cd_clean

        sweep_results.append({
            "alpha": round(alpha_val, 1),
            "cl": round(float(cl), 4),
            "cd": round(float(cd_clean), 4),
            "ld": round(float(ld), 2)
        })

    # Determine stall and zero lift characteristics
    cl_values = [r["cl"] for r in sweep_results]
    max_idx = int(np.argmax(cl_values))
    cl_max = sweep_results[max_idx]["cl"]
    stall_alpha = sweep_results[max_idx]["alpha"]

    # Zero-lift alpha approximation
    zero_lift_alpha = None
    min_abs_cl = 1e9
    for r in sweep_results:
        if abs(r["cl"]) < min_abs_cl:
            min_abs_cl = abs(r["cl"])
            zero_lift_alpha = r["alpha"]

    return {
        "sweep_data": sweep_results,
        "cl_max": cl_max,
        "stall_alpha": stall_alpha,
        "zero_lift_alpha": zero_lift_alpha,
        "reynolds": reynolds,
        "shape_type": shape_type
    }
