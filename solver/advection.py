"""Advection schemes for staggered MAC grid using Numba acceleration.

Implements conservative flux formulation with donor-cell / 2nd-order upwind blending
for both u and v momentum advection terms.
"""

import numpy as np
from numba import njit


@njit(fastmath=True, cache=True)
def compute_advection_u(
    u: np.ndarray,
    v: np.ndarray,
    dx: float,
    dy: float,
    gamma: float = 0.25,
    periodic_y: bool = False
) -> np.ndarray:
    """Compute advection of u: du_dt = - [ d(u*u)/dx + d(v*u)/dy ] on vertical faces.

    Args:
        u: shape (ny, nx + 1)
        v: shape (ny + 1, nx)
        dx: grid spacing x
        dy: grid spacing y
        gamma: upwind blending parameter (0.0 = pure 2nd order central, 1.0 = full upwind)
        periodic_y: whether y-boundary is periodic (cascade mode)

    Returns:
        adv_u: shape (ny, nx + 1), zeros at boundaries where Dirichlet applies
    """
    ny, nx_plus_1 = u.shape
    nx = nx_plus_1 - 1
    adv_u = np.zeros_like(u)

    # Interior u faces: i from 1 to nx - 1, j from 0 to ny - 1
    for j in range(ny):
        # Y-neighbor indices with periodic or Neumann support
        if periodic_y:
            jp1 = (j + 1) % ny
            jm1 = (j - 1 + ny) % ny
        else:
            jp1 = min(j + 1, ny - 1)
            jm1 = max(j - 1, 0)

        for i in range(1, nx):
            # 1. d(u*u)/dx: cell centers at i-1 and i
            # u_right (at cell center i)
            u_e = 0.5 * (u[j, i] + u[j, i + 1])
            u_diff_e = 0.5 * (u[j, i] - u[j, i + 1])
            flux_e = u_e * u_e + gamma * np.abs(u_e) * u_diff_e

            # u_left (at cell center i-1)
            u_w = 0.5 * (u[j, i - 1] + u[j, i])
            u_diff_w = 0.5 * (u[j, i - 1] - u[j, i])
            flux_w = u_w * u_w + gamma * np.abs(u_w) * u_diff_w

            duu_dx = (flux_e - flux_w) / dx

            # 2. d(v*u)/dy: horizontal cell faces at j and j+1
            # v at top corner (j+1, i)
            v_n = 0.5 * (v[j + 1, i - 1] + v[j + 1, i])
            u_n = 0.5 * (u[j, i] + u[jp1, i])
            u_diff_n = 0.5 * (u[j, i] - u[jp1, i])
            flux_n = v_n * u_n + gamma * np.abs(v_n) * u_diff_n

            # v at bottom corner (j, i)
            v_s = 0.5 * (v[j, i - 1] + v[j, i])
            u_s = 0.5 * (u[jm1, i] + u[j, i])
            u_diff_s = 0.5 * (u[jm1, i] - u[j, i])
            flux_s = v_s * u_s + gamma * np.abs(v_s) * u_diff_s

            dvu_dy = (flux_n - flux_s) / dy

            adv_u[j, i] = -(duu_dx + dvu_dy)

    return adv_u


@njit(fastmath=True, cache=True)
def compute_advection_v(
    u: np.ndarray,
    v: np.ndarray,
    dx: float,
    dy: float,
    gamma: float = 0.25,
    periodic_y: bool = False
) -> np.ndarray:
    """Compute advection of v: dv_dt = - [ d(u*v)/dx + d(v*v)/dy ] on horizontal faces.

    Args:
        u: shape (ny, nx + 1)
        v: shape (ny + 1, nx)
        dx: grid spacing x
        dy: grid spacing y
        gamma: upwind blending parameter
        periodic_y: whether y-boundary is periodic

    Returns:
        adv_v: shape (ny + 1, nx), zeros at boundaries where Dirichlet applies
    """
    ny_plus_1, nx = v.shape
    ny = ny_plus_1 - 1
    adv_v = np.zeros_like(v)

    # Interior v faces: j from 1 to ny - 1, i from 0 to nx - 1
    j_start = 0 if periodic_y else 1
    j_end = ny_plus_1 if periodic_y else ny

    for j in range(j_start, j_end):
        actual_j = j % ny if periodic_y else j
        jm1 = (actual_j - 1 + ny) % ny if periodic_y else actual_j - 1
        jp1 = (actual_j + 1) % ny if periodic_y else actual_j + 1

        for i in range(nx):
            ip1 = min(i + 1, nx - 1)
            im1 = max(i - 1, 0)

            # 1. d(u*v)/dx: vertical cell faces at i and i+1
            # u at east corner (j, i+1)
            u_e = 0.5 * (u[jm1, i + 1] + u[actual_j if actual_j < ny else ny - 1, i + 1])
            v_e = 0.5 * (v[actual_j, i] + v[actual_j, ip1])
            v_diff_e = 0.5 * (v[actual_j, i] - v[actual_j, ip1])
            flux_e = u_e * v_e + gamma * np.abs(u_e) * v_diff_e

            # u at west corner (j, i)
            u_w = 0.5 * (u[jm1, i] + u[actual_j if actual_j < ny else ny - 1, i])
            v_w = 0.5 * (v[actual_j, im1] + v[actual_j, i])
            v_diff_w = 0.5 * (v[actual_j, im1] - v[actual_j, i])
            flux_w = u_w * v_w + gamma * np.abs(u_w) * v_diff_w

            duv_dx = (flux_e - flux_w) / dx

            # 2. d(v*v)/dy: cell centers at j-1 and j
            # v_north (at cell center j)
            v_n = 0.5 * (v[actual_j, i] + v[jp1 if not periodic_y else (actual_j + 1) % (ny + 1), i])
            v_diff_n = 0.5 * (v[actual_j, i] - v[jp1 if not periodic_y else (actual_j + 1) % (ny + 1), i])
            flux_n = v_n * v_n + gamma * np.abs(v_n) * v_diff_n

            # v_south (at cell center j-1)
            v_s = 0.5 * (v[jm1, i] + v[actual_j, i])
            v_diff_s = 0.5 * (v[jm1, i] - v[actual_j, i])
            flux_s = v_s * v_s + gamma * np.abs(v_s) * v_diff_s

            dvv_dy = (flux_n - flux_s) / dy

            adv_v[actual_j, i] = -(duv_dx + dvv_dy)

    if periodic_y:
        # Wrap boundary face
        adv_v[ny, :] = adv_v[0, :]

    return adv_v
