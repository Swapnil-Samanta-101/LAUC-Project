"""Aerodynamic Diagnostics and Post-Processing.

Calculates:
- Surface pressure coefficient Cp(x/c) distribution (upper and lower surfaces)
- Integrated Lift Cl and Drag Cd
- Mass conservation (velocity divergence monitor)
- Cascade total pressure loss coefficient Yp and flow turning angle Delta_beta
"""

from typing import Tuple, Dict, Any, List
import numpy as np
try:
    from solver.grid import MACGrid
    from solver.ns_solver import NavierStokesSolver
except (ImportError, ValueError):
    from ..solver.grid import MACGrid
    from ..solver.ns_solver import NavierStokesSolver


class AerodynamicDiagnostics:
    """Computes aerodynamic and turbomachinery diagnostics from flow fields."""

    @staticmethod
    def extract_surface_cp(
        solver: NavierStokesSolver,
        x_le: float = 1.0,
        chord: float = 1.0,
        n_samples: int = 50
    ) -> Dict[str, np.ndarray]:
        """Extract pressure coefficient Cp(x/c) along upper (suction) and lower (pressure) surfaces.

        Cp = (p - p_inf) / (0.5 * rho * U_inf^2) = 2.0 * p
        """
        grid = solver.grid
        p = solver.p
        chi = solver.chi_c

        x_te = x_le + chord
        xc_norm = np.linspace(0.02, 0.98, n_samples)
        x_eval = x_le + xc_norm * chord

        cp_upper = np.zeros(n_samples, dtype=np.float64)
        cp_lower = np.zeros(n_samples, dtype=np.float64)

        for idx, x_target in enumerate(x_eval):
            # Find closest cell column i
            i = int(np.clip(np.searchsorted(grid.xc, x_target), 0, grid.nx - 1))

            col_mask = chi[:, i]
            # Identify indices where solid exists in this column
            solid_indices = np.where(col_mask > 0.4)[0]

            if len(solid_indices) > 0:
                j_bot_solid = solid_indices[0]
                j_top_solid = solid_indices[-1]

                # Upper surface: cell just above solid
                j_up = min(j_top_solid + 1, grid.ny - 1)
                # Lower surface: cell just below solid
                j_low = max(j_bot_solid - 1, 0)

                cp_upper[idx] = 2.0 * p[j_up, i]
                cp_lower[idx] = 2.0 * p[j_low, i]
            else:
                # If chord slice not masked (e.g. sharp trailing/leading edge)
                j_mid = grid.ny // 2
                cp_upper[idx] = 2.0 * p[min(j_mid + 2, grid.ny - 1), i]
                cp_lower[idx] = 2.0 * p[max(j_mid - 2, 0), i]

        return {
            "x_c": xc_norm,
            "cp_upper": cp_upper,
            "cp_lower": cp_lower
        }

    @staticmethod
    def compute_cascade_metrics(
        solver: NavierStokesSolver,
        x_inlet_slice: int = 5,
        x_outlet_slice: int = -6
    ) -> Dict[str, float]:
        """Compute cascade flow turning angle and total pressure loss coefficient Yp.

        - Inlet flow angle: beta1 = arctan(mean(v_in) / mean(u_in))
        - Outlet flow angle: beta2 = arctan(mean(v_out) / mean(u_out))
        - Flow turning: Delta_beta = beta1 - beta2
        - Total pressure loss: Yp = (p0_in - p0_out) / (p0_in - p_in)
        """
        grid = solver.grid
        u_c, v_c = grid.to_cell_centers(solver.u, solver.v)
        p = solver.p

        # Total pressure field: p0 = p + 0.5 * (u^2 + v^2)
        p0 = p + 0.5 * (u_c * u_c + v_c * v_c)

        # Inlet station
        u_in = np.mean(u_c[:, x_inlet_slice])
        v_in = np.mean(v_c[:, x_inlet_slice])
        p_in = np.mean(p[:, x_inlet_slice])
        p0_in = np.mean(p0[:, x_inlet_slice])
        beta1_deg = float(np.degrees(np.arctan2(v_in, u_in)))

        # Outlet station
        u_out = np.mean(u_c[:, x_outlet_slice])
        v_out = np.mean(v_c[:, x_outlet_slice])
        p0_out = np.mean(p0[:, x_outlet_slice])
        beta2_deg = float(np.degrees(np.arctan2(v_out, u_out)))

        turning_angle = beta1_deg - beta2_deg
        dyn_press_in = max(p0_in - p_in, 1e-5)
        loss_coeff = (p0_in - p0_out) / dyn_press_in

        return {
            "inlet_angle_deg": beta1_deg,
            "outlet_angle_deg": beta2_deg,
            "turning_angle_deg": turning_angle,
            "total_pressure_loss_yp": float(max(0.0, loss_coeff))
        }

    @staticmethod
    def get_summary_telemetry(solver: NavierStokesSolver) -> Dict[str, Any]:
        """Compile a fast telemetry dictionary for frontend streaming."""
        fx, fy, cl, cd = solver.compute_aerodynamic_forces()
        return {
            "time": round(solver.time, 4),
            "step": solver.step_count,
            "dt": round(solver.dt, 6),
            "cl": round(cl, 4),
            "cd": round(cd, 4),
            "lift_to_drag": round(cl / max(cd, 1e-4), 3),
            "max_divergence": f"{solver.max_div:.2e}",
            "rms_divergence": f"{solver.rms_div:.2e}"
        }
