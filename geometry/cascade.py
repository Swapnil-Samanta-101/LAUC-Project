"""Turbofan and Compressor 2D Blade-to-Blade Cascade Generator.

Models periodic linear cascades with:
- Adjustable pitch-to-chord ratio (solidity sigma = c / s)
- Stagger angle gamma
- Camber and thickness (NACA 4-digit or circular-arc profile)
- Pitchwise repeating blade representations
"""

from typing import List, Tuple
import numpy as np
from .naca import NACA4Airfoil


class TurbofanCascade:
    """Represents a 2D blade-to-blade linear cascade."""

    def __init__(
        self,
        chord: float = 1.0,
        pitch: float = 1.0,
        stagger_deg: float = 25.0,
        camber_code: str = "6412",
        domain_ly: float = 2.0,
        x_axial_pos: float = 1.0,
        inlet_flow_angle_deg: float = 30.0
    ) -> None:
        self.chord = float(chord)
        self.pitch = float(pitch)
        self.stagger_deg = float(stagger_deg)
        self.camber_code = camber_code
        self.domain_ly = float(domain_ly)
        self.x_axial_pos = float(x_axial_pos)
        self.inlet_flow_angle_deg = float(inlet_flow_angle_deg)

        self.solidity = self.chord / self.pitch

        # Compute polygons for all blades crossing the domain height Ly
        self.polygons = self._generate_blade_polygons()

    def _generate_blade_polygons(self) -> List[np.ndarray]:
        """Generate polygon vertices for each blade in the cascade across domain height Ly."""
        polys = []

        # Find blade centers in y: y_k = y_ref + k * pitch
        # Place central blade near 0.5 * Ly
        y_ref = 0.5 * self.domain_ly

        # Determine range of k so blades covering [0, Ly] plus periodic boundary wrapping are included
        k_min = int(np.floor(-y_ref / self.pitch)) - 1
        k_max = int(np.ceil((self.domain_ly - y_ref) / self.pitch)) + 1

        for k in range(k_min, k_max + 1):
            y_pos = y_ref + k * self.pitch
            # Only include if blade is within or partially intersects [0, Ly]
            if -0.5 * self.chord <= y_pos <= self.domain_ly + 0.5 * self.chord:
                # In turbomachinery, stagger angle gamma rotates the chord line
                blade = NACA4Airfoil(
                    code=self.camber_code,
                    chord=self.chord,
                    x_origin=self.x_axial_pos,
                    y_origin=y_pos,
                    alpha_deg=self.stagger_deg,
                    n_points=120
                )
                polys.append(blade.polygon)

        return polys
