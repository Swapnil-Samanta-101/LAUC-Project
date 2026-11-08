"""Marker-and-Cell (MAC) staggered grid representation for 2D Navier-Stokes equations."""

from dataclasses import dataclass
from typing import Tuple
import numpy as np


@dataclass
class MACGrid:
    """Represents a 2D staggered Cartesian MAC grid.

    Coordinate layout:
      - Domain: [0, Lx] x [0, Ly]
      - Cells: Nx x Ny cells of dimensions dx = Lx/Nx, dy = Ly/Ny.
      - Indexing convention: array[j, i] where j is y-index (0 to Ny-1) and i is x-index (0 to Nx-1).
      - p (pressure) & scalars: defined at cell centers (j, i). Shape: (Ny, Nx).
      - u (streamwise velocity): defined at vertical cell faces (j, i+1/2). Shape: (Ny, Nx + 1).
      - v (transverse velocity): defined at horizontal cell faces (j+1/2, i). Shape: (Ny + 1, Nx).
    """

    nx: int
    ny: int
    lx: float
    ly: float

    def __post_init__(self) -> None:
        self.dx: float = self.lx / float(self.nx)
        self.dy: float = self.ly / float(self.ny)

        # 1D coordinates
        self.xc: np.ndarray = np.linspace(0.5 * self.dx, self.lx - 0.5 * self.dx, self.nx)
        self.yc: np.ndarray = np.linspace(0.5 * self.dy, self.ly - 0.5 * self.dy, self.ny)

        self.xu: np.ndarray = np.linspace(0.0, self.lx, self.nx + 1)
        self.yu: np.ndarray = self.yc.copy()

        self.xv: np.ndarray = self.xc.copy()
        self.yv: np.ndarray = np.linspace(0.0, self.ly, self.ny + 1)

        # 2D coordinate meshgrids for cell centers (indexed [j, i])
        self.X_c, self.Y_c = np.meshgrid(self.xc, self.yc)

        # 2D coordinate meshgrids for u-faces
        self.X_u, self.Y_u = np.meshgrid(self.xu, self.yu)

        # 2D coordinate meshgrids for v-faces
        self.X_v, self.Y_v = np.meshgrid(self.xv, self.yv)

    def allocate_pressure(self) -> np.ndarray:
        """Allocate scalar pressure array at cell centers: shape (ny, nx)."""
        return np.zeros((self.ny, self.nx), dtype=np.float64)

    def allocate_u(self) -> np.ndarray:
        """Allocate u-velocity array at vertical faces: shape (ny, nx + 1)."""
        return np.zeros((self.ny, self.nx + 1), dtype=np.float64)

    def allocate_v(self) -> np.ndarray:
        """Allocate v-velocity array at horizontal faces: shape (ny + 1, nx)."""
        return np.zeros((self.ny + 1, self.nx), dtype=np.float64)

    def to_cell_centers(self, u: np.ndarray, v: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Interpolate staggered u and v velocities to cell centers (ny, nx).

        Args:
            u: u-velocity array of shape (ny, nx + 1)
            v: v-velocity array of shape (ny + 1, nx)

        Returns:
            (u_center, v_center), both of shape (ny, nx)
        """
        u_center = 0.5 * (u[:, :-1] + u[:, 1:])
        v_center = 0.5 * (v[:-1, :] + v[1:, :])
        return u_center, v_center

    def velocity_magnitude(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Compute velocity magnitude |u| = sqrt(u^2 + v^2) at cell centers."""
        uc, vc = self.to_cell_centers(u, v)
        return np.sqrt(uc * uc + vc * vc)

    def compute_vorticity(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Compute vorticity omega = dv/dx - du/dy at cell centers.

        Uses second-order central differences:
        dv/dx at cell center (j, i): (v_mid[j, i+1] - v_mid[j, i-1]) / (2*dx)
        du/dy at cell center (j, i): (u_mid[j+1, i] - u_mid[j-1, i]) / (2*dy)
        or direct face values:
        dv/dx = (v_avg_right - v_avg_left) / dx
        du/dy = (u_avg_top - u_avg_bottom) / dy
        """
        uc, vc = self.to_cell_centers(u, v)
        omega = np.zeros((self.ny, self.nx), dtype=np.float64)

        # dv/dx interior
        dudx = np.zeros_like(uc)
        dudy = np.zeros_like(uc)
        dvdx = np.zeros_like(vc)
        dvdy = np.zeros_like(vc)

        dvdx[:, 1:-1] = (vc[:, 2:] - vc[:, :-2]) / (2.0 * self.dx)
        dvdx[:, 0] = (vc[:, 1] - vc[:, 0]) / self.dx
        dvdx[:, -1] = (vc[:, -1] - vc[:, -2]) / self.dx

        dudy[1:-1, :] = (uc[2:, :] - uc[:-2, :]) / (2.0 * self.dy)
        dudy[0, :] = (uc[1, :] - uc[0, :]) / self.dy
        dudy[-1, :] = (uc[-1, :] - uc[-2, :]) / self.dy

        omega = dvdx - dudy
        return omega

    def compute_divergence(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Compute velocity field divergence at cell centers:
        div = (u[j, i+1] - u[j, i])/dx + (v[j+1, i] - v[j, i])/dy
        """
        div = (u[:, 1:] - u[:, :-1]) / self.dx + (v[1:, :] - v[:-1, :]) / self.dy
        return div
