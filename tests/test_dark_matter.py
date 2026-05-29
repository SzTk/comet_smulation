import numpy as np
import pytest
from physics.dark_matter import NFWProfile

def test_zero_dark_matter_gives_zero_density():
    nfw = NFWProfile(rho0_gev_cm3=0.0, rs_kpc=20.0)
    assert nfw.density_at_r(1.0e9) == 0.0

def test_density_decreases_with_radius():
    nfw = NFWProfile(rho0_gev_cm3=0.3, rs_kpc=20.0)
    r_inner = 1.0e8   # AU (~0.5 kpc)
    r_outer = 4.0e8   # AU (~2 kpc)
    assert nfw.density_at_r(r_inner) > nfw.density_at_r(r_outer)

def test_mass_enclosed_positive_and_increasing():
    nfw = NFWProfile(rho0_gev_cm3=0.3, rs_kpc=20.0)
    r1 = 1.0e9   # AU
    r2 = 2.0e9   # AU
    assert nfw.mass_enclosed(r1) > 0
    assert nfw.mass_enclosed(r2) > nfw.mass_enclosed(r1)

def test_tidal_acceleration_zero_when_rho0_zero():
    nfw = NFWProfile(rho0_gev_cm3=0.0, rs_kpc=20.0)
    pos = np.array([50000.0, 0.0, 0.0])
    a = nfw.tidal_acceleration(pos)
    np.testing.assert_array_equal(a, np.zeros(3))

def test_tidal_acceleration_vertical_dominates():
    """Vertical (z) tidal component should be non-zero and restoring for galactic halo"""
    nfw = NFWProfile(rho0_gev_cm3=0.3, rs_kpc=20.0)
    # Comet at 50000 AU in z direction
    pos = np.array([0.0, 0.0, 50000.0])
    a = nfw.tidal_acceleration(pos)
    # z-component should be non-zero and opposing z displacement (restoring)
    assert a[2] < 0  # toward galactic plane

def test_tidal_acceleration_scales_with_position():
    nfw = NFWProfile(rho0_gev_cm3=0.3, rs_kpc=20.0)
    pos1 = np.array([0.0, 0.0, 25000.0])
    pos2 = np.array([0.0, 0.0, 50000.0])
    a1 = nfw.tidal_acceleration(pos1)
    a2 = nfw.tidal_acceleration(pos2)
    # Double the distance → approximately double the tidal force
    assert abs(a2[2]) > abs(a1[2])
