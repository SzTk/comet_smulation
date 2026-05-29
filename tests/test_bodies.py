import numpy as np
import pytest
from physics.bodies import comet_initial_conditions, jupiter_position, saturn_position

def test_comet_at_perihelion_correct_distance():
    pos, vel = comet_initial_conditions(
        semi_major_axis_au=50000.0,
        eccentricity=0.9999,
        inclination_deg=0.0,
    )
    perihelion = 50000.0 * (1.0 - 0.9999)  # = 5.0 AU
    assert abs(np.linalg.norm(pos) - perihelion) < 0.01

def test_comet_velocity_perpendicular_to_radius_at_perihelion():
    pos, vel = comet_initial_conditions(50000.0, 0.9999, 0.0)
    # At perihelion the velocity is perpendicular to the position vector
    dot = np.dot(pos, vel)
    assert abs(dot) < 1e-6

def test_comet_inclination_tilts_orbit():
    pos_0, _ = comet_initial_conditions(50000.0, 0.9999, 0.0)
    pos_45, _ = comet_initial_conditions(50000.0, 0.9999, 45.0)
    # With non-zero inclination, z-component should be non-zero
    assert abs(pos_45[2]) > 0.01
    assert abs(pos_0[2]) < 1e-10

def test_jupiter_position_at_origin_of_time():
    pos = jupiter_position(0.0)
    # At t=0, Jupiter is at (a, 0, 0)
    assert abs(pos[0] - 5.2) < 1e-10
    assert abs(pos[1]) < 1e-10
    assert abs(pos[2]) < 1e-10

def test_saturn_position_one_period_returns_to_start():
    pos_0 = saturn_position(0.0)
    pos_T = saturn_position(29.46)
    np.testing.assert_allclose(pos_0, pos_T, atol=1e-6)

def test_orbital_period_from_kepler():
    from physics.bodies import orbital_period_years
    # Kepler: T = a^1.5 for M_sun=1 in AU/yr units
    assert abs(orbital_period_years(1.0) - 1.0) < 1e-6   # Earth: 1 yr
    assert abs(orbital_period_years(4.0) - 8.0) < 1e-6   # a=4 → T=8
