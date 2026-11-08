"""Boundary condition handlers for staggered MAC grid Navier-Stokes simulations."""

from dataclasses import dataclass
from typing import Literal
import numpy as np


@dataclass
class BoundaryConditions:
    """Configurable boundary conditions for domain boundaries."""

    # Options: "uniform_inlet", "lid", "no_slip"
    inlet_type: str = "uniform_inlet"
    # Options: "convective", "zero_gradient"
    outlet_type: str = "convective"
    # Options: "free_slip", "no_slip", "periodic"
    top_bottom_type: str = "free_slip"

    # Inlet parameters
    u_inlet: float = 1.0
    v_inlet: float = 0.0

    # Lid parameters (for cavity)
    u_lid: float = 1.0

    # Convective outflow velocity
    u_conv: float = 1.0

    def apply_velocity_bc(
        self,
        u: np.ndarray,
        v: np.ndarray,
        dx: float,
        dy: float,
        dt: float
    ) -> None:
        """Apply boundary conditions directly to u and v arrays in place."""
        ny, nx_plus_1 = u.shape
        nx = nx_plus_1 - 1
        ny_plus_1 = v.shape[0]

        # 1. Inlet boundary (x = 0)
        if self.inlet_type == "uniform_inlet":
            u[:, 0] = self.u_inlet
            v[:, 0] = self.v_inlet
        elif self.inlet_type in ("no_slip", "lid"):
            u[:, 0] = 0.0
            v[:, 0] = 0.0

        # 2. Outlet boundary (x = Lx)
        if self.outlet_type == "convective":
            cfl_out = min(1.0, max(0.0, self.u_conv * dt / dx))
            u[:, nx] = (1.0 - cfl_out) * u[:, nx] + cfl_out * u[:, nx - 1]
            v[:, nx - 1] = (1.0 - cfl_out) * v[:, nx - 1] + cfl_out * v[:, nx - 2]
        elif self.outlet_type == "zero_gradient":
            u[:, nx] = u[:, nx - 1]
            v[:, nx - 1] = v[:, nx - 2]
        elif self.outlet_type in ("no_slip", "lid"):
            u[:, nx] = 0.0
            v[:, nx - 1] = 0.0

        # 3. Top and Bottom boundaries (y = 0 and y = Ly)
        if self.top_bottom_type in ("free_slip", "no_slip", "lid"):
            # Normal velocity v is strictly zero at physical walls
            v[0, :] = 0.0
            v[ny, :] = 0.0
        elif self.top_bottom_type == "periodic":
            # Pitchwise periodic: wrap bottom and top
            v[0, :] = 0.5 * (v[0, :] + v[ny, :])
            v[ny, :] = v[0, :]
            u[0, :] = 0.5 * (u[0, :] + u[ny - 1, :])
            u[ny - 1, :] = u[0, :]
