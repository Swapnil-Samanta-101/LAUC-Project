"""High-performance Pressure Poisson Solvers for staggered MAC grids.

Includes:
1. SpectralPoissonSolver:
   Direct O(N log N) direct solver using scipy.fft (DCT-II / FFT) combined with
   vectorized Thomas tridiagonal solves or 2D DCT for machine-precision divergence free projection.
2. RedBlackSORSolver:
   Numba-accelerated Red-Black Successive Over-Relaxation (SOR) iterative solver.
"""

from typing import Tuple, Optional
import numpy as np
import scipy.fft
from numba import njit


@njit(fastmath=True, cache=True)
def solve_tridiagonal_batch(
    sub: np.ndarray,
    diag: np.ndarray,
    sup: np.ndarray,
    rhs: np.ndarray
) -> np.ndarray:
    """Vectorized Thomas algorithm solving (Ny, Nx) tridiagonal systems along axis 1.

    Solves A * x = rhs where A is tridiagonal:
      sub[j, i] * x[j, i-1] + diag[j, i] * x[j, i] + sup[j, i] * x[j, i+1] = rhs[j, i]
    """
    ny, nx = rhs.shape
    x = np.zeros((ny, nx), dtype=rhs.dtype)
    c_prime = np.zeros((ny, nx), dtype=rhs.dtype)
    d_prime = np.zeros((ny, nx), dtype=rhs.dtype)

    # Forward sweep
    for j in range(ny):
        c_prime[j, 0] = sup[j, 0] / diag[j, 0]
        d_prime[j, 0] = rhs[j, 0] / diag[j, 0]

        for i in range(1, nx):
            m = 1.0 / (diag[j, i] - sub[j, i] * c_prime[j, i - 1])
            if i < nx - 1:
                c_prime[j, i] = sup[j, i] * m
            d_prime[j, i] = (rhs[j, i] - sub[j, i] * d_prime[j, i - 1]) * m

        # Back substitution
        x[j, nx - 1] = d_prime[j, nx - 1]
        for i in range(nx - 2, -1, -1):
            x[j, i] = d_prime[j, i] - c_prime[j, i] * x[j, i + 1]

    return x


class SpectralPoissonSolver:
    """Fast Direct Poisson Solver using 1D/2D Spectral Transforms (FFT/DCT) and Tridiagonal Solves.

    Supports:
    - Periodic in y (cascade mode)
    - Neumann in y (free-slip walls, single airfoil/cylinder)
    - Mixed Neumann/Dirichlet in x: Neumann (dp/dx=0) at inlet, Dirichlet (p=0) at outlet
    - Pure Neumann (all 4 boundaries, lid cavity)
    """

    def __init__(
        self,
        nx: int,
        ny: int,
        dx: float,
        dy: float,
        periodic_y: bool = False,
        bc_x_left: str = "neumann",
        bc_x_right: str = "dirichlet"
    ) -> None:
        self.nx = nx
        self.ny = ny
        self.dx = dx
        self.dy = dy
        self.periodic_y = periodic_y
        self.bc_x_left = bc_x_left
        self.bc_x_right = bc_x_right

        self.inv_dx2 = 1.0 / (dx * dx)
        self.inv_dy2 = 1.0 / (dy * dy)

        # Precompute eigenvalues along y
        if self.periodic_y:
            # Fourier modes for periodic boundary: k = 0, ..., ny-1
            ky = np.fft.fftfreq(self.ny, d=1.0) * (2.0 * np.pi)
            # Discrete Laplacian eigenvalue: 2*(cos(ky*dy) - 1)/dy^2
            self.evals_y = 2.0 * (np.cos(ky) - 1.0) * self.inv_dy2
        else:
            # DCT-II modes for Neumann boundary: k = 0, ..., ny-1
            ky = np.pi * np.arange(self.ny) / float(self.ny)
            self.evals_y = 2.0 * (np.cos(ky) - 1.0) * self.inv_dy2

        # Precompute tridiagonal matrices in x for each y-mode
        self._setup_tridiagonal_systems()

    def _setup_tridiagonal_systems(self) -> None:
        """Precompute tridiagonal coefficients for the batch Thomas solver."""
        # For each y-mode j:
        # (p_{i-1} - 2 p_i + p_{i+1})/dx^2 + evals_y[j] * p_i = S_hat
        # => 1/dx^2 * p_{i-1} + (-2/dx^2 + evals_y[j]) * p_i + 1/dx^2 * p_{i+1} = S_hat
        self.sub = np.full((self.ny, self.nx), self.inv_dx2, dtype=np.complex128 if self.periodic_y else np.float64)
        self.sup = np.full((self.ny, self.nx), self.inv_dx2, dtype=np.complex128 if self.periodic_y else np.float64)
        self.diag = np.zeros((self.ny, self.nx), dtype=np.complex128 if self.periodic_y else np.float64)

        for j in range(self.ny):
            base_diag = -2.0 * self.inv_dx2 + self.evals_y[j]
            self.diag[j, :] = base_diag

            # Left boundary (i = 0): dp/dx = 0 -> p[-1] = p[0]
            # (p[1] - p[0])/dx^2 + evals_y[j] * p[0] => diag = -1/dx^2 + evals_y[j]
            if self.bc_x_left == "neumann":
                self.diag[j, 0] = -1.0 * self.inv_dx2 + self.evals_y[j]
                self.sub[j, 0] = 0.0

            # Right boundary (i = nx - 1):
            if self.bc_x_right == "dirichlet":
                # p[nx] = 0 -> p[nx-2] - 2*p[nx-1] + 0 => regular diag, but sup[nx-1] = 0
                # Or ghost p[nx] = -p[nx-1] for face center -> diag = -3/dx^2
                self.diag[j, self.nx - 1] = -3.0 * self.inv_dx2 + self.evals_y[j]
                self.sup[j, self.nx - 1] = 0.0
            elif self.bc_x_right == "neumann":
                # dp/dx = 0 -> p[nx] = p[nx-1]
                self.diag[j, self.nx - 1] = -1.0 * self.inv_dx2 + self.evals_y[j]
                self.sup[j, self.nx - 1] = 0.0

            # Handle singular mode (j=0 in pure Neumann case)
            if abs(self.evals_y[j]) < 1e-12 and self.bc_x_left == "neumann" and self.bc_x_right == "neumann":
                # Pin pressure at i=0 for zero mode
                self.diag[j, 0] = -1.0
                self.sup[j, 0] = 0.0

    def solve(self, rhs: np.ndarray) -> np.ndarray:
        """Solve Laplacian(p) = rhs directly in spectral space.

        Args:
            rhs: shape (ny, nx), divergence term (1/dt) * div(u*)

        Returns:
            p: shape (ny, nx), solution satisfying boundary conditions
        """
        # Step 1: Forward transform in y
        if self.periodic_y:
            rhs_hat = scipy.fft.fft(rhs, axis=0)
            p_hat = solve_tridiagonal_batch(self.sub, self.diag, self.sup, rhs_hat)
            p = scipy.fft.ifft(p_hat, axis=0).real
        else:
            rhs_hat = scipy.fft.dct(rhs, axis=0, type=2, norm="ortho")
            p_hat = solve_tridiagonal_batch(self.sub, self.diag, self.sup, rhs_hat)
            p = scipy.fft.idct(p_hat, axis=0, type=2, norm="ortho")

        return p


@njit(fastmath=True, cache=True)
def red_black_sor_kernel(
    p: np.ndarray,
    rhs: np.ndarray,
    dx: float,
    dy: float,
    omega: float,
    max_iter: int,
    tol: float
) -> Tuple[np.ndarray, int, float]:
    """Red-Black Successive Over-Relaxation kernel for Poisson equation with Neumann boundaries."""
    ny, nx = p.shape
    inv_dx2 = 1.0 / (dx * dx)
    inv_dy2 = 1.0 / (dy * dy)
    inv_diag = 1.0 / (2.0 * inv_dx2 + 2.0 * inv_dy2)

    diff = 1.0
    iter_count = 0

    while iter_count < max_iter and diff > tol:
        diff = 0.0
        # Red sweep: (i + j) % 2 == 0
        for j in range(ny):
            jm1 = max(j - 1, 0)
            jp1 = min(j + 1, ny - 1)
            for i in range(nx):
                if (i + j) % 2 == 0:
                    im1 = max(i - 1, 0)
                    ip1 = min(i + 1, nx - 1)
                    p_star = (
                        (p[j, ip1] + p[j, im1]) * inv_dx2
                        + (p[jp1, i] + p[jm1, i]) * inv_dy2
                        - rhs[j, i]
                    ) * inv_diag
                    res = p_star - p[j, i]
                    p[j, i] += omega * res
                    diff += abs(res)

        # Black sweep: (i + j) % 2 == 1
        for j in range(ny):
            jm1 = max(j - 1, 0)
            jp1 = min(j + 1, ny - 1)
            for i in range(nx):
                if (i + j) % 2 == 1:
                    im1 = max(i - 1, 0)
                    ip1 = min(i + 1, nx - 1)
                    p_star = (
                        (p[j, ip1] + p[j, im1]) * inv_dx2
                        + (p[jp1, i] + p[jm1, i]) * inv_dy2
                        - rhs[j, i]
                    ) * inv_diag
                    res = p_star - p[j, i]
                    p[j, i] += omega * res
                    diff += abs(res)

        diff /= float(nx * ny)
        iter_count += 1

    return p, iter_count, diff


class RedBlackSORSolver:
    """Iterative Red-Black SOR Poisson Solver."""

    def __init__(self, nx: int, ny: int, dx: float, dy: float, max_iter: int = 500, tol: float = 1e-5) -> None:
        self.nx = nx
        self.ny = ny
        self.dx = dx
        self.dy = dy
        self.max_iter = max_iter
        self.tol = tol
        # Optimal SOR relaxation factor for rectangular grid
        rho = 0.5 * (np.cos(np.pi / nx) + np.cos(np.pi / ny))
        self.omega = 2.0 / (1.0 + np.sqrt(1.0 - rho * rho))

    def solve(self, rhs: np.ndarray, p_init: Optional[np.ndarray] = None) -> np.ndarray:
        if p_init is None:
            p = np.zeros((self.ny, self.nx), dtype=np.float64)
        else:
            p = p_init.copy()

        p, _, _ = red_black_sor_kernel(p, rhs, self.dx, self.dy, self.omega, self.max_iter, self.tol)
        return p
