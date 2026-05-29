from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
import numpy as np

from physics.bodies import comet_initial_conditions, orbital_period_years
from physics.dark_matter import NFWProfile
from physics.integrator import leapfrog_step


@dataclass
class SimulationParams:
    rho0_gev_cm3: float
    rs_kpc: float
    semi_major_axis_au: float
    eccentricity: float
    inclination_deg: float
    duration_years: float | None   # None → one orbital period
    timestep_years: float
    n_output_points: int = 10_000


def run_simulation(
    params: SimulationParams,
    progress_cb: Callable[[int], None] | None,
) -> dict:
    """
    Run the comet orbit simulation twice: with and without dark matter.

    progress_cb: called with integer 0-100 as simulation progresses.

    Returns dict with keys:
        trajectory_with_dm:    list of [x, y, z] (AU), length = n_output_points
        trajectory_without_dm: list of [x, y, z] (AU)
        time_years:            list of float
        metadata:              dict with period_years, perihelion_au
    """
    period = orbital_period_years(params.semi_major_axis_au)
    duration = params.duration_years if params.duration_years is not None else period
    dt = params.timestep_years
    n_steps = max(1, int(duration / dt))

    # Output every k-th step so we get ≤ n_output_points
    stride = max(1, n_steps // params.n_output_points)

    nfw = NFWProfile(params.rho0_gev_cm3, params.rs_kpc)

    pos0, vel0 = comet_initial_conditions(
        params.semi_major_axis_au,
        params.eccentricity,
        params.inclination_deg,
    )

    traj_dm: list[list[float]] = []
    traj_nodm: list[list[float]] = []
    times: list[float] = []

    # Integrate both trajectories in lock-step
    pos_dm, vel_dm = pos0.copy(), vel0.copy()
    pos_nodm, vel_nodm = pos0.copy(), vel0.copy()
    t = 0.0
    min_r = np.linalg.norm(pos0)

    last_pct = -1
    for i in range(n_steps):
        if i % stride == 0:
            traj_dm.append(pos_dm.tolist())
            traj_nodm.append(pos_nodm.tolist())
            times.append(t)

        pos_dm, vel_dm = leapfrog_step(pos_dm, vel_dm, dt, t, nfw)
        pos_nodm, vel_nodm = leapfrog_step(pos_nodm, vel_nodm, dt, t, None)
        t += dt

        r = np.linalg.norm(pos_nodm)
        if r < min_r:
            min_r = r

        if progress_cb is not None:
            pct = int(100 * i / n_steps)
            if pct != last_pct:
                progress_cb(pct)
                last_pct = pct

    if progress_cb is not None:
        progress_cb(100)

    return {
        "trajectory_with_dm": traj_dm,
        "trajectory_without_dm": traj_nodm,
        "time_years": times,
        "metadata": {
            "period_years": period,
            "perihelion_au": round(min_r, 3),
        },
    }
