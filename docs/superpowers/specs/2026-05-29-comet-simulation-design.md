# Comet Simulation with Dark Matter Halo — Design Spec

**Date:** 2026-05-29
**Status:** Approved

---

## Overview

A 3D interactive web simulation of long-period comet (Oort cloud) orbits that demonstrates the gravitational influence of a dark matter halo on comet trajectories. Users can adjust NFW dark matter profile parameters and compare orbits with and without dark matter side-by-side.

---

## Goals

- Simulate long-period comet trajectories under the gravitational influence of the Sun, major planets (Jupiter, Saturn), and an NFW dark matter halo
- Visualize the difference in comet orbits with varying dark matter parameters
- Visualize the NFW dark matter density profile (ρ vs r) alongside the orbit simulation
- Host as a public demo on the user's website via Azure Container Apps (scale-to-zero)

---

## Architecture

```
[ Browser (Three.js + Chart.js) ]
         ↕  HTTP POST /simulate
         ↕  SSE (progress stream)
[ FastAPI (Python) ]
    ├── physics/
    │     ├── integrator.py     # Leapfrog symplectic integrator
    │     ├── bodies.py         # Sun, Jupiter, Saturn, comet(s)
    │     └── dark_matter.py    # NFW analytical potential & force
    └── api/
          └── routes.py         # POST /simulate, GET /presets
[ Docker Container ]
    → Azure Container Apps (min replicas = 0, HTTP trigger)
    ※ FastAPI also serves static frontend files from /static
```

### Data Flow

1. User configures parameters (or selects a preset) in the browser
2. User clicks "計算実行" → `POST /simulate` with JSON payload → backend returns `{"job_id": "..."}` immediately
3. Browser connects to `GET /simulate/{job_id}/stream` (SSE); backend streams progress events (0–100%)
4. Final SSE event contains the complete trajectory data payload
5. Three.js renders animated 3D orbits; Chart.js renders NFW profile graph

---

## Physics Model

### Bodies

| Body | Role |
|------|------|
| Sun | Primary gravitational source (fixed at origin or center-of-mass frame) |
| Jupiter | Gravitational perturber (~5.2 AU) |
| Saturn | Gravitational perturber (~9.5 AU) |
| Comet | 1–3 simultaneous comets, Oort cloud initial conditions (semi-major axis 2,000–100,000 AU) |

### Integrator: Leapfrog (Störmer–Verlet)

Leapfrog is a symplectic integrator — it conserves energy over long timescales better than RK4, making it appropriate for long-period orbit simulation spanning thousands of years.

```
v(t + dt/2) = v(t) + a(t) * dt/2
x(t + dt)   = x(t) + v(t + dt/2) * dt
a(t + dt)   = force(x(t + dt)) / m
v(t + dt)   = v(t + dt/2) + a(t + dt) * dt/2
```

Time step is adaptive: smaller near perihelion, larger near aphelion.

Simulation duration defaults to one full orbital period (computed from Kepler's third law: T = a^1.5 years, where a is in AU). For a = 50,000 AU this is ~11 million years. The user can override the duration, but the default ensures at least one complete orbit is shown.

### Dark Matter Model: NFW Profile

The Navarro–Frenk–White (NFW) halo density profile:

```
ρ(r) = ρ₀ / [ (r/rs) * (1 + r/rs)² ]
```

Parameters:
- `ρ₀` — characteristic density [GeV/cm³ or M☉/pc³]
- `rs` — scale radius [kpc]

The gravitational force on a body at distance `r` from the galactic center is derived analytically from the NFW mass enclosed `M(r)`:

```
M(r) = 4π ρ₀ rs³ [ ln(1 + r/rs) - (r/rs)/(1 + r/rs) ]
F(r) = -G M(r) / r²  (radial, toward galactic center)
```

The solar system is offset from the galactic center (~8 kpc), so the NFW force is applied as a gradient across the simulation volume.

### Presets

| Name | ρ₀ | rs | Description |
|------|----|----|-------------|
| ダークマターなし | 0 | — | Pure Newtonian gravity only |
| 標準銀河系ハロー | 0.3 GeV/cm³ | 20 kpc | Observationally motivated Milky Way values |
| 高密度ハロー | 1.0 GeV/cm³ | 10 kpc | Extreme high-density case |

---

## Frontend

### Layout

```
┌─────────────────────────────────────────┐
│  3D Orbit View (Three.js)               │
│  - Mouse drag to rotate                 │
│  - Scroll to zoom                       │
│  - Scale toggle: inner (~50 AU) /       │
│    outer (~100,000 AU)                  │
├──────────────────┬──────────────────────┤
│ NFW Profile      │ Parameter Panel      │
│ Chart (Chart.js) │ ρ₀  [slider/input]   │
│  ρ↑              │ rs  [slider/input]   │
│   \              │ Preset [dropdown]    │
│    ───           │ [計算実行] button    │
│        r→        │                      │
└──────────────────┴──────────────────────┘
```

### Three.js Scene

- **Camera:** OrbitControls (rotate, zoom, pan)
- **Scale modes:**
  - Inner solar system view: 0–50 AU
  - Oort cloud view: 0–100,000 AU (with logarithmic scale option)
- **Orbit rendering:**
  - Comet without dark matter: white trail line
  - Comet with dark matter: orange trail line
  - Both rendered simultaneously for direct comparison
- **Bodies:**
  - Sun: yellow sphere
  - Jupiter: brown sphere
  - Saturn: sphere with ring geometry
  - Comet: cyan sphere with trail

### NFW Profile Chart (Chart.js)

- X-axis: distance from galactic center r [kpc], log scale
- Y-axis: density ρ(r) [GeV/cm³], log scale
- Updates in real-time as sliders change (no need to hit "計算実行")
- Multiple presets can be overlaid for comparison
- Vertical marker at solar system position (~8 kpc from center)

### Parameter Panel

- `ρ₀` slider + numeric input
- `rs` slider + numeric input
- Preset dropdown (populates sliders on selection)
- "計算実行" button — triggers `POST /simulate`
- Progress bar (fed by SSE stream during calculation)

---

## API

### `POST /simulate`

Starts a simulation job and returns a job ID immediately. The browser then connects to the SSE stream.

**Request:**
```json
{
  "dark_matter": {
    "rho0": 0.3,
    "rs": 20.0
  },
  "comet": {
    "semi_major_axis_au": 50000,
    "eccentricity": 0.999,
    "inclination_deg": 45.0
  },
  "duration_years": null,
  "timestep_years": 100
}
```

- `duration_years`: if null, defaults to one full orbital period (computed server-side)

**Response:**
```json
{ "job_id": "abc123" }
```

### `GET /simulate/{job_id}/stream`

SSE endpoint. Streams progress events, then a final payload event.

**Progress event:**
```json
{ "type": "progress", "percent": 42 }
```

**Final event:**
```json
{
  "type": "result",
  "trajectory_with_dm": [[x, y, z], ...],
  "trajectory_without_dm": [[x, y, z], ...],
  "time_years": [...],
  "metadata": { "perihelion_au": 1.2, "period_years": 11180000 }
}
```

### `GET /presets`

Returns the list of named dark matter presets.

---

## Deployment

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install fastapi uvicorn numpy scipy
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Azure Container Apps

- **Min replicas:** 0 (scale-to-zero when idle)
- **Max replicas:** 1 (demo workload)
- **Trigger:** HTTP
- **Cold start estimate:** 5–10 seconds (acceptable for demo)
- FastAPI serves static frontend from `/static` directory (no separate static hosting needed)

---

## Out of Scope

- Multi-user sessions or persistence
- Moons, asteroids, or dwarf planets
- Alternative dark matter models (only NFW)
- Galactic tide effects (can be added later)
- Rust performance extension (deferred; Python + NumPy is sufficient for this N-body count)
