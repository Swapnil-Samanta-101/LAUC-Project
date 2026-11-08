"""Analytical NACA 4-Digit Airfoil Geometry Generator.

Implements standard NACA 4-digit profiles with camber, thickness,
chord scaling, quarter-chord center placement, and angle of attack rotation.
"""

from typing import Tuple, List
import numpy as np


def parse_naca_4digit(code: str) -> Tuple[float, float, float]:
    """Parse a 4-digit NACA string (e.g. '0012', '2412', '4412').

    Returns:
        (m, p, t):
          m: maximum camber as fraction of chord (e.g., 0.02 for '2412')
          p: location of maximum camber as fraction of chord (e.g., 0.4 for '2412')
          t: maximum thickness as fraction of chord (e.g., 0.12 for '0012' or '2412')
    """
    clean_code = code.strip().replace("NACA", "").replace("naca", "").strip()
    if len(clean_code) != 4 or not clean_code.isdigit():
        # Default fallback to NACA 0012
        return 0.0, 0.0, 0.12

    m = float(clean_code[0]) / 100.0
    p = float(clean_code[1]) / 10.0
    t = float(clean_code[2:]) / 100.0
    return m, p, t


class NACA4Airfoil:
    """Generates coordinate points and closed polygon for a NACA 4-digit airfoil."""

    def __init__(
        self,
        code: str = "0012",
        chord: float = 1.0,
        x_origin: float = 1.0,
        y_origin: float = 1.0,
        alpha_deg: float = 0.0,
        n_points: int = 150
    ) -> None:
        self.code = code
        self.chord = float(chord)
        self.x_origin = float(x_origin)
        self.y_origin = float(y_origin)
        self.alpha_deg = float(alpha_deg)
        self.n_points = int(n_points)

        self.m, self.p, self.t = parse_naca_4digit(code)
        self.polygon = self._generate_polygon()

    def _generate_polygon(self) -> np.ndarray:
        """Compute closed (N, 2) polygon representing the rotated airfoil."""
        # Non-linear cosine distribution of x/c for higher resolution at leading/trailing edges
        beta = np.linspace(0.0, np.pi, self.n_points)
        xc = 0.5 * (1.0 - np.cos(beta))  # x / chord from 0 to 1

        # Half-thickness distribution y_t
        yt = 5.0 * self.t * (
            0.2969 * np.sqrt(xc)
            - 0.1260 * xc
            - 0.3516 * (xc ** 2)
            + 0.2843 * (xc ** 3)
            - 0.1015 * (xc ** 4)
        )

        # Camber line yc and gradient dyc/dx
        yc = np.zeros_like(xc)
        dyc_dx = np.zeros_like(xc)

        if self.m > 0.0 and self.p > 0.0:
            for idx, x_val in enumerate(xc):
                if x_val < self.p:
                    yc[idx] = (self.m / (self.p ** 2)) * (2.0 * self.p * x_val - x_val ** 2)
                    dyc_dx[idx] = (2.0 * self.m / (self.p ** 2)) * (self.p - x_val)
                else:
                    yc[idx] = (self.m / ((1.0 - self.p) ** 2)) * (
                        (1.0 - 2.0 * self.p) + 2.0 * self.p * x_val - x_val ** 2
                    )
                    dyc_dx[idx] = (2.0 * self.m / ((1.0 - self.p) ** 2)) * (self.p - x_val)

        theta = np.arctan(dyc_dx)

        # Upper and lower coordinates (in chord units)
        xu = xc - yt * np.sin(theta)
        yu = yc + yt * np.cos(theta)

        xl = xc + yt * np.sin(theta)
        yl = yc - yt * np.cos(theta)

        # Scale by chord and position leading edge at (x_origin, y_origin)
        xu = self.x_origin + xu * self.chord
        yu = self.y_origin + yu * self.chord
        xl = self.x_origin + xl * self.chord
        yl = self.y_origin + yl * self.chord

        # Rotate around quarter-chord point (x_qc, y_qc)
        x_qc = self.x_origin + 0.25 * self.chord
        y_qc = self.y_origin
        alpha_rad = np.radians(self.alpha_deg)
        cos_a = np.cos(alpha_rad)
        sin_a = np.sin(alpha_rad)

        def rotate(x_arr: np.ndarray, y_arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
            dx = x_arr - x_qc
            dy = y_arr - y_qc
            # Standard aerodynamic angle of attack: positive alpha pitches nose UP (leading edge moves +y)
            # which rotates clockwise around quarter chord
            x_rot = x_qc + (dx * cos_a + dy * sin_a)
            y_rot = y_qc + (-dx * sin_a + dy * cos_a)
            return x_rot, y_rot

        xu_rot, yu_rot = rotate(xu, yu)
        xl_rot, yl_rot = rotate(xl, yl)

        # Build closed polygon: trailing edge -> upper surface -> leading edge -> lower surface -> trailing edge
        poly_upper = np.column_stack((xu_rot[::-1], yu_rot[::-1]))
        poly_lower = np.column_stack((xl_rot[1:], yl_rot[1:]))
        closed_poly = np.vstack((poly_upper, poly_lower))

        return closed_poly
