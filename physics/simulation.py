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
    dt_base = params.timestep_years

    # Adaptive timestep: small near perihelion, base value far away.
    # dt_eff = min(dt_base, dt_peri * (r / r_peri)^1.5)
    # This ensures perihelion crossing is resolved without increasing
    # total step count significantly (the orbit spends little time near perihelion).
    r_peri = params.semi_major_axis_au * (1.0 - params.eccentricity)
    # Adaptive perihelion timestep: scales with r_peri^1.5 (Keplerian dynamical time).
    # For e→1, the orbit is nearly parabolic and KE/E_bind >> 1, making numerical
    # accuracy extremely sensitive near perihelion.  When r_peri < ~100 AU (Jupiter
    # or inner system region), the comet may be physically scattered by Jupiter,
    # producing chaotic multi-perihelion trajectories that inflate step counts.
    # r_peri^1.5/5000 balances accuracy (~1-5% orbital energy error) and speed.
    dt_peri = max(0.001, r_peri ** 1.5 / 5000.0)

    # Safety: prevent API timeout from chaotic scattering (e.g. e≈1, perihelion near Jupiter)
    MAX_STEPS = 500_000

    output_interval = duration / params.n_output_points

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
    next_output_t = 0.0
    last_pct = -1

    truncated = False
    step = 0
    while t < duration:
        if step >= MAX_STEPS:
            truncated = True
            break

        if t >= next_output_t:
            traj_dm.append(pos_dm.tolist())
            traj_nodm.append(pos_nodm.tolist())
            times.append(t)
            next_output_t += output_interval

        r = np.linalg.norm(pos_nodm)
        # Floor at dt_peri prevents dt→0 if Jupiter scatters comet closer than r_peri
        dt_eff = max(dt_peri, min(dt_base, dt_peri * (r / r_peri) ** 1.5))

        pos_dm, vel_dm = leapfrog_step(pos_dm, vel_dm, dt_eff, t, nfw)
        pos_nodm, vel_nodm = leapfrog_step(pos_nodm, vel_nodm, dt_eff, t, None)
        t += dt_eff
        step += 1

        r_new = np.linalg.norm(pos_nodm)
        if r_new < min_r:
            min_r = r_new

        if progress_cb is not None:
            pct = int(100 * t / duration)
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
            "truncated": truncated,
            "perihelion_au": round(min_r, 3),
        },
    }
