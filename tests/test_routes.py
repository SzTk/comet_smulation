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
