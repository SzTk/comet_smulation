import numpy as np
from physics.constants import G, M_SUN, M_JUPITER, M_SATURN
from physics.bodies import jupiter_position, saturn_position
from physics.dark_matter import NFWProfile


def compute_acceleration(
    pos: np.ndarray,
    t: float,
    nfw: NFWProfile | None,
) -> np.ndarray:
    """
    Total gravitational acceleration on the comet at position pos (AU) and
    time t (years).

    Contributions:
    - Sun (fixed at origin)
    - Jupiter (analytical circular orbit)
    - Saturn (analytical circular orbit)
    - NFW dark matter tidal force (if nfw is not None)

    Returns acceleration in AU/yr².
    """
    # Solar gravity
    r = np.linalg.norm(pos)
    a = -G * M_SUN / r**3 * pos

    # Jupiter
    jup = jupiter_position(t)
    d_jup = pos - jup
    a += -G * M_JUPITER / np.linalg.norm(d_jup)**3 * d_jup

    # Saturn
    sat = saturn_position(t)
    d_sat = pos - sat
    a += -G * M_SATURN / np.linalg.norm(d_sat)**3 * d_sat

    # Dark matter tidal acceleration
    if nfw is not None:
        a += nfw.tidal_acceleration(pos)

    return a


def leapfrog_step(
    pos: np.ndarray,
    vel: np.ndarray,
    dt: float,
    t: float,
    nfw: NFWProfile | None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    One Velocity Verlet (leapfrog) step.

    pos: comet position (AU)
    vel: comet velocity (AU/yr)
    dt:  timestep (years)
    t:   current time (years), for planet positions
    nfw: NFW profile or None

    Returns: (new_pos, new_vel)
    """
    a0 = compute_acceleration(pos, t, nfw)
    vel_half = vel + 0.5 * dt * a0
    new_pos = pos + dt * vel_half
    a1 = compute_acceleration(new_pos, t + dt, nfw)
    new_vel = vel_half + 0.5 * dt * a1
    return new_pos, new_vel
