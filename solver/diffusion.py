"""Viscous diffusion operator for staggered MAC grid using Numba acceleration.

Implements second-order central differences for:
  diff_u = (1/Re) * (d^2 u / dx^2 + d^2 u / dy^2)
  diff_v = (1/Re) * (d^2 v / dx^2 + d^2 v / dy^2)
supporting free-slip, no-slip, and periodic pitchwise boundaries.
"""

import numpy as np
from numba import njit


@njit(fastmath=True, cache=True)
def compute_diffusion_u(
    u: np.ndarray,
    re: float,
    dx: float,
    dy: float,
    periodic_y: bool = False,
    slip_walls: bool = True,
    u_lid: float = 0.0
) -> np.ndarray:
    """Compute (1/Re) * laplacian(u) on vertical faces.

    Args:
        u: shape (ny, nx + 1)
        re: Reynolds number
        dx: cell width
        dy: cell height
        periodic_y: pitchwise periodic boundary
        slip_walls: top/bottom free slip (du/dy = 0) vs no-slip (u = 0)
        u_lid: moving top wall velocity (for lid-driven cavity)

    Returns:
        diff_u: shape (ny, nx + 1)
    """
    ny, nx_plus_1 = u.shape
    nx = nx_plus_1 - 1
    diff_u = np.zeros_like(u)
    inv_re = 1.0 / re
    inv_dx2 = 1.0 / (dx * dx)
    inv_dy2 = 1.0 / (dy * dy)

    for j in range(ny):
        if periodic_y:
            jp1 = (j + 1) % ny
            jm1 = (j - 1 + ny) % ny
        else:
            jp1 = min(j + 1, ny - 1)
            jm1 = max(j - 1, 0)

        for i in range(1, nx):
            # d^2 u / dx^2
            d2u_dx2 = (u[j, i + 1] - 2.0 * u[j, i] + u[j, i - 1]) * inv_dx2

            # d^2 u / dy^2
            if periodic_y:
                d2u_dy2 = (u[jp1, i] - 2.0 * u[j, i] + u[jm1, i]) * inv_dy2
            else:
                if j == 0:
                    if slip_walls:
                        d2u_dy2 = (u[1, i] - u[0, i]) * inv_dy2
                    else:
                        d2u_dy2 = (u[1, i] - 3.0 * u[0, i]) * inv_dy2
                elif j == ny - 1:
                    if slip_walls:
                        d2u_dy2 = (u[ny - 2, i] - u[ny - 1, i]) * inv_dy2
                    else:
                        d2u_dy2 = (2.0 * u_lid + u[ny - 2, i] - 3.0 * u[ny - 1, i]) * inv_dy2
                else:
                    d2u_dy2 = (u[j + 1, i] - 2.0 * u[j, i] + u[j - 1, i]) * inv_dy2

            diff_u[j, i] = inv_re * (d2u_dx2 + d2u_dy2)

    return diff_u


@njit(fastmath=True, cache=True)
def compute_diffusion_v(
    v: np.ndarray,
    re: float,
    dx: float,
    dy: float,
    periodic_y: bool = False,
    slip_x_right: bool = True
) -> np.ndarray:
    """Compute (1/Re) * laplacian(v) on horizontal faces.

    Args:
        v: shape (ny + 1, nx)
        re: Reynolds number
        dx: cell width
        dy: cell height
        periodic_y: pitchwise periodic boundary
        slip_x_right: open convective/zero-gradient outlet vs no-slip right wall

    Returns:
        diff_v: shape (ny + 1, nx)
    """
    ny_plus_1, nx = v.shape
    ny = ny_plus_1 - 1
    diff_v = np.zeros_like(v)
    inv_re = 1.0 / re
    inv_dx2 = 1.0 / (dx * dx)
    inv_dy2 = 1.0 / (dy * dy)

    j_start = 0 if periodic_y else 1
    j_end = ny_plus_1 if periodic_y else ny

    for j in range(j_start, j_end):
        actual_j = j % ny if periodic_y else j
        jm1 = (actual_j - 1 + ny) % ny if periodic_y else actual_j - 1
        jp1 = (actual_j + 1) % ny if periodic_y else actual_j + 1

        for i in range(nx):
            # d^2 v / dx^2
            if i == 0:
                # Left wall v=0 -> v[-1] = -v[0]
                d2v_dx2 = (v[actual_j, 1] - 3.0 * v[actual_j, 0]) * inv_dx2
            elif i == nx - 1:
                if slip_x_right:
                    # Convective / zero-gradient outlet -> v[nx] = v[nx-1]
                    d2v_dx2 = (v[actual_j, nx - 2] - v[actual_j, nx - 1]) * inv_dx2
                else:
                    # No-slip right wall -> v[nx] = -v[nx-1]
                    d2v_dx2 = (v[actual_j, nx - 2] - 3.0 * v[actual_j, nx - 1]) * inv_dx2
            else:
                d2v_dx2 = (v[actual_j, i + 1] - 2.0 * v[actual_j, i] + v[actual_j, i - 1]) * inv_dx2

            # d^2 v / dy^2
            if periodic_y:
                d2v_dy2 = (v[jp1, i] - 2.0 * v[actual_j, i] + v[jm1, i]) * inv_dy2
            else:
                d2v_dy2 = (v[actual_j + 1, i] - 2.0 * v[actual_j, i] + v[actual_j - 1, i]) * inv_dy2

            diff_v[actual_j, i] = inv_re * (d2v_dx2 + d2v_dy2)

    if periodic_y:
        diff_v[ny, :] = diff_v[0, :]

    return diff_v
