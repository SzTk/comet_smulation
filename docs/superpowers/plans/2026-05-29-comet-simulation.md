# Comet Simulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 3D long-period comet orbit simulator that visualizes the effect of an NFW dark matter halo on Oort cloud comet trajectories, served as a web app via FastAPI + Three.js on Azure Container Apps.

**Architecture:** Python/FastAPI backend handles Leapfrog orbit integration and NFW dark matter physics; frontend is vanilla Three.js + Chart.js served as static files from the same container. The browser POSTs simulation parameters, receives a job ID, then connects to an SSE stream for progress and trajectory data.

**Tech Stack:** Python 3.12, FastAPI, NumPy, uvicorn, Three.js (CDN), Chart.js (CDN), Docker, Azure Container Apps

---

## File Structure

```
comet_simulation/
├── main.py                    # FastAPI app: mounts API + serves /static
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── api/
│   ├── __init__.py
│   └── routes.py              # POST /simulate, GET /simulate/{id}/stream, GET /presets
├── physics/
│   ├── __init__.py
│   ├── constants.py           # G, unit conversions, planet masses/periods
│   ├── dark_matter.py         # NFWProfile: density, mass enclosed, tidal force
│   ├── bodies.py              # Comet initial conditions, planet position functions
│   ├── integrator.py          # Leapfrog step + full integration loop
│   └── simulation.py          # Orchestrate: run with DM + without DM, downsample
├── tests/
│   ├── conftest.py
│   ├── test_dark_matter.py
│   ├── test_bodies.py
│   ├── test_integrator.py
│   ├── test_simulation.py
│   └── test_routes.py
└── static/
    ├── index.html
    └── js/
        ├── api.js             # SSE client, job management
        ├── scene.js           # Three.js 3D orbit scene
        ├── nfw_chart.js       # Chart.js NFW density profile
        └── ui.js              # Parameter panel, presets, wiring
```

**Key design decisions:**
- Sun is fixed at origin (M_sun >> M_planets, valid approximation)
- Jupiter and Saturn use analytical circular orbits (positions computed from t, not integrated) — captures gravitational perturbation on comets without expensive N-body integration
- Only the comet is Leapfrog-integrated
- Dark matter enters as a galactic tidal acceleration on the comet (NFW tidal tensor evaluated at the Sun's galactocentric position)
- Simulation outputs are downsampled to ≤10,000 points for frontend performance

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `main.py`
- Create: `api/__init__.py`, `physics/__init__.py`
- Create: `static/index.html` (placeholder)

- [ ] **Step 1: Create requirements.txt**

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
numpy>=1.26.0
httpx>=0.27.0
pytest>=8.2.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 2: Create placeholder static/index.html**

```html
<!DOCTYPE html>
<html><body><h1>Comet Simulation</h1></body></html>
```

- [ ] **Step 3: Create main.py**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from api.routes import router

app = FastAPI(title="Comet Simulation")
app.include_router(router)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

- [ ] **Step 4: Create api/__init__.py and physics/__init__.py**

Both are empty files.

- [ ] **Step 5: Create minimal api/routes.py to verify startup**

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Install dependencies and verify server starts**

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Expected: Server starts at http://localhost:8000. `curl http://localhost:8000/health` returns `{"status":"ok"}`.

- [ ] **Step 7: Commit**

```bash
git add main.py requirements.txt api/ physics/ static/
git commit -m "feat: project scaffold with FastAPI and static file serving"
```

---

## Task 2: Physical Constants

**Files:**
- Create: `physics/constants.py`

- [ ] **Step 1: Write constants.py**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add physics/constants.py
git commit -m "feat: physical constants for orbit simulation"
```

---

## Task 3: NFW Dark Matter Module

**Files:**
- Create: `physics/dark_matter.py`
- Create: `tests/test_dark_matter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_dark_matter.py
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
    """Vertical (z) tidal component should exceed horizontal for galactic halo"""
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_dark_matter.py -v
```

Expected: ImportError or NameError — `NFWProfile` does not exist yet.

- [ ] **Step 3: Implement physics/dark_matter.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_dark_matter.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add physics/dark_matter.py tests/test_dark_matter.py
git commit -m "feat: NFW dark matter profile with tidal acceleration"
```

---

## Task 4: Bodies and Initial Conditions

**Files:**
- Create: `physics/bodies.py`
- Create: `tests/test_bodies.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_bodies.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_bodies.py -v
```

Expected: ImportError — `physics.bodies` does not exist.

- [ ] **Step 3: Implement physics/bodies.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_bodies.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add physics/bodies.py tests/test_bodies.py
git commit -m "feat: comet initial conditions and planet position functions"
```

---

## Task 5: Leapfrog Integrator

**Files:**
- Create: `physics/integrator.py`
- Create: `tests/test_integrator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_integrator.py
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
    """With dark matter, a comet's z-velocity should change differently than without."""
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

    # With dark matter, z-component of position should differ
    assert not np.allclose(pos_nodm[2], pos_dm[2], rtol=1e-3)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_integrator.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement physics/integrator.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_integrator.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add physics/integrator.py tests/test_integrator.py
git commit -m "feat: leapfrog integrator with solar system + NFW dark matter forces"
```

---

## Task 6: Simulation Orchestrator

**Files:**
- Create: `physics/simulation.py`
- Create: `tests/test_simulation.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_simulation.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_simulation.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement physics/simulation.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_simulation.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add physics/simulation.py tests/test_simulation.py
git commit -m "feat: simulation orchestrator with dual-trajectory output and progress callback"
```

---

## Task 7: API Routes

**Files:**
- Modify: `api/routes.py`
- Create: `tests/conftest.py`
- Create: `tests/test_routes.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
```

```python
# tests/test_routes.py
import json
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

SIMULATE_PAYLOAD = {
    "dark_matter": {"rho0": 0.3, "rs": 20.0},
    "comet": {
        "semi_major_axis_au": 500.0,
        "eccentricity": 0.99,
        "inclination_deg": 0.0,
    },
    "duration_years": None,
    "timestep_years": 50.0,
    "n_output_points": 100,
}

async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200

async def test_simulate_returns_job_id(client: AsyncClient):
    r = await client.post("/simulate", json=SIMULATE_PAYLOAD)
    assert r.status_code == 200
    data = r.json()
    assert "job_id" in data
    assert isinstance(data["job_id"], str)

async def test_stream_returns_result(client: AsyncClient):
    r = await client.post("/simulate", json=SIMULATE_PAYLOAD)
    job_id = r.json()["job_id"]

    events = []
    async with client.stream("GET", f"/simulate/{job_id}/stream") as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

    result_events = [e for e in events if e.get("type") == "result"]
    assert len(result_events) == 1
    result = result_events[0]
    assert "trajectory_with_dm" in result
    assert "trajectory_without_dm" in result

async def test_presets_returns_list(client: AsyncClient):
    r = await client.get("/presets")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 3
    names = [p["name"] for p in data]
    assert "ダークマターなし" in names
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_routes.py -v
```

Expected: Tests fail — routes don't implement `/simulate` or `/presets` yet.

- [ ] **Step 3: Implement api/routes.py**

```python
import asyncio
import uuid
from typing import Any
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from physics.simulation import SimulationParams, run_simulation

router = APIRouter()

# In-memory job store: job_id -> asyncio.Queue of SSE messages
_jobs: dict[str, asyncio.Queue] = {}

PRESETS = [
    {"name": "ダークマターなし",   "rho0": 0.0,  "rs": 20.0,
     "description": "純粋なニュートン重力のみ"},
    {"name": "標準銀河系ハロー",   "rho0": 0.3,  "rs": 20.0,
     "description": "観測値ベースの天の川銀河NFWハロー"},
    {"name": "高密度ハロー",        "rho0": 3.0,  "rs": 10.0,
     "description": "高密度・小スケール半径の極端なケース"},
]


class DarkMatterParams(BaseModel):
    rho0: float
    rs: float


class CometParams(BaseModel):
    semi_major_axis_au: float
    eccentricity: float
    inclination_deg: float


class SimulateRequest(BaseModel):
    dark_matter: DarkMatterParams
    comet: CometParams
    duration_years: float | None = None
    timestep_years: float = 100.0
    n_output_points: int = 5000


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/presets")
def get_presets():
    return PRESETS


@router.post("/simulate")
async def start_simulation(req: SimulateRequest):
    job_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _jobs[job_id] = queue

    params = SimulationParams(
        rho0_gev_cm3=req.dark_matter.rho0,
        rs_kpc=req.dark_matter.rs,
        semi_major_axis_au=req.comet.semi_major_axis_au,
        eccentricity=req.comet.eccentricity,
        inclination_deg=req.comet.inclination_deg,
        duration_years=req.duration_years,
        timestep_years=req.timestep_years,
        n_output_points=req.n_output_points,
    )

    loop = asyncio.get_event_loop()

    def run_and_enqueue():
        def progress_cb(pct: int):
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "progress", "percent": pct}), loop
            )

        result = run_simulation(params, progress_cb=progress_cb)
        result["type"] = "result"
        asyncio.run_coroutine_threadsafe(queue.put(result), loop)
        asyncio.run_coroutine_threadsafe(queue.put(None), loop)  # sentinel

    loop.run_in_executor(None, run_and_enqueue)
    return {"job_id": job_id}


@router.get("/simulate/{job_id}/stream")
async def stream_simulation(job_id: str):
    import json

    queue = _jobs.get(job_id)
    if queue is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        while True:
            msg = await queue.get()
            if msg is None:
                _jobs.pop(job_id, None)
                break
            yield f"data: {json.dumps(msg)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 4: Add asyncio mode to pytest config**

Create `pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_routes.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add api/routes.py tests/test_routes.py tests/conftest.py pytest.ini
git commit -m "feat: FastAPI routes with SSE streaming job system"
```

---

## Task 8: Three.js 3D Scene

**Files:**
- Create: `static/js/scene.js`

- [ ] **Step 1: Create static/js/scene.js**

```javascript
// static/js/scene.js
// Manages the Three.js 3D orbit visualization.

let renderer, scene, camera, controls;
let orbitLineWith, orbitLineWithout;
const AU_SCALE = 1 / 1000;  // 1 AU → 0.001 scene units (1000 AU = 1 unit)

export function initScene(canvasEl) {
  renderer = new THREE.WebGLRenderer({ canvas: canvasEl, antialias: true });
  renderer.setSize(canvasEl.clientWidth, canvasEl.clientHeight);
  renderer.setPixelRatio(window.devicePixelRatio);

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000010);

  camera = new THREE.PerspectiveCamera(
    60,
    canvasEl.clientWidth / canvasEl.clientHeight,
    0.001,
    1e9
  );
  camera.position.set(0, 50, 100);

  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  _addLights();
  _addSun();
  _addPlanets();
  _addStarField();

  window.addEventListener("resize", () => {
    camera.aspect = canvasEl.clientWidth / canvasEl.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(canvasEl.clientWidth, canvasEl.clientHeight);
  });

  _animate();
}

function _animate() {
  requestAnimationFrame(_animate);
  controls.update();
  renderer.render(scene, camera);
}

function _addLights() {
  scene.add(new THREE.AmbientLight(0x404040));
  const sun_light = new THREE.PointLight(0xffffff, 2, 0);
  scene.add(sun_light);
}

function _addSun() {
  const geo = new THREE.SphereGeometry(2, 32, 32);
  const mat = new THREE.MeshBasicMaterial({ color: 0xffdd44 });
  scene.add(new THREE.Mesh(geo, mat));
}

function _addPlanets() {
  // Jupiter
  const jGeo = new THREE.SphereGeometry(0.8, 16, 16);
  const jMat = new THREE.MeshStandardMaterial({ color: 0xc88b3a });
  const jupiter = new THREE.Mesh(jGeo, jMat);
  jupiter.position.set(5.2 * AU_SCALE * 1000, 0, 0);  // at t=0
  scene.add(jupiter);

  // Saturn
  const sGeo = new THREE.SphereGeometry(0.6, 16, 16);
  const sMat = new THREE.MeshStandardMaterial({ color: 0xe4d191 });
  const saturn = new THREE.Mesh(sGeo, sMat);
  saturn.position.set(9.54 * AU_SCALE * 1000, 0, 0);

  // Saturn ring
  const ringGeo = new THREE.RingGeometry(0.9, 1.5, 32);
  const ringMat = new THREE.MeshBasicMaterial({
    color: 0xd4b483,
    side: THREE.DoubleSide,
  });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.rotation.x = Math.PI / 3;
  saturn.add(ring);
  scene.add(saturn);
}

function _addStarField() {
  const verts = [];
  for (let i = 0; i < 5000; i++) {
    verts.push(
      (Math.random() - 0.5) * 2000,
      (Math.random() - 0.5) * 2000,
      (Math.random() - 0.5) * 2000
    );
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(verts, 3));
  scene.add(new THREE.Points(geo, new THREE.PointsMaterial({ color: 0xffffff, size: 0.3 })));
}

export function drawOrbits(trajectoryWithDM, trajectoryWithoutDM) {
  // Remove existing orbit lines
  if (orbitLineWith) scene.remove(orbitLineWith);
  if (orbitLineWithout) scene.remove(orbitLineWithout);

  orbitLineWith = _buildLine(trajectoryWithDM, 0xff8800);      // orange
  orbitLineWithout = _buildLine(trajectoryWithoutDM, 0xffffff); // white

  scene.add(orbitLineWith);
  scene.add(orbitLineWithout);

  // Fit camera to trajectory extent
  const maxR = Math.max(...trajectoryWithoutDM.map(
    ([x, y, z]) => Math.sqrt(x * x + y * y + z * z)
  ));
  const viewDist = maxR * AU_SCALE * 2.5;
  camera.position.set(viewDist * 0.6, viewDist * 0.4, viewDist);
  camera.far = viewDist * 20;
  camera.updateProjectionMatrix();
  controls.update();
}

function _buildLine(points, color) {
  const verts = points.flatMap(([x, y, z]) => [
    x * AU_SCALE, z * AU_SCALE, -y * AU_SCALE,  // y/z swap for Three.js convention
  ]);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(verts, 3));
  return new THREE.Line(geo, new THREE.LineBasicMaterial({ color }));
}
```

- [ ] **Step 2: Commit**

```bash
git add static/js/scene.js
git commit -m "feat: Three.js 3D orbit scene with Sun, Jupiter, Saturn"
```

---

## Task 9: NFW Profile Chart

**Files:**
- Create: `static/js/nfw_chart.js`

- [ ] **Step 1: Create static/js/nfw_chart.js**

```javascript
// static/js/nfw_chart.js
// Renders the NFW dark matter density profile using Chart.js.

let chart = null;

const R_SUN_KPC = 8.0;
const KPC_TO_AU = 206_264_806.0;
const GEV_CM3_TO_MSUN_AU3 = 3.0e-18;

function nfwDensity(r_kpc, rho0, rs_kpc) {
  if (rho0 === 0) return 0;
  const x = r_kpc / rs_kpc;
  return rho0 / (x * Math.pow(1 + x, 2));
}

export function initNFWChart(canvasEl) {
  chart = new Chart(canvasEl, {
    type: "line",
    data: { datasets: [] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          type: "logarithmic",
          title: { display: true, text: "r (kpc)", color: "#aaa" },
          ticks: { color: "#aaa" },
          grid: { color: "#333" },
        },
        y: {
          type: "logarithmic",
          title: { display: true, text: "ρ (GeV/cm³)", color: "#aaa" },
          ticks: { color: "#aaa" },
          grid: { color: "#333" },
        },
      },
      plugins: {
        legend: { labels: { color: "#ddd" } },
        annotation: {
          annotations: {
            sunLine: {
              type: "line",
              xMin: R_SUN_KPC, xMax: R_SUN_KPC,
              borderColor: "rgba(255, 221, 68, 0.6)",
              borderWidth: 1,
              borderDash: [5, 5],
              label: {
                content: "太陽系",
                display: true,
                color: "#ffdd44",
                position: "start",
              },
            },
          },
        },
      },
      backgroundColor: "#111",
    },
  });
}

export function updateNFWChart(datasets) {
  // datasets: array of { name, rho0, rs, color }
  if (!chart) return;

  const rValues = [];
  for (let i = -1; i <= 2.5; i += 0.05) {
    rValues.push(Math.pow(10, i));  // 0.1 to ~316 kpc
  }

  chart.data.datasets = datasets.map((ds) => ({
    label: ds.name,
    data: rValues.map((r) => ({
      x: r,
      y: nfwDensity(r, ds.rho0, ds.rs),
    })).filter((p) => p.y > 0),
    borderColor: ds.color,
    borderWidth: 2,
    pointRadius: 0,
    fill: false,
  }));

  chart.update();
}
```

- [ ] **Step 2: Commit**

```bash
git add static/js/nfw_chart.js
git commit -m "feat: Chart.js NFW density profile visualization with log-log axes"
```

---

## Task 10: API Client and UI

**Files:**
- Create: `static/js/api.js`
- Create: `static/js/ui.js`

- [ ] **Step 1: Create static/js/api.js**

```javascript
// static/js/api.js
// Handles POST /simulate and SSE streaming.

export async function startSimulation(payload, onProgress, onResult, onError) {
  let resp;
  try {
    resp = await fetch("/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    onError("サーバーへの接続に失敗しました。");
    return;
  }

  if (!resp.ok) {
    onError(`サーバーエラー: ${resp.status}`);
    return;
  }

  const { job_id } = await resp.json();

  const es = new EventSource(`/simulate/${job_id}/stream`);

  es.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "progress") {
      onProgress(msg.percent);
    } else if (msg.type === "result") {
      es.close();
      onResult(msg);
    }
  };

  es.onerror = () => {
    es.close();
    onError("ストリーム接続エラー。");
  };
}

export async function fetchPresets() {
  const resp = await fetch("/presets");
  return resp.json();
}
```

- [ ] **Step 2: Create static/js/ui.js**

```javascript
// static/js/ui.js
// Wires the parameter panel, presets, and run button to the scene and chart.

import { initScene, drawOrbits } from "./scene.js";
import { initNFWChart, updateNFWChart } from "./nfw_chart.js";
import { startSimulation, fetchPresets } from "./api.js";

const CHART_COLORS = ["#ff8800", "#00aaff", "#44ff88", "#ff4466"];

export async function initUI() {
  const canvas3d = document.getElementById("canvas3d");
  const canvasChart = document.getElementById("canvasChart");

  initScene(canvas3d);
  initNFWChart(canvasChart);

  const presets = await fetchPresets();
  _populatePresets(presets);
  _syncChartWithCurrentParams(presets);

  document.getElementById("presetSelect").addEventListener("change", (e) => {
    const preset = presets.find((p) => p.name === e.target.value);
    if (preset) {
      document.getElementById("rho0Input").value = preset.rho0;
      document.getElementById("rsInput").value = preset.rs;
      _syncChartWithCurrentParams(presets);
    }
  });

  ["rho0Input", "rsInput"].forEach((id) => {
    document.getElementById(id).addEventListener("input", () =>
      _syncChartWithCurrentParams(presets)
    );
  });

  document.getElementById("runBtn").addEventListener("click", _runSimulation);
}

function _populatePresets(presets) {
  const sel = document.getElementById("presetSelect");
  presets.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.name;
    opt.textContent = p.name;
    sel.appendChild(opt);
  });
  // Select second preset (標準銀河系ハロー) by default
  if (presets[1]) {
    sel.value = presets[1].name;
    document.getElementById("rho0Input").value = presets[1].rho0;
    document.getElementById("rsInput").value = presets[1].rs;
  }
}

function _syncChartWithCurrentParams(presets) {
  const rho0 = parseFloat(document.getElementById("rho0Input").value) || 0;
  const rs = parseFloat(document.getElementById("rsInput").value) || 20;
  // Show current + all presets on the chart
  const datasets = [
    { name: "現在の設定", rho0, rs, color: CHART_COLORS[0] },
    ...presets.map((p, i) => ({
      name: p.name, rho0: p.rho0, rs: p.rs, color: CHART_COLORS[i + 1] || "#888",
    })),
  ];
  updateNFWChart(datasets);
}

async function _runSimulation() {
  const rho0 = parseFloat(document.getElementById("rho0Input").value) || 0;
  const rs = parseFloat(document.getElementById("rsInput").value) || 20;
  const a = parseFloat(document.getElementById("aInput").value) || 50000;
  const ecc = parseFloat(document.getElementById("eccInput").value) || 0.9999;
  const inc = parseFloat(document.getElementById("incInput").value) || 0;

  const payload = {
    dark_matter: { rho0, rs },
    comet: { semi_major_axis_au: a, eccentricity: ecc, inclination_deg: inc },
    duration_years: null,
    timestep_years: Math.max(10, a * 0.002),  // scale timestep with orbit size
    n_output_points: 5000,
  };

  const runBtn = document.getElementById("runBtn");
  const progressBar = document.getElementById("progressBar");
  const statusText = document.getElementById("statusText");

  runBtn.disabled = true;
  progressBar.style.width = "0%";
  statusText.textContent = "計算中...";

  await startSimulation(
    payload,
    (pct) => {
      progressBar.style.width = `${pct}%`;
    },
    (result) => {
      drawOrbits(result.trajectory_with_dm, result.trajectory_without_dm);
      const meta = result.metadata;
      statusText.textContent =
        `完了 | 軌道周期: ${(meta.period_years / 1e6).toFixed(2)}M年 ` +
        `| 近日点: ${meta.perihelion_au} AU`;
      runBtn.disabled = false;
    },
    (err) => {
      statusText.textContent = `エラー: ${err}`;
      runBtn.disabled = false;
    }
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add static/js/api.js static/js/ui.js
git commit -m "feat: SSE API client and UI parameter panel"
```

---

## Task 11: index.html

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: Write static/index.html**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Comet Simulation — Dark Matter Halo</title>
  <script src="https://cdn.jsdelivr.net/npm/three@0.165.0/build/three.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.165.0/examples/js/controls/OrbitControls.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #000; color: #ddd; font-family: sans-serif; height: 100vh; display: flex; flex-direction: column; }
    #canvas3d { width: 100%; flex: 1 1 60%; display: block; }
    #bottom { display: flex; flex: 0 0 280px; border-top: 1px solid #333; }
    #chartPanel { flex: 1; padding: 8px; position: relative; }
    #canvasChart { width: 100%; height: 100%; }
    #controlPanel { width: 280px; padding: 12px; background: #0a0a14; border-left: 1px solid #333; display: flex; flex-direction: column; gap: 8px; overflow-y: auto; }
    label { font-size: 0.8em; color: #999; }
    input[type=number], select { width: 100%; background: #1a1a2e; border: 1px solid #444; color: #ddd; padding: 4px 6px; border-radius: 4px; font-size: 0.85em; }
    #runBtn { background: #2255cc; color: #fff; border: none; padding: 8px; border-radius: 4px; cursor: pointer; font-size: 0.9em; }
    #runBtn:disabled { background: #334; cursor: not-allowed; }
    #progressWrap { background: #111; border-radius: 3px; height: 6px; }
    #progressBar { background: #2255cc; height: 6px; border-radius: 3px; width: 0%; transition: width 0.2s; }
    #statusText { font-size: 0.75em; color: #888; min-height: 2em; }
    .section-title { font-size: 0.75em; color: #667; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 4px; }
    .legend { display: flex; gap: 12px; font-size: 0.75em; padding: 4px 0; }
    .legend-dot { width: 12px; height: 3px; display: inline-block; vertical-align: middle; margin-right: 4px; }
  </style>
</head>
<body>
  <canvas id="canvas3d"></canvas>
  <div id="bottom">
    <div id="chartPanel">
      <canvas id="canvasChart"></canvas>
    </div>
    <div id="controlPanel">
      <div class="section-title">ダークマター (NFW)</div>
      <label>プリセット</label>
      <select id="presetSelect"><option value="">カスタム</option></select>
      <label>ρ₀ (GeV/cm³)</label>
      <input type="number" id="rho0Input" value="0.3" min="0" step="0.1" />
      <label>rs (kpc)</label>
      <input type="number" id="rsInput" value="20" min="1" step="1" />

      <div class="section-title">彗星軌道</div>
      <label>半長軸 a (AU)</label>
      <input type="number" id="aInput" value="50000" min="1000" step="1000" />
      <label>離心率 e</label>
      <input type="number" id="eccInput" value="0.9999" min="0.9" max="0.99999" step="0.0001" />
      <label>傾斜角 i (度)</label>
      <input type="number" id="incInput" value="30" min="0" max="180" step="5" />

      <button id="runBtn">計算実行</button>
      <div id="progressWrap"><div id="progressBar"></div></div>
      <div id="statusText"></div>

      <div class="legend">
        <span><span class="legend-dot" style="background:#ff8800"></span>DM あり</span>
        <span><span class="legend-dot" style="background:#ffffff"></span>DM なし</span>
      </div>
    </div>
  </div>
  <script type="module">
    import { initUI } from "./js/ui.js";
    initUI();
  </script>
</body>
</html>
```

- [ ] **Step 2: Start the server and open http://localhost:8000 in a browser**

```bash
uvicorn main:app --reload
```

Verify:
- Page loads with dark background, 3D canvas, chart panel, and control panel
- NFW chart renders immediately with preset curves
- Changing ρ₀/rs updates the chart in real-time
- Clicking "計算実行" shows progress bar and eventually renders two orbit lines (white + orange)

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat: main HTML page with Three.js scene, NFW chart, and control panel"
```

---

## Task 12: Dockerfile

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [ ] **Step 1: Create .dockerignore**

```
__pycache__
*.pyc
.pytest_cache
tests/
*.egg-info
.git
```

- [ ] **Step 2: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY api/ api/
COPY physics/ physics/
COPY static/ static/

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Build and run the container**

```bash
docker build -t comet-sim .
docker run -p 8000:8000 comet-sim
```

Expected: Server starts. Open http://localhost:8000 and verify the simulation works identically to the non-containerized version.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "feat: Dockerfile for Azure Container Apps deployment"
```

---

## Task 13: Run All Tests

- [ ] **Step 1: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass. Approximate output:
```
tests/test_dark_matter.py::test_zero_dark_matter_gives_zero_density PASSED
tests/test_dark_matter.py::test_density_decreases_with_radius PASSED
tests/test_dark_matter.py::test_mass_enclosed_positive_and_increasing PASSED
tests/test_dark_matter.py::test_tidal_acceleration_zero_when_rho0_zero PASSED
tests/test_dark_matter.py::test_tidal_acceleration_vertical_dominates PASSED
tests/test_dark_matter.py::test_tidal_acceleration_scales_with_position PASSED
tests/test_bodies.py::test_comet_at_perihelion_correct_distance PASSED
tests/test_bodies.py::test_comet_velocity_perpendicular_to_radius_at_perihelion PASSED
tests/test_bodies.py::test_comet_inclination_tilts_orbit PASSED
tests/test_bodies.py::test_jupiter_position_at_origin_of_time PASSED
tests/test_bodies.py::test_saturn_position_one_period_returns_to_start PASSED
tests/test_bodies.py::test_orbital_period_from_kepler PASSED
tests/test_integrator.py::test_circular_orbit_energy_conservation PASSED
tests/test_integrator.py::test_leapfrog_step_returns_correct_shapes PASSED
tests/test_integrator.py::test_dark_matter_changes_trajectory PASSED
tests/test_simulation.py::test_simulation_returns_expected_keys PASSED
tests/test_simulation.py::test_simulation_trajectory_shapes_match PASSED
tests/test_simulation.py::test_simulation_dm_zero_matches_no_dm PASSED
tests/test_simulation.py::test_duration_defaults_to_orbital_period PASSED
tests/test_simulation.py::test_progress_callback_called PASSED
tests/test_routes.py::test_health PASSED
tests/test_routes.py::test_simulate_returns_job_id PASSED
tests/test_routes.py::test_stream_returns_result PASSED
tests/test_routes.py::test_presets_returns_list PASSED
```

- [ ] **Step 2: Final commit**

```bash
git commit --allow-empty -m "chore: all tests passing"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ Long-period Oort cloud comet orbits
- ✅ 3D simulation (Three.js with OrbitControls)
- ✅ NFW dark matter halo with ρ₀ and rs parameters
- ✅ Leapfrog integrator (Task 5)
- ✅ Jupiter and Saturn included
- ✅ FastAPI backend + Three.js frontend
- ✅ SSE progress streaming (Tasks 7, 8)
- ✅ Parameter panel with presets
- ✅ "計算実行" button (Task 10, 11)
- ✅ NFW density profile chart (Task 9)
- ✅ With/without dark matter comparison (white vs orange lines)
- ✅ Dockerfile for Azure Container Apps
- ✅ Scale-to-zero compatible (no background workers, stateless except in-flight jobs)

**Type consistency check:**
- `SimulationParams` fields match usage in `routes.py` ✅
- `NFWProfile` constructor signature matches all call sites ✅
- `leapfrog_step` signature matches all call sites ✅
- `drawOrbits(trajectoryWithDM, trajectoryWithoutDM)` matches `result.trajectory_with_dm/without_dm` keys ✅
