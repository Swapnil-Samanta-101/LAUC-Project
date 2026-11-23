"""Navier-Stokes Solver orchestrating the fractional-step (Chorin projection) method.

Coordinates MAC grid, advection, diffusion, Brinkman penalization, spectral/iterative
Poisson solvers, and adaptive time stepping.
"""

from typing import Tuple, Optional, Dict, Any
import numpy as np
from numba import njit

from .grid import MACGrid
from .advection import compute_advection_u, compute_advection_v
from .diffusion import compute_diffusion_u, compute_diffusion_v
from .poisson import SpectralPoissonSolver, RedBlackSORSolver
from .boundary import BoundaryConditions


@njit(fastmath=True, cache=True)
def project_velocities(
    u: np.ndarray,
    v: np.ndarray,
    p: np.ndarray,
    dx: float,
    dy: float,
    dt: float,
    periodic_y: bool = False
) -> Tuple[np.ndarray, np.ndarray]:
    """Correct intermediate velocities using pressure gradient: u = u* - dt * grad(p)."""
    ny, nx_plus_1 = u.shape
    nx = nx_plus_1 - 1
    inv_dx = dt / dx
    inv_dy = dt / dy

    # Correct interior u: i from 1 to nx - 1
    for j in range(ny):
        for i in range(1, nx):
            u[j, i] -= inv_dx * (p[j, i] - p[j, i - 1])

    # Correct interior v: j from 1 to ny - 1
    for j in range(1, ny):
        for i in range(nx):
            v[j, i] -= inv_dy * (p[j, i] - p[j - 1, i])

    if periodic_y:
        # Periodic boundary face: dp/dy = (p[0, i] - p[ny-1, i]) / dy
        for i in range(nx):
            dp_dy = p[0, i] - p[ny - 1, i]
            v[0, i] -= inv_dy * dp_dy
            v[ny, i] = v[0, i]

    return u, v


@njit(fastmath=True, cache=True)
def apply_brinkman_penalization(
    u: np.ndarray,
    v: np.ndarray,
    chi_u: np.ndarray,
    chi_v: np.ndarray,
    eta: float,
    dt: float
) -> Tuple[np.ndarray, np.ndarray]:
    """Apply implicit Brinkman volume penalization for stationary body: u** = u* / (1 + chi * dt / eta)."""
    factor_u = dt / eta
    factor_v = dt / eta
    ny, nx_plus_1 = u.shape
    for j in range(ny):
        for i in range(nx_plus_1):
            if chi_u[j, i] > 0.0:
                u[j, i] /= (1.0 + chi_u[j, i] * factor_u)

    ny_plus_1, nx = v.shape
    for j in range(ny_plus_1):
        for i in range(nx):
            if chi_v[j, i] > 0.0:
                v[j, i] /= (1.0 + chi_v[j, i] * factor_v)

    return u, v


@njit(fastmath=True, cache=True)
def apply_brinkman_penalization_moving(
    u: np.ndarray,
    v: np.ndarray,
    chi_u: np.ndarray,
    chi_v: np.ndarray,
    eta: float,
    dt: float,
    u_solid: np.ndarray,
    v_solid: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Apply implicit Brinkman volume penalization for moving body (e.g. rotating cylinder)."""
    factor = dt / eta
    ny, nx_plus_1 = u.shape
    for j in range(ny):
        for i in range(nx_plus_1):
            if chi_u[j, i] > 0.0:
                chi_dt_eta = chi_u[j, i] * factor
                u[j, i] = (u[j, i] + chi_dt_eta * u_solid[j, i]) / (1.0 + chi_dt_eta)

    ny_plus_1, nx = v.shape
    for j in range(ny_plus_1):
        for i in range(nx):
            if chi_v[j, i] > 0.0:
                chi_dt_eta = chi_v[j, i] * factor
                v[j, i] = (v[j, i] + chi_dt_eta * v_solid[j, i]) / (1.0 + chi_dt_eta)

    return u, v


class NavierStokesSolver:
    """Incompressible Navier-Stokes solver on a staggered MAC grid."""

    def __init__(
        self,
        grid: MACGrid,
        re: float = 100.0,
        cfl: float = 0.35,
        dt_max: float = 0.02,
        poisson_solver_type: str = "spectral",
        boundary_conditions: Optional[BoundaryConditions] = None,
        eta_penalization: float = 1e-3,
        upwind_gamma: float = 0.25
    ) -> None:
        self.grid = grid
        self.re = float(re)
        self.cfl = float(cfl)
        self.dt_max = float(dt_max)
        self.eta_penalization = float(eta_penalization)
        self.upwind_gamma = float(upwind_gamma)

        self.bc = boundary_conditions if boundary_conditions is not None else BoundaryConditions()

        # State fields
        self.u = self.grid.allocate_u()
        self.v = self.grid.allocate_v()
        self.p = self.grid.allocate_pressure()

        # Solid penalization masks (0 = fluid, 1 = solid)
        self.chi_c = np.zeros((self.grid.ny, self.grid.nx), dtype=np.float64)
        self.chi_u = np.zeros((self.grid.ny, self.grid.nx + 1), dtype=np.float64)
        self.chi_v = np.zeros((self.grid.ny + 1, self.grid.nx), dtype=np.float64)

        # Simulation telemetry
        self.time: float = 0.0
        self.step_count: int = 0
        self.dt: float = 0.001
        self.max_div: float = 0.0
        self.rms_div: float = 0.0

        # Poisson solver selection
        self.poisson_solver_type = poisson_solver_type
        self.is_periodic_y = (self.bc.top_bottom_type == "periodic")

        if self.poisson_solver_type == "spectral":
            bc_right = "neumann" if self.bc.outlet_type in ("zero_gradient", "no_slip", "lid") else "dirichlet"
            self.poisson_solver = SpectralPoissonSolver(
                nx=self.grid.nx,
                ny=self.grid.ny,
                dx=self.grid.dx,
                dy=self.grid.dy,
                periodic_y=self.is_periodic_y,
                bc_x_left="neumann",
                bc_x_right=bc_right
            )
        else:
            self.poisson_solver = RedBlackSORSolver(
                nx=self.grid.nx,
                ny=self.grid.ny,
                dx=self.grid.dx,
                dy=self.grid.dy
            )

        # Initialize flow with inlet conditions
        self.u_solid: Optional[np.ndarray] = None
        self.v_solid: Optional[np.ndarray] = None
        self.u_solid_c: Optional[np.ndarray] = None
        self.v_solid_c: Optional[np.ndarray] = None
        self.reset_flow(u_val=self.bc.u_inlet, v_val=self.bc.v_inlet)

    def set_solid_mask(
        self,
        mask_centers: np.ndarray,
        u_solid: Optional[np.ndarray] = None,
        v_solid: Optional[np.ndarray] = None,
        u_solid_c: Optional[np.ndarray] = None,
        v_solid_c: Optional[np.ndarray] = None
    ) -> None:
        """Set solid volume fraction mask and interpolate to u and v face locations."""
        self.chi_c = np.clip(mask_centers, 0.0, 1.0).astype(np.float64)
        self.u_solid = u_solid
        self.v_solid = v_solid
        self.u_solid_c = u_solid_c
        self.v_solid_c = v_solid_c

        # Face interpolation
        self.chi_u = np.zeros((self.grid.ny, self.grid.nx + 1), dtype=np.float64)
        self.chi_u[:, 1:-1] = 0.5 * (self.chi_c[:, :-1] + self.chi_c[:, 1:])
        self.chi_u[:, 0] = self.chi_c[:, 0]
        self.chi_u[:, -1] = self.chi_c[:, -1]

        self.chi_v = np.zeros((self.grid.ny + 1, self.grid.nx), dtype=np.float64)
        self.chi_v[1:-1, :] = 0.5 * (self.chi_c[:-1, :] + self.chi_c[1:, :])
        self.chi_v[0, :] = self.chi_c[0, :]
        self.chi_v[-1, :] = self.chi_c[-1, :]

    def reset_flow(self, u_val: float = 1.0, v_val: float = 0.0) -> None:
        """Reset velocity and pressure fields to initial state."""
        self.u.fill(u_val)
        self.v.fill(v_val)
        self.p.fill(0.0)
        self.time = 0.0
        self.step_count = 0

        # Zero inside solid mask
        self.u *= (1.0 - self.chi_u)
        self.v *= (1.0 - self.chi_v)
        self.bc.apply_velocity_bc(self.u, self.v, self.grid.dx, self.grid.dy, 0.001)

    def compute_adaptive_dt(self) -> float:
        """Compute stable time step adhering to both convective CFL and diffusion limits."""
        u_max = float(np.max(np.abs(self.u)))
        v_max = float(np.max(np.abs(self.v)))
        vel_max = max(u_max, v_max, 1e-6)

        # CFL limit
        min_cell = min(self.grid.dx, self.grid.dy)
        dt_cfl = self.cfl * (min_cell / vel_max)

        # Diffusion limit
        sigma_diff = 0.8
        inv_h2 = (1.0 / (self.grid.dx * self.grid.dx)) + (1.0 / (self.grid.dy * self.grid.dy))
        dt_diff = sigma_diff * 0.5 * self.re / inv_h2

        dt = min(dt_cfl, dt_diff, self.dt_max)
        return max(dt, 1e-5)

    def step(self, dt: Optional[float] = None) -> float:
        """Perform one fractional-step Chorin projection time step."""
        if dt is None:
            dt = self.compute_adaptive_dt()
        self.dt = dt

        # 1. Advection
        adv_u = compute_advection_u(
            self.u, self.v, self.grid.dx, self.grid.dy,
            gamma=self.upwind_gamma, periodic_y=self.is_periodic_y
        )
        adv_v = compute_advection_v(
            self.u, self.v, self.grid.dx, self.grid.dy,
            gamma=self.upwind_gamma, periodic_y=self.is_periodic_y
        )

        # 2. Viscous Diffusion
        diff_u = compute_diffusion_u(
            self.u, self.re, self.grid.dx, self.grid.dy,
            periodic_y=self.is_periodic_y,
            slip_walls=(self.bc.top_bottom_type == "free_slip"),
            u_lid=self.bc.u_lid if self.bc.top_bottom_type == "lid" else 0.0
        )
        diff_v = compute_diffusion_v(
            self.v, self.re, self.grid.dx, self.grid.dy,
            periodic_y=self.is_periodic_y,
            slip_x_right=(self.bc.outlet_type not in ("no_slip", "lid"))
        )

        # 3. Intermediate predictor velocity u*, v*
        u_star = self.u + dt * (adv_u + diff_u)
        v_star = self.v + dt * (adv_v + diff_v)

        # 4. Brinkman Volume Penalization
        if self.u_solid is not None and self.v_solid is not None:
            u_star, v_star = apply_brinkman_penalization_moving(
                u_star, v_star, self.chi_u, self.chi_v, self.eta_penalization, dt,
                self.u_solid, self.v_solid
            )
        else:
            u_star, v_star = apply_brinkman_penalization(
                u_star, v_star, self.chi_u, self.chi_v, self.eta_penalization, dt
            )

        # 5. Boundary conditions on predictor
        self.bc.apply_velocity_bc(u_star, v_star, self.grid.dx, self.grid.dy, dt)

        # 6. Pressure Poisson RHS: (1/dt) * div(u*)
        div_star = (u_star[:, 1:] - u_star[:, :-1]) / self.grid.dx + (v_star[1:, :] - v_star[:-1, :]) / self.grid.dy
        rhs = (1.0 / dt) * div_star

        # 7. Solve Pressure Poisson
        self.p = self.poisson_solver.solve(rhs)

        # 8. Velocity Correction: u^(n+1) = u* - dt * grad(p)
        self.u, self.v = project_velocities(
            u_star, v_star, self.p, self.grid.dx, self.grid.dy, dt, self.is_periodic_y
        )

        # 9. Compute divergence diagnostics (exact on projected field)
        div_final = self.grid.compute_divergence(self.u, self.v)
        self.max_div = float(np.max(np.abs(div_final)))
        self.rms_div = float(np.sqrt(np.mean(div_final * div_final)))

        self.time += dt
        self.step_count += 1
        return dt

    def compute_aerodynamic_forces(self) -> Tuple[float, float, float, float]:
        """Compute aerodynamic forces via Brinkman penalization volume integral.

        F_x = integral( chi/eta * (u - u_solid) ) dOmega
        F_y = integral( chi/eta * (v - v_solid) ) dOmega
        Cd = 2 * F_x / (rho * U_inf^2 * chord)
        Cl = 2 * F_y / (rho * U_inf^2 * chord)
        """
        cell_area = self.grid.dx * self.grid.dy
        u_c, v_c = self.grid.to_cell_centers(self.u, self.v)

        if self.u_solid_c is not None and self.v_solid_c is not None:
            u_rel = u_c - self.u_solid_c
            v_rel = v_c - self.v_solid_c
        else:
            u_rel = u_c
            v_rel = v_c

        f_x = np.sum((self.chi_c / self.eta_penalization) * u_rel) * cell_area
        f_y = np.sum((self.chi_c / self.eta_penalization) * v_rel) * cell_area

        # Non-dimensional reference: chord c = 1.0, U_inf = 1.0, rho = 1.0
        # Dynamic pressure q = 0.5 * rho * U_inf^2 * chord = 0.5
        cd = 2.0 * f_x
        cl = 2.0 * f_y
        return float(f_x), float(f_y), float(cl), float(cd)
