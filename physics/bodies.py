import numpy as np
from physics.constants import G, M_SUN, JUPITER_A_AU, JUPITER_T_YR, SATURN_A_AU, SATURN_T_YR


def orbital_period_years(semi_major_axis_au: float) -> float:
    """Keplerian orbital period in years. T = a^1.5 for M_sun = 1 M☉."""
    return semi_major_axis_au**1.5


def comet_initial_conditions(
    semi_major_axis_au: float,
    eccentricity: float,
    inclination_deg: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return (position, velocity) for a comet starting at perihelion.

    Position is in the orbital plane, then rotated by inclination about the
    y-axis (so the ascending node is along x, perihelion in the x-y plane
    rotated into x-z plane by inclination).

    Returns:
        pos: (3,) AU
        vel: (3,) AU/yr
    """
    r_peri = semi_major_axis_au * (1.0 - eccentricity)  # AU

    # Perihelion speed from vis-viva: v² = GM(2/r - 1/a)
    v_peri = np.sqrt(G * M_SUN * (2.0 / r_peri - 1.0 / semi_major_axis_au))

    # In orbital plane: position along x, velocity along y
    pos_orb = np.array([r_peri, 0.0, 0.0])
    vel_orb = np.array([0.0, v_peri, 0.0])

    # Rotate by inclination about y-axis
    inc = np.radians(inclination_deg)
    cos_i, sin_i = np.cos(inc), np.sin(inc)
    R = np.array([
        [cos_i,  0.0, sin_i],
        [0.0,    1.0, 0.0  ],
        [-sin_i, 0.0, cos_i],
    ])
    return R @ pos_orb, R @ vel_orb


def jupiter_position(t_years: float) -> np.ndarray:
    """Jupiter's position at time t (years). Circular orbit in the x-y plane."""
    omega = 2.0 * np.pi / JUPITER_T_YR
    return np.array([
        JUPITER_A_AU * np.cos(omega * t_years),
        JUPITER_A_AU * np.sin(omega * t_years),
        0.0,
    ])


def saturn_position(t_years: float) -> np.ndarray:
    """Saturn's position at time t (years). Circular orbit in the x-y plane."""
    omega = 2.0 * np.pi / SATURN_T_YR
    return np.array([
        SATURN_A_AU * np.cos(omega * t_years),
        SATURN_A_AU * np.sin(omega * t_years),
        0.0,
    ])
