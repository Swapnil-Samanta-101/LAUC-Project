"""1976 International Standard Atmosphere (ISA) and Flight Dynamics Calculator.

Computes atmospheric properties (temperature, pressure, density, viscosity)
as a function of altitude, derives Reynolds and Mach numbers for flight conditions,
and converts dimensionless lift and drag coefficients (Cl, Cd) to dimensional forces (Newtons).
"""

import math
from typing import Dict, Tuple


class InternationalStandardAtmosphere:
    """Standard 1976 ISA model up to 20,000 meters."""

    # Sea level constants
    T0: float = 288.15        # Sea-level standard temperature [K]
    P0: float = 101325.0      # Sea-level standard pressure [Pa]
    RHO0: float = 1.225       # Sea-level standard density [kg/m^3]
    R_SPECIFIC: float = 287.05287  # Specific gas constant for dry air [J/(kg*K)]
    GAMMA: float = 1.4        # Ratio of specific heats
    G0: float = 9.80665       # Standard gravitational acceleration [m/s^2]
    LAPSE_RATE: float = 0.0065  # Troposphere temperature lapse rate [K/m]
    H_TROPO: float = 11000.0  # Troposphere upper boundary [m]

    # Sutherland's law constants for dynamic viscosity
    MU0: float = 1.7894e-5    # Reference viscosity at T0 [kg/(m*s)]
    S_SUTHERLAND: float = 110.4  # Sutherland temperature constant [K]

    @classmethod
    def dynamic_viscosity(cls, temperature_k: float) -> float:
        """Compute dynamic viscosity mu [kg/(m*s)] using Sutherland's law."""
        t = max(100.0, temperature_k)
        return cls.MU0 * ((t / cls.T0) ** 1.5) * ((cls.T0 + cls.S_SUTHERLAND) / (t + cls.S_SUTHERLAND))

    @classmethod
    def compute_properties(cls, altitude_m: float) -> Dict[str, float]:
        """Compute ISA atmospheric state at a given geopotential altitude in meters.

        Args:
            altitude_m: Geopotential altitude in meters (-500 to 25,000 m).

        Returns:
            Dictionary containing:
                - altitude_m: altitude in meters
                - temperature_k: ambient temperature [K]
                - temperature_c: ambient temperature [°C]
                - pressure_pa: ambient static pressure [Pa]
                - density_kg_m3: air density [kg/m^3]
                - dynamic_viscosity: dynamic viscosity mu [kg/(m*s)]
                - kinematic_viscosity: kinematic viscosity nu [m^2/s]
                - speed_of_sound_mps: speed of sound [m/s]
        """
        h = max(-500.0, min(float(altitude_m), 25000.0))

        if h <= cls.H_TROPO:
            # Troposphere: linear temperature decrease
            t = cls.T0 - cls.LAPSE_RATE * h
            p = cls.P0 * ((t / cls.T0) ** (cls.G0 / (cls.R_SPECIFIC * cls.LAPSE_RATE)))
        else:
            # Lower stratosphere (isothermal layer 11 km to 20 km)
            t_tropo = cls.T0 - cls.LAPSE_RATE * cls.H_TROPO  # ~216.65 K
            p_tropo = cls.P0 * ((t_tropo / cls.T0) ** (cls.G0 / (cls.R_SPECIFIC * cls.LAPSE_RATE)))
            delta_h = h - cls.H_TROPO
            exponent = -cls.G0 * delta_h / (cls.R_SPECIFIC * t_tropo)
            p = p_tropo * math.exp(exponent)
            t = t_tropo

        rho = p / (cls.R_SPECIFIC * t)
        mu = cls.dynamic_viscosity(t)
        nu = mu / rho
        a = math.sqrt(cls.GAMMA * cls.R_SPECIFIC * t)

        return {
            "altitude_m": round(h, 1),
            "temperature_k": round(t, 2),
            "temperature_c": round(t - 273.15, 2),
            "pressure_pa": round(p, 1),
            "density_kg_m3": round(rho, 5),
            "dynamic_viscosity": mu,
            "kinematic_viscosity": nu,
            "speed_of_sound_mps": round(a, 2)
        }

    @classmethod
    def compute_flight_conditions(
        cls,
        altitude_m: float = 0.0,
        airspeed_mps: float = 40.0,
        chord_m: float = 1.0,
        wing_area_m2: float = 1.0
    ) -> Dict[str, float]:
        """Compute full aerodynamic flight conditions including Reynolds number and dynamic pressure.

        Args:
            altitude_m: Altitude in meters.
            airspeed_mps: True airspeed V_inf in m/s.
            chord_m: Aerodynamic chord length c in meters.
            wing_area_m2: Reference wing area S in m^2.

        Returns:
            Dictionary with atmospheric metrics, dynamic pressure, Reynolds number, and Mach.
        """
        props = cls.compute_properties(altitude_m)
        v = max(0.1, float(airspeed_mps))
        c = max(0.01, float(chord_m))
        s = max(0.01, float(wing_area_m2))

        rho = props["density_kg_m3"]
        nu = props["kinematic_viscosity"]
        a = props["speed_of_sound_mps"]

        q_inf = 0.5 * rho * (v ** 2)
        reynolds = (v * c) / nu
        mach = v / a

        return {
            **props,
            "airspeed_mps": round(v, 2),
            "chord_m": round(c, 3),
            "wing_area_m2": round(s, 3),
            "q_inf_pa": round(q_inf, 2),
            "reynolds": round(reynolds, 1),
            "mach": round(mach, 4)
        }

    @classmethod
    def compute_dimensional_forces(
        cls,
        cl: float,
        cd: float,
        q_inf_pa: float,
        wing_area_m2: float = 1.0
    ) -> Tuple[float, float]:
        """Convert dimensionless lift and drag coefficients (Cl, Cd) into Newtons.

        Lift: L = Cl * q_inf * S
        Drag: D = Cd * q_inf * S
        """
        lift_n = float(cl) * float(q_inf_pa) * float(wing_area_m2)
        drag_n = float(cd) * float(q_inf_pa) * float(wing_area_m2)
        return lift_n, drag_n
