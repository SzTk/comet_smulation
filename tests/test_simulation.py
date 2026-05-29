import numpy as np
import pytest
from physics.simulation import run_simulation, SimulationParams

def test_simulation_returns_expected_keys():
    params = SimulationParams(
        rho0_gev_cm3=0.3,
        rs_kpc=20.0,
        semi_major_axis_au=500.0,
        eccentricity=0.99,
        inclination_deg=0.0,
        duration_years=None,
        timestep_years=10.0,
        n_output_points=100,
    )
    result = run_simulation(params, progress_cb=None)
    assert "trajectory_with_dm" in result
    assert "trajectory_without_dm" in result
    assert "time_years" in result
    assert "metadata" in result

def test_simulation_trajectory_shapes_match():
    params = SimulationParams(
        rho0_gev_cm3=0.3, rs_kpc=20.0,
        semi_major_axis_au=500.0, eccentricity=0.99,
        inclination_deg=0.0, duration_years=None,
        timestep_years=10.0, n_output_points=50,
    )
    result = run_simulation(params, progress_cb=None)
    n = len(result["time_years"])
    assert len(result["trajectory_with_dm"]) == n
    assert len(result["trajectory_without_dm"]) == n

def test_simulation_dm_zero_matches_no_dm():
    """When rho0=0, both trajectories should be identical."""
    params = SimulationParams(
        rho0_gev_cm3=0.0, rs_kpc=20.0,
        semi_major_axis_au=500.0, eccentricity=0.99,
        inclination_deg=0.0, duration_years=None,
        timestep_years=10.0, n_output_points=50,
    )
    result = run_simulation(params, progress_cb=None)
    np.testing.assert_allclose(
        result["trajectory_with_dm"],
        result["trajectory_without_dm"],
        rtol=1e-10,
    )

def test_duration_defaults_to_orbital_period():
    from physics.bodies import orbital_period_years
    params = SimulationParams(
        rho0_gev_cm3=0.3, rs_kpc=20.0,
        semi_major_axis_au=500.0, eccentricity=0.99,
        inclination_deg=0.0, duration_years=None,
        timestep_years=10.0, n_output_points=50,
    )
    result = run_simulation(params, progress_cb=None)
    expected_period = orbital_period_years(500.0)
    assert abs(result["metadata"]["period_years"] - expected_period) < 1.0

def test_progress_callback_called():
    calls = []
    def cb(pct): calls.append(pct)
    params = SimulationParams(
        rho0_gev_cm3=0.3, rs_kpc=20.0,
        semi_major_axis_au=500.0, eccentricity=0.99,
        inclination_deg=0.0, duration_years=None,
        timestep_years=10.0, n_output_points=20,
    )
    run_simulation(params, progress_cb=cb)
    assert len(calls) > 0
    assert calls[-1] == 100
