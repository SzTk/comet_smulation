import numpy as np

# Gravitational constant in AU³/(M☉·yr²)
# Derived from: 1 AU³/(M☉·yr²) = 4π² by Kepler's third law
G = 4.0 * np.pi**2

# Unit conversions
KPC_TO_AU = 206_264_806.0          # AU per kiloparsec
GEV_CM3_TO_MSUN_AU3 = 3.0e-18     # M☉/AU³ per GeV/cm³

# Solar system galactocentric distance
R_SUN_KPC = 8.0                    # kpc from galactic center

# Planet masses
M_SUN = 1.0                        # M☉
M_JUPITER = 9.548e-4               # M☉ (= 1/1047 M☉)
M_SATURN = 2.858e-4                # M☉ (= 1/3497 M☉)

# Planet orbital parameters (circular approximation)
JUPITER_A_AU = 5.2                 # AU
JUPITER_T_YR = 11.86               # years

SATURN_A_AU = 9.54                 # AU
SATURN_T_YR = 29.46                # years
