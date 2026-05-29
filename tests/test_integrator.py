import numpy as np
import pytest
from physics.integrator import leapfrog_step, compute_acceleration
from physics.dark_matter import NFWProfile

def _solar_only_accel(pos, t, nfw=None):
    return compute_acceleration(pos, t, nfw)

def test_circular_orbit_energy_conservation():
    """
    A comet on a circular orbit should conserve energy over one full period.
    Uses G=4π², M_sun=1: circular velocity at r=1 AU is 2π AU/yr, period=1 yr.
    """
    from physics.constants import G, M_SUN
    r = 1.0  # AU
    v_circ = np.sqrt(G * M_SUN / r)  # 2π AU/yr
    pos = np.array([r, 0.0, 0.0])
    vel = np.array([0.0, v_circ, 0.0])

    dt = 0.001  # years
    n_steps = 1000  # one full orbit

    E0 = 0.5 * np.dot(vel, vel) - G * M_SUN / np.linalg.norm(pos)

    for i in range(n_steps):
        t = i * dt
        pos, vel = leapfrog_step(pos, vel, dt, t, nfw=None)

    E1 = 0.5 * np.dot(vel, vel) - G * M_SUN / np.linalg.norm(pos)
    # Energy conservation: < 0.01% drift
    assert abs((E1 - E0) / E0) < 1e-4

def test_leapfrog_step_returns_correct_shapes():
    pos = np.array([1.0, 0.0, 0.0])
    vel = np.array([0.0, 6.28, 0.0])
    new_pos, new_vel = leapfrog_step(pos, vel, 0.001, 0.0, nfw=None)
    assert new_pos.shape == (3,)
    assert new_vel.shape == (3,)

def test_dark_matter_changes_trajectory():
    """With dark matter, a comet's z-position should change differently than without."""
    from physics.bodies import comet_initial_conditions
    pos, vel = comet_initial_conditions(50000.0, 0.9999, 30.0)
    pos_dm = pos.copy()
    vel_dm = vel.copy()

    nfw = NFWProfile(rho0_gev_cm3=10.0, rs_kpc=20.0)  # exaggerated for test
    dt = 100.0  # years
    n = 500

    pos_nodm = pos.copy()
    vel_nodm = vel.copy()

    for i in range(n):
        t = i * dt
        pos_nodm, vel_nodm = leapfrog_step(pos_nodm, vel_nodm, dt, t, nfw=None)
        pos_dm, vel_dm = leapfrog_step(pos_dm, vel_dm, dt, t, nfw=nfw)

    # With dark matter, z-component of position should differ by at least 1 AU
    # (absolute check: relative check fails because positions are ~millions of AU)
    assert abs(pos_nodm[2] - pos_dm[2]) > 1.0
