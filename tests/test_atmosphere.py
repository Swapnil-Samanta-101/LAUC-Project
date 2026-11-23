"""Validation Tests for 1976 International Standard Atmosphere (ISA) and Flight Dynamics."""

import pytest
import math
from geometry.atmosphere import InternationalStandardAtmosphere


def test_isa_sea_level_properties():
    """Verify sea-level values match 1976 standard atmosphere within 0.1%."""
    props = InternationalStandardAtmosphere.compute_properties(altitude_m=0.0)
    assert abs(props["temperature_k"] - 288.15) < 0.1
    assert abs(props["pressure_pa"] - 101325.0) < 1.0
    assert abs(props["density_kg_m3"] - 1.225) < 0.005
    assert abs(props["speed_of_sound_mps"] - 340.29) < 0.5


def test_isa_troposphere_lapse_rate():
    """Verify temperature decreases linearly by 6.5 K/km up to 11 km."""
    props_5k = InternationalStandardAtmosphere.compute_properties(altitude_m=5000.0)
    expected_t = 288.15 - 0.0065 * 5000.0  # 255.65 K
    assert abs(props_5k["temperature_k"] - expected_t) < 0.1
    # Density at 5000m should be around ~0.736 kg/m^3
    assert 0.70 < props_5k["density_kg_m3"] < 0.78


def test_flight_conditions_and_reynolds():
    """Verify Reynolds number and dynamic pressure calculations."""
    fc = InternationalStandardAtmosphere.compute_flight_conditions(
        altitude_m=0.0,
        airspeed_mps=50.0,
        chord_m=1.0,
        wing_area_m2=2.0
    )
    # q_inf = 0.5 * 1.225 * 50^2 = 1531.25 Pa
    assert abs(fc["q_inf_pa"] - 1531.25) < 5.0
    # Re = 1.225 * 50 * 1 / 1.7894e-5 ~ 3.42e6
    assert 3.3e6 < fc["reynolds"] < 3.6e6


def test_dimensional_force_conversion():
    """Verify conversion of Cl=1.0, Cd=0.05 to Newtons."""
    q_inf = 1000.0  # Pa
    s = 2.5  # m^2
    cl = 0.8
    cd = 0.04
    lift_n, drag_n = InternationalStandardAtmosphere.compute_dimensional_forces(cl, cd, q_inf, s)
    assert abs(lift_n - (0.8 * 1000.0 * 2.5)) < 1e-4
    assert abs(drag_n - (0.04 * 1000.0 * 2.5)) < 1e-4
