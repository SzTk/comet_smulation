import numpy as np
from physics.constants import G, KPC_TO_AU, GEV_CM3_TO_MSUN_AU3, R_SUN_KPC


class NFWProfile:
    """
    Navarro-Frenk-White dark matter halo profile.
    ρ(r) = ρ₀ / [(r/rs)(1 + r/rs)²]

    Provides galactic tidal acceleration on bodies in the solar system.
    """

    def __init__(self, rho0_gev_cm3: float, rs_kpc: float):
        # Store in simulation units: M☉/AU³ and AU
        self.rho0 = rho0_gev_cm3 * GEV_CM3_TO_MSUN_AU3  # M☉/AU³
        self.rs = rs_kpc * KPC_TO_AU                      # AU
        self.rho0_gev_cm3 = rho0_gev_cm3
        self.rs_kpc = rs_kpc

    def density_at_r(self, r_au: float) -> float:
        """NFW density at galactocentric radius r (AU), returns M☉/AU³."""
        if self.rho0 == 0.0 or r_au <= 0.0:
            return 0.0
        x = r_au / self.rs
        return self.rho0 / (x * (1.0 + x) ** 2)

    def mass_enclosed(self, r_au: float) -> float:
        """Total dark matter mass enclosed within radius r (AU), in M☉."""
        if self.rho0 == 0.0 or r_au <= 0.0:
            return 0.0
        x = r_au / self.rs
        return (4.0 * np.pi * self.rho0 * self.rs**3
                * (np.log(1.0 + x) - x / (1.0 + x)))

    def tidal_acceleration(
        self, pos_helio: np.ndarray, r_sun_kpc: float = R_SUN_KPC
    ) -> np.ndarray:
        """
        Galactic tidal acceleration on a body at heliocentric position pos_helio (AU).

        Coordinate system: x = toward galactic center, z = perpendicular to
        galactic plane.

        Uses the NFW tidal tensor evaluated at the Sun's galactocentric position:
            T_RR = 4πGρ_local - 2GM(R_sun)/R_sun³    (radial)
            T_tt = GM(R_sun)/R_sun³                    (transverse, including z)

        Tidal acceleration: a_i = -T_ii * pos_i
        """
        if self.rho0 == 0.0:
            return np.zeros(3)

        r_sun_au = r_sun_kpc * KPC_TO_AU
        rho_local = self.density_at_r(r_sun_au)
        m_enclosed = self.mass_enclosed(r_sun_au)

        t_rr = 4.0 * np.pi * G * rho_local - 2.0 * G * m_enclosed / r_sun_au**3
        t_tt = G * m_enclosed / r_sun_au**3

        return np.array([
            -t_rr * pos_helio[0],  # radial (toward galactic center)
            -t_tt * pos_helio[1],  # transverse
            -t_tt * pos_helio[2],  # vertical (perpendicular to galactic plane)
        ])
